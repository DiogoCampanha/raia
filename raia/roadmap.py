"""
raia.roadmap
============

The roadmap is computed, never generated.

It answers three questions from facts the project already holds — the
approved requirements, the backlog, the sprints and the approved audits:

* **Where does each requirement stand?** No story yet, planned, in the sprint,
  delivered, verified, or at risk.
* **Is the project improving?** Verified requirements per sprint, criteria
  verified, stories carried over, and a trend read off that series.
* **What comes next?** A suggestion for the next sprint, ranked by rules alone:
  no model is called, and a person accepts all, some or none of it.

Everything here is a pure function of plain dicts, so the board, the Auditor's
rule engine and the tests all read the same numbers.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import backlog as B

NO_STORY = "no_story"
PLANNED = "planned"
IN_SPRINT = "in_sprint"
DELIVERED = "delivered"
VERIFIED = "verified"
AT_RISK = "at_risk"
REQ_STATES = (NO_STORY, PLANNED, IN_SPRINT, DELIVERED, VERIFIED, AT_RISK)
REQ_STATE_LABELS = {
    NO_STORY: "No story", PLANNED: "Planned", IN_SPRINT: "In sprint", DELIVERED: "Delivered, not verified",
    VERIFIED: "Verified", AT_RISK: "At risk",
}
PRIORITY_ORDER = ("critical", "high", "medium", "low", "")

#: The default size of every list the board and the generate mode start from.
SHORT_LIST = 5
#: The most a person can widen the generate mode to in one run.
MAX_GENERATE = 10
#: Stories per sprint when the team has not set a capacity.
DEFAULT_CAPACITY = 5


# ---------------------------------------------------------------------------
# Requirements: priority and state
# ---------------------------------------------------------------------------


def _higher(a: str, b: str) -> str:
    ia = PRIORITY_ORDER.index(a) if a in PRIORITY_ORDER else len(PRIORITY_ORDER)
    ib = PRIORITY_ORDER.index(b) if b in PRIORITY_ORDER else len(PRIORITY_ORDER)
    return a if ia <= ib else b


def requirement_facts(review: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Per approved requirement: its wording, whether it closes a legal gap, its priority.

    The priority is the highest computed priority among the approved review's
    findings that link the requirement; a requirement closing a legal
    obligation gap is at least high. Both were computed by code at that gate.
    """
    review = review or {}
    evrs = review.get("evrs") or []
    ids = [str(e.get("id")) for e in evrs if e.get("id")] or [str(x) for x in review.get("evr_ids") or []]
    out: Dict[str, Dict[str, Any]] = {}
    for pos, eid in enumerate(ids):
        e = next((x for x in evrs if str(x.get("id")) == eid), {})
        out[eid] = {"id": eid, "statement": str(e.get("statement") or ""),
                    "fit_criterion": str(e.get("fit_criterion") or ""),
                    "legal": False, "obligation": "", "priority": "", "order": pos}
    for g in review.get("gaps") or []:
        eid = str(g.get("evr_id") or "")
        ref = str(g.get("ref") or "")
        if eid in out:
            if not out[eid]["statement"]:
                out[eid]["statement"] = str(g.get("subject") or "")
            if g.get("kind") != "principle" and ref.startswith(("eu.", "br.")):
                out[eid]["legal"] = True
                out[eid]["obligation"] = ref
                out[eid]["priority"] = _higher(out[eid]["priority"], "high")
    record = review.get("record") or {}
    for f in record.get("findings") or []:
        for link in f.get("links") or []:
            if str(link) in out:
                out[str(link)]["priority"] = _higher(out[str(link)]["priority"], str(f.get("priority") or ""))
    return out


def requirement_states(review: Dict[str, Any], bl: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Every approved requirement with its stories and where it stands, highest priority first."""
    facts = requirement_facts(review)
    stories = B.live(bl)
    rows = []
    for eid, f in facts.items():
        linked = [s for s in stories if eid in (s.get("evr_ids") or [])]
        statuses = [s["status"] for s in linked]
        if not linked:
            state = NO_STORY
        elif all(x == B.VERIFIED for x in statuses):
            state = VERIFIED
        elif any(s.get("carried_over", 0) >= 1 and s.get("last_verdict") in ("not_verified", "at_risk")
                 and s["status"] != B.VERIFIED for s in linked):
            state = AT_RISK
        elif any(x == B.IN_SPRINT for x in statuses):
            state = IN_SPRINT
        elif all(x in (B.DONE, B.VERIFIED) for x in statuses):
            state = DELIVERED
        else:
            state = PLANNED
        verified_in = ""
        if state == VERIFIED:
            verified_in = max((s.get("verified_in") or "" for s in linked), key=_sprint_no, default="")
        rows.append({**f, "state": state, "stories": [s["id"] for s in linked], "verified_in": verified_in,
                     "scheduled": any(s.get("sprints") for s in linked)})
    rows.sort(key=lambda r: (not r["legal"], PRIORITY_ORDER.index(r["priority"]) if r["priority"] in PRIORITY_ORDER else 9,
                             r["order"]))
    return rows


def _sprint_no(spr_id: str) -> int:
    try:
        return int(str(spr_id).split("-")[-1])
    except ValueError:
        return 0


def state_counts(rows: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    out = {k: 0 for k in REQ_STATES}
    for r in rows:
        out[r["state"]] = out.get(r["state"], 0) + 1
    return out


def uncovered_requirements(review: Dict[str, Any], bl: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Requirements with no live RAI story, highest priority first (the generate mode's scope)."""
    rai = [s for s in B.live(bl) if s.get("origin") == B.RAI]
    covered = {e for s in rai for e in s.get("evr_ids") or []}
    return [r for r in requirement_states(review, bl) if r["id"] not in covered]


# ---------------------------------------------------------------------------
# Progress across sprints
# ---------------------------------------------------------------------------


def metrics(bl: Dict[str, Any], review: Dict[str, Any], spr_id: str = "",
            result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The numbers recorded for a sprint when it closes (cumulative where it says so)."""
    rows = requirement_states(review, bl)
    stories = B.live(bl)
    result = result or {}
    return {
        "sprint": spr_id,
        "verified_requirements": sum(1 for r in rows if r["state"] == VERIFIED),
        "requirements": len(rows),
        "verified_criteria": sum(len(B.ethical_criteria(s)) for s in stories if s["status"] == B.VERIFIED),
        "stories_verified": len(result.get("verified") or []),
        "stories_done": len(result.get("done") or []),
        "carried_over": len(result.get("carried_over") or []),
        "open_rai_stories": sum(1 for s in stories if s.get("origin") == B.RAI and s["status"] != B.VERIFIED),
    }


def trend(series: Sequence[Dict[str, Any]]) -> Dict[str, str]:
    """Improving, flat or declining, from the last two sprints of the series.

    Read off requirements newly verified each sprint, then stories carried
    over. With fewer than two sprints there is nothing to compare.
    """
    if len(series) < 2:
        return {"direction": "first_sprint" if series else "none",
                "reason": "One sprint on record: the trend starts with the next." if series
                else "No sprint has closed yet."}
    def newly(i: int) -> int:
        prev = series[i - 1]["verified_requirements"] if i > 0 else 0
        return int(series[i]["verified_requirements"]) - int(prev)
    last, prev = newly(len(series) - 1), newly(len(series) - 2)
    c_last, c_prev = int(series[-1].get("carried_over") or 0), int(series[-2].get("carried_over") or 0)
    if last > prev or (last == prev and c_last < c_prev):
        direction = "improving"
    elif last < prev or (last == prev and c_last > c_prev):
        direction = "declining"
    else:
        direction = "flat"
    reason = (f"{last} requirement(s) newly verified against {prev} the sprint before; "
              f"{c_last} story(ies) carried over against {c_prev}.")
    return {"direction": direction, "reason": reason}


def history(sp: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The recorded metrics of every closed sprint, in order."""
    return [dict(x.get("snapshot") or {}, sprint=x["id"], name=x.get("name", x["id"]),
                 opinion=x.get("opinion", ""), trend=x.get("trend", ""))
            for x in B.closed_sprints(sp) if x.get("snapshot")]


def sprints_left(series: Sequence[Dict[str, Any]], open_rai: int) -> Optional[int]:
    """Sprints to verify the open RAI stories at the average pace so far — an estimate, labelled as one."""
    done = [int(x.get("stories_verified") or 0) for x in series]
    if not done or open_rai <= 0:
        return 0 if open_rai <= 0 else None
    pace = sum(done) / len(done)
    return math.ceil(open_rai / pace) if pace > 0 else None


def project_close(bl: Dict[str, Any], sp: Dict[str, Any], review: Dict[str, Any], spr_id: str,
                  verdicts: Dict[str, str]) -> Dict[str, Any]:
    """What closing ``spr_id`` with these verdicts would record: metrics and trend.

    Run on a copy, so the Auditor's report and the approval that closes the
    sprint compute the same numbers from the same rule.
    """
    bl2, sp2 = B.normalize_backlog(bl), B.normalize_sprints(sp)
    x = B.sprint(sp2, spr_id)
    if x is None:
        return {}
    if x["state"] != B.REVIEW:
        x["state"] = B.REVIEW
    record = {"extension": {"items": [{"item_id": k, "verdict": v} for k, v in verdicts.items()]}}
    result = B.apply_audit(bl2, sp2, spr_id, record, {})
    m = metrics(bl2, review, spr_id, result)
    m["name"] = x.get("name", spr_id)
    series = history(sp) + [m]
    return {"metrics": m, "series": series, "trend": trend(series), "result": result,
            "requirements": requirement_states(review, bl2)}


# ---------------------------------------------------------------------------
# What comes next: the rule-based sprint suggestion
# ---------------------------------------------------------------------------


def _blocked_refs(issues: Sequence[Dict[str, Any]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for i in issues or []:
        if i.get("status", "open") == "open" and i.get("blocking"):
            for link in i.get("links") or []:
                out.setdefault(str(link), str(i.get("id") or ""))
    return out


def suggest(bl: Dict[str, Any], sp: Dict[str, Any], review: Dict[str, Any],
            issues: Sequence[Dict[str, Any]] = (), capacity: Optional[int] = None,
            unit: str = "stories", exclude: Sequence[str] = ()) -> Dict[str, Any]:
    """Stories for the next sprint, each with its one-line reason. No model is called.

    Candidates are backlog stories whose dependencies are verified or already
    chosen. They are ranked: carried over from the last sprint; RAI stories
    closing a legal obligation gap; the highest computed priority among the
    findings linked to their requirements; then the longest waiting. Stories
    linked to a blocking open issue are listed as blocked, never suggested.
    """
    facts = requirement_facts(review)
    blocked_by = _blocked_refs(issues)
    capacity = capacity if capacity and capacity > 0 else DEFAULT_CAPACITY
    chosen_ids = set(exclude)
    verified = {s["id"] for s in bl.get("stories") or [] if s.get("status") in (B.VERIFIED,)}
    ranked: List[Tuple[Tuple, Dict[str, Any]]] = []
    blocked: List[Dict[str, Any]] = []
    for s in bl.get("stories") or []:
        if s.get("status") != B.BACKLOG or s["id"] in chosen_ids:
            continue
        refs = [s["id"], *(s.get("evr_ids") or [])]
        hit = next((r for r in refs if r in blocked_by), None)
        if hit:
            blocked.append({"id": s["id"], "reason": f"blocked by open issue {blocked_by[hit]} ({hit})"})
            continue
        legal = [e for e in s.get("evr_ids") or [] if facts.get(e, {}).get("legal")]
        prio = ""
        for e in s.get("evr_ids") or []:
            prio = _higher(prio, facts.get(e, {}).get("priority", ""))
        carried = int(s.get("carried_over") or 0)
        if carried:
            reason = f"carried over from the last sprint ({carried}x)"
        elif s.get("origin") == B.RAI and legal:
            reason = "closes a legal obligation gap (" + ", ".join(
                facts[e]["obligation"] or e for e in legal) + ")"
        elif prio:
            reason = f"{prio} priority requirement ({', '.join(s.get('evr_ids') or [])})"
        else:
            reason = "waiting longest in the backlog"
        key = (0 if carried else 1,
               0 if (s.get("origin") == B.RAI and legal) else 1,
               PRIORITY_ORDER.index(prio) if prio in PRIORITY_ORDER else 9,
               s.get("created_at") or "", s["id"])
        ranked.append((key, {"id": s["id"], "title": s.get("title") or s.get("description", "")[:80],
                             "origin": s.get("origin"), "reason": reason, "priority": prio,
                             "estimate": s.get("estimate"), "depends_on": list(s.get("depends_on") or [])}))
    ranked.sort(key=lambda kv: kv[0])
    picked: List[Dict[str, Any]] = []
    waiting: List[Dict[str, Any]] = []
    used = 0
    for _, cand in ranked:
        deps = [d for d in cand["depends_on"] if d not in verified and d not in chosen_ids]
        if deps:
            waiting.append({"id": cand["id"], "reason": "waits for " + ", ".join(deps)})
            continue
        cost = (cand["estimate"] or 1) if unit == "points" else 1
        if used + cost > capacity:
            continue
        picked.append(cand)
        chosen_ids.add(cand["id"])
        used += cost
    return {"suggested": picked, "blocked": blocked, "waiting": waiting, "capacity": capacity,
            "unit": unit, "used": used}


def roadmap(bl: Dict[str, Any], sp: Dict[str, Any], review: Dict[str, Any]) -> Dict[str, Any]:
    """Everything the Roadmap view shows."""
    rows = requirement_states(review, bl)
    series = history(sp)
    open_rai = sum(1 for s in B.live(bl) if s.get("origin") == B.RAI and s["status"] != B.VERIFIED)
    return {
        "requirements": rows,
        "counts": state_counts(rows),
        "series": series,
        "trend": trend(series),
        "open_stories": sum(1 for s in B.live(bl) if s["status"] not in (B.VERIFIED,)
                            and not s.get("closed_in")),
        "open_rai": open_rai,
        "closed_sprints": len(B.closed_sprints(sp)),
        "sprints_left": sprints_left(series, open_rai),
    }
