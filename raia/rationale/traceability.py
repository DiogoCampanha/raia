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
from typing import Any, Dict, List, Optional, Tuple

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


#: The opinion scale, weakest first, and the rule that places an audit on it.
#: Kept here, beside the evidence matching, so the one rule serves both the
#: engine's ceiling (before the model) and the final rating (after it).
OPINIONS = ("not_rated", "not_effective", "needs_improvement", "effective_with_observations", "effective")
SATISFIED_SHARE = 0.6


def rate(items: int, satisfied: int, *, evidence_declared: bool, at_risk: int = 0,
         critical: int = 0, high: int = 0, blocking: int = 0) -> Tuple[str, List[str]]:
    """(rating, reasons): the audit opinion, and why, from facts code holds."""
    if items <= 0:
        return "not_rated", ["no approved requirement or criterion register to audit"]
    share = satisfied / items
    pct = f"{satisfied} of {items} items satisfied ({share:.0%})"
    worst: List[str] = []
    if not evidence_declared:
        worst.append("no evidence artifact was declared for the sprint")
    if satisfied == 0:
        worst.append("no item is satisfied")
    if blocking:
        worst.append(f"{blocking} blocking decision(s) open")
    if worst:
        return "not_effective", worst + ([pct] if satisfied else [])
    weak: List[str] = []
    if share < SATISFIED_SHARE:
        weak.append(f"{pct}, under {SATISFIED_SHARE:.0%}")
    if at_risk:
        weak.append(f"{at_risk} item(s) at risk")
    if critical:
        weak.append(f"{critical} critical finding(s)")
    if weak:
        return "needs_improvement", weak
    if satisfied == items and not high:
        return "effective", [pct, "no high or critical finding"]
    rest = []
    if satisfied < items:
        rest.append(f"{items - satisfied} item(s) not yet satisfied")
    if high:
        rest.append(f"{high} high finding(s)")
    return "effective_with_observations", [pct] + rest


def at_most(rating: str, ceiling: str) -> str:
    """The lower of two ratings: a rating never rises above its ceiling."""
    return rating if OPINIONS.index(rating) <= OPINIONS.index(ceiling) else ceiling


def _baseline(upstream: Dict[str, Any]) -> List[Dict[str, str]]:
    """Which approved versions the audit is against, from their approval records."""
    names = {"risk_classification": "Risk classification", "requirements_review": "Ethical requirements",
             "refined_stories": "Refined stories"}
    out = []
    for key, label in names.items():
        art = upstream.get(key)
        if not art:
            continue
        approval = (art.get("provenance") or {}).get("approval") or {}
        out.append({"artifact": key, "label": label, "approved_by": str(approval.get("approved_by") or ""),
                    "approved_at": str(approval.get("approved_at") or "")[:10]})
    return out


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
    # Prefer the approved wording of each requirement over the gap it closed:
    # the audit is of what the team adopted, not of what the engine found missing.
    for evr in review.get("evrs") or []:
        if evr.get("id") and evr.get("statement"):
            subject_by_id[evr["id"]] = f"{evr['statement']} {evr.get('fit_criterion', '')}".strip()
    criteria: List[Dict[str, str]] = stories.get("criteria") or []
    high_risk = bool(risk.get("eu_is_high_risk") or risk.get("br_is_high_risk"))

    # Once the project has a backlog, the audit is project-wide: this sprint's
    # work is audited item by item, and everything else is reported where it
    # stands — verified earlier, planned, or with no story yet — instead of
    # being marked NOT VERIFIED for not being scheduled yet.
    backlog = (upstream.get("backlog") or {}).get("data") or {}
    sprints = (upstream.get("sprints") or {}).get("data") or {}
    project_mode = bool(backlog.get("stories"))
    # Items are audited per sprint once the team works in sprints; a team that
    # has not planned one yet is audited on everything, as before.
    sprint_mode = project_mode and bool(sprints.get("sprints"))
    open_sprint = next((x for x in sprints.get("sprints") or [] if x.get("state") != "closed"), None)
    if project_mode and open_sprint and sprint_id == "this sprint":
        sprint_id = open_sprint.get("name") or open_sprint.get("id")

    # -- 1. Verdict assignment ----------------------------------------------

    rows: List[List[str]] = []
    not_verified: List[str] = []
    assessable: List[str] = []
    subjects: Dict[str, str] = {}

    def assess(item_id: str, subject: str, kind: str) -> None:
        found, why = _evidence_for(item_id, subject, outcomes)
        if found and evidence_types:
            rows.append([item_id, kind, subject[:70], EVIDENCE_FOUND, why])
            subjects[item_id] = subject
            assessable.append(item_id)
        else:
            reason = why if evidence_types else "no evidence artifact of any kind was declared for this sprint"
            rows.append([item_id, kind, subject[:70], NOT_VERIFIED, reason])
            subjects[item_id] = subject
            not_verified.append(item_id)

    def not_delivered(item_id: str, subject: str, kind: str, why: str) -> None:
        rows.append([item_id, kind, subject[:70], NOT_VERIFIED, why])
        subjects[item_id] = subject
        not_verified.append(item_id)

    if not sprint_mode:
        for eid in evr_ids:
            assess(eid, subject_by_id.get(eid, ""), "ethical value requirement")
        for c in criteria:
            cid = str(c.get("id") or "")
            if cid:
                assess(cid, str(c.get("text") or ""), "acceptance criterion")
    elif open_sprint:
        spr = open_sprint.get("id")
        live = [x for x in backlog.get("stories") or [] if x.get("status") != "obsolete"]
        in_sprint = [x for x in live if x.get("sprint") == spr]
        for st in in_sprint:
            for c in st.get("criteria") or []:
                if c.get("kind") != "ethical" or not c.get("id"):
                    continue
                if st.get("status") != "done":
                    not_delivered(c["id"], str(c.get("text") or ""), "acceptance criterion",
                                  f"{st['id']} was not marked done this sprint")
                else:
                    assess(c["id"], str(c.get("text") or ""), "acceptance criterion")
        # A requirement is audited in the sprint that completes its stories.
        here = {x["id"] for x in in_sprint}
        for eid in evr_ids:
            linked = [x for x in live if eid in (x.get("evr_ids") or [])]
            if not linked or not any(x["id"] in here for x in linked):
                continue
            if not all(x["id"] in here or x.get("status") == "verified" for x in linked):
                continue
            pending = [x["id"] for x in linked if x["id"] in here and x.get("status") != "done"]
            if pending:
                not_delivered(eid, subject_by_id.get(eid, ""), "ethical value requirement",
                              "not delivered this sprint: " + ", ".join(pending))
            else:
                assess(eid, subject_by_id.get(eid, ""), "ethical value requirement")
    else:
        r.notes.append("No sprint is open, so no item is audited this time: the report covers where the "
                       "project stands, whether the backlog is enough, and what comes next.")

    if rows:
        r.tables[
            "Verdicts assigned by code (you may downgrade a verdict, never upgrade one)"
        ] = md_table(["Item", "Kind", "Subject", "Computed verdict", "Basis"], rows)
    elif sprint_mode:
        pass
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
        r.raise_issue(
            f"{len(not_verified)} ethical item(s) are unverified on a high-risk system after "
            f"{sprint_id}. Each needs an owner and a sprint, or an accepted-risk decision on record.",
            type="risk_acceptance", decision_owner="product", blocking=False,
        )
    if "disaggregated" not in evidence_types and high_risk:
        r.raise_issue(
            "No disaggregated evaluation was declared for a high-risk system. Aggregate results "
            "cannot evidence a non-discrimination obligation.",
            type="missing_information", decision_owner="data_science", blocking=False,
        )
    if planned and not_verified:
        r.raise_issue(
            "Work is planned forward while ethical items from the current scope remain unverified. "
            "Sequencing is a human decision and should be recorded as one.",
            type="risk_acceptance", decision_owner="product", blocking=False,
        )

    # -- 3. The project as a whole (project mode) -----------------------------

    ceiling_caps: List[str] = []
    project: Dict[str, Any] = {}
    if project_mode:
        project = _project_view(backlog, sprints, review, risk, open_sprint, r)
        closing_no = int((open_sprint or {}).get("number") or len(project["history"]))
        if project["coverage"]["severe_uncovered"]:
            ceiling_caps.append("a high or critical risk has no story: "
                                + ", ".join(project["coverage"]["severe_uncovered"]))
        if closing_no >= 2 and project["legal_unscheduled"]:
            ceiling_caps.append("legal-obligation requirement(s) with no story in any sprint by sprint "
                                f"{closing_no}: " + ", ".join(project["legal_unscheduled"]))

    # -- 4. Pins, checklist --------------------------------------------------

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
        ChecklistItem("strengths", "State the strengths the evidence supports, and nothing it does not"),
        ChecklistItem("pathway", "Recommend the way forward, in order"),
        ChecklistItem("open_issues", "Carry forward every open issue raised here, plus any you add"),
    ]

    # The best opinion the evidence allows: every item with evidence satisfied,
    # nothing at risk, no finding. The final verdicts and findings only lower it.
    ceiling, ceiling_reasons = rate(len(rows), len(assessable), evidence_declared=bool(evidence_types))
    if ceiling_caps and at_most(ceiling, "needs_improvement") != ceiling:
        ceiling = "needs_improvement"
        ceiling_reasons = ceiling_reasons + [f"capped: {c}" for c in ceiling_caps]
    r.findings.append(
        Finding("audit.opinion_ceiling", "Best audit opinion the evidence allows",
                f"{ceiling.replace('_', ' ')} — " + "; ".join(ceiling_reasons)
                + ". The final verdicts and findings can only lower it.")
    )

    r.verdict = {
        "items_audited": len(rows),
        "opinion_ceiling": ceiling,
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
            "evidence_labels": [next((o.label for o in EVIDENCE_OPTIONS if o.value == e), e) for e in evidence_types],
            "audited_items": [
                {"id": row[0], "kind": row[1], "subject": subjects.get(row[0], ""),
                 "computed_verdict": row[3], "basis": row[4]}
                for row in rows
            ],
            "not_verified": not_verified,
            "high_risk": high_risk,
            "subjects": subjects,
            "baseline": _baseline(upstream),
            "opinion_ceiling": {"rating": ceiling, "reasons": ceiling_reasons},
            "project_mode": project_mode,
        }
    )
    if project_mode:
        r.checklist += [
            ChecklistItem("backlog", "Judge whether the backlog covers each listed requirement; never raise a computed gap"),
            ChecklistItem("trajectory", "Comment on the progress across sprints, from the computed series"),
            ChecklistItem("next", "Say what the next sprint should tackle first"),
        ]
        r.data.update({
            "sprint_ref": (open_sprint or {}).get("id", ""),
            "sprint_close": (open_sprint or {}).get("id", "") if (open_sprint or {}).get("state") == "review" else "",
            "project_state": project["state"],
            "backlog_coverage": project["coverage"],
            "history": project["history"],
            "next": project["next"],
            "legal_unscheduled": project["legal_unscheduled"],
            "ceiling_caps": ceiling_caps,
            "board": project["board"],
        })
    return r


def _project_view(backlog: Dict[str, Any], sprints: Dict[str, Any], review: Dict[str, Any],
                  risk: Dict[str, Any], open_sprint: Optional[Dict[str, Any]], r: RationaleResult) -> Dict[str, Any]:
    """Where the project stands, how it is moving, whether the backlog is enough, what comes next.

    All four are computed here, before the model is asked anything, and shown
    to it as ground truth; the tables are also what the report prints.
    """
    from .. import roadmap as R
    from . import backlog_coverage

    rows = R.requirement_states(review, backlog)
    counts = R.state_counts(rows)
    coverage = backlog_coverage.run(backlog, review, risk)
    history = R.history(sprints)
    legal_unscheduled = backlog_coverage.legal_unscheduled(rows)
    suggestion = R.suggest(backlog, sprints, review, [], (open_sprint or {}).get("capacity"),
                           (open_sprint or {}).get("unit") or "stories")
    open_rai = sum(1 for s in backlog.get("stories") or []
                   if s.get("origin") == "rai" and s.get("status") not in ("verified", "obsolete"))

    r.tables["Where the project stands (computed): every approved requirement"] = md_table(
        ["Requirement", "State", "Stories", "Legal", "Priority", "Verified in"],
        [[x["id"], R.REQ_STATE_LABELS[x["state"]], ", ".join(x["stories"]) or "—", x["obligation"] or "—",
          x["priority"] or "—", x["verified_in"] or "—"] for x in rows])
    if history:
        r.tables["Progress across closed sprints (computed)"] = md_table(
            ["Sprint", "Requirements verified (cumulative)", "Criteria verified", "Stories verified",
             "Carried over", "Opinion"],
            [[h.get("name"), h.get("verified_requirements"), h.get("verified_criteria"), h.get("stories_verified"),
              h.get("carried_over"), str(h.get("opinion") or "").replace("_", " ")] for h in history])
    if coverage["gaps"]:
        r.tables["Backlog gaps (computed; each needs an action)"] = md_table(
            ["Gap", "Ref", "Detail", "Action"],
            [[g["title"], g["ref"], g["text"][:120], g["action"]] for g in coverage["gaps"][:20]])
    if coverage["covered"]:
        r.tables["Requirements the backlog covers: judge each in backlog_assessment (you may lower, never raise)"] = md_table(
            ["Requirement", "Stories", "Their ethical criteria"],
            [[c["ref"], ", ".join(c["stories"]), " / ".join(c["criteria"]) or "none"] for c in coverage["covered"]])
    if suggestion["suggested"]:
        r.tables["What comes next: the rule-based suggestion for the next sprint"] = md_table(
            ["Story", "Title", "Why"], [[x["id"], x["title"][:80], x["reason"]] for x in suggestion["suggested"]])

    r.findings.append(Finding(
        "audit.project_state", "Requirements by state",
        ", ".join(f"{R.REQ_STATE_LABELS[k]} {v}" for k, v in counts.items() if v) or "no approved requirement"))
    r.findings.append(Finding(
        "audit.backlog_gaps", f"{len(coverage['gaps'])} backlog gap(s)",
        ", ".join(f"{g['kind'].replace('_', ' ')}: {g['ref']}" for g in coverage["gaps"][:8]) or "none"))
    no_story = [g["ref"] for g in coverage["gaps"] if g["kind"] in ("legal_without_story", "requirement_without_story")]
    if no_story:
        r.raise_issue(
            f"{len(no_story)} approved requirement(s) have no story in the backlog: {', '.join(no_story)}. "
            "Generate stories for them, or record why none is needed.",
            type="missing_information", decision_owner="product", blocking=False,
        )
    if coverage["severe_uncovered"]:
        r.raise_issue(
            "High or critical risk(s) with no story behind them: " + ", ".join(coverage["severe_uncovered"])
            + ". Link each to a requirement with a story, or record the accepted risk.",
            type="risk_acceptance", decision_owner="product", blocking=False,
        )

    compact_review = {"evrs": review.get("evrs") or [], "evr_ids": review.get("evr_ids") or [],
                      "gaps": review.get("gaps") or [],
                      "record": {"findings": [{"links": f.get("links"), "priority": f.get("priority")}
                                              for f in (review.get("record") or {}).get("findings") or []]}}
    return {
        "state": {"counts": counts, "requirements": [
            {k: x[k] for k in ("id", "statement", "state", "stories", "legal", "obligation", "priority", "verified_in")}
            for x in rows]},
        "coverage": coverage,
        "history": history,
        "legal_unscheduled": legal_unscheduled,
        "next": {"suggested": suggestion["suggested"], "blocked": suggestion["blocked"],
                 "sprints_left": R.sprints_left(history, open_rai), "open_rai": open_rai},
        "board": {"backlog": backlog, "sprints": sprints, "review": compact_review},
    }
