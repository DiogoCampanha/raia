"""
raia.pipeline
=============

LangGraph orchestration with **mandatory human checkpoints**.

A core RAIA governance rule: no agent ever triggers another autonomously;
every output requires explicit human review and approval before being
persisted and consumed downstream (the "H" gates).

Consequently RAIA is NOT one long autonomous chain. Each agent run is a small
state graph:

    generate  ──►  human_review (interrupt)  ──►  persist
        ▲               │
        └── revise ◄────┘   (rejection loops back with feedback)

* ``generate``     — the agent reads the blackboard, runs its decision
                     procedure, retrieves norms, drafts, and validates.
* ``human_review`` — ``interrupt()`` pauses the graph and surfaces the draft
                     *together with its evidence, its computed rationale and
                     its check results* to the UI.
* ``persist``      — only reached after approval: the artifact is re-validated
                     as the human left it, then committed to the Git-versioned
                     shared repository with its structured sidecar.

Sequencing BETWEEN agents is enforced by stage gates (each agent's
``required_upstream``), not by automatic triggering.

One node deserves explanation: ``generate`` accepts a *preset* draft. A hosted
deployment that restarts mid-review loses the in-memory graph thread while the
browser still shows the draft, and the tester's Approve then fails. Rather than
adding a persistence path that bypasses the gate, a restored review re-enters
the graph with the saved draft injected — so it still stops at the interrupt,
still requires an explicit approval, and still reaches ``persist`` the only way
anything ever reaches it. Nothing is written that a human did not approve.
"""

from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from . import validators
from .agents import AGENTS
from .storage import build_checkpointer, open_repository


class StageState(TypedDict, total=False):
    """State carried through one agent-run graph."""

    project: str
    agent_key: str
    actor: Dict[str, Any]           # the authenticated person who started the run
    inputs: Dict[str, Any]
    preset: Dict[str, Any]          # restored review payload, used once
    run: Dict[str, Any]             # latest draft + evidence + checks
    feedback: List[str]
    rejections: List[Dict[str, str]]
    decision: Dict[str, Any]
    commit: str
    approved_content: str


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------


def _generate(state: StageState) -> StageState:
    """Run the agent's decision procedure and specialized analysis."""
    agent = AGENTS[state["agent_key"]]
    attempt = len(state.get("feedback") or []) + 1

    preset = state.get("preset")
    if preset and not state.get("feedback"):
        payload = dict(preset)
        payload["restored"] = True
        payload["attempt"] = payload.get("attempt", attempt)
        return {"run": payload, "preset": {}}

    repo = open_repository(state["project"])
    result = agent.run(repo, state["inputs"], feedback=state.get("feedback") or [])
    payload = result.to_payload(
        agent_key=agent.spec.key,
        agent_name=agent.spec.name,
        artifact_key=agent.spec.output_key,
        attempt=attempt,
    )
    payload["required_sections"] = list(agent.spec.required_sections)
    payload["checklist_keys"] = result.rationale.checklist_keys() if result.rationale else []
    # Who ran the stage and with which answers. The first lets a project
    # require that a different person approves; the second lets a restored
    # review still record the human-authored brief it was based on.
    actor = state.get("actor") or {}
    payload["run_by"] = actor.get("id", "")
    payload["run_by_name"] = actor.get("name", "")
    payload["inputs"] = state.get("inputs") or {}
    repo.save_pending(agent.spec.key, payload)
    return {"run": payload}


def _human_review(state: StageState) -> StageState:
    """Mandatory human checkpoint (the 'H' gate).

    ``interrupt()`` suspends execution and hands the payload to the caller.
    Execution resumes only when the human submits a decision::

        {"action": "approve", "content": "<final text>", "approver": "..."}
        {"action": "reject",  "feedback": "<what to fix>", "reason": "<code>"}
    """
    decision = interrupt(state["run"])
    return {"decision": decision}


def _route_after_review(state: StageState) -> str:
    """Approve -> persist. Reject -> regenerate with feedback."""
    if state["decision"].get("action") == "approve":
        return "persist"
    return "revise"


def _revise(state: StageState) -> StageState:
    """Accumulate rejection feedback before looping back to generate."""
    decision = state.get("decision") or {}
    feedback = list(state.get("feedback") or [])
    text = decision.get("feedback") or "Please revise."
    feedback.append(text)

    rejections = list(state.get("rejections") or [])
    rejections.append(
        {
            "attempt": str(len(feedback)),
            "reason_code": decision.get("reason", "unspecified"),
            "feedback": text,
            "by": decision.get("approver", "reviewer"),
        }
    )
    open_repository(state["project"]).record_event(
        "rejection",
        {"agent": state["agent_key"], "user": decision.get("approver_id", ""), **rejections[-1]},
    )
    return {"feedback": feedback, "rejections": rejections}


def _persist(state: StageState) -> StageState:
    """Write the approved artifact to the Git-versioned blackboard."""
    agent = AGENTS[state["agent_key"]]
    repo = open_repository(state["project"])
    run = state.get("run") or {}
    decision = state.get("decision") or {}
    approver = decision.get("approver") or "human"
    rationale = _rationale_stub(run)
    original = run.get("record") or {}

    # A reviewer edits the record's fields, never the rendered text: an edit to
    # free text could not be validated, prioritised or compared across projects,
    # and the standard would stop being one at the exact point a person touched it.
    if decision.get("record") is not None:
        record = agent.finalize_record(decision["record"], rationale, run.get("evidence") or [],
                                       run.get("attempt", 1))
    else:
        if decision.get("content") and decision["content"].strip() != (run.get("draft") or "").strip():
            raise ValueError("Edits are made to the record's fields at the gate; free-text "
                             "changes to the rendered document are not accepted.")
        record = original
    edited = _core(record) != _core(original)

    if record:
        content = agent.render_record(record, rationale)
    else:
        # A draft saved before the standard record existed (restored from disk
        # after an upgrade): approve it exactly as shown, never re-rendered empty.
        content = run.get("draft") or ""
    if record and run.get("sanitization"):
        from .sanitize import sanitization_notice

        content = sanitization_notice(run["sanitization"]) + content

    # Re-validate what the human actually approved.
    report = revalidate(content, run, record)

    structured = agent.structured_from(record, rationale)
    prov = dict(run.get("provenance") or {})
    from . import provenance as _prov

    prov = _prov.finalize(
        prov,
        approver=approver,
        edited=edited,
        validation=report.to_dict(),
        rejection_history=state.get("rejections") or [],
    )
    if decision.get("approver_id"):
        prov["approval"]["approver_id"] = decision["approver_id"]
    if run.get("run_by"):
        prov["approval"]["run_by"] = run["run_by"]

    commit = repo.save_artifact(
        agent.spec.output_key,
        content,
        approved_by=approver,
        structured=structured,
        run_provenance=prov,
    )

    # Every issue in the approved record reaches the register with its type,
    # deciding role and blocking flag — the engine's, the agent's and the ones
    # code opened for a disagreement or an accepted risk. None evaporates
    # because a record was edited: engine issues are re-inserted by finalisation.
    issues = list(record.get("open_issues") or [])
    if issues:
        repo.append_open_issues(
            issues, raised_by=agent.spec.name, artifact=agent.spec.output_key, commit=commit
        )

    if agent.spec.key == "risk_classifier":
        _persist_product_brief(repo, agent, run.get("inputs") or state.get("inputs") or {},
                               approver, decision.get("approver_id", ""))

    repo.record_event(
        "approval",
        {
            "user": decision.get("approver_id", ""),
            "agent": agent.spec.key,
            "commit": commit,
            "attempt": run.get("attempt", 1),
            "edited": edited,
            "validation": report.headline(),
            "restored": bool(run.get("restored")),
        },
    )
    return {"commit": commit, "approved_content": content}


def _core(record: Dict[str, Any]) -> str:
    """The parts of a record a person can change, for edit detection."""
    import json

    keys = ("summary", "overall_status", "declared_verdict", "agrees_with_rule_engine",
            "disagreement_rationale", "findings", "actions", "open_issues", "not_grounded",
            "coverage", "extension")
    return json.dumps({k: record.get(k) for k in keys}, sort_keys=True, default=str)


def _persist_product_brief(repo, agent, inputs: Dict[str, Any], approver: str,
                           approver_id: str) -> None:
    """Record the human-authored brief alongside the approved classification.

    This is the one artifact a person writes rather than an agent. It is
    committed inside the same approval that persists the classification, so it
    passes through the gate like everything else and lands in the audit trail
    next to the output it produced.
    """
    fields = [f for f in agent.spec.input_fields if f.is_text and f.group.endswith("The product")]
    parts = [f"## {f.label}\n{inputs[f.key]}" for f in fields if inputs.get(f.key)]
    if not parts:
        return
    structured = {f.key: inputs.get(f.key) for f in agent.spec.input_fields}
    repo.save_artifact(
        "product_brief",
        "\n\n".join(parts),
        approved_by=approver or "author",
        structured={"intake": structured, "note": "human-authored input, not agent output"},
        run_provenance={"rationale_engine": None, "attempt": 1,
                        "approval": {"approved_by": approver, "approver_id": approver_id}},
    )


def revalidate(content: str, run: Dict[str, Any],
               record: Optional[Dict[str, Any]] = None) -> validators.ValidationReport:
    """Re-run the deterministic checks against the record and text the human approved."""
    from .contract import checks as contract_checks

    agent = AGENTS[run["agent_key"]] if run.get("agent_key") in AGENTS else None
    rationale = _rationale_stub(run)
    record = record if record is not None else (run.get("record") or {})
    allowed = [e.get("citation", "") for e in run.get("evidence") or []]
    report = validators.ValidationReport()
    report.add(contract_checks.check_schema(record, run.get("repairs", 0)))
    for item in contract_checks.check_corrections(record):
        report.add(item)
    report.add(contract_checks.check_responses(record))
    report.add(validators.check_sections(content, run.get("required_sections") or []))
    if allowed:
        report.add(validators.check_citations(content, allowed))
    report.add(validators.check_coverage(content, run.get("checklist_keys") or []))
    report.add(validators.check_open_issues(content, rationale.open_issues))
    if agent is not None:
        if agent.spec.verdict_keys:
            report.add(validators.check_reconciliation(content, rationale.verdict, agent.spec.verdict_keys))
        agent.extra_checks(report, content, rationale, record)
    return report


def _rationale_stub(run: Dict[str, Any]):
    """Rebuild the RationaleResult that finalisation, rendering and checks need."""
    from .rationale.types import ChecklistItem, RationaleResult

    rationale = run.get("rationale") or {}
    return RationaleResult(
        engine=rationale.get("engine", "unknown"),
        verdict=rationale.get("verdict") or {},
        checklist=[ChecklistItem(c.get("key", ""), c.get("label", "")) for c in rationale.get("checklist") or []],
        open_issues=list(rationale.get("open_issues") or []),
        issue_meta=list(rationale.get("issue_meta") or []),
        data=rationale.get("data") or {},
    )


def build_stage_graph(checkpointer: Any = None):
    """Compile the generate -> review -> persist graph (the RAIA stage pattern)."""
    g = StateGraph(StageState)
    g.add_node("generate", _generate)
    g.add_node("human_review", _human_review)
    g.add_node("revise", _revise)
    g.add_node("persist", _persist)

    g.add_edge(START, "generate")
    g.add_edge("generate", "human_review")
    g.add_conditional_edges(
        "human_review", _route_after_review, {"persist": "persist", "revise": "revise"}
    )
    g.add_edge("revise", "generate")
    g.add_edge("persist", END)

    if checkpointer is None:
        from langgraph.checkpoint.memory import MemorySaver

        checkpointer = MemorySaver()
    return g.compile(checkpointer=checkpointer)


# ---------------------------------------------------------------------------
# Runner facade used by the UI
# ---------------------------------------------------------------------------


class StageRunner:
    """Small facade so the UI never touches LangGraph internals."""

    def __init__(self, checkpointer: Any = None) -> None:
        self._checkpointer = checkpointer if checkpointer is not None else build_checkpointer()
        self._graph = build_stage_graph(self._checkpointer)

    def _config(self, project: str, agent_key: str) -> dict:
        return {"configurable": {"thread_id": f"{project}::{agent_key}"}}

    @staticmethod
    def _outcome(result: dict) -> dict:
        """Normalize a graph result into {status, payload|commit|content}."""
        if "__interrupt__" in result:
            payload = result["__interrupt__"][0].value
            return {"status": "awaiting_review", "payload": payload}
        return {
            "status": "approved",
            "commit": result.get("commit", ""),
            "content": result.get("approved_content", ""),
        }

    def check_gate(self, project: str, agent_key: str) -> List[str]:
        """Return missing prerequisite artifacts (stage gate), if any."""
        agent = AGENTS[agent_key]
        return agent.missing_prerequisites(open_repository(project))

    def start(self, project: str, agent_key: str, inputs: Dict[str, Any],
              actor: Optional[Dict[str, Any]] = None) -> dict:
        """Kick off one agent run; returns the review payload."""
        missing = self.check_gate(project, agent_key)
        if missing:
            raise PermissionError(
                "Stage gate: the following upstream artifacts must be approved "
                f"first: {', '.join(missing)}"
            )
        result = self._graph.invoke(
            {
                "project": project,
                "agent_key": agent_key,
                "inputs": inputs,
                "actor": actor or {},
                "feedback": [],
                "rejections": [],
            },
            config=self._config(project, agent_key),
        )
        return self._outcome(result)

    def restore(self, project: str, agent_key: str, payload: Dict[str, Any],
                inputs: Optional[Dict[str, Any]] = None) -> dict:
        """Re-enter the graph with a draft recovered from disk.

        Used when the server restarted while a review was open. The run still
        stops at the human checkpoint and still requires an explicit approval:
        the recovery path re-enters the gate, it does not step around it.
        """
        result = self._graph.invoke(
            {
                "project": project,
                "agent_key": agent_key,
                "inputs": inputs or payload.get("inputs") or {},
                "actor": {"id": payload.get("run_by", ""), "name": payload.get("run_by_name", "")},
                "preset": payload,
                "feedback": [],
                "rejections": [],
            },
            config=self._config(project, agent_key),
        )
        return self._outcome(result)

    def resume(self, project: str, agent_key: str, decision: Dict[str, Any]) -> dict:
        """Feed the human decision back into the paused graph."""
        result = self._graph.invoke(
            Command(resume=decision), config=self._config(project, agent_key)
        )
        return self._outcome(result)

    def has_thread(self, project: str, agent_key: str) -> bool:
        """True when a paused graph thread still exists in this process.

        The UI checks this before offering Approve on a draft it is showing: if
        the process restarted, the thread is gone and the review must be
        restored rather than resumed.
        """
        try:
            state = self._graph.get_state(self._config(project, agent_key))
        except Exception:
            return False
        return bool(state and state.next)
