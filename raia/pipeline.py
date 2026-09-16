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

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from . import validators
from .agents import AGENTS
from .repository import ArtifactRepository


class StageState(TypedDict, total=False):
    """State carried through one agent-run graph."""

    project: str
    agent_key: str
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

    repo = ArtifactRepository(state["project"])
    result = agent.run(repo, state["inputs"], feedback=state.get("feedback") or [])
    payload = result.to_payload(
        agent_key=agent.spec.key,
        agent_name=agent.spec.name,
        artifact_key=agent.spec.output_key,
        attempt=attempt,
    )
    payload["required_sections"] = list(agent.spec.required_sections)
    payload["checklist_keys"] = result.rationale.checklist_keys() if result.rationale else []
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
    ArtifactRepository(state["project"]).record_event(
        "rejection",
        {"agent": state["agent_key"], **rejections[-1]},
    )
    return {"feedback": feedback, "rejections": rejections}


def _persist(state: StageState) -> StageState:
    """Write the approved artifact to the Git-versioned blackboard."""
    agent = AGENTS[state["agent_key"]]
    repo = ArtifactRepository(state["project"])
    run = state.get("run") or {}
    decision = state.get("decision") or {}

    draft = run.get("draft", "")
    content = decision.get("content") or draft
    approver = decision.get("approver") or "human"
    edited = content.strip() != draft.strip()

    # Re-validate what the human actually approved. A reviewer may edit a draft
    # at the gate, and the record should describe the approved text rather than
    # the text the model happened to produce.
    report = revalidate(content, run)

    structured = agent.structured_from(content, _rationale_stub(run))
    record = dict(run.get("provenance") or {})
    from . import provenance as _prov

    record = _prov.finalize(
        record,
        approver=approver,
        edited=edited,
        validation=report.to_dict(),
        rejection_history=state.get("rejections") or [],
    )

    commit = repo.save_artifact(
        agent.spec.output_key,
        content,
        approved_by=approver,
        structured=structured,
        run_provenance=record,
    )

    # Conflicts reach the register from both sides: what the rule engine raised
    # and what the agent wrote under Open Issues. Neither is allowed to
    # evaporate because a draft was edited.
    issues = list(dict.fromkeys(
        list((run.get("rationale") or {}).get("open_issues") or [])
        + validators.extract_open_issues(content)
    ))
    if issues:
        repo.append_open_issues(
            issues, raised_by=agent.spec.name, artifact=agent.spec.output_key, commit=commit
        )

    repo.record_event(
        "approval",
        {
            "agent": agent.spec.key,
            "commit": commit,
            "attempt": run.get("attempt", 1),
            "edited": edited,
            "validation": report.headline(),
            "restored": bool(run.get("restored")),
        },
    )
    return {"commit": commit, "approved_content": content}


def revalidate(content: str, run: Dict[str, Any]) -> validators.ValidationReport:
    """Re-run the deterministic checks against the text the human approved."""
    rationale = run.get("rationale") or {}
    allowed = [e.get("citation", "") for e in run.get("evidence") or []]
    report = validators.ValidationReport()
    report.add(validators.check_sections(content, run.get("required_sections") or []))
    if allowed:
        report.add(validators.check_citations(content, allowed))
    report.add(validators.check_coverage(content, run.get("checklist_keys") or []))
    report.add(validators.check_open_issues(content, rationale.get("open_issues") or []))
    return report


def _rationale_stub(run: Dict[str, Any]):
    """Rebuild the minimum of a RationaleResult that ``structured_from`` needs."""
    from .rationale.types import RationaleResult

    rationale = run.get("rationale") or {}
    return RationaleResult(
        engine=rationale.get("engine", "unknown"),
        verdict=rationale.get("verdict") or {},
        open_issues=list(rationale.get("open_issues") or []),
        data=rationale.get("data") or {},
    )


def build_stage_graph(checkpointer: Optional[MemorySaver] = None):
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

    return g.compile(checkpointer=checkpointer or MemorySaver())


# ---------------------------------------------------------------------------
# Runner facade used by the UI
# ---------------------------------------------------------------------------


class StageRunner:
    """Small facade so the UI never touches LangGraph internals."""

    def __init__(self) -> None:
        self._checkpointer = MemorySaver()
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
        return agent.missing_prerequisites(ArtifactRepository(project))

    def start(self, project: str, agent_key: str, inputs: Dict[str, Any]) -> dict:
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
                "inputs": inputs or {},
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
