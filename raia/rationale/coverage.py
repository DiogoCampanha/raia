"""
raia.rationale.coverage
=======================

Deterministic coverage matrix for the Requirements Reviewer.

The gap list used to be whatever the model decided to call a gap. Here it is
*derived*: the obligations produced by the approved risk classification and the
seven adopted Responsible AI principles form a matrix, each cell is tested
against the team's stated requirements and the controls they say already
exist, and the empty cells are the gaps. The model then writes an ethical value
requirement for each computed gap — it does not choose which gaps there are.

Ethical value requirement identifiers are also assigned here, not by the model,
so downstream agents can be checked against a register that actually exists.
"""

import re
from typing import Any, Dict, List

from ..fields import options, selected, text_of
from . import principles
from .types import ChecklistItem, Finding, Pin, RationaleResult, md_table

# ---------------------------------------------------------------------------
# Option vocabularies (form ↔ engine contract)
# ---------------------------------------------------------------------------

#: Controls a team may already have in place, and the obligation codes each one
#: discharges. An obligation with neither a control nor a matching requirement
#: is a computed gap.
CONTROLS: Dict[str, Dict[str, Any]] = {
    "risk_management": {
        "label": "A documented, ongoing risk-management process for this system",
        "covers": ["eu.art9"],
    },
    "bias_testing": {
        "label": "Disaggregated bias testing on training and validation data",
        "covers": ["eu.art10", "br.data_governance"],
    },
    "technical_docs": {
        "label": "Maintained technical documentation of the system",
        "covers": ["eu.art11"],
    },
    "logging": {
        "label": "Automatic logging of decisions, retained and queryable",
        "covers": ["eu.art12", "br.logging"],
    },
    "instructions": {
        "label": "Written instructions for use given to whoever operates the system",
        "covers": ["eu.art13"],
    },
    "human_review": {
        "label": "A human-review step a person can actually use to override an output",
        "covers": ["eu.art14", "eu.art26", "br.supervision"],
    },
    "robustness_testing": {
        "label": "Accuracy, robustness and security testing before release",
        "covers": ["eu.art15", "br.testing"],
    },
    "impact_assessment": {
        "label": "A completed impact assessment for this system",
        "covers": ["eu.art27", "br.aia"],
    },
    "explanation": {
        "label": "An explanation of individual decisions, available to affected people",
        "covers": ["br.explainability", "br.rights"],
    },
    "contestation": {
        "label": "A channel where an affected person can contest a decision",
        "covers": ["br.rights"],
    },
    "transparency_notice": {
        "label": "A notice telling people they are interacting with, or affected by, an AI system",
        "covers": ["eu.art50", "br.rights"],
    },
    "governance": {
        "label": "Internal governance structure and named owners for this system",
        "covers": ["br.governance"],
    },
}

CONTROL_OPTIONS = options(
    *[(k, v["label"]) for k, v in CONTROLS.items()],
    ("none", "None of these are in place yet"),
)

STAKEHOLDER_OPTIONS = options(
    ("users", "Direct users / operators of the system"),
    ("subjects", "People the system makes decisions about"),
    ("non_users", "Affected people who never touch the system"),
    ("vulnerable", "Groups in a vulnerable position relative to this decision"),
    ("workers", "Workers whose job the system changes"),
    ("regulators", "Regulators, auditors or oversight bodies"),
    ("society", "Wider society or the environment"),
)

PRINCIPLE_OPTIONS = options(*[(p.key, p.name) for p in principles.PRINCIPLES])

FORMAT_OPTIONS = options(
    ("numbered", "Numbered requirements (R1, R2, … or 1., 2., …)"),
    ("bullets", "A bullet list, one requirement per line"),
    ("prose", "Prose paragraphs"),
)

SECTION_IEEE_EVR = "Writing Good EVRs (Practical Guidance)"
SECTION_IEEE_DEF = "3. Ethical Requirements Definition (Value-Based Requirements Engineering)"
SECTION_IEEE_VALUES = "2. Ethical Values Elicitation and Prioritization"
SECTION_MS_STYLE = "Practical Requirement Style (What RAIA Borrows)"

_ID_LINE = re.compile(r"^\s*(?:[-*]\s*)?(?:(R\d+|REQ-?\d+|NFR-?\d+)[.):\-]?\s+|(\d+)[.)]\s+)(.*)$", re.I)


def parse_requirements(text: str, fmt: str = "numbered") -> List[Dict[str, str]]:
    """Split a requirements blob into identified items.

    Identifiers the team already uses are preserved; unlabelled lines get a
    positional id so that every requirement can be referred to unambiguously in
    the gap analysis.
    """
    items: List[Dict[str, str]] = []
    if fmt == "prose":
        blocks = [b.strip() for b in re.split(r"\n\s*\n", text or "") if b.strip()]
        return [{"id": f"R{i}", "text": b} for i, b in enumerate(blocks, 1)]

    for line in (text or "").splitlines():
        if not line.strip():
            continue
        m = _ID_LINE.match(line)
        if m:
            rid = (m.group(1) or f"R{m.group(2)}").upper().replace("REQ-", "R").replace("REQ", "R")
            items.append({"id": rid, "text": m.group(3).strip()})
        else:
            items.append({"id": f"R{len(items) + 1}", "text": line.strip()})
    return items


def run(inputs: Dict[str, Any], upstream: Dict[str, Any]) -> RationaleResult:
    r = RationaleResult(engine="requirements_coverage")

    fmt = (inputs.get("requirement_format") or "numbered")
    reqs = parse_requirements(text_of(inputs, "requirements"), str(fmt))
    req_blob = "\n".join(i["text"] for i in reqs)
    controls = [c for c in selected(inputs, "existing_controls") if c != "none"]
    stakeholders = selected(inputs, "stakeholders")
    values = selected(inputs, "values_at_stake")
    constraints = text_of(inputs, "constraints")

    risk = (upstream.get("risk_classification") or {}).get("data") or {}
    obligations: List[Dict[str, str]] = risk.get("obligations") or []
    eu_high = bool(risk.get("eu_is_high_risk"))
    br_high = bool(risk.get("br_is_high_risk"))
    data_cats = risk.get("data_categories") or []

    r.findings.append(
        Finding("requirements.parsed", f"{len(reqs)} requirement(s) identified",
                ", ".join(i["id"] for i in reqs[:12]) + ("…" if len(reqs) > 12 else ""))
    )
    if not obligations:
        r.notes.append(
            "The approved risk classification carries no machine-readable obligation list "
            "(it predates structured artifacts). Obligation coverage could not be computed; "
            "principle coverage still applies."
        )

    covered_codes = {c for ctrl in controls for c in CONTROLS.get(ctrl, {}).get("covers", [])}

    # -- 1. Obligation × requirement matrix ---------------------------------

    obligation_rows: List[List[str]] = []
    obligation_gaps: List[Dict[str, str]] = []
    for ob in obligations:
        code, title = ob.get("code", "?"), ob.get("title", "")
        by_control = code in covered_codes
        by_requirement = _mentions(req_blob, title)
        status = (
            "control in place" if by_control
            else "addressed by a requirement" if by_requirement
            else "GAP"
        )
        obligation_rows.append([code, ob.get("jurisdiction", ""), title[:90], status])
        if status == "GAP":
            obligation_gaps.append({"kind": "obligation", "ref": code, "subject": title})

    if obligation_rows:
        r.tables["Obligation coverage (computed — the GAP rows are the ones to write requirements for)"] = md_table(
            ["Obligation", "Jurisdiction", "What it requires", "Status"], obligation_rows
        )

    # -- 2. Principle × requirement matrix ----------------------------------

    principle_rows: List[List[str]] = []
    principle_gaps: List[Dict[str, str]] = []
    for p in principles.PRINCIPLES:
        hit = principles.covered_by(req_blob, p)
        flagged = p.key in values
        status = "addressed" if hit else ("GAP — declared at stake" if flagged else "GAP")
        principle_rows.append([p.name, "yes" if flagged else "—", status])
        if not hit:
            principle_gaps.append({"kind": "principle", "ref": p.key, "subject": p.probe})

    r.tables["Principle coverage (computed from the requirements text)"] = md_table(
        ["Principle", "Declared at stake", "Status"], principle_rows
    )

    # -- 3. Assign the EVR register -----------------------------------------

    gaps = obligation_gaps + principle_gaps
    for i, g in enumerate(gaps, 1):
        g["evr_id"] = f"EVR-{i}"
    evr_ids = [g["evr_id"] for g in gaps]

    if gaps:
        r.tables["Ethical value requirements to write (ids are assigned — use exactly these)"] = md_table(
            ["EVR id", "Derived from", "Reference", "What it must address"],
            [[g["evr_id"], g["kind"], g["ref"], g["subject"][:90]] for g in gaps],
        )
    else:
        r.notes.append(
            "No gap was computed: every obligation has a control or a requirement, and every "
            "principle is touched by the requirements text. Review whether the coverage is real "
            "or merely lexical before concluding that nothing is missing."
        )

    # -- 4. Stakeholder coverage --------------------------------------------

    missing_stakeholders = []
    if eu_high or br_high:
        for expected in ("subjects", "non_users", "vulnerable"):
            if expected not in stakeholders:
                missing_stakeholders.append(expected)
    if missing_stakeholders:
        r.notes.append(
            "High-risk classification with stakeholder groups not declared: "
            + ", ".join(missing_stakeholders)
            + ". Value elicitation that omits the people a decision is made about is incomplete."
        )

    # -- 5. Open issues ------------------------------------------------------

    if (eu_high or br_high) and "impact_assessment" not in controls:
        r.raise_issue(
            "The system is classified high-risk and no impact assessment is in place. "
            "This blocks several obligations at once and needs an owner and a date.",
            type="missing_information", decision_owner="product", blocking=False,
        )
    if "fairness" in values and "robustness" in values:
        r.raise_issue(
            "Fairness and predictive accuracy were both declared as values at stake. Where they "
            "trade off, the ranking between them is a human decision, not a technical one.",
            type="value_tradeoff", decision_owner="leadership", blocking=False,
        )
    if constraints:
        r.raise_issue(
            "Delivery constraints were declared alongside the requirements. Any ethical value "
            "requirement that cannot be met within them must be recorded here rather than dropped.",
            type="risk_acceptance", decision_owner="product", blocking=False,
        )
    if not controls:
        r.notes.append("The team declared no existing controls, so every obligation starts as a gap.")

    # -- 6. Pins, checklist, query ------------------------------------------

    r.pins = [
        Pin("ieee_7000", SECTION_IEEE_DEF, "how ethical value requirements are derived"),
        Pin("ieee_7000", SECTION_IEEE_EVR, "what makes a requirement verifiable"),
        Pin("ieee_7000", SECTION_IEEE_VALUES, "value elicitation and prioritization"),
        Pin("ms_rai_v2", SECTION_MS_STYLE, "requirement style"),
    ]
    for src, sec in principles.grounding_pins([g["ref"] for g in principle_gaps]):
        if src in ("ms_rai_v2", "ieee_7000"):
            r.pins.append(Pin(src, sec, "principle grounding"))

    r.checklist = [
        ChecklistItem("gap_analysis", "Explain every computed GAP row in the team's own context"),
        ChecklistItem("evrs", "Write one ethical value requirement per assigned id, all verifiable"),
        ChecklistItem("stakeholders", "Name the stakeholders and values each requirement protects"),
        ChecklistItem("impact_assessment", "State what an impact assessment would flag for this system"),
        ChecklistItem("tradeoffs", "Surface value trade-offs rather than resolving them"),
        ChecklistItem("open_issues", "Carry forward every open issue raised here, plus any you add"),
    ]

    r.verdict = {
        "gap_count": len(gaps),
        "evr_ids": evr_ids,
        "obligation_gaps": len(obligation_gaps),
        "principle_gaps": len(principle_gaps),
    }
    r.query_terms = (
        [p.name for p in principles.PRINCIPLES if p.key in {g["ref"] for g in principle_gaps}]
        + [g["subject"] for g in obligation_gaps][:6]
        + ["ethical value requirements", "impact assessment"]
        + data_cats
    )
    r.data.update(
        {
            "requirements": reqs,
            "controls": controls,
            "stakeholders": stakeholders,
            "values_at_stake": values,
            "gaps": gaps,
            "evr_ids": evr_ids,
            "principle_coverage": {row[0]: row[2] for row in principle_rows},
        }
    )
    return r


def _mentions(blob: str, title: str) -> bool:
    """Coarse lexical test that a requirements blob addresses an obligation.

    Transparent on purpose: it produces a *candidate* gap list that the model
    reviews and the human approves. Over-reporting a gap costs a sentence;
    under-reporting is caught because the model sees the same requirements.
    """
    low = (blob or "").lower()
    words = [w for w in re.findall(r"[a-z]{5,}", (title or "").lower())
             if w not in ("shall", "system", "provide", "should", "their", "which", "those")]
    if not words:
        return False
    hits = sum(1 for w in words[:8] if w in low)
    return hits >= max(2, len(words[:8]) // 3)
