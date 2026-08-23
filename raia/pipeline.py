"""
raia.pipeline
=============

LangGraph orchestration with **mandatory human checkpoints**.

A core RAIA governance rule: "no agent ever triggers another
autonomously; every output requires explicit human review and approval
before being persisted and consumed downstream (the 'H' gates)."

Consequently RAIA is NOT one long autonomous chain. Each agent run is a
small LangGraph state graph:

    generate  ──►  human_review (interrupt)  ──►  persist
        ▲               │
        └── revise ◄────┘   (rejection loops back with feedback)

* ``generate``     -- the agent reads the blackboard, retrieves norms, drafts.
* ``human_review`` -- LangGraph's native ``interrupt()`` pauses the graph and
                      surfaces the draft to the UI. The human may approve
                      (optionally after editing) or reject with feedback.
* ``persist``      -- only reached after approval: the artifact is committed
                      to the Git-versioned shared repository.

Sequencing BETWEEN agents is enforced by stage gates (each agent's
``required_upstream``), not by automatic triggering -- faithfully mirroring
RAIA's human-driven pipeline design.
"""

from typing import Any, Dict, List, Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from .agents import AGENTS
from .repository import ArtifactRepository


class StageState(TypedDict, total=False):
    """State carried through one agent-run graph."""

    project: str                  # project slug (selects the blackboard)
    agent_key: str                # which of the five agents is running
    inputs: Dict[str, str]        # human-provided inputs for this stage
    draft: str                    # latest LLM draft awaiting review
    feedback: List[str]           # accumulated rejection feedback
    decision: Dict[str, Any]      # human decision returned by interrupt()
    commit: str                   # Git commit hash after persistence
    approved_content: str         # final (possibly human-edited) content


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------


def _generate(state: StageState) -> StageState:
    """Run the agent's specialized analysis and store the draft."""
    agent = AGENTS[state["agent_key"]]
    repo = ArtifactRepository(state["project"])
    draft = agent.run(repo, state["inputs"], feedback=state.get("feedback") or [])
    return {"draft": draft}


def _human_review(state: StageState) -> StageState:
    """Mandatory human checkpoint (the 'H' gate).

    ``interrupt()`` suspends execution and hands the payload to the caller
    (the Streamlit UI). Execution resumes only when the human submits a
    decision::

        {"action": "approve", "content": "<final text>"}   # content optional
        {"action": "reject",  "feedback": "<what to fix>"}
    """
    agent = AGENTS[state["agent_key"]]
    decision = interrupt(
        {
            "agent_key": state["agent_key"],
            "agent_name": agent.spec.name,
            "artifact_key": agent.spec.output_key,
            "draft": state["draft"],
            "attempt": len(state.get("feedback") or []) + 1,
        }
    )
    return {"decision": decision}


def _route_after_review(state: StageState) -> str:
    """Approve -> persist. Reject -> regenerate with feedback."""
    if state["decision"].get("action") == "approve":
        return "persist"
    return "revise"


def _revise(state: StageState) -> StageState:
    """Accumulate rejection feedback before looping back to generate."""
    fb = list(state.get("feedback") or [])
    fb.append(state["decision"].get("feedback", "Please revise."))
    return {"feedback": fb}


def _persist(state: StageState) -> StageState:
    """Write the approved artifact to the Git-versioned blackboard."""
    agent = AGENTS[state["agent_key"]]
    repo = ArtifactRepository(state["project"])
    content = state["decision"].get("content") or state["draft"]
    approver = state["decision"].get("approver", "human")
    commit = repo.save_artifact(agent.spec.output_key, content, approved_by=approver)
    return {"commit": commit, "approved_content": content}


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
    """Small facade so the UI never touches LangGraph internals.

    A single compiled graph serves all stages; each (project, agent) pair
    gets its own thread so parallel projects don't interfere.
    """

    def __init__(self) -> None:
        self._checkpointer = MemorySaver()
        self._graph = build_stage_graph(self._checkpointer)

    def _config(self, project: str, agent_key: str) -> dict:
        return {"configurable": {"thread_id": f"{project}::{agent_key}"}}

    @staticmethod
    def _outcome(result: dict) -> dict:
        """Normalize a graph result into {status, payload|commit|content}."""
        if "__interrupt__" in result:
            # Graph paused at the human checkpoint: surface the draft.
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

    def start(self, project: str, agent_key: str, inputs: Dict[str, str]) -> dict:
        """Kick off one agent run; returns either the review payload or the result."""
        missing = self.check_gate(project, agent_key)
        if missing:
            raise PermissionError(
                "Stage gate: the following upstream artifacts must be approved "
                f"first: {', '.join(missing)}"
            )
        result = self._graph.invoke(
            {"project": project, "agent_key": agent_key, "inputs": inputs, "feedback": []},
            config=self._config(project, agent_key),
        )
        return self._outcome(result)

    def resume(self, project: str, agent_key: str, decision: Dict[str, Any]) -> dict:
        """Feed the human decision back into the paused graph."""
        result = self._graph.invoke(
            Command(resume=decision), config=self._config(project, agent_key)
        )
        return self._outcome(result)
