"""
raia.lineage
============

Which stages depend on which, and which approved stages no longer rest on the
current version of their upstream work.

A RAIA stage reads the approved artifacts of earlier stages. When one of those
is revised and approved again, everything built on it was approved against a
version that no longer exists. RAIA does not re-run those stages on its own:
re-running an agent calls the model and produces a draft nobody asked for, and
nothing is ever saved without a person approving it. Instead the stages are
**flagged for review**, and a person either revises them or confirms they
still hold. Both answers are recorded.

Like every other notion of progress in RAIA, the flag is *derived*, never
stored. It is computed from the project's event log, in order:

* an ``approval`` event makes a stage current as of that point;
* a ``stage_reconfirmed`` event makes a stage current again without changing
  its artifact;
* an approved stage is **needs review** when any stage it depends on — directly
  or through another stage — was approved *after* this stage was last made
  current.

A stage whose approval predates the event log carries no approval event; it is
never flagged, because there is nothing to compare it against.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

APPROVED = "approved"
IN_REVIEW = "in_review"
READY = "ready"
BLOCKED = "blocked"
STALE = "stale"

#: Artifacts that are written together with another agent's approval.
_EXTRA_PRODUCERS = {"product_brief": "risk_classifier"}


def _agents(agents: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if agents is not None:
        return agents
    from .agents import AGENTS

    return AGENTS


def producers(agents: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """Artifact key -> the agent whose approval writes it."""
    agents = _agents(agents)
    out = {a.spec.output_key: key for key, a in agents.items()}
    out.update({k: v for k, v in _EXTRA_PRODUCERS.items() if v in agents})
    return out


def direct_upstream(agent_key: str, agents: Optional[Dict[str, Any]] = None) -> List[str]:
    """Agents whose approved artifacts this agent reads."""
    agents = _agents(agents)
    prod = producers(agents)
    seen: List[str] = []
    for artifact in agents[agent_key].spec.upstream_keys:
        src = prod.get(artifact)
        if src and src != agent_key and src not in seen:
            seen.append(src)
    return seen


def ancestors(agent_key: str, agents: Optional[Dict[str, Any]] = None) -> List[str]:
    """Every agent this one depends on, directly or transitively, in pipeline order."""
    agents = _agents(agents)
    found: Set[str] = set()
    stack = list(direct_upstream(agent_key, agents))
    while stack:
        key = stack.pop()
        if key in found:
            continue
        found.add(key)
        stack.extend(direct_upstream(key, agents))
    return [k for k in agents if k in found]


def descendants(agent_key: str, agents: Optional[Dict[str, Any]] = None) -> List[str]:
    """Every agent that depends on this one, in pipeline order."""
    agents = _agents(agents)
    return [k for k in agents if agent_key in ancestors(k, agents)]


def _marks(events: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    approved_at: Dict[str, int] = {}
    current_at: Dict[str, int] = {}
    for i, e in enumerate(events):
        kind, agent = e.get("kind"), e.get("agent")
        if not agent:
            continue
        if kind == "approval":
            approved_at[agent] = i
            current_at[agent] = i
        elif kind == "stage_reconfirmed":
            current_at[agent] = i
    return {"approved": approved_at, "current": current_at}


def stage_states(repo, agents: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Status of every stage of a project, in pipeline order.

    Each entry: ``agent``, ``name``, ``layer``, ``status`` (one of approved,
    stale, in_review, ready, blocked), ``approved`` (an artifact exists),
    ``stale_because`` (agent keys whose newer approval triggered the flag) and
    ``missing`` (prerequisite artifacts not yet approved).
    """
    agents = _agents(agents)
    done = set(repo.existing_artifacts())
    pending = set(repo.pending_agents())
    marks = _marks(repo.events())
    out: List[Dict[str, Any]] = []
    for key, agent in agents.items():
        approved = agent.spec.output_key in done
        missing = agent.missing_prerequisites(repo)
        because: List[str] = []
        if approved and key in marks["current"]:
            mine = marks["current"][key]
            because = [u for u in ancestors(key, agents)
                       if marks["approved"].get(u, -1) > mine]
        if key in pending:
            status = IN_REVIEW
        elif approved and because:
            status = STALE
        elif approved:
            status = APPROVED
        elif missing:
            status = BLOCKED
        else:
            status = READY
        out.append({
            "agent": key,
            "name": agent.spec.name,
            "layer": agent.spec.layer,
            "status": status,
            "approved": approved,
            "stale_because": because,
            "missing": missing,
        })
    return out


def revision_impact(repo, agent_key: str, agents: Optional[Dict[str, Any]] = None) -> List[str]:
    """Approved stages that will be flagged for review if ``agent_key`` is re-approved."""
    agents = _agents(agents)
    done = set(repo.existing_artifacts())
    return [k for k in descendants(agent_key, agents) if agents[k].spec.output_key in done]
