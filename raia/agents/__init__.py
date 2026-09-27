"""
raia.agents
===========

The five specialized RAIA agents, organized in three
functional layers:

* **Product**: Risk Classifier, Requirements Reviewer
* **Dev**    : User Story Refiner, Auditor
* **Ops**    : Drift Monitor

``AGENTS`` maps agent keys to singleton instances in pipeline order; it is
the single registry used by both the LangGraph pipeline and the Streamlit UI.
"""

from typing import Dict

from .auditor import AuditorAgent
from .base import BaseAgent
from .drift_monitor import DriftMonitorAgent
from .requirements_reviewer import RequirementsReviewerAgent
from .risk_classifier import RiskClassifierAgent
from .story_generate import StoryGeneratorMode
from .story_refiner import UserStoryRefinerAgent

#: Registry of agent instances, keyed by agent key, in pipeline order.
AGENTS: Dict[str, BaseAgent] = {
    a.spec.key: a
    for a in (
        RiskClassifierAgent(),
        RequirementsReviewerAgent(),
        UserStoryRefinerAgent(),
        AuditorAgent(),
        DriftMonitorAgent(),
    )
}

#: Modes of an agent that run through the same gate with their own record.
#: They are not agents of their own: the architecture keeps five.
MODES: Dict[str, BaseAgent] = {m.spec.key: m for m in (StoryGeneratorMode(),)}

#: Every runnable key, agents and modes, for the pipeline.
RUNNABLE: Dict[str, BaseAgent] = {**AGENTS, **MODES}


def get_agent(key: str) -> BaseAgent:
    """The agent or mode that runs under ``key``."""
    return RUNNABLE[key]


def identity_key(key: str) -> str:
    """The agent whose identity a key wears: a mode wears its parent's."""
    agent = RUNNABLE.get(key)
    return (agent.spec.parent or key) if agent else key


__all__ = ["AGENTS", "MODES", "RUNNABLE", "BaseAgent", "get_agent", "identity_key"]
