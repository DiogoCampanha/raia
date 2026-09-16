"""
raia.rationale.traceability
===========================

Deterministic evidence matching for the Auditor.

The anti-ethics-washing rule used to be an instruction: never call a
requirement satisfied without evidence. An instruction is exactly what an
audit report should not rely on. Here the register of approved ethical value
requirements and acceptance criteria is read from the upstream artifacts, each
one is matched against the sprint outcomes the team reported, and any item with
no evidence is assigned **NOT VERIFIED by code**, before the model is asked
anything. The model may downgrade a verdict; a validator prevents it from
upgrading one.

The match is lexical and deliberately transparent: identifier mentions first,
then distinctive terms from the requirement. It is designed to be conservative
— when in doubt, an item lands in NOT VERIFIED and a human looks at it.
"""

import re
from typing import Any, Dict, List, Tuple

from ..fields import options, selected, text_of
from .types import ChecklistItem, Finding, Pin, RationaleResult, md_table

EVIDENCE_OPTIONS = options(
    ("test_results", "Automated test results"),
    ("disaggregated", "Disaggregated evaluation across groups"),
    ("code_review", "Code review or pull-request record"),
    ("documentation", "Documentation updated in this sprint"),
    ("audit_log", "Audit-log sample showing the behaviour"),
    ("user_research", "User research or pilot feedback"),
    ("external_review", "External or independent review"),
    ("none", "No evidence artifacts produced this sprint"),
)

OUTCOME_OPTIONS = options(
    ("delivered", "Delivered and released"),
    ("delivered_untested", "Delivered without the planned verification"),
    ("partial", "Partially delivered"),
    ("dropped", "Dropped or deferred"),
)

SECTION_MS_ACCOUNTABILITY = "Accountability Goals"
SECTION_NIST_GOVERN = "GOVERN (cross-cutting)"
SECTION_NIST_MEASURE = "MEASURE (analysis and tracking)"

NOT_VERIFIED = "NOT VERIFIED"
EVIDENCE_FOUND = "evidence present — agent to assess"

_STOP = {
    "shall", "system", "the", "and", "for", "with", "that", "this", "must", "each",
    "their", "which", "from", "into", "when", "where", "such", "been", "than",
    "requirement", "ensure", "provide", "support", "across", "within",
}


def _terms(text: str, limit: int = 8) -> List[str]:
    words = [w for w in re.findall(r"[a-z][a-z-]{4,}", (text or "").lower()) if w not in _STOP]
    seen: List[str] = []
    for w in words:
        if w not in seen:
            seen.append(w)
    return seen[:limit]


def _evidence_for(item_id: str, text: str, evidence_blob: str) -> Tuple[bool, str]:
    """Is there anything in the sprint outcomes that speaks to this item?"""
    blob = (evidence_blob or "").lower()
    if re.search(rf"(?<![\w-]){re.escape(item_id.lower())}(?![\w-])", blob):
        return True, f"the sprint outcomes mention {item_id} explicitly"
    terms = _terms(text)
    hits = [t for t in terms if t in blob]
    if len(hits) >= max(2, len(terms) // 3):
        return True, "sprint outcomes discuss: " + ", ".join(hits[:5])
    return False, "no mention of this item, or of its distinctive terms, in the sprint outcomes"


def run(inputs: Dict[str, Any], upstream: Dict[str, Any]) -> RationaleResult:
    r = RationaleResult(engine="audit_traceability")

    outcomes = text_of(inputs, "sprint_outcomes")
    planned = text_of(inputs, "planned_epics")
    sprint_id = text_of(inputs, "sprint_id") or "this sprint"
    evidence_types = [e for e in selected(inputs, "evidence_types") if e != "none"]

    review = (upstream.get("requirements_review") or {}).get("data") or {}
    stories = (upstream.get("refined_stories") or {}).get("data") or {}
    risk = (upstream.get("risk_classification") or {}).get("data") or {}

    evr_ids: List[str] = review.get("evr_ids") or []
    gaps: List[Dict[str, str]] = review.get("gaps") or []
    subject_by_id = {g.get("evr_id"): g.get("subject", "") for g in gaps if g.get("evr_id")}
    criteria: List[Dict[str, str]] = stories.get("criteria") or []
    high_risk = bool(risk.get("eu_is_high_risk") or risk.get("br_is_high_risk"))

    # -- 1. Verdict assignment ----------------------------------------------

    rows: List[List[str]] = []
    not_verified: List[str] = []
    assessable: List[str] = []

    def assess(item_id: str, subject: str, kind: str) -> None:
        found, why = _evidence_for(item_id, subject, outcomes)
        if found and evidence_types:
            rows.append([item_id, kind, subject[:70], EVIDENCE_FOUND, why])
            assessable.append(item_id)
        else:
            reason = why if evidence_types else "no evidence artifact of any kind was declared for this sprint"
            rows.append([item_id, kind, subject[:70], NOT_VERIFIED, reason])
            not_verified.append(item_id)

    for eid in evr_ids:
        assess(eid, subject_by_id.get(eid, ""), "ethical value requirement")
    for c in criteria:
        cid = str(c.get("id") or "")
        if cid:
            assess(cid, str(c.get("text") or ""), "acceptance criterion")

    if rows:
        r.tables[
            "Verdicts assigned by code (you may downgrade a verdict, never upgrade one)"
        ] = md_table(["Item", "Kind", "Subject", "Computed verdict", "Basis"], rows)
    else:
        r.notes.append(
            "No machine-readable requirement or criterion register was found upstream, so no "
            "verdict could be pre-assigned. Audit against the approved artifacts' text and say "
            "explicitly that the register was unavailable."
        )

    r.findings.append(
        Finding("audit.register", f"{len(rows)} auditable item(s) from the approved artifacts",
                f"{len(not_verified)} pre-assigned NOT VERIFIED, {len(assessable)} with evidence to assess")
    )
    if not evidence_types:
        r.findings.append(
            Finding("audit.no_evidence", "No evidence artifacts declared for this sprint",
                    "every item is NOT VERIFIED regardless of what the narrative claims")
        )
    else:
        r.findings.append(
            Finding("audit.evidence_types", "Declared evidence types", ", ".join(evidence_types))
        )

    # -- 2. Open issues ------------------------------------------------------

    if not_verified and high_risk:
        r.open_issues.append(
            f"{len(not_verified)} ethical item(s) are unverified on a high-risk system after "
            f"{sprint_id}. Each needs an owner and a sprint, or an accepted-risk decision on record."
        )
    if "disaggregated" not in evidence_types and high_risk:
        r.open_issues.append(
            "No disaggregated evaluation was declared for a high-risk system. Aggregate results "
            "cannot evidence a non-discrimination obligation."
        )
    if planned and not_verified:
        r.open_issues.append(
            "Work is planned forward while ethical items from the current scope remain unverified. "
            "Sequencing is a human decision and should be recorded as one."
        )

    # -- 3. Pins, checklist --------------------------------------------------

    r.pins = [
        Pin("ms_rai_v2", SECTION_MS_ACCOUNTABILITY, "accountability documentation"),
        Pin("nist_ai_rmf", SECTION_NIST_GOVERN, "governance practices"),
        Pin("nist_ai_rmf", SECTION_NIST_MEASURE, "what counts as measurement evidence"),
    ]

    r.checklist = [
        ChecklistItem("verdicts", "Give a verdict and its evidence for every item in the computed table"),
        ChecklistItem("not_verified", "Explain what evidence each NOT VERIFIED item would need"),
        ChecklistItem("accountability", "Record who decided what, from the upstream approval headers"),
        ChecklistItem("upcoming", "Flag the ethical checkpoints the planned work will hit"),
        ChecklistItem("open_issues", "Carry forward every open issue raised here, plus any you add"),
    ]

    r.verdict = {
        "items_audited": len(rows),
        "not_verified": not_verified,
        "assessable": assessable,
        "evidence_declared": bool(evidence_types),
    }
    r.query_terms = (
        ["accountability documentation", "audit evidence", "governance"]
        + [subject_by_id.get(e, "")[:60] for e in evr_ids][:5]
        + evidence_types
    )
    r.data.update(
        {
            "sprint_id": sprint_id,
            "evidence_types": evidence_types,
            "audited_items": [
                {"id": row[0], "kind": row[1], "computed_verdict": row[3], "basis": row[4]}
                for row in rows
            ],
            "not_verified": not_verified,
        }
    )
    return r
