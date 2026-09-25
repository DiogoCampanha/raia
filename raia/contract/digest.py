"""
raia.contract.digest
====================

The reading order of every RAIA record, computed from the record.

People act on a record between other work, so every stage is read the same
way, top to bottom, and can be put down at any point:

1. **Summary** — the status, a one-line headline, the stage's signature (one
   picture only this agent draws — see :func:`signature`), a few numbers
   (risks found, actions to take, decisions needed, one figure specific to the
   stage) and the main issues.
2. **Actions** — what to do, grouped by computed priority (Do now, Plan,
   Track), each with its owner, when, and what shows it is done; then the
   decisions only a person can take.
3. **Deep dive** — the analysis behind each point, one section per topic, each
   opening with its conclusion. Last comes the traceability appendix
   (grounding gaps, declared coverage, verdict reconciliation).

This module builds that view as plain data. It does not call a model and does
not touch Streamlit: the screen (:mod:`raia.ui.record_view`) and the Markdown
document (:mod:`raia.contract.render`) both draw the same digest, so the
exported document reads exactly like the screen. Nothing here decides
anything — counts, groups and conclusions are read off fields code already
computed or the model already wrote.

Blocks
------
A deep-dive section is a list of typed blocks:

``text``     ``{"label", "text"}`` — a labelled paragraph, conclusion first
``table``    ``{"headers", "rows"}``
``cards``    ``{"items": [card]}`` — see :func:`card`
``bullets``  ``{"items": [str]}``
``note``     ``{"text"}`` — a quiet remark
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import vocab as V

#: Colour tones the views understand. Priority tones double as severity tones.
TONES = ("critical", "high", "medium", "low", "ok", "decision", "neutral")

STATUS_TONE = {"on_track": "ok", "needs_attention": "medium", "blocked": "critical"}

#: The Markdown heading of each tail section, in the order they are printed.
TRACE_SECTIONS = ["Not Grounded in Retrieved Excerpts", "Declared Coverage", "Verdict Reconciliation"]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def label(value: Any) -> str:
    return str(value or "—").replace("_", " ")


def first_sentence(text: Any) -> str:
    """The lead sentence of a field — the contract asks for the conclusion first."""
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    if not t:
        return ""
    m = re.search(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])", t)
    return t[: m.start()].strip() if m else t


def rest_after_first(text: Any) -> str:
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    lead = first_sentence(t)
    return t[len(lead):].strip()


def short_tier(tier: Any) -> str:
    """'high-risk unless the narrow-task exemption …' → 'High-risk'."""
    t = str(tier or "").strip()
    if not t:
        return "—"
    t = re.split(r"\s+[—–-]\s+|\s+unless\s+|\s*\(", t)[0].strip()
    return t[:1].upper() + t[1:]


def plural(n: int, one: str, many: Optional[str] = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def principle_name(key: Any) -> str:
    return V.PRINCIPLE_NAMES.get(str(key), label(key))


def priority_rank(p: Any) -> int:
    return V.rank(V.PRIORITIES, str(p or ""))


def tone_of_priority(p: Any) -> str:
    return p if p in V.PRIORITIES else "neutral"


def tag(text: str, tone: str = "neutral") -> Tuple[str, str]:
    return (text, tone)


def card(id: str = "", title: str = "", tone: str = "neutral", tags: Sequence[Tuple[str, str]] = (),
         body: str = "", fields: Sequence[Tuple[str, Any]] = (), cites: Sequence[str] = (),
         lead: str = "") -> Dict[str, Any]:
    """One card in a deep-dive section.

    ``lead`` is a highlighted line (a conclusion or a new criterion), ``body``
    the prose, ``fields`` labelled values (a list value becomes a sub-list),
    ``cites`` the grounding tags.
    """
    return {"id": id, "title": title, "tone": tone, "tags": list(tags), "lead": lead,
            "body": body, "fields": [(k, v) for k, v in fields if v not in (None, "", [])],
            "cites": [c for c in cites or [] if c]}


def _count_by(items: Sequence[Dict[str, Any]], key: str, scale: Sequence[str]) -> Dict[str, int]:
    out = {s: 0 for s in scale}
    for i in items:
        v = i.get(key)
        if v in out:
            out[v] += 1
    return out


def _breakdown(counts: Dict[str, int], order: Sequence[str]) -> str:
    return ", ".join(f"{counts[k]} {label(k)}" for k in order if counts.get(k))


# ---------------------------------------------------------------------------
# Summary and actions (shared by every agent)
# ---------------------------------------------------------------------------


def _findings_sorted(findings: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(findings, key=lambda f: (-int(bool(f.get("blocking"))), -priority_rank(f.get("priority"))))


def _action_view(a: Dict[str, Any], blocking_findings: set) -> Dict[str, Any]:
    when = V.LIFECYCLE_LABELS.get(a.get("lifecycle_stage"), label(a.get("lifecycle_stage")))
    cadence = V.CADENCE_LABELS.get(a.get("review_cadence"), label(a.get("review_cadence")))
    method = str(a.get("verification_method") or "")
    evidence = str(a.get("evidence_artifact") or "").strip()
    done = (f"{method.capitalize()}: {evidence}" if method and evidence else (evidence or method.capitalize()))
    return {
        "id": a.get("id", ""),
        "text": str(a.get("action") or "").strip(),
        "priority": a.get("priority") or "medium",
        "tone": tone_of_priority(a.get("priority") or "medium"),
        "blocking": any(fid in blocking_findings for fid in a.get("finding_ids") or []),
        "owner": a.get("owner_role", ""),
        "owner_label": V.OWNER_LABELS.get(a.get("owner_role"), label(a.get("owner_role"))),
        "when": f"{when}, reviewed {cadence}" if cadence and cadence != "once" else when,
        "done_when": done,
        "response": label(a.get("response")),
        "findings": list(a.get("finding_ids") or []),
        "cites": list(a.get("citations") or []),
    }


def _decision_view(i: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": i.get("id", ""),
        "type": i.get("type", ""),
        "type_label": V.ISSUE_TYPE_LABELS.get(i.get("type"), label(i.get("type"))),
        "text": str(i.get("description") or "").strip(),
        "options": [str(o) for o in i.get("options") or [] if str(o).strip()],
        "owner": i.get("decision_owner", ""),
        "owner_label": V.OWNER_LABELS.get(i.get("decision_owner"), label(i.get("decision_owner"))),
        "blocking": bool(i.get("blocking")),
        "origin": i.get("origin", "agent"),
        "links": list(i.get("links") or []),
        "tone": "critical" if i.get("blocking") else "decision",
    }


def _kpis_common(findings, actions, decisions) -> List[Dict[str, Any]]:
    by_p = _count_by(findings, "priority", V.PRIORITIES)
    top = next((p for p in reversed(V.PRIORITIES) if by_p.get(p)), None)
    now = sum(1 for a in actions if a["priority"] in ("critical", "high"))
    blocking = sum(1 for d in decisions if d["blocking"])
    return [
        {"label": "Risks identified", "value": len(findings),
         "hint": _breakdown(by_p, list(reversed(V.PRIORITIES))) or "none found",
         "tone": tone_of_priority(top) if top else "ok"},
        {"label": "Actions to take", "value": len(actions),
         "hint": (f"{now} to do now" if now else "none urgent") if actions else "nothing to do",
         "tone": "high" if now else ("neutral" if actions else "ok")},
        {"label": "Decisions needed", "value": len(decisions),
         "hint": (f"{blocking} blocking" if blocking else "none blocking") if decisions else "none open",
         "tone": "critical" if blocking else ("decision" if decisions else "ok")},
    ]


# ---------------------------------------------------------------------------
# Deep dive: shared sections
# ---------------------------------------------------------------------------


def _findings_section(findings: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    ordered = _findings_sorted(findings)
    if not ordered:
        conclusion = "No risks were identified at this stage."
    else:
        by_p = _count_by(ordered, "priority", V.PRIORITIES)
        conclusion = (f"{plural(len(ordered), 'risk')} identified "
                      f"({_breakdown(by_p, list(reversed(V.PRIORITIES)))}). "
                      f"Most pressing: {ordered[0].get('title', '').rstrip('.')}.")
    cards = []
    for f in ordered:
        tags = [tag(V.PRIORITY_LABELS.get(f.get("priority"), label(f.get("priority"))), tone_of_priority(f.get("priority")))]
        if f.get("blocking"):
            tags.append(tag("Blocking", "critical"))
        tags += [tag(principle_name(f.get("principle"))), tag(str(f.get("nist_category") or ""))]
        cards.append(card(
            id=f.get("id", ""), title=str(f.get("title") or "").rstrip("."), tone=tone_of_priority(f.get("priority")),
            tags=[t for t in tags if t[0]], body=str(f.get("statement") or ""),
            fields=[
                ("Affected", ", ".join(f.get("stakeholders") or [])),
                ("Why this priority", f"{label(f.get('magnitude')).capitalize()} impact, {label(f.get('likelihood'))} — "
                                      f"{str(f.get('placement_rationale') or '').strip()}".rstrip(" —")),
                ("Raised because", str(f.get("priority_basis") or "").split(";", 1)[1].strip()
                 if ";" in str(f.get("priority_basis") or "") else ""),
                ("Concerns", ", ".join(f.get("links") or [])),
            ],
            cites=f.get("citations") or [],
        ))
    return {"key": "findings", "title": "Findings", "md_title": "Findings", "group": "analysis",
            "conclusion": conclusion, "blocks": [{"type": "cards", "items": cards}] if cards else
            [{"type": "note", "text": "None."}]}


def _trace_sections(record: Dict[str, Any], computed_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    ng = [str(x) for x in record.get("not_grounded") or [] if str(x).strip()]
    coverage = record.get("coverage") or []
    declined = [c for c in coverage if c.get("status") != "covered"]
    computed = record.get("computed_verdict") or {}
    declared = record.get("declared_verdict") or {}
    keys = list(dict.fromkeys(list(declared) + [k for k, v in computed.items() if not isinstance(v, (list, dict))]))
    agrees = record.get("agrees_with_rule_engine", True)
    meta = record.get("meta") or {}
    frameworks = "; ".join(f.get("name", "") for f in meta.get("frameworks") or [])
    notes = [str(n) for n in record.get("contract_notes") or []]

    verdict_blocks: List[Dict[str, Any]] = [
        {"type": "table", "headers": ["Verdict", "Computed by code", "Declared by the agent"],
         "rows": [[k, computed.get(k), declared.get(k)] for k in keys]},
        {"type": "text", "label": "Agrees with the rule engine",
         "text": "Yes." if agrees else "No — " + (record.get("disagreement_rationale") or "no rationale given.")},
    ]
    if frameworks:
        verdict_blocks.append({"type": "text", "label": "Grounded in", "text": frameworks + "."})
    if notes:
        verdict_blocks.append({"type": "text", "label": "Corrections applied by code", "text": ""})
        verdict_blocks.append({"type": "bullets", "items": notes})

    return [
        {"key": "not_grounded", "title": "Not grounded", "md_title": "Not Grounded in Retrieved Excerpts",
         "group": "trace",
         "conclusion": (f"{plural(len(ng), 'claim')} matter but the retrieved excerpts do not support "
                        f"{'it' if len(ng) == 1 else 'them'}: verify before relying on them.") if ng
                       else "Every claim is supported by the retrieved excerpts.",
         "blocks": [{"type": "bullets", "items": ng}] if ng else [{"type": "note", "text": "None declared."}]},
        {"key": "coverage", "title": "Coverage", "md_title": "Declared Coverage", "group": "trace",
         "conclusion": (f"All {len(coverage)} checklist items are covered." if coverage and not declined else
                        f"{len(coverage) - len(declined)} of {len(coverage)} checklist items covered; "
                        f"{len(declined)} declared not applicable or not grounded." if coverage else
                        "No coverage was declared."),
         "blocks": [{"type": "table", "headers": ["Checklist item", "Status", "Justification"],
                     "rows": [[c.get("key"), c.get("status"), c.get("justification")] for c in coverage]}]},
        {"key": "reconciliation", "title": "Verdicts", "md_title": "Verdict Reconciliation", "group": "trace",
         "conclusion": "The agent agrees with the rule engine's verdict." if agrees else
                       "The agent disagrees with the rule engine — a person decides (see Decisions).",
         "blocks": verdict_blocks},
    ]


# ---------------------------------------------------------------------------
# Deep dive: agent sections and the stage-specific figure
# ---------------------------------------------------------------------------


def _text(lbl: str, value: Any) -> Dict[str, Any]:
    return {"type": "text", "label": lbl, "text": str(value or "").strip() or "Not provided."}


def _risk(ext: Dict[str, Any], data: Dict[str, Any], record: Dict[str, Any]):
    v = record.get("computed_verdict") or {}
    obligations = data.get("obligations") or []
    notes = {o.get("code"): o for o in ext.get("obligations") or []}
    eu = sum(1 for o in obligations if str(o.get("jurisdiction")).upper() == "EU")
    br = len(obligations) - eu
    prohibited = any(i.get("type") == "prohibited_practice" for i in record.get("open_issues") or [])
    rows = [[o.get("code"), o.get("jurisdiction"), o.get("title"),
             notes.get(o.get("code"), {}).get("meaning_for_this_product"),
             " ".join(notes.get(o.get("code"), {}).get("citations") or [])] for o in obligations]
    extra = [c for c in notes if c not in {o.get("code") for o in obligations}]
    obl_blocks: List[Dict[str, Any]] = [{"type": "table", "headers": ["Code", "Where", "Obligation", "What it means here", "Grounding"],
                                         "rows": rows}]
    if extra:
        obl_blocks.append({"type": "note", "text": "Notes for codes not in the computed table: " + ", ".join(map(str, extra))})
    sections = [
        {"key": "classification", "title": "Classification", "md_title": "Risk Classification",
         "conclusion": (f"EU AI Act: {short_tier(v.get('eu_tier'))}. PL 2338/2023: {short_tier(v.get('br_tier'))}."
                        + (" A prohibited or excessive-risk practice was declared." if prohibited else "")),
         "blocks": [_text("Prohibited-practice screen (EU AI Act Art. 5; PL 2338/2023 excessive risk)", ext.get("prohibited_screen")),
                    _text("EU AI Act tier", ext.get("eu_tier_justification")),
                    _text("PL 2338/2023 tier", ext.get("br_tier_justification"))]},
        {"key": "obligations", "title": "Legal obligations", "md_title": "Applicable Legal Obligations",
         "conclusion": (f"{plural(len(obligations), 'legal obligation')} apply ({eu} EU, {br} Brazil)."
                        if obligations else "No legal obligations were computed for this product."),
         "blocks": obl_blocks},
        {"key": "oversight", "title": "Oversight and rights", "md_title": "Human Oversight and Affected Persons",
         "conclusion": first_sentence(ext.get("human_oversight_assessment")) or "No oversight assessment was provided.",
         "blocks": [_text("Human oversight", ext.get("human_oversight_assessment")),
                    _text("Rights of affected persons", ext.get("affected_persons_rights")),
                    _text("Impact assessments required", ext.get("impact_assessments"))]},
    ]
    kpi = {"label": "EU AI Act tier", "value": short_tier(v.get("eu_tier")),
           "hint": f"PL 2338/2023: {short_tier(v.get('br_tier'))}",
           "tone": "critical" if prohibited else ("high" if "high" in str(v.get("eu_tier", "")).lower() else "neutral")}
    return sections, kpi


def _origin_note(origin: Dict[str, Any]) -> str:
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
    return "Where the inputs came from (computed): " + " ".join(parts)


def _requirements(ext: Dict[str, Any], data: Dict[str, Any], record: Dict[str, Any]):
    ia = ext.get("impact_assessment") or {}
    gaps = {g.get("evr_id"): g for g in data.get("gaps") or []}
    stakeholders = ext.get("stakeholders") or []
    direct = sum(1 for s in stakeholders if s.get("kind") == "direct")
    register = sorted(ext.get("value_register") or [], key=lambda x: x.get("rank") or 99)
    evrs = ext.get("evrs") or []
    v = record.get("computed_verdict") or {}
    legal = int(v.get("obligation_gaps") or sum(1 for g in gaps.values() if g.get("kind") != "principle"))
    gap_count = int(v.get("gap_count") or len(ext.get("gap_analysis") or []))
    gap_blocks: List[Dict[str, Any]] = [{"type": "table", "headers": ["EVR", "Derived from (computed)", "Why it matters here", "Grounding"],
                                         "rows": [[g.get("evr_id"),
                                                   f"{gaps.get(g.get('evr_id'), {}).get('kind', '—')} {gaps.get(g.get('evr_id'), {}).get('ref', '')}".strip(),
                                                   g.get("explanation"), " ".join(g.get("citations") or [])]
                                                  for g in ext.get("gap_analysis") or []]}]
    origin = _origin_note(data.get("suggestion_origin") or {})
    if origin:
        gap_blocks.append({"type": "note", "text": origin})
    evr_cards = [card(
        id=e.get("id", ""), title=principle_name(e.get("value")), tone="neutral",
        tags=[tag(str(e.get("verification_method") or "").capitalize())] + [tag(t) for t in e.get("traces_to") or []],
        lead=str(e.get("statement") or ""),
        fields=[("Fit criterion", e.get("fit_criterion")), ("Stakeholders", ", ".join(e.get("stakeholders") or []))],
        cites=e.get("citations") or []) for e in evrs]
    sections = [
        {"key": "context", "title": "Context and stakeholders", "md_title": "Context of Use and Stakeholders",
         "conclusion": (f"{plural(len(stakeholders), 'stakeholder group')} "
                        f"({direct} direct, {len(stakeholders) - direct} indirect). " + first_sentence(ext.get("context_of_use"))).strip(),
         "blocks": [_text("Context of use", ext.get("context_of_use")),
                    {"type": "table", "headers": ["Stakeholder", "Kind", "Values at stake"],
                     "rows": [[s.get("name"), s.get("kind"), ", ".join(principle_name(x) for x in s.get("values") or [])]
                              for s in stakeholders]}]},
        {"key": "values", "title": "Values", "md_title": "Value Register",
         "conclusion": (f"Top value: {principle_name(register[0].get('value'))}. "
                        f"{plural(len(register), 'core value')} ranked.") if register else "No values were ranked.",
         "blocks": [{"type": "table", "headers": ["Rank", "Core value", "Threats", "Opportunities"],
                     "rows": [[x.get("rank"), principle_name(x.get("value")), x.get("threats"), x.get("opportunities")]
                              for x in register]}]},
        {"key": "gaps", "title": "Gaps", "md_title": "Gap Analysis",
         "conclusion": (f"{plural(gap_count, 'gap')}: {legal} from legal obligations, {max(gap_count - legal, 0)} "
                        "from principles.") if gap_count else "No gaps between the declared controls and the obligations.",
         "blocks": gap_blocks},
        {"key": "evrs", "title": "Requirements", "md_title": "Ethical Value Requirements",
         "conclusion": (f"{plural(len(evrs), 'ethical value requirement')}, each with a fit criterion and a "
                        "verification method.") if evrs else "No requirements were written.",
         "blocks": [{"type": "cards", "items": evr_cards}] if evr_cards else [{"type": "note", "text": "None."}]},
        {"key": "impact", "title": "Impact assessment", "md_title": "Impact Assessment",
         "conclusion": first_sentence(ia.get("mitigations")) or first_sentence(ia.get("intended_uses")) or "Not provided.",
         "blocks": [_text("Intended uses", ia.get("intended_uses")),
                    {"type": "table", "headers": ["Stakeholder", "Potential harms", "Potential benefits"],
                     "rows": [[h.get("stakeholder"), h.get("harms"), h.get("benefits")] for h in ia.get("harms_and_benefits") or []]},
                    _text("Mitigations", ia.get("mitigations"))]},
    ]
    kpi = {"label": "Requirements", "value": len(evrs),
           "hint": f"{plural(gap_count, 'gap')} closed, {legal} legal", "tone": "neutral"}
    return sections, kpi


def _stories(ext: Dict[str, Any], data: Dict[str, Any], record: Dict[str, Any]):
    given = {s.get("id"): s for s in data.get("stories") or []}
    entries = ext.get("stories") or []
    refined = [s for s in entries if s.get("criteria") or s.get("conflicts")]
    plain = [s for s in entries if not (s.get("criteria") or s.get("conflicts"))]
    n_criteria = sum(len(s.get("criteria") or []) for s in entries)
    n_conflicts = sum(len(s.get("conflicts") or []) for s in entries)
    issue_by_criterion = {}
    for i in record.get("open_issues") or []:
        for link in i.get("links") or []:
            issue_by_criterion.setdefault(link, i.get("id"))

    cards = []
    for s in refined:
        sid = s.get("story_id", "")
        src = given.get(sid) or {}
        conflicts = {c.get("criterion_id"): c for c in s.get("conflicts") or []}
        existing = []
        for c in src.get("criteria") or []:
            flag = conflicts.get(c.get("id"))
            existing.append(f"{c.get('id')}: {c.get('text')}" + (
                f" — CONFLICT ({', '.join(flag.get('conflicts_with') or [])}): {flag.get('problem', '')}"
                + (f" Suggested: {flag.get('suggested_rewrite')}" if flag.get("suggested_rewrite") else "")
                + (f" [decision {issue_by_criterion[c.get('id')]}]" if issue_by_criterion.get(c.get("id")) else "")
                if flag else ""))
        for cid, flag in conflicts.items():
            if cid not in {c.get("id") for c in src.get("criteria") or []}:
                existing.append(f"{cid}: CONFLICT — {flag.get('problem', '')}")
        new = [f"{c.get('id')}: {c.get('condition')} (evidence: {c.get('evidence_artifact')}; "
               f"owner: {V.OWNER_LABELS.get(c.get('owner_role'), label(c.get('owner_role')))}; "
               f"{c.get('ms_goal')} {V.MS_GOALS.get(c.get('ms_goal'), '')}"
               + (f"; implements {', '.join(c.get('evr_ids'))}" if c.get("evr_ids") else "") + ")"
               for c in s.get("criteria") or []]
        tags = [tag(f"{plural(len(s.get('criteria') or []), 'new criterion', 'new criteria')}", "ok")]
        if s.get("conflicts"):
            tags.append(tag(plural(len(s["conflicts"]), "conflict"), "high"))
        tags += [tag(f"{c} {V.ECCOLA_CARDS.get(c, '')}".strip()) for c in s.get("eccola_cards") or []]
        cards.append(card(
            id=sid, title=src.get("title") or first_sentence(src.get("text")) or sid,
            tone="high" if s.get("conflicts") else "ok", tags=tags,
            body=str(s.get("card_discussion") or ""),
            fields=[("Story", src.get("description") or src.get("text") or ""),
                    ("Existing acceptance criteria", existing),
                    ("New ethical acceptance criteria", new)],
        ))
    log = ext.get("sprint_ethics_log") or []
    if isinstance(log, str):
        log = [log] if log.strip() else []
    sections = [
        {"key": "refined", "title": "Refined stories", "md_title": "Refined Stories",
         "conclusion": (f"{len(refined)} of {plural(len(entries), 'story', 'stories')} need ethical criteria: "
                        f"{plural(n_criteria, 'criterion', 'criteria')} added"
                        + (f", {plural(n_conflicts, 'existing criterion', 'existing criteria')} in conflict." if n_conflicts else "."))
                       if entries else "No stories were refined.",
         "blocks": [{"type": "cards", "items": cards}] if cards else [{"type": "note", "text": "None."}]},
        {"key": "no_impact", "title": "No ethical impact", "md_title": "Stories Without Ethical Impact",
         "conclusion": (f"{plural(len(plain), 'story', 'stories')} need no ethical criteria."
                        if plain else "Every story needs ethical criteria."),
         "blocks": [{"type": "table", "headers": ["Story", "Why no ethical criteria are needed"],
                     "rows": [[s.get("story_id"), s.get("no_impact_reason")] for s in plain]}]},
        {"key": "log", "title": "Sprint ethics log", "md_title": "Sprint Ethics Log",
         "conclusion": f"{plural(len(log), 'decision')} recorded this sprint." if log else "No decisions recorded.",
         "blocks": [{"type": "bullets", "items": [str(x) for x in log]}] if log else [{"type": "note", "text": "None."}]},
    ]
    kpi = {"label": "Stories refined", "value": f"{len(refined)} / {len(entries)}",
           "hint": f"{plural(n_criteria, 'new criterion', 'new criteria')}"
                   + (f", {plural(n_conflicts, 'conflict')}" if n_conflicts else ""),
           "tone": "high" if n_conflicts else "neutral"}
    return sections, kpi


def stories_paste(record: Dict[str, Any], data: Dict[str, Any]) -> str:
    """The refined stories as plain text, ready to paste back into the team's tracker.

    Each story keeps its own acceptance criteria; a conflicting one is marked
    for review with the suggested rewrite; the new ethical criteria follow,
    with their identifiers so the Auditor can find them again.
    """
    given = {s.get("id"): s for s in data.get("stories") or []}
    out: List[str] = []
    for entry in (record.get("extension") or {}).get("stories") or []:
        sid = entry.get("story_id", "")
        src = given.get(sid) or {}
        conflicts = {c.get("criterion_id"): c for c in entry.get("conflicts") or []}
        lines = [f"{sid} — {src.get('title')}" if src.get("title") else str(sid)]
        if src.get("description") or src.get("text"):
            lines.append(str(src.get("description") or src.get("text")))
        lines += ["", "Acceptance criteria:"]
        for c in src.get("criteria") or []:
            flag = conflicts.get(c.get("id"))
            if flag:
                lines.append(f"- [REVIEW — conflicts with {', '.join(flag.get('conflicts_with') or []) or 'an ethical requirement'}] "
                             f"{c.get('text')}" + (f" → suggested: {flag.get('suggested_rewrite')}" if flag.get("suggested_rewrite") else ""))
            else:
                lines.append(f"- {c.get('text')}")
        for c in entry.get("criteria") or []:
            lines.append(f"- {c.get('condition')} (ethics {c.get('id')}; evidence: {c.get('evidence_artifact')})")
        if not (src.get("criteria") or entry.get("criteria")):
            lines.append("- (none)")
        if entry.get("no_impact_reason") and not entry.get("criteria"):
            lines.append(f"No ethical criteria needed: {entry.get('no_impact_reason')}")
        out.append("\n".join(lines))
    return "\n\n".join(out)


VERDICT_TONE = {"satisfied": "ok", "partially_satisfied": "medium", "at_risk": "high", "not_verified": "critical"}


def _audit(ext: Dict[str, Any], data: Dict[str, Any], record: Dict[str, Any]):
    items = ext.get("items") or []
    counts = _count_by(items, "verdict", V.AUDIT_VERDICTS)
    order = ["not_verified", "at_risk", "partially_satisfied", "satisfied"]
    cards = [card(
        id=str(i.get("item_id", "")), title=V.AUDIT_VERDICT_LABELS.get(i.get("verdict"), label(i.get("verdict"))),
        tone=VERDICT_TONE.get(i.get("verdict"), "neutral"),
        tags=[tag("Computed: " + label(i.get("computed_verdict")))] if i.get("computed_verdict") else [],
        body=str(i.get("evidence") or ""),
        fields=[("Evidence needed", i.get("evidence_needed")), ("Downgrade reason", i.get("downgrade_reason"))],
        cites=i.get("citations") or [])
        for i in sorted(items, key=lambda x: order.index(x.get("verdict")) if x.get("verdict") in order else 9)]
    checkpoints = ext.get("upcoming_checkpoints") or []
    log = ext.get("accountability_log") or []
    sections = [
        {"key": "audit", "title": "Progress audit", "md_title": "Progress Audit",
         "conclusion": (f"{counts['satisfied']} of {len(items)} items satisfied"
                        + (f"; {_breakdown({k: counts[k] for k in order[:3]}, order[:3])}." if len(items) - counts["satisfied"] else "."))
                       if items else "No items were audited.",
         "blocks": [{"type": "cards", "items": cards}] if cards else [{"type": "note", "text": "None."}]},
        {"key": "accountability", "title": "Accountability", "md_title": "Accountability Documentation",
         "conclusion": f"{plural(len(log), 'decision')} on record, each traced to an approved artifact." if log
                       else "No decisions on record.",
         "blocks": [{"type": "table", "headers": ["Decision", "Decided by", "Artifact", "Reference"],
                     "rows": [[d.get("decision"), d.get("decided_by"), d.get("artifact"), d.get("reference")] for d in log]}]},
        {"key": "checkpoints", "title": "Next checkpoints", "md_title": "Upcoming Ethical Checkpoints",
         "conclusion": (f"Next: {str(checkpoints[0].get('checkpoint') or '').rstrip('.')}." if checkpoints
                        else "No upcoming checkpoints."),
         "blocks": [{"type": "table", "headers": ["Checkpoint", "Triggered by", "Items", "Lifecycle stage"],
                     "rows": [[c.get("checkpoint"), c.get("triggered_by"), ", ".join(c.get("item_ids") or []),
                               V.LIFECYCLE_LABELS.get(c.get("lifecycle_stage"), label(c.get("lifecycle_stage")))]
                              for c in checkpoints]}]},
    ]
    weak = counts["not_verified"] + counts["at_risk"]
    kpi = {"label": "Items verified", "value": f"{counts['satisfied']} / {len(items)}",
           "hint": f"{counts['at_risk']} at risk, {counts['not_verified']} not verified",
           "tone": "high" if weak else "ok"}
    return sections, kpi


def _drift(ext: Dict[str, Any], data: Dict[str, Any], record: Dict[str, Any]):
    alerts = ext.get("alerts") or []
    plan = ext.get("response_plan") or {}
    adequacy = [str(x) for x in ext.get("sample_adequacy") or [] if str(x).strip()]
    sev = [a.get("severity") for a in alerts]
    worst = next((s for s in ("high", "medium", "low") if s in sev), None)
    v = record.get("computed_verdict") or {}
    cards = [card(id=str(a.get("window", "")), title=f"{str(a.get('severity') or '').capitalize()} severity",
                  tone=tone_of_priority(a.get("severity")), body=str(a.get("meaning_for_affected_people") or ""),
                  cites=a.get("citations") or []) for a in alerts]
    fair_blocks = [_text("Trend", ext.get("trend_interpretation")), _text("Representativeness", ext.get("representativeness")),
                   {"type": "text", "label": "Sample adequacy", "text": "" if adequacy else "No concern declared."}]
    if adequacy:
        fair_blocks.append({"type": "bullets", "items": adequacy})
    sections = [
        {"key": "alerts", "title": "Drift alerts", "md_title": "Drift Alerts",
         "conclusion": (f"{plural(len(alerts), 'window')} breached the threshold; highest severity {worst}."
                        if alerts else "No window breached the threshold."),
         "blocks": [{"type": "cards", "items": cards}] if cards else [{"type": "note", "text": "None."}]},
        {"key": "fairness", "title": "Fairness", "md_title": "Fairness & Representativeness Analysis",
         "conclusion": first_sentence(ext.get("trend_interpretation")) or "No trend interpretation was provided.",
         "blocks": fair_blocks},
        {"key": "response", "title": "Response plan", "md_title": "Response Plan",
         "conclusion": first_sentence(plan.get("deactivation_criteria")) or first_sentence(plan.get("escalation_path"))
                       or "No response plan was provided.",
         "blocks": [_text("Escalation path", plan.get("escalation_path")),
                    _text("Rollback and deactivation criteria", plan.get("deactivation_criteria")),
                    _text("Feedback from users and affected communities", plan.get("affected_community_feedback")),
                    _text("Recovery and communication", plan.get("recovery_and_communication"))]},
    ]
    kpi = {"label": "Drift alerts", "value": len(alerts),
           "hint": f"trend {label(v.get('trend') or 'unknown')}, {plural(int(v.get('windows') or 0), 'window')}",
           "tone": tone_of_priority(worst) if worst else "ok"}
    return sections, kpi


AGENT_SECTIONS = {
    "risk_classifier": _risk,
    "requirements_reviewer": _requirements,
    "story_refiner": _stories,
    "auditor": _audit,
    "drift_monitor": _drift,
}

#: The Markdown heading of each agent's own sections, in order. The contract's
#: layout (and the section check) is read from here.
AGENT_MD_SECTIONS: Dict[str, List[str]] = {
    "risk_classifier": ["Risk Classification", "Applicable Legal Obligations", "Human Oversight and Affected Persons"],
    "requirements_reviewer": ["Context of Use and Stakeholders", "Value Register", "Gap Analysis",
                              "Ethical Value Requirements", "Impact Assessment"],
    "story_refiner": ["Refined Stories", "Stories Without Ethical Impact", "Sprint Ethics Log"],
    "auditor": ["Progress Audit", "Accountability Documentation", "Upcoming Ethical Checkpoints"],
    "drift_monitor": ["Drift Alerts", "Fairness & Representativeness Analysis", "Response Plan"],
}


# ---------------------------------------------------------------------------
# Signature: the one picture each agent draws at the top of its summary
# ---------------------------------------------------------------------------
#
# Every agent reads the same way, but each answers a different question, and
# its summary opens with the picture of that answer: where the product sits on
# the legal risk scales, which principles the requirements cover, how each
# story came out, what the audit could verify, how the fairness gap moved
# across windows. Only facts code computed (or the record's own verdict
# fields) are drawn; tones keep their shared meaning. Kinds:
#
# ``scale``   ``{"rows": [{"label", "steps": [str], "active": int, "tone", "note"}]}``
# ``cells``   ``{"cells": [{"label", "state", "tone"}]}``
# ``split``   ``{"segments": [{"label", "value": int, "tone"}]}`` — parts of one whole
# ``series``  ``{"points": [{"label", "value": float, "tone", "note"}], "threshold": float, "unit"}``

EU_STEPS = ["Minimal", "Limited", "High", "Prohibited"]
BR_STEPS = ["Not listed", "High", "Excessive"]
_STEP_TONES = {"Minimal": "ok", "Limited": "medium", "High": "high", "Prohibited": "critical",
               "Not listed": "ok", "Excessive": "critical"}


def _eu_step(tier: str) -> Optional[int]:
    t = tier.lower()
    if not t:
        return None
    if t.startswith("unacceptable") or t.startswith("prohibited"):
        return 3
    if t.startswith("high"):
        return 2
    if t.startswith("limited"):
        return 1
    if t.startswith("minimal"):
        return 0
    return None


def _br_step(tier: str) -> Optional[int]:
    t = tier.lower()
    if not t:
        return None
    if t.startswith("excessive") or t.startswith("prohibited"):
        return 2
    if t.startswith("high"):
        return 1
    if t.startswith("not in"):
        return 0
    return None


def _sig_risk(ext, data, record) -> Optional[Dict[str, Any]]:
    v = record.get("computed_verdict") or {}
    rows = []
    for name, steps, tier, step in (("EU AI Act", EU_STEPS, str(v.get("eu_tier") or ""), _eu_step),
                                    ("PL 2338/2023", BR_STEPS, str(v.get("br_tier") or ""), _br_step)):
        at = step(tier)
        if at is not None:
            note = short_tier(tier)
            rows.append({"label": name, "steps": steps, "active": at, "tone": _STEP_TONES[steps[at]],
                         # The step already says it; keep the note only when it adds something.
                         "note": "" if note.lower().startswith(steps[at].lower()) else note})
    if not rows:
        return None
    return {"kind": "scale", "title": "Where the product sits", "rows": rows,
            "caption": "Tiers computed by the rule engine from the declared answers."}


def _sig_requirements(ext, data, record) -> Optional[Dict[str, Any]]:
    cov = data.get("principle_coverage") or {}
    if not cov:
        return None
    cells = []
    for name, status in cov.items():
        st_ = str(status)
        if st_ == "addressed":
            cells.append({"label": name, "state": "Addressed", "tone": "ok"})
        elif st_.startswith("addressed"):
            cells.append({"label": name, "state": "By an adopted suggestion", "tone": "low"})
        elif "at stake" in st_:
            cells.append({"label": name, "state": "Gap · at stake", "tone": "high"})
        else:
            cells.append({"label": name, "state": "Gap", "tone": "medium"})
    covered = sum(1 for c in cells if c["tone"] in ("ok", "low"))
    v = record.get("computed_verdict") or {}
    legal, total = int(v.get("obligation_gaps") or 0), int(v.get("gap_count") or 0)
    return {"kind": "cells", "title": "Principle coverage",
            "cells": cells,
            "caption": f"{covered} of {len(cells)} principles covered by the team's requirements"
                       + (f"; {plural(total, 'gap')} to close ({legal} from legal obligations)." if total else ".")}


def _sig_stories(ext, data, record) -> Optional[Dict[str, Any]]:
    given = {s.get("id"): s for s in data.get("stories") or []}
    entries = ext.get("stories") or []
    if not entries:
        return None
    cells = []
    for s in entries:
        sid = str(s.get("story_id") or "")
        title = (given.get(sid) or {}).get("title") or ""
        n_new, n_conf = len(s.get("criteria") or []), len(s.get("conflicts") or [])
        if n_conf:
            state, tone = plural(n_conf, "conflict") + (f", {n_new} new" if n_new else ""), "high"
        elif n_new:
            state, tone = plural(n_new, "new criterion", "new criteria"), "ok"
        else:
            state, tone = "No ethical impact", "neutral"
        cells.append({"label": f"{sid} · {title}" if title else sid, "state": state, "tone": tone})
    return {"kind": "cells", "title": "How each story came out", "cells": cells,
            "caption": "Conflicts with existing criteria are decisions for the team; RAIA never rewrites one."}


def _sig_audit(ext, data, record) -> Optional[Dict[str, Any]]:
    items = ext.get("items") or []
    if not items:
        return None
    counts = _count_by(items, "verdict", V.AUDIT_VERDICTS)
    return {"kind": "split", "title": "What the evidence verifies",
            "segments": [{"label": V.AUDIT_VERDICT_LABELS[k], "value": counts[k], "tone": VERDICT_TONE[k]}
                         for k in V.AUDIT_VERDICTS],
            "caption": f"{plural(len(items), 'item')} audited. When in doubt an item stays Not verified."}


def _sig_drift(ext, data, record) -> Optional[Dict[str, Any]]:
    windows = ((data.get("analysis") or {}).get("windows")) or []
    points = [w for w in windows if isinstance(w.get("dp_difference"), (int, float))]
    if not points:
        return None
    threshold = ((data.get("thresholds") or {}).get("parity_difference") or {}).get("value")
    trend = ((data.get("analysis") or {}).get("trend") or {}).get("direction")
    return {"kind": "series", "title": "Parity gap by window",
            "threshold": threshold, "unit": "",
            "points": [{"label": str(w.get("window")), "value": float(w["dp_difference"]),
                        "tone": "high" if w.get("parity_breach") else "ok",
                        "note": "breach" if w.get("parity_breach") else ""} for w in points],
            "caption": "Demographic-parity difference computed from the telemetry"
                       + (f"; the trend is {trend}." if trend else ".")}


SIGNATURES = {
    "risk_classifier": _sig_risk,
    "requirements_reviewer": _sig_requirements,
    "story_refiner": _sig_stories,
    "auditor": _sig_audit,
    "drift_monitor": _sig_drift,
}


def signature(agent_key: str, record: Dict[str, Any], data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The agent's own summary picture, or ``None`` when its facts are missing."""
    fn = SIGNATURES.get(agent_key)
    if not fn:
        return None
    try:
        return fn(record.get("extension") or {}, data, record)
    except (TypeError, ValueError, KeyError, AttributeError):
        # A record from an older schema may lack a field; the picture is an aid,
        # never the only place a fact is shown, so it is simply left out.
        return None


def signature_text(sig: Optional[Dict[str, Any]]) -> str:
    """One Markdown line for the exported document, so it reads like the screen."""
    if not sig:
        return ""
    kind = sig["kind"]
    if kind == "scale":
        body = "; ".join(f"{r['label']}: **{r['steps'][r['active']]}** (of {' · '.join(r['steps'])})"
                         for r in sig["rows"])
    elif kind == "cells":
        body = "; ".join(f"{c['label']}: {c['state']}" for c in sig["cells"])
    elif kind == "split":
        body = " · ".join(f"{s['label']} {s['value']}" for s in sig["segments"])
    elif kind == "series":
        thr = sig.get("threshold")
        body = ((f"threshold {thr:g} — " if isinstance(thr, (int, float)) else "")
                + " · ".join(f"{p['label']}: {p['value']:g}" + (f" ({p['note']})" if p["note"] else "")
                             for p in sig["points"]))
    else:
        return ""
    return f"**{sig['title']}** — {body}. {sig.get('caption', '')}".strip()


# ---------------------------------------------------------------------------
# The digest
# ---------------------------------------------------------------------------


def build(agent_key: str, record: Dict[str, Any], computed_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Everything the three tiers show, in reading order."""
    record = record or {}
    data = computed_data or {}
    findings = record.get("findings") or []
    blocking_findings = {f.get("id") for f in findings if f.get("blocking")}
    actions = [_action_view(a, blocking_findings) for a in record.get("actions") or []]
    actions.sort(key=lambda a: (-int(a["blocking"]), -priority_rank(a["priority"])))
    decisions = [_decision_view(i) for i in record.get("open_issues") or []]
    decisions.sort(key=lambda d: -int(d["blocking"]))

    status = record.get("overall_status") or "needs_attention"
    headline = str(record.get("headline") or "").strip() or first_sentence(record.get("summary"))
    summary = str(record.get("summary") or "").strip()
    if not record.get("headline") and summary.startswith(headline):
        summary = summary[len(headline):].strip()

    agent_sections, agent_kpi = AGENT_SECTIONS.get(agent_key, lambda e, d, r: ([], None))(
        record.get("extension") or {}, data, record)
    for s in agent_sections:
        s.setdefault("group", "analysis")
    kpis = _kpis_common(findings, actions, decisions) + ([agent_kpi] if agent_kpi else [])

    principles: Dict[str, int] = {}
    for f in findings:
        name = principle_name(f.get("principle"))
        principles[name] = principles.get(name, 0) + 1

    groups = []
    for key, title, members, hint in V.ACTION_GROUPS:
        items = [a for a in actions if a["priority"] in members]
        groups.append({"key": key, "title": title, "hint": hint, "actions": items,
                       "tone": {"now": "high", "plan": "medium", "track": "low"}[key]})

    owners = list(dict.fromkeys([a["owner"] for a in actions] + [d["owner"] for d in decisions]))
    owners = [o for o in V.OWNER_ROLES if o in owners] + [o for o in owners if o not in V.OWNER_ROLES and o]

    notices = []
    if record.get("schema_errors"):
        notices.append("The model's reply did not conform to the output contract. Errors: "
                       + "; ".join(str(e) for e in record["schema_errors"][:8]))

    meta = record.get("meta") or {}
    return {
        "signature": signature(agent_key, record, data),
        "agent_key": agent_key,
        "meta": meta,
        "status": {"key": status, "label": V.STATUS_LABELS.get(status, label(status)),
                   "tone": STATUS_TONE.get(status, "neutral")},
        "headline": headline,
        "summary": summary,
        "kpis": kpis,
        "top_issues": _findings_sorted(findings)[:3],
        "principles": sorted(principles.items(), key=lambda kv: -kv[1]),
        "action_groups": groups,
        "actions": actions,
        "decisions": decisions,
        "owners": owners,
        "deep": [_findings_section(findings)] + agent_sections + _trace_sections(record, data),
        "notices": notices,
        "unparsed": record.get("unparsed_response") or "",
        "paste": stories_paste(record, data) if agent_key == "story_refiner" else "",
    }


def owner_counts(digest: Dict[str, Any]) -> Dict[str, int]:
    """Actions and decisions per owner role, for the owner filter."""
    out: Dict[str, int] = {}
    for a in digest.get("actions") or []:
        out[a["owner"]] = out.get(a["owner"], 0) + 1
    for d in digest.get("decisions") or []:
        out[d["owner"]] = out.get(d["owner"], 0) + 1
    return out
