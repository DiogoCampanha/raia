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
    origin = read_origin(inputs, reqs)
    adopted_ids = set(origin["adopted_ids"])
    team_blob = "\n".join(i["text"] for i in reqs if i["id"] not in adopted_ids)
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
        by_team = _mentions(team_blob, title)
        by_adopted = not by_team and bool(adopted_ids) and _mentions(req_blob, title)
        status = (
            "control in place" if by_control
            else "addressed by a requirement" if by_team
            else ADOPTED_STATUS if by_adopted
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
        hit_team = principles.covered_by(team_blob, p)
        hit = hit_team or (bool(adopted_ids) and principles.covered_by(req_blob, p))
        flagged = p.key in values
        status = ("addressed" if hit_team else ADOPTED_STATUS if hit
                  else ("GAP — declared at stake" if flagged else "GAP"))
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

    # -- 5b. Where the answers came from ----------------------------------------

    _report_origin(r, origin, len(reqs), obligation_rows, principle_rows)

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
            "suggestion_origin": origin,
        }
    )
    return r


ADOPTED_STATUS = "addressed by an adopted suggestion"


def _report_origin(r: RationaleResult, origin: Dict[str, Any], total: int,
                   obligation_rows: List[List[str]], principle_rows: List[List[str]]) -> None:
    """Say plainly which answers RAIA proposed and a person adopted.

    Coverage that rests on a requirement RAIA recommended is not the same claim
    as coverage by a requirement the team wrote, even once a person adopted it:
    the record keeps the two apart so a reader can weigh them.
    """
    adopted = origin.get("adopted") or []
    if adopted:
        edited = [a["id"] for a in adopted if a.get("edited")]
        by_adopted = sum(1 for row in obligation_rows if row[-1] == ADOPTED_STATUS) \
            + sum(1 for row in principle_rows if row[-1] == ADOPTED_STATUS)
        r.findings.append(Finding(
            "requirements.adopted_suggestions",
            f"{len(adopted)} of {total} requirement(s) originated as RAIA recommendations "
            "adopted by the team",
            ", ".join(a["id"] for a in adopted)
            + (f"; edited before or after adoption: {', '.join(edited)}" if edited else "; adopted as proposed")
            + (f"; {by_adopted} coverage cell(s) rest on them" if by_adopted else ""),
        ))
        r.notes.append(
            "Some requirements were recommended by RAIA and adopted by a person. Cells marked "
            f"'{ADOPTED_STATUS}' are covered only by those: check they are commitments the team "
            "will actually deliver, not wording accepted to close a gap."
        )
    for key, meta in (origin.get("fields") or {}).items():
        label = {"stakeholders": "Stakeholder groups", "values_at_stake": "Principles at stake"}.get(key, key)
        if meta["status"] == "unchanged":
            detail = "kept as proposed"
        else:
            parts = []
            if meta["added"]:
                parts.append("added " + ", ".join(meta["added"]))
            if meta["removed"]:
                parts.append("removed " + ", ".join(meta["removed"]))
            detail = "adjusted by the team (" + "; ".join(parts) + ")" if parts else "adjusted by the team"
        r.findings.append(Finding(
            f"intake.suggested.{key}",
            f"{label} were pre-filled from the approved risk classification",
            detail + (f"; reviewed by {origin['reviewed_by']}" if origin.get("reviewed_by") else ""),
        ))
    if "stakeholders" in (origin.get("fields") or {}):
        r.notes.append(
            "The stakeholder groups were proposed from the classification, not elicited from the "
            "stakeholders. Treat the value register as a starting point for elicitation."
        )


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


# ---------------------------------------------------------------------------
# Suggestions from the approved risk classification
# ---------------------------------------------------------------------------
#
# The Requirements Reviewer can pre-fill part of its own intake from what the
# approved risk classification already established. The rule that governs
# this section is deliberate:
#
#     **Only context is suggested. Facts about the team are never pre-filled.**
#
# Which stakeholders a decision touches and which principles it puts at stake
# follow from the classification, so they can be proposed. Which controls are
# already in place, which requirements the team has written and its delivery
# constraints are facts only the team knows; a suggestion there would be
# invented evidence (a ticked control discharges obligations). Those fields are
# never written by a suggestion — at most the controls field is annotated with
# the controls the classification makes relevant.
#
# A suggestion only fills a field that is empty, it carries a reason per value,
# and it is recorded as a suggestion in the intake so the engine can tell a
# pre-filled answer from one the team gave.

#: Intake fields a suggestion may fill. Nothing else is ever written.
SUGGESTIBLE_FIELDS = ("stakeholders", "values_at_stake")

#: Intake fields a suggestion must never write, whatever the classification says.
NEVER_SUGGESTED = ("existing_controls", "requirements", "constraints", "requirement_format")

#: Key under which the intake carries where its answers came from.
ORIGIN_KEY = "_origin"

_ALLOCATING_AREAS = {"employment", "education", "essential_services", "law_enforcement",
                     "migration", "justice"}
_VULNERABLE_AREAS = {"education", "essential_services", "law_enforcement", "migration",
                     "justice", "health"}
_SAFETY_AREAS = {"critical_infra", "health", "autonomous_vehicles"}
_SOCIETAL_AREAS = {"critical_infra", "justice", "content_curation"}
_SENSITIVE_DATA = {"biometric", "health", "protected_attributes", "proxies", "children",
                   "location", "financial", "communications"}
_VULNERABLE_DATA = {"children", "health", "biometric", "protected_attributes"}


def _risk_data(upstream: Dict[str, Any]) -> Dict[str, Any]:
    return (upstream.get("risk_classification") or {}).get("data") or {}


def _named(values: List[str]) -> str:
    return ", ".join(v.replace("_", " ") for v in values)


def suggest_intake(upstream: Dict[str, Any]) -> Dict[str, Any]:
    """Propose answers to the context questions from the approved classification.

    Returns ``{"fields": {field: {"values": [...], "reasons": {value: why}}},
    "basis": str, "control_hints": [...]}``. Every proposed value has a reason
    a person can check against the classification; a value with no reason is
    not proposed. Only :data:`SUGGESTIBLE_FIELDS` ever appear in ``fields``.
    """
    risk = _risk_data(upstream)
    if not risk:
        return {"fields": {}, "basis": "", "control_hints": []}

    areas = [a for a in risk.get("purpose_areas") or [] if a and a != "none"]
    data_cats = [d for d in risk.get("data_categories") or [] if d and d != "none"]
    triggers = [t for t in (risk.get("transparency_triggers") or [])
                + (risk.get("derived_transparency_triggers") or []) if t and t != "none"]
    autonomy = risk.get("decision_autonomy") or ""
    oversight = risk.get("human_oversight") or ""
    techniques = risk.get("ai_techniques") or []
    codes = {o.get("code") for o in risk.get("obligations") or []}
    eu_high, br_high = bool(risk.get("eu_is_high_risk")), bool(risk.get("br_is_high_risk"))
    high = eu_high or br_high
    public_sector = bool(risk.get("public_sector"))
    decides_about_people = bool(risk.get("significant_effects")) or bool(areas) \
        or autonomy in ("fully_automated", "human_confirms", "human_override")

    stakeholders: Dict[str, str] = {}
    stakeholders["users"] = "Someone operates the system or acts on its output."
    if decides_about_people:
        stakeholders["subjects"] = (
            "The classification records outputs that inform or make decisions about people"
            + (f" (area: {_named(areas)})." if areas else ".")
        )
    if high or {"deepfake", "synthetic_content"} & set(triggers):
        stakeholders["non_users"] = (
            "Classified high-risk: people outside the interface bear its effects."
            if high else "Generated content reaches people who never use the system."
        )
    vuln_area, vuln_data = set(areas) & _VULNERABLE_AREAS, set(data_cats) & _VULNERABLE_DATA
    if vuln_area or vuln_data or (high and decides_about_people):
        why = []
        if vuln_area:
            why.append(f"area {_named(sorted(vuln_area))}")
        if vuln_data:
            why.append(f"data about {_named(sorted(vuln_data))}")
        if not why:
            why.append("a high-risk decision about people")
        stakeholders["vulnerable"] = "The classification records " + " and ".join(why) + "."
    if "employment" in areas:
        stakeholders["workers"] = "Employment area: the system changes how people are hired, managed or evaluated."
    if high or public_sector:
        stakeholders["regulators"] = (
            "Classified high-risk: conformity, supervision and audit duties apply."
            if high else "Public-sector deployment: publicity and oversight duties apply."
        )
    if set(areas) & _SOCIETAL_AREAS or {"deepfake", "synthetic_content"} & set(triggers):
        stakeholders["society"] = "The area or the generated content has effects beyond the people it decides about."

    # Principles are proposed on specific facts only. Every principle applies to
    # a high-risk system in the abstract; proposing all seven would tell the
    # team nothing and invite them to accept the list unread.
    values: Dict[str, str] = {}
    if (high and oversight == "none_designed") or public_sector:
        values["accountability"] = (
            "Public-sector deployment: decisions must be answerable to the public."
            if public_sector and not (high and oversight == "none_designed")
            else "High-risk, and no oversight mechanism is designed yet: nobody is named as "
                 "answerable for an individual outcome."
        )
    fair_data = {"protected_attributes", "proxies"} & set(data_cats)
    fair_areas = set(areas) & _ALLOCATING_AREAS
    if fair_data or fair_areas:
        why = []
        if fair_data:
            why.append("protected attributes or their proxies are processed")
        if fair_areas:
            why.append(f"it allocates opportunities in {_named(sorted(fair_areas))}")
        values["fairness"] = "The classification records that " + " and ".join(why) + "."
    if autonomy in ("fully_automated", "human_confirms") or oversight in ("none_designed", "monitoring_only"):
        values["human_oversight"] = (
            f"Declared autonomy '{autonomy.replace('_', ' ')}' with oversight "
            f"'{oversight.replace('_', ' ')}': a person may not be able to intervene in a case."
        )
    private = set(data_cats) & (_SENSITIVE_DATA - {"proxies"})
    if private:
        values["privacy"] = f"Sensitive data is processed: {_named(sorted(private))}."
    if set(areas) & _SAFETY_AREAS or "generative" in techniques:
        values["robustness"] = (
            f"Safety-relevant area: {_named(sorted(set(areas) & _SAFETY_AREAS))}."
            if set(areas) & _SAFETY_AREAS else "Generative output can be wrong in fluent, plausible ways."
        )
    if triggers:
        values["transparency"] = f"Transparency triggers: {_named(sorted(set(triggers)))}."
    elif {"eu.art13", "br.explainability"} & codes and autonomy in ("fully_automated", "human_confirms"):
        values["transparency"] = ("Explanation is an obligation and the output is, in practice, the "
                                  "decision: affected people need to know why.")
    if set(areas) & _SOCIETAL_AREAS or {"deepfake", "synthetic_content"} & set(triggers):
        values["wellbeing"] = "The system's effects reach communities or the information environment."

    order_s = [o.value for o in STAKEHOLDER_OPTIONS]
    order_v = [o.value for o in PRINCIPLE_OPTIONS]
    fields = {
        "stakeholders": {"values": [v for v in order_s if v in stakeholders],
                         "reasons": {v: stakeholders[v] for v in order_s if v in stakeholders}},
        "values_at_stake": {"values": [v for v in order_v if v in values],
                            "reasons": {v: values[v] for v in order_v if v in values}},
    }
    fields = {k: v for k, v in fields.items() if v["values"] and k in SUGGESTIBLE_FIELDS}

    basis = [f"EU: {risk.get('eu_tier') or ('high-risk' if eu_high else 'not high-risk')}",
             f"BR: {'high-risk' if br_high else 'not high-risk'}"]
    if areas:
        basis.append(f"areas: {_named(areas)}")
    if data_cats:
        basis.append(f"data: {_named(data_cats)}")
    return {"fields": fields, "basis": "; ".join(basis), "control_hints": relevant_controls(upstream)}


def relevant_controls(upstream: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Controls that would discharge an obligation the classification assigned.

    A hint for the person answering, never an answer: the field stays theirs.
    """
    codes = [o.get("code") for o in _risk_data(upstream).get("obligations") or []]
    out = []
    for key, ctrl in CONTROLS.items():
        hit = [c for c in ctrl["covers"] if c in codes]
        if hit:
            out.append({"key": key, "label": ctrl["label"], "obligations": hit})
    return out


def next_requirement(text: str, fmt: str, statement: str) -> Dict[str, str]:
    """Append one requirement to a requirements blob in the team's own format.

    Returns ``{"text": new_blob, "id": assigned_id, "line": appended_text}``.
    The id is the one :func:`parse_requirements` will give the new item, so an
    adopted suggestion can be found again when the stage runs.
    """
    fmt = fmt or "numbered"
    text = (text or "").rstrip()
    items = parse_requirements(text, fmt)
    statement = " ".join((statement or "").split())
    if fmt == "prose":
        rid = f"R{len(items) + 1}"
        return {"text": (text + "\n\n" if text else "") + statement, "id": rid, "line": statement}
    used = [int(m.group(1)) for i in items for m in [re.match(r"R(\d+)$", i["id"])] if m]
    rid = f"R{max(used + [len(items)]) + 1}"
    line = ("- " if fmt == "bullets" else "") + f"{rid}. {statement}"
    return {"text": (text + "\n" if text else "") + line, "id": rid, "line": statement}


def _norm_text(s: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (s or "").lower()))


def read_origin(inputs: Dict[str, Any], reqs: List[Dict[str, str]]) -> Dict[str, Any]:
    """Where the answers in this intake came from, checked against the answers now.

    The intake records what was suggested; this compares it with what the form
    holds at run time. A suggested field the person changed is reported as
    edited; an adopted requirement the person deleted is no longer adopted; one
    they rewrote is still theirs to own, and reported as edited.
    """
    raw = inputs.get(ORIGIN_KEY) or {}
    if not isinstance(raw, dict):
        raw = {}
    out: Dict[str, Any] = {"fields": {}, "adopted": [], "adopted_ids": [],
                           "reviewed_by": str(raw.get("reviewed_by") or "")}
    for key, meta in (raw.get("fields") or {}).items():
        if key not in SUGGESTIBLE_FIELDS or not isinstance(meta, dict):
            continue
        suggested = sorted(meta.get("values") or [])
        current = sorted(selected(inputs, key))
        out["fields"][key] = {
            "suggested": suggested,
            "status": "unchanged" if current == suggested else "edited",
            "added": [v for v in current if v not in suggested],
            "removed": [v for v in suggested if v not in current],
        }
    by_id = {r["id"]: r["text"] for r in reqs}
    for a in raw.get("adopted") or []:
        rid = (a or {}).get("id")
        if rid not in by_id:
            continue
        out["adopted"].append({
            "id": rid,
            "candidate_id": a.get("candidate_id", ""),
            "addresses": a.get("addresses", ""),
            "edited": _norm_text(by_id[rid]) != _norm_text(a.get("text", "")) or bool(a.get("edited")),
        })
        out["adopted_ids"].append(rid)
    return out
