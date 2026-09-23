"""
raia.contract.rubric
====================

How a finding's risk level and priority are computed — by code, never by the
model.

NIST AI RMF asks that impacts be characterised by likelihood and magnitude
(MAP 5) and that risks be prioritised on impact and likelihood before they are
responded to (MANAGE 1). It deliberately does not fix a scale or a matrix. If
the model assigned priorities, two runs over the same project would disagree
for no reason anyone could inspect. So the model places each finding on the
two anchored scales in :mod:`raia.contract.vocab` and argues the placement;
this module turns the placement into a level with a published table, and then
applies floors the normative sources impose regardless of the matrix:

* a prohibited or excessive-risk practice is ``critical`` and blocking
  (EU AI Act Art. 5, PL 2338/2023 excessive risk);
* anything grounded in a legal obligation is at least ``high`` (the authority
  precedence legal > standard > advisory);
* a severity the rule engine computed from measured data is a floor the model
  cannot talk down (NIST MEASURE 3 — tracked risks stay tracked).

Every computed priority carries its basis in words, so the reviewer can see
why a line is red.
"""

from typing import Dict, Iterable, List, Tuple

from .vocab import LIKELIHOOD, MAGNITUDE, PRIORITIES, rank

#: MAP 5 matrix. Rows: magnitude (negligible → severe). Columns: likelihood
#: (rare → observed).
RISK_MATRIX: Dict[str, Dict[str, str]] = {
    "negligible":  {"rare": "low",    "possible": "low",    "likely": "low",      "observed": "medium"},
    "limited":     {"rare": "low",    "possible": "low",    "likely": "medium",   "observed": "medium"},
    "significant": {"rare": "medium", "possible": "medium", "likely": "high",     "observed": "high"},
    "severe":      {"rare": "high",   "possible": "high",   "likely": "critical", "observed": "critical"},
}


def risk_level(magnitude: str, likelihood: str) -> str:
    row = RISK_MATRIX.get(magnitude)
    if row is None or likelihood not in row:
        return "medium"  # unknown placement is never silently low
    return row[likelihood]


def higher(a: str, b: str) -> str:
    return a if rank(PRIORITIES, a) >= rank(PRIORITIES, b) else b


Floor = Tuple[str, str]  # (priority, reason)


def prioritise(magnitude: str, likelihood: str, links: Iterable[str],
               cited_authorities: Iterable[str], floors: Dict[str, Floor]) -> Dict[str, object]:
    """Compute risk level, priority, blocking flag and the basis for them."""
    level = risk_level(magnitude, likelihood)
    priority = level
    basis: List[str] = [f"likelihood × magnitude (NIST AI RMF MAP 5): {magnitude} × {likelihood} = {level}"]

    if "legal" in set(cited_authorities):
        if rank(PRIORITIES, priority) < rank(PRIORITIES, "high"):
            basis.append("raised to high: grounded in a legal instrument (authority precedence)")
        priority = higher(priority, "high")

    for link in links:
        floor = floors.get(link)
        if not floor:
            continue
        value, reason = floor
        if rank(PRIORITIES, value) > rank(PRIORITIES, priority):
            basis.append(f"raised to {value}: {reason}")
        priority = higher(priority, value)

    return {
        "risk_level": level,
        "priority": priority,
        "blocking": priority == "critical",
        "priority_basis": "; ".join(basis),
    }


def action_priority(finding_priorities: Iterable[str], default: str = "medium") -> str:
    values = [p for p in finding_priorities if p in PRIORITIES]
    if not values:
        return default
    out = values[0]
    for v in values[1:]:
        out = higher(out, v)
    return out


def matrix_rows() -> List[List[str]]:
    """The matrix as table rows, for documentation and the prompt."""
    return [[m] + [RISK_MATRIX[m][l] for l in LIKELIHOOD] for m in MAGNITUDE]


def matrix_md() -> str:
    head = "| magnitude \\ likelihood | " + " | ".join(LIKELIHOOD) + " |"
    sep = "|---|" + "---|" * len(LIKELIHOOD)
    body = ["| " + " | ".join(r) + " |" for r in matrix_rows()]
    return "\n".join([head, sep, *body])
