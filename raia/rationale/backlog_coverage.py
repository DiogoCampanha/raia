"""
raia.rationale.backlog_coverage
===============================

Is the backlog enough to answer the project's ethical risks?

The Auditor audits the whole project at every sprint close, and one of the
things an audit has to say is whether the work planned is the work needed. The
checks are enumerable, so they are computed here, before the model is asked
anything:

1. every approved requirement has at least one live story;
2. every high or critical finding of the approved risk classification and
   requirements review traces to a requirement that has a story;
3. every requirement that closes a legal obligation gap has a story;
4. every ethical acceptance criterion names the evidence artifact that would
   demonstrate it;
5. no product story that touches scoring, automated decisions or personal data
   is marked "no ethical impact" without a second look;
6. every ECCOLA theme in scope for the product has at least one story.

Each gap becomes an item of the report with the action that closes it. What
code cannot judge is whether a story's criteria really answer the risk; the
model does that, for the requirements code found covered, and may only lower
that judgement — the same one-way rule the audit verdicts follow.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from .. import backlog as B
from .. import roadmap as R
from .story_map import CARDS, MODULE_SECTIONS, cards_for

SENSITIVE_TOUCHES = ("scoring", "automation", "data_collection")
SEVERE = ("critical", "high")

#: Gap kinds, most serious first, with the action that closes each.
KINDS = {
    "legal_without_story": ("A requirement closing a legal obligation gap has no story",
                            "Generate stories for it now"),
    "risk_without_story": ("A high or critical risk has no story behind it",
                           "Link it to a requirement with a story, or generate one"),
    "requirement_without_story": ("An approved requirement has no story", "Generate stories for it"),
    "criterion_without_evidence": ("An ethical criterion names no evidence artifact",
                                   "Name the artifact that would demonstrate it"),
    "no_impact_second_look": ("A story touching a sensitive capability is marked no ethical impact",
                              "Refine it again, or record why it needs no criteria"),
    "theme_without_story": ("An ECCOLA theme in scope has no story", "Consider a story for this theme"),
}


def _findings(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    return list(((data or {}).get("record") or {}).get("findings") or [])


def run(backlog: Dict[str, Any], review: Dict[str, Any], risk: Dict[str, Any]) -> Dict[str, Any]:
    """``{"gaps": [...], "covered": [...], "severe_uncovered": [...], "legal_uncovered": [...]}``."""
    bl = B.normalize_backlog(backlog)
    rows = R.requirement_states(review, bl)
    by_id = {r["id"]: r for r in rows}
    gaps: List[Dict[str, Any]] = []

    def gap(kind: str, ref: str, text: str, legal: bool = False) -> None:
        title, action = KINDS[kind]
        gaps.append({"kind": kind, "ref": ref, "title": title, "text": text, "action": action,
                     "legal": legal})

    # 1 and 3: requirements without a story (legal ones first, and apart).
    for r in rows:
        if r["state"] == R.NO_STORY:
            if r["legal"]:
                gap("legal_without_story", r["id"], f"{r['id']} closes {r['obligation']}: {r['statement'][:120]}",
                    legal=True)
            else:
                gap("requirement_without_story", r["id"], f"{r['id']}: {r['statement'][:120]}")

    # 2: severe findings upstream that no story answers.
    obligation_to_evr = {str(g.get("ref")): str(g.get("evr_id")) for g in review.get("gaps") or [] if g.get("evr_id")}
    severe_uncovered: List[str] = []
    for source, data in (("risk classification", risk), ("requirements review", review)):
        for f in _findings(data):
            if f.get("priority") not in SEVERE:
                continue
            evrs = {str(l) for l in f.get("links") or [] if str(l) in by_id}
            evrs |= {obligation_to_evr[str(l)] for l in f.get("links") or [] if str(l) in obligation_to_evr}
            if any(by_id[e]["state"] != R.NO_STORY for e in evrs if e in by_id):
                continue
            severe_uncovered.append(str(f.get("id")))
            gap("risk_without_story", str(f.get("id")),
                f"{f.get('id')} ({f.get('priority')}, {source}): {str(f.get('title') or '')[:100]}"
                + (f" — linked to {', '.join(sorted(evrs))}, which have no story" if evrs
                   else " — linked to no requirement"))

    # 4: criteria without an evidence artifact.
    for s in B.live(bl):
        for c in B.ethical_criteria(s):
            if not str(c.get("evidence_artifact") or "").strip():
                gap("criterion_without_evidence", str(c.get("id")), f"{c.get('id')} on {s['id']}")

    # 5: sensitive product stories marked no impact.
    for s in B.live(bl):
        touches = set(s.get("touches") or [])
        if s.get("origin") == B.PRODUCT and s.get("no_impact_reason") and touches & set(SENSITIVE_TOUCHES):
            gap("no_impact_second_look", s["id"],
                f"{s['id']} touches {', '.join(sorted(touches & set(SENSITIVE_TOUCHES)))} but is marked no ethical impact")

    # 6: ECCOLA themes in scope for the product with no story. The analysis
    # module applies to any product and is left out: it is covered by the
    # requirements work itself.
    all_touches = sorted({t for s in B.live(bl) for t in s.get("touches") or []})
    in_scope = {c["module"] for c in cards_for(risk, all_touches)} - {"Analyze"}
    used_cards = {c for s in B.live(bl) for c in s.get("eccola_cards") or []}
    module_of = {c["id"]: c["module"] for c in CARDS}
    used_modules = {module_of.get(c) for c in used_cards}
    for module in sorted(in_scope - used_modules):
        gap("theme_without_story", module, MODULE_SECTIONS.get(module, module))

    covered = [{"ref": r["id"], "statement": r["statement"][:160], "stories": r["stories"],
                "criteria": [c.get("text", "")[:120] for sid in r["stories"]
                             for c in B.ethical_criteria(B.story(bl, sid) or {})][:4],
                "legal": r["legal"], "priority": r["priority"]}
               for r in rows if r["state"] != R.NO_STORY]
    order = list(KINDS)
    gaps.sort(key=lambda g: order.index(g["kind"]))
    return {
        "gaps": gaps,
        "covered": covered,
        "severe_uncovered": severe_uncovered,
        "legal_uncovered": [g["ref"] for g in gaps if g["kind"] == "legal_without_story"],
        "counts": {k: sum(1 for g in gaps if g["kind"] == k) for k in KINDS},
    }


def legal_unscheduled(rows: Sequence[Dict[str, Any]]) -> List[str]:
    """Legal-obligation requirements whose stories have never been in any sprint (or have none)."""
    return [r["id"] for r in rows if r["legal"] and r["state"] != R.VERIFIED and not r.get("scheduled")]
