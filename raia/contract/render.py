"""
raia.contract.render
====================

The one layout every RAIA artifact follows, rendered by code from the record.

Every document has the same frame — Summary, Findings, the agent's own
sections, Action Plan, Open Issues, Not Grounded in Retrieved Excerpts,
Declared Coverage — so a reviewer who has read one stage can read any stage of
any project, and two projects can be compared line by line. The agent's own
sections are named after what its normative source produces (a value register
and ethical value requirements, a sprint ethics log, drift alerts and a
response plan). Nothing in the Markdown is written by the model directly; it
is all a view of fields that were validated first.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from . import vocab as V

COMMON_HEAD = ["Summary", "Findings"]
COMMON_TAIL = ["Action Plan", "Open Issues", "Not Grounded in Retrieved Excerpts", "Declared Coverage"]

AGENT_SECTIONS: Dict[str, List[str]] = {
    "risk_classifier": ["Risk Classification", "Applicable Legal Obligations",
                        "Human Oversight and Affected Persons"],
    "requirements_reviewer": ["Context of Use and Stakeholders", "Value Register", "Gap Analysis",
                              "Ethical Value Requirements", "Impact Assessment"],
    "story_refiner": ["Refined Stories", "Stories Without Ethical Impact", "Sprint Ethics Log"],
    "auditor": ["Progress Audit", "Accountability Documentation", "Upcoming Ethical Checkpoints"],
    "drift_monitor": ["Drift Alerts", "Fairness & Representativeness Analysis", "Response Plan"],
}

STATUS_LABELS = {"on_track": "On track", "needs_attention": "Needs attention", "blocked": "Blocked"}


def required_sections(agent_key: str) -> List[str]:
    return COMMON_HEAD + AGENT_SECTIONS.get(agent_key, []) + COMMON_TAIL


def cell(value: Any) -> str:
    if value is None or value == "" or value == []:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value) or "—"
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def table(headers: List[str], rows: List[List[Any]]) -> str:
    if not rows:
        return "_None._"
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def sentence(value: Any) -> str:
    """A cell value ending in exactly one full stop."""
    text = cell(value)
    return text if text.endswith((".", "!", "?")) else text + "."


def label(value: Any) -> str:
    return str(value or "—").replace("_", " ")


def cites(values: Any) -> str:
    return " ".join(str(v) for v in values or [])


def para(value: Any) -> str:
    return str(value).strip() if value and str(value).strip() else "_Not provided._"


# ---------------------------------------------------------------------------
# Agent sections
# ---------------------------------------------------------------------------


def _risk(ext: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, str]:
    notes = {o.get("code"): o for o in ext.get("obligations") or []}
    rows = []
    for o in data.get("obligations") or []:
        n = notes.get(o.get("code"), {})
        rows.append([o.get("code"), o.get("jurisdiction"), o.get("title"),
                     n.get("meaning_for_this_product"), cites(n.get("citations"))])
    extra = [c for c in notes if c not in {o.get("code") for o in data.get("obligations") or []}]
    body = table(["Code", "Jurisdiction", "Obligation (computed)", "What it means for this product", "Grounding"], rows)
    if extra:
        body += "\n\nNotes for codes not in the computed table: " + ", ".join(str(e) for e in extra)
    return {
        "Risk Classification": "\n\n".join([
            "**Prohibited-practice screen (EU AI Act Art. 5; PL 2338/2023 excessive risk).** " + para(ext.get("prohibited_screen")),
            "**EU AI Act tier.** " + para(ext.get("eu_tier_justification")),
            "**PL 2338/2023 tier.** " + para(ext.get("br_tier_justification")),
        ]),
        "Applicable Legal Obligations": body,
        "Human Oversight and Affected Persons": "\n\n".join([
            "**Human oversight.** " + para(ext.get("human_oversight_assessment")),
            "**Rights of affected persons.** " + para(ext.get("affected_persons_rights")),
            "**Impact assessments required.** " + para(ext.get("impact_assessments")),
        ]),
    }


def _origin_note(origin: Dict[str, Any]) -> str:
    """Computed statement of which inputs RAIA proposed and a person adopted."""
    adopted = origin.get("adopted") or []
    fields = origin.get("fields") or {}
    if not adopted and not fields:
        return ""
    parts = []
    if adopted:
        edited = [a["id"] for a in adopted if a.get("edited")]
        parts.append(", ".join(a["id"] for a in adopted) + " were recommended by RAIA and adopted by the team"
                     + (f" ({', '.join(edited)} edited)" if edited else "") + "; coverage marked "
                     "'addressed by an adopted suggestion' rests on them.")
    names = {"stakeholders": "stakeholder groups", "values_at_stake": "principles at stake"}
    for key, meta in fields.items():
        parts.append(f"The {names.get(key, key)} were pre-filled from the approved risk classification and "
                     + ("kept as proposed" if meta.get("status") == "unchanged" else "adjusted by the team")
                     + (f", reviewed by {origin['reviewed_by']}" if origin.get("reviewed_by") else "") + ".")
    return "\n\n**Where the inputs came from (computed).** " + " ".join(parts)


def _requirements(ext: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, str]:
    ia = ext.get("impact_assessment") or {}
    gaps = {g.get("evr_id"): g for g in data.get("gaps") or []}
    return {
        "Context of Use and Stakeholders": para(ext.get("context_of_use")) + "\n\n" + table(
            ["Stakeholder", "Kind (IEEE 7000)", "Values at stake"],
            [[s.get("name"), s.get("kind"), [V.PRINCIPLE_NAMES.get(v, v) for v in s.get("values") or []]]
             for s in ext.get("stakeholders") or []]),
        "Value Register": table(
            ["Rank", "Core value", "Threats", "Opportunities"],
            [[v.get("rank"), V.PRINCIPLE_NAMES.get(v.get("value"), v.get("value")), v.get("threats"), v.get("opportunities")]
             for v in sorted(ext.get("value_register") or [], key=lambda x: x.get("rank") or 99)]),
        "Gap Analysis": table(
            ["EVR id", "Derived from (computed)", "Why it matters here", "Grounding"],
            [[g.get("evr_id"), f"{gaps.get(g.get('evr_id'), {}).get('kind', '—')} {gaps.get(g.get('evr_id'), {}).get('ref', '')}",
              g.get("explanation"), cites(g.get("citations"))] for g in ext.get("gap_analysis") or []]) + _origin_note(data.get("suggestion_origin") or {}),
        "Ethical Value Requirements": table(
            ["EVR id", "Value", "Stakeholders", "Requirement", "Fit criterion", "Verification", "Traces to", "Grounding"],
            [[e.get("id"), V.PRINCIPLE_NAMES.get(e.get("value"), e.get("value")), e.get("stakeholders"),
              e.get("statement"), e.get("fit_criterion"), e.get("verification_method"), e.get("traces_to"),
              cites(e.get("citations"))] for e in ext.get("evrs") or []]),
        "Impact Assessment": "\n\n".join([
            "**Intended uses.** " + para(ia.get("intended_uses")),
            table(["Stakeholder", "Potential harms", "Potential benefits"],
                  [[h.get("stakeholder"), h.get("harms"), h.get("benefits")] for h in ia.get("harms_and_benefits") or []]),
            "**Mitigations.** " + para(ia.get("mitigations")),
        ]),
    }


def _stories(ext: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, str]:
    refined, plain = [], []
    for s in ext.get("stories") or []:
        if s.get("criteria"):
            lines = [f"### {s.get('story_id')}",
                     "ECCOLA cards: " + cell([(c + " " + V.ECCOLA_CARDS.get(c, "")).strip()
                                              for c in s.get("eccola_cards") or []]),
                     "", para(s.get("card_discussion")), "",
                     table(["Criterion", "MS RAI v2 goal", "Stakeholder group", "Condition", "Evidence artifact", "Owner", "EVR"],
                           [[c.get("id"), f"{c.get('ms_goal')} {V.MS_GOALS.get(c.get('ms_goal'), '')}", c.get("stakeholder_group"),
                             c.get("condition"), c.get("evidence_artifact"), label(c.get("owner_role")), c.get("evr_ids")]
                            for c in s.get("criteria") or []])]
            refined.append("\n".join(lines))
        else:
            plain.append([s.get("story_id"), s.get("no_impact_reason")])
    return {
        "Refined Stories": "\n\n".join(refined) or "_None._",
        "Stories Without Ethical Impact": table(["Story", "Why no ethical criteria are needed"], plain),
        "Sprint Ethics Log": para(ext.get("sprint_ethics_log")),
    }


VERDICT_LABELS = {"satisfied": "Satisfied", "partially_satisfied": "Partially satisfied",
                  "at_risk": "At risk", "not_verified": "Not verified"}


def _audit(ext: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, str]:
    return {
        "Progress Audit": table(
            ["Item", "Verdict", "Computed by code", "Evidence", "Evidence needed", "Downgrade reason", "Grounding"],
            [[i.get("item_id"), VERDICT_LABELS.get(i.get("verdict"), i.get("verdict")), i.get("computed_verdict"),
              i.get("evidence"), i.get("evidence_needed"), i.get("downgrade_reason"), cites(i.get("citations"))]
             for i in ext.get("items") or []]),
        "Accountability Documentation": table(
            ["Decision", "Decided by", "Artifact", "Reference"],
            [[d.get("decision"), d.get("decided_by"), d.get("artifact"), d.get("reference")]
             for d in ext.get("accountability_log") or []]),
        "Upcoming Ethical Checkpoints": table(
            ["Checkpoint", "Triggered by", "Items", "Lifecycle stage"],
            [[c.get("checkpoint"), c.get("triggered_by"), c.get("item_ids"),
              V.LIFECYCLE_LABELS.get(c.get("lifecycle_stage"), c.get("lifecycle_stage"))]
             for c in ext.get("upcoming_checkpoints") or []]),
    }


def _drift(ext: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, str]:
    plan = ext.get("response_plan") or {}
    adequacy = ext.get("sample_adequacy") or []
    return {
        "Drift Alerts": table(["Window", "Severity (computed)", "What it means for affected people", "Grounding"],
                              [[a.get("window"), a.get("severity"), a.get("meaning_for_affected_people"), cites(a.get("citations"))]
                               for a in ext.get("alerts") or []]),
        "Fairness & Representativeness Analysis": "\n\n".join([
            "**Trend.** " + para(ext.get("trend_interpretation")),
            "**Representativeness.** " + para(ext.get("representativeness")),
            "**Sample adequacy.**\n" + ("\n".join(f"- {s}" for s in adequacy) if adequacy else "_No concern declared._"),
        ]),
        "Response Plan": "\n\n".join([
            "**Escalation path.** " + para(plan.get("escalation_path")),
            "**Rollback and deactivation criteria (NIST AI RMF MANAGE 2).** " + para(plan.get("deactivation_criteria")),
            "**Feedback from users and affected communities (NIST AI RMF MANAGE 4).** " + para(plan.get("affected_community_feedback")),
            "**Recovery and communication.** " + para(plan.get("recovery_and_communication")),
        ]),
    }


RENDERERS: Dict[str, Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, str]]] = {
    "risk_classifier": _risk,
    "requirements_reviewer": _requirements,
    "story_refiner": _stories,
    "auditor": _audit,
    "drift_monitor": _drift,
}


# ---------------------------------------------------------------------------
# The document
# ---------------------------------------------------------------------------


def machine_block(record: Dict[str, Any], checklist_keys: List[str]) -> str:
    lines = ["```raia", f"schema: {record.get('meta', {}).get('schema_version', V.SCHEMA_VERSION)}"]
    for k, v in (record.get("declared_verdict") or {}).items():
        lines.append(f"verdict.{k}: {v}")
    lines.append("verdict.agrees_with_screen: " + ("yes" if record.get("agrees_with_rule_engine", True) else "no"))
    cov = {c.get("key"): c for c in record.get("coverage") or []}
    for key in list(dict.fromkeys(list(checklist_keys) + list(cov))):
        c = cov.get(key)
        if c:
            lines.append(f"coverage.{key}: {c.get('status')} — {cell(c.get('justification'))}")
    lines.append("```")
    return "\n".join(lines)


def render(agent_key: str, record: Dict[str, Any], computed_data: Dict[str, Any],
           checklist_keys: List[str]) -> str:
    meta = record.get("meta") or {}
    frameworks = "; ".join(f["name"] for f in meta.get("frameworks") or [])
    parts: List[str] = [
        f"> **{meta.get('record_type', 'RAIA record')}** · `{meta.get('schema_version', V.SCHEMA_VERSION)}` · "
        f"{meta.get('agent_name', agent_key)} · {meta.get('layer', '')} layer · {meta.get('sdlc_phase', '')}  \n"
        f"> Grounded in: {frameworks or '—'}",
        "",
    ]

    if record.get("schema_errors"):
        parts += ["> **The model's reply did not conform to the output contract.** Errors: "
                  + "; ".join(record["schema_errors"][:8]), ""]

    computed = record.get("computed_verdict") or {}
    declared = record.get("declared_verdict") or {}
    keys = list(dict.fromkeys(list(declared) + [k for k, v in computed.items() if not isinstance(v, (list, dict))]))
    summary = [
        f"**Status: {STATUS_LABELS.get(record.get('overall_status'), label(record.get('overall_status')))}**",
        "",
        para(record.get("summary")),
        "",
        table(["Verdict", "Computed by code", "Declared by the agent"],
              [[k, computed.get(k), declared.get(k)] for k in keys]),
        "",
        "**Agrees with the rule engine:** " + ("yes" if record.get("agrees_with_rule_engine", True) else
                                               "no — " + para(record.get("disagreement_rationale"))),
    ]
    sections: Dict[str, str] = {"Summary": "\n".join(summary)}

    findings = record.get("findings") or []
    detail = []
    for f in findings:
        detail.append(
            f"- **{f.get('id')} — {sentence(f.get('title'))}** {sentence(f.get('statement'))} "
            f"_Affected: {sentence(f.get('stakeholders'))}_ _Placement: {sentence(f.get('placement_rationale'))}_ "
            f"_Priority basis: {sentence(f.get('priority_basis'))}_ {cites(f.get('citations'))}".rstrip()
        )
    sections["Findings"] = table(
        ["ID", "Finding", "Principle", "NIST AI RMF", "Magnitude", "Likelihood", "Risk level", "Priority", "Blocking", "Links"],
        [[f.get("id"), f.get("title"), V.PRINCIPLE_NAMES.get(f.get("principle"), f.get("principle")),
          f.get("nist_category"), f.get("magnitude"), f.get("likelihood"), f.get("risk_level"),
          f.get("priority"), f.get("blocking"), f.get("links")] for f in findings]
    ) + ("\n\n" + "\n".join(detail) if detail else "")

    sections.update(RENDERERS.get(agent_key, lambda e, d: {})(record.get("extension") or {}, computed_data or {}))

    sections["Action Plan"] = table(
        ["ID", "Action", "Response", "Owner", "Lifecycle stage", "Review cadence", "Verification",
         "Evidence artifact", "Priority", "Findings"],
        [[a.get("id"), a.get("action"), a.get("response"), V.OWNER_LABELS.get(a.get("owner_role"), a.get("owner_role")),
          V.LIFECYCLE_LABELS.get(a.get("lifecycle_stage"), a.get("lifecycle_stage")), label(a.get("review_cadence")),
          a.get("verification_method"), a.get("evidence_artifact"), a.get("priority"), a.get("finding_ids")]
         for a in record.get("actions") or []]
    ) + "".join(f"\n\n{a.get('id')} grounding: {cites(a.get('citations'))}" for a in record.get("actions") or [] if a.get("citations"))

    issues = record.get("open_issues") or []
    sections["Open Issues"] = "\n".join(
        f"- **{i.get('id')}** · {V.ISSUE_TYPE_LABELS.get(i.get('type'), label(i.get('type')))} · "
        f"decided by {V.OWNER_LABELS.get(i.get('decision_owner'), label(i.get('decision_owner')))}"
        f"{' · **blocking**' if i.get('blocking') else ''} · raised by {i.get('origin', 'agent')} — "
        f"{cell(i.get('description'))}"
        + (f" Options: {'; '.join(i.get('options'))}." if i.get("options") else "")
        for i in issues
    ) or "- None."

    ng = record.get("not_grounded") or []
    sections["Not Grounded in Retrieved Excerpts"] = "\n".join(f"- {cell(x)}" for x in ng) or "_None declared._"

    sections["Declared Coverage"] = table(
        ["Checklist item", "Status", "Justification"],
        [[c.get("key"), c.get("status"), c.get("justification")] for c in record.get("coverage") or []])

    for title in required_sections(agent_key):
        parts += [f"## {title}", "", sections.get(title) or "_None._", ""]

    if record.get("unparsed_response"):
        parts += ["## Unparsed Model Reply", "", "```text", record["unparsed_response"][:6000], "```", ""]

    parts.append(machine_block(record, checklist_keys))
    return "\n".join(parts)
