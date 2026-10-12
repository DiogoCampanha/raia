"""
raia.handoff
============

What each stage receives from the stages before it, what it did with each
item, and what is still open — computed from the blackboard, never inferred.

Agents never call each other: each reads the approved artifacts of earlier
stages. That flow was always there, but invisible on screen, so a person could
not see that the Requirements Reviewer answered the Risk Classifier's
obligations, or which requirements the stories implement. This module makes the
thread explicit, on identifiers code already assigns and keeps across stages
(never on per-record ids such as ``RC-F1``, which are renumbered on every run):

====================  =========================  ==================  ========================
From                  Item handed on             Stable id           Addressed when
====================  =========================  ==================  ========================
Risk Classifier       legal obligation           ``eu.art9`` …       covered by a requirement,
                                                                     a control, or a new EVR
Requirements Reviewer ethical value requirement  ``EVR-n``           a story implements it, or
                                                                     a criterion cites it
User Story Refiner    requirement in the backlog ``EVR-n``           audited: verified or not
any stage             open decision              register entry      decided, accepted, resolved
any stage             card a person excluded     the card id         shown as excluded
====================  =========================  ==================  ========================

Nothing here calls a model or writes anything. The same functions feed the stage
page (before the run), the draft (a hand-off strip), the next-step card and the
project's Traceability tab.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

ADDRESSED = "addressed"
PARTIAL = "partial"
OPEN = "open"
EXCLUDED = "excluded"

STATUS_LABELS = {ADDRESSED: "addressed", PARTIAL: "partly addressed", OPEN: "still open", EXCLUDED: "excluded by a person"}

_COVERED = ("control in place", "addressed by a requirement", "addressed by an adopted suggestion")


def _data(repo, key: str) -> Dict[str, Any]:
    payload = repo.read_data(key) or {}
    return payload.get("structured", payload) or {}


def _record(repo, key: str) -> Dict[str, Any]:
    return _data(repo, key).get("record") or {}


def _approval(repo, key: str) -> Dict[str, str]:
    prov = (repo.read_data(key) or {}).get("provenance") or {}
    a = prov.get("approval") or {}
    return {"by": str(a.get("approved_by") or ""), "at": str(a.get("approved_at") or "")[:10]}


def _backlog(repo) -> List[Dict[str, Any]]:
    from . import backlog as B

    try:
        bl, _ = B.load(repo)
    except Exception:  # noqa: BLE001 - a project without a board yet
        return []
    return list(bl.get("stories") or [])


def _excluded(record: Dict[str, Any]) -> List[str]:
    r = (record or {}).get("review") or {}
    return [x["id"] for x in (r.get("rejected") or []) + (r.get("overridden") or []) if x.get("id")]


def _norm(text: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()


# ---------------------------------------------------------------------------
# What a stage receives
# ---------------------------------------------------------------------------


def _upstream_artifacts(agent_key: str) -> List[str]:
    from .agents import RUNNABLE

    agent = RUNNABLE.get(agent_key)
    return [k for k in (agent.spec.upstream_keys if agent else []) if k not in ("backlog", "sprints", "product_brief")]


def open_decisions(repo, agent_key: str) -> List[Dict[str, Any]]:
    """Register entries raised by earlier stages and not yet decided, blocking first."""
    upstream = set(_upstream_artifacts(agent_key))
    issues = [i for i in repo.open_issues() if i.get("status") == "open" and i.get("artifact") in upstream]
    return sorted(issues, key=lambda i: not i.get("blocking"))


def inherited(repo, agent_key: str, draft: Optional[Dict[str, Any]] = None,
              computed: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The items this stage receives, each with what this stage (or its draft) does with it.

    Without ``draft`` it describes what is about to be handed on (before a run);
    with the draft record and its computed data it says what the draft did.
    """
    from .agents import RUNNABLE, identity_key

    computed = computed or {}
    base = identity_key(agent_key)
    items: List[Dict[str, Any]] = []
    sources: List[Dict[str, str]] = []
    names = {a.spec.output_key: a.spec.name for a in RUNNABLE.values()}

    if base == "requirements_reviewer":
        rc = _data(repo, "risk_classification")
        if rc:
            sources.append({"name": names.get("risk_classification", "Risk Classifier"),
                            **_approval(repo, "risk_classification")})
            coverage = computed.get("obligation_coverage") or {}
            gaps = {str(g.get("ref")): g.get("evr_id") for g in computed.get("gaps") or []}
            rejected = set(_excluded(draft or {}))
            for o in rc.get("obligations") or []:
                code = str(o.get("code", ""))
                item = {"id": code, "kind": "obligation", "label": str(o.get("title") or code), "status": OPEN,
                        "by": ""}
                if draft is not None:
                    if coverage.get(code) in _COVERED:
                        item.update(status=ADDRESSED, by=coverage[code])
                    elif gaps.get(code):
                        evr = gaps[code]
                        item.update(status=OPEN if evr in rejected else ADDRESSED,
                                    by=f"new requirement {evr}" + (" (overridden)" if evr in rejected else ""))
                items.append(item)
            principles = sorted({str(f.get("principle")) for f in (rc.get("record") or {}).get("findings") or []
                                 if f.get("principle")})
            from .contract import vocab as V

            for p in principles:
                name = V.PRINCIPLE_NAMES.get(p, p.replace("_", " "))
                item = {"id": p, "kind": "principle", "label": name, "status": OPEN, "by": ""}
                if draft is not None:
                    evrs = [str(e.get("id")) for e in (draft.get("extension") or {}).get("evrs") or []
                            if e.get("value") == p and str(e.get("id")) not in rejected]
                    covered = computed.get("principle_coverage") or {}
                    if gaps.get(p) and gaps[p] not in rejected:
                        item.update(status=ADDRESSED, by=f"new requirement {gaps[p]}")
                    elif evrs:
                        item.update(status=ADDRESSED, by="requirements " + ", ".join(evrs))
                    elif str(covered.get(name, "")).startswith("addressed"):
                        item.update(status=ADDRESSED, by="your requirements")
                items.append(item)

    elif base in ("story_refiner", "auditor"):
        rr = _data(repo, "requirements_review")
        if rr:
            sources.append({"name": names.get("requirements_review", "Requirements Reviewer"),
                            **_approval(repo, "requirements_review")})
            backlog = _backlog(repo)
            in_backlog: Dict[str, List[str]] = {}
            for s in backlog:
                if s.get("status") in ("obsolete",):
                    continue
                for e in s.get("evr_ids") or []:
                    in_backlog.setdefault(str(e), []).append(str(s.get("id")))
            drafted: Dict[str, List[str]] = {}
            verdicts: Dict[str, str] = {}
            if draft is not None:
                for s in (draft.get("extension") or {}).get("stories") or []:
                    for e in list(s.get("evr_ids") or []) + [x for c in s.get("criteria") or [] for x in c.get("evr_ids") or []]:
                        drafted.setdefault(str(e), []).append(str(s.get("story_id")))
                for it in (draft.get("extension") or {}).get("items") or []:
                    verdicts[str(it.get("item_id"))] = str(it.get("verdict") or "")
            for e in rr.get("evrs") or []:
                eid = str(e.get("id"))
                item = {"id": eid, "kind": "requirement", "label": str(e.get("statement") or eid), "status": OPEN,
                        "by": ""}
                if base == "auditor" and draft is not None:
                    v = verdicts.get(eid, "")
                    item.update(status=ADDRESSED if v == "satisfied" else PARTIAL if v == "partially_satisfied" else OPEN,
                                by=v.replace("_", " ") if v else "not audited in this run")
                elif drafted.get(eid):
                    item.update(status=ADDRESSED, by="stories " + ", ".join(sorted(set(drafted[eid]))))
                elif in_backlog.get(eid):
                    item.update(status=ADDRESSED, by="backlog " + ", ".join(sorted(set(in_backlog[eid]))))
                items.append(item)
            for eid in rr.get("excluded_evrs") or []:
                items.append({"id": str(eid), "kind": "requirement", "label": "overridden at review",
                              "status": EXCLUDED, "by": ""})

    elif base == "risk_classifier":
        pass  # The first stage receives the product answers only.

    decisions = open_decisions(repo, agent_key)
    excluded = []
    for key in _upstream_artifacts(agent_key):
        rec = _record(repo, key)
        for x in ((rec.get("review") or {}).get("rejected") or []):
            excluded.append({"id": x["id"], "kind": x.get("kind", ""), "label": x.get("title", ""),
                             "reason": x.get("reason", ""), "from": names.get(key, key)})

    counts = {s: sum(1 for i in items if i["status"] == s) for s in (ADDRESSED, PARTIAL, OPEN, EXCLUDED)}
    return {"agent": agent_key, "sources": sources, "items": items, "counts": counts,
            "decisions": decisions, "excluded": excluded, "evaluated": draft is not None,
            "line": _line(items, decisions, sources, draft is not None)}


def _plural(n: int, one: str, many: str = "") -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def _line(items: Sequence[Dict[str, Any]], decisions: Sequence[Dict[str, Any]],
          sources: Sequence[Dict[str, str]], evaluated: bool) -> str:
    if not sources and not decisions:
        return ""
    kinds: Dict[str, int] = {}
    for i in items:
        kinds[i["kind"]] = kinds.get(i["kind"], 0) + 1
    received = ", ".join(_plural(n, k) for k, n in kinds.items())
    who = " and ".join(s["name"] for s in sources) or "earlier stages"
    out = f"From the {who}: {received or 'no structured items'}"
    if evaluated and items:
        a = sum(1 for i in items if i["status"] == ADDRESSED)
        p = sum(1 for i in items if i["status"] == PARTIAL)
        o = sum(1 for i in items if i["status"] == OPEN)
        out += f" — {a} addressed" + (f", {p} partly" if p else "") + (f", {o} still open" if o else "")
    blocking = sum(1 for d in decisions if d.get("blocking"))
    if decisions:
        out += f"; {_plural(len(decisions), 'open decision')}" + (f" ({blocking} blocking)" if blocking else "")
    return out + "."


# ---------------------------------------------------------------------------
# What changed since the last approved version of a stage
# ---------------------------------------------------------------------------


def _keys(agent_key: str, record: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, set]:
    from .agents import identity_key

    base = identity_key(agent_key)
    out: Dict[str, set] = {"risks": {_norm(f.get("title")) for f in record.get("findings") or [] if f.get("title")}}
    out["blocking"] = {_norm(i.get("description")) for i in record.get("open_issues") or [] if i.get("blocking")}
    if base == "requirements_reviewer":
        out["gaps"] = {str(g.get("ref")) for g in data.get("gaps") or []}
    if base == "auditor":
        out["verified"] = {str(i.get("item_id")) for i in (record.get("extension") or {}).get("items") or []
                           if i.get("verdict") == "satisfied"}
    return out


def delta(agent_key: str, previous: Dict[str, Any], prev_data: Dict[str, Any],
          current: Dict[str, Any], cur_data: Dict[str, Any]) -> Dict[str, Any]:
    """Improvements and regressions between two versions of one stage, in plain counts."""
    if not previous or not current:
        return {}
    a, b = _keys(agent_key, previous, prev_data), _keys(agent_key, current, cur_data)
    parts: List[str] = []
    better: List[str] = []
    worse: List[str] = []
    if "gaps" in a:
        closed, new = a["gaps"] - b["gaps"], b["gaps"] - a["gaps"]
        if closed:
            better.append(_plural(len(closed), "gap") + " closed")
        if new:
            worse.append(_plural(len(new), "new gap"))
    if "verified" in a:
        gained, lost = b["verified"] - a["verified"], a["verified"] - b["verified"]
        if gained:
            better.append(_plural(len(gained), "more item") + " verified")
        if lost:
            worse.append(_plural(len(lost), "item") + " no longer verified")
    gone, new = a["risks"] - b["risks"], b["risks"] - a["risks"]
    if gone:
        better.append(_plural(len(gone), "risk") + " no longer raised")
    if new:
        worse.append(_plural(len(new), "new risk"))
    unblocked, blocked = a["blocking"] - b["blocking"], b["blocking"] - a["blocking"]
    if unblocked:
        better.append(_plural(len(unblocked), "blocking issue") + " gone")
    if blocked:
        worse.append(_plural(len(blocked), "new blocking issue"))
    same = len(a["risks"] & b["risks"])
    parts = better + worse
    line = ("Since the approved version: " + ", ".join(parts) + (f"; {same} risk(s) unchanged" if same else "") + "."
            if parts else "Since the approved version: no change in risks, gaps or blocking issues.")
    return {"better": better, "worse": worse, "unchanged": same, "line": line}


# ---------------------------------------------------------------------------
# What a stage hands on
# ---------------------------------------------------------------------------


def hands_on(repo, agent_key: str) -> str:
    """One line for the next-step card: what travels to the next stage after this approval."""
    from .agents import identity_key

    base = identity_key(agent_key)
    issues = [i for i in repo.open_issues() if i.get("status") == "open"]
    mine = {"risk_classifier": "risk_classification", "requirements_reviewer": "requirements_review",
            "story_refiner": "refined_stories", "story_generate": "rai_backlog", "auditor": "audit_report"}.get(agent_key)
    open_here = [i for i in issues if i.get("artifact") == mine]
    bits: List[str] = []
    if base == "risk_classifier":
        rc = _data(repo, "risk_classification")
        bits.append(_plural(len(rc.get("obligations") or []), "legal obligation"))
    elif base == "requirements_reviewer":
        rr = _data(repo, "requirements_review")
        bits.append(_plural(len(rr.get("evrs") or []), "ethical requirement"))
    elif agent_key == "story_generate":
        bits.append("the new RAI stories in the backlog")
    elif base == "story_refiner":
        bits.append("the refined criteria on the backlog stories")
    if open_here:
        bits.append(_plural(len(open_here), "open decision"))
    return ("Travels to the next stage: " + " and ".join(bits) + ".") if bits else ""


# ---------------------------------------------------------------------------
# The whole thread, for the project page
# ---------------------------------------------------------------------------


def thread(repo, backlog: Optional[List[Dict[str, Any]]] = None,
           review: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """One row per legal obligation and per requirement: classification → requirement → story → audit.

    ``backlog`` and ``review`` may be passed by a page that has already read
    them, to save a round trip each on a hosted database.
    """
    rc = _data(repo, "risk_classification")
    rr = review if review is not None else _data(repo, "requirements_review")
    audit = _record(repo, "audit_report")
    backlog = backlog if backlog is not None else _backlog(repo)
    coverage = rr.get("obligation_coverage") or {}
    evr_of: Dict[str, str] = {str(g.get("ref")): str(g.get("evr_id")) for g in rr.get("gaps") or []}
    excluded = set(str(x) for x in rr.get("excluded_evrs") or [])
    stories_of: Dict[str, List[Dict[str, Any]]] = {}
    for s in backlog:
        for e in s.get("evr_ids") or []:
            stories_of.setdefault(str(e), []).append(s)
    verdict = {str(i.get("item_id")): str(i.get("verdict") or "")
               for i in (audit.get("extension") or {}).get("items") or []}
    statements = {str(e.get("id")): str(e.get("statement") or "") for e in rr.get("evrs") or []}

    rows: List[Dict[str, Any]] = []
    seen: set = set()
    for o in rc.get("obligations") or []:
        code = str(o.get("code", ""))
        evr = evr_of.get(code, "")
        rows.append(_row(code, str(o.get("title") or ""), coverage.get(code, "") if rr else "",
                         evr, evr in excluded, stories_of.get(evr, []), verdict.get(evr, ""), bool(rr)))
        seen.add(evr)
    for eid, text in statements.items():
        if eid not in seen:
            rows.append(_row("", text, "", eid, eid in excluded, stories_of.get(eid, []), verdict.get(eid, ""), True))
    return rows


def _row(code: str, label: str, coverage: str, evr: str, excluded: bool, stories: List[Dict[str, Any]],
         verdict: str, reviewed: bool) -> Dict[str, Any]:
    if not reviewed:
        req = "not reviewed yet"
    elif coverage in _COVERED:
        req = coverage
    elif evr:
        req = f"{evr} (overridden)" if excluded else evr
    else:
        req = "gap"
    story = ", ".join(f"{s.get('id')} ({str(s.get('status') or '').replace('_', ' ')})" for s in stories) or (
        "—" if not evr or excluded else "no story yet")
    audited = verdict.replace("_", " ") if verdict else ("—" if not stories else "not audited yet")
    gap = (reviewed and not coverage in _COVERED and (not evr or excluded)) or (evr and not excluded and not stories)
    return {"obligation": code, "label": label, "requirement": req, "stories": story, "audit": audited,
            "gap": bool(gap), "verified": verdict == "satisfied"}


# ---------------------------------------------------------------------------
# What the next agent is told
# ---------------------------------------------------------------------------


def prompt_note(repo, agent_key: str) -> str:
    """Decisions people took on earlier stages, and what they excluded, for the next prompt.

    Engines are unchanged: they still compute everything. The model is told what
    people already settled, so it builds on it instead of raising it again.
    """
    upstream = set(_upstream_artifacts(agent_key))
    if not upstream:
        return ""
    lines: List[str] = []
    for i in repo.open_issues():
        if i.get("artifact") not in upstream:
            continue
        if i.get("status") == "decided":
            lines.append(f"- DECIDED {i.get('id')}: {i.get('text')} -> {i.get('decision')}"
                         + (f" (because: {i.get('rationale')})" if i.get("rationale") else ""))
        elif i.get("status") in ("resolved", "accepted"):
            lines.append(f"- {str(i.get('status')).upper()} {i.get('id')}: {i.get('text')}")
        elif i.get("status") == "open":
            lines.append(f"- STILL OPEN {i.get('id')}{' (blocking)' if i.get('blocking') else ''}: {i.get('text')}")
    for key in sorted(upstream):
        for x in ((_record(repo, key).get("review") or {}).get("rejected") or []):
            lines.append(f"- EXCLUDED by a reviewer: {x.get('id')} ({x.get('kind')}) \"{x.get('title')}\""
                         + (f" because: {x.get('reason')}" if x.get("reason") else ""))
    if not lines:
        return ""
    return ("## Decided and excluded upstream (by people)\n"
            "Build on these. Do not raise a decided issue again, and do not reintroduce an excluded item; "
            "an issue still open may be referenced, not settled.\n" + "\n".join(lines[:40]))
