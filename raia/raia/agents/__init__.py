"""
raia.agents
===========

The five specialized RAIA agents (paper, Table 2), organized in three
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

__all__ = ["AGENTS", "BaseAgent"]
