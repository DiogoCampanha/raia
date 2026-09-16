"""
raia.rationale
==============

Deterministic decision procedures — one per agent.

Before any prompt is assembled, the agent's engine reads the structured intake
and the approved upstream artifacts and computes what can be computed: which
prohibitions and high-risk areas match, which obligations follow, which
principles the current requirements leave uncovered, which ECCOLA cards apply
to a story, which ethical requirements have no evidence behind them, which
fairness thresholds were breached.

The model is then asked to justify, to handle the open-textured questions a
rule table would get confidently wrong, and to write for humans — never to
produce the facts the engine already established. Where the two disagree, the
disagreement is escalated to the human rather than averaged away.
"""

from .types import (  # noqa: F401
    COVERED,
    NOT_APPLICABLE,
    NOT_GROUNDED,
    VALID_STATUSES,
    ChecklistItem,
    Finding,
    Pin,
    RationaleResult,
    empty_rationale,
    md_table,
)

__all__ = [
    "COVERED",
    "NOT_APPLICABLE",
    "NOT_GROUNDED",
    "VALID_STATUSES",
    "ChecklistItem",
    "Finding",
    "Pin",
    "RationaleResult",
    "empty_rationale",
    "md_table",
]
