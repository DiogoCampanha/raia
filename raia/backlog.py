"""
raia.backlog
============

The project's story backlog and its sprints: two registers on the blackboard.

Once the risk classification and the ethical requirements are approved, a RAIA
project runs as a loop of sprints over one backlog. Requirements are constants;
the work they generate is not done at once. So the backlog holds two kinds of
story, side by side and in one numbering scheme:

* **RAI stories** (``RAI-n``) are generated from the approved requirements by
  the User Story Refiner's generate mode. Each one links at least one
  requirement; that is checked in code.
* **Product stories** (``US-n``) come from ordinary product work. The Refiner's
  refine mode adds ethical acceptance criteria to them, or records in one line
  why a story needs none.

Both registers are written through the same commit path as every artifact —
Markdown for people, a JSON sidecar for code — so every change is a recorded
version, hash-chained on the database backend and part of the project download.
When an approval changes them (generated stories entering the backlog, a sprint
closing on its audit) they go into the same commit as the approved artifact.

Statuses, and who may set them::

    backlog       waiting to be scheduled          generation, refinement, carry-over
    in_sprint     selected into the open sprint    a person, on the board
    done          delivered, not yet verified      a person's tick, or a Jira sync
    verified      ethical criteria verified        an approved Auditor run, only
    needs_review  a linked requirement changed     requirements change control
    obsolete      its requirements were removed    change control proposes, a person confirms

Two rules are load-bearing and tested:

1. Only an approved audit sets ``verified``. A tick or a sync means delivered.
2. Nothing here needs Jira. Every status change has a manual path; a Jira
   sync is an optional extra and never overwrites a manual change.

Everything in this module is a pure function over plain dicts: no model, no
storage, no Streamlit. :class:`raia.projects.ProjectService` loads the
registers, calls these functions and commits the result.
"""

from __future__ import annotations

import copy
import datetime as _dt
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

BACKLOG = "backlog"
IN_SPRINT = "in_sprint"
DONE = "done"
VERIFIED = "verified"
NEEDS_REVIEW = "needs_review"
OBSOLETE = "obsolete"
STATUSES = (BACKLOG, IN_SPRINT, DONE, VERIFIED, NEEDS_REVIEW, OBSOLETE)
STATUS_LABELS = {
    BACKLOG: "Backlog", IN_SPRINT: "In sprint", DONE: "Done", VERIFIED: "Verified",
    NEEDS_REVIEW: "Needs review", OBSOLETE: "Obsolete",
}
#: Statuses a story can still move out of (everything but the end states).
LIVE = (BACKLOG, IN_SPRINT, DONE, VERIFIED, NEEDS_REVIEW)

RAI = "rai"
PRODUCT = "product"
ORIGIN_LABELS = {RAI: "RAI", PRODUCT: "Product"}

PLANNING = "planning"
ACTIVE = "active"
REVIEW = "review"
CLOSED = "closed"
SPRINT_STATES = (PLANNING, ACTIVE, REVIEW, CLOSED)
SPRINT_STATE_LABELS = {PLANNING: "Planning", ACTIVE: "Active", REVIEW: "Ended, awaiting audit",
                       CLOSED: "Closed"}

#: How many history lines a story keeps inline. The full trail is the version history.
HISTORY_KEEP = 30

_ID = re.compile(r"^(RAI|US)-(\d+)$")


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Empty registers and small accessors
# ---------------------------------------------------------------------------


def empty_backlog() -> Dict[str, Any]:
    return {"stories": [], "counters": {"RAI": 0, "US": 0}}


def empty_sprints() -> Dict[str, Any]:
    return {"sprints": [], "counter": 0, "settings": {}}


def normalize_backlog(state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    out = copy.deepcopy(state) if state else empty_backlog()
    out.setdefault("stories", [])
    out.setdefault("counters", {"RAI": 0, "US": 0})
    return out


def normalize_sprints(state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    out = copy.deepcopy(state) if state else empty_sprints()
    out.setdefault("sprints", [])
    out.setdefault("counter", 0)
    out.setdefault("settings", {})
    return out


def story(bl: Dict[str, Any], sid: str) -> Optional[Dict[str, Any]]:
    return next((s for s in bl.get("stories") or [] if s.get("id") == sid), None)


def require(bl: Dict[str, Any], sid: str) -> Dict[str, Any]:
    s = story(bl, sid)
    if s is None:
        raise ValueError(f"There is no story {sid} in the backlog.")
    return s


def sprint(sp: Dict[str, Any], spr_id: str) -> Optional[Dict[str, Any]]:
    return next((x for x in sp.get("sprints") or [] if x.get("id") == spr_id), None)


def open_sprint(sp: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The one sprint that is not closed (planning, active or awaiting its audit), if any."""
    return next((x for x in sp.get("sprints") or [] if x.get("state") != CLOSED), None)


def closed_sprints(sp: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [x for x in sp.get("sprints") or [] if x.get("state") == CLOSED]


def live(bl: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [s for s in bl.get("stories") or [] if s.get("status") != OBSOLETE]


def in_sprint(bl: Dict[str, Any], spr_id: str) -> List[Dict[str, Any]]:
    return [s for s in bl.get("stories") or [] if s.get("sprint") == spr_id and s.get("status") != OBSOLETE]


def ethical_criteria(s: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [c for c in s.get("criteria") or [] if c.get("kind") == "ethical"]


def _log(s: Dict[str, Any], by: str, what: str) -> None:
    s.setdefault("history", []).append({"at": _now(), "by": by, "what": what})
    s["history"] = s["history"][-HISTORY_KEEP:]
    s["updated_at"] = _now()


# ---------------------------------------------------------------------------
# Stories
# ---------------------------------------------------------------------------


def _allocate(bl: Dict[str, Any], prefix: str, hint: str = "") -> str:
    counters = bl.setdefault("counters", {"RAI": 0, "US": 0})
    m = _ID.match(str(hint or "").strip().upper())
    if m and m.group(1) == prefix and story(bl, m.group(0)) is None:
        counters[prefix] = max(int(counters.get(prefix, 0)), int(m.group(2)))
        return m.group(0)
    counters[prefix] = int(counters.get(prefix, 0)) + 1
    while story(bl, f"{prefix}-{counters[prefix]}") is not None:
        counters[prefix] += 1
    return f"{prefix}-{counters[prefix]}"


def _existing(lines: Iterable[str], sid: str) -> List[Dict[str, Any]]:
    return [{"id": f"{sid}-E{i}", "kind": "existing", "text": t}
            for i, t in enumerate((str(x).strip() for x in lines if str(x).strip()), 1)]


def add_story(bl: Dict[str, Any], *, origin: str, title: str, description: str = "",
              existing_criteria: Sequence[str] = (), evr_ids: Sequence[str] = (),
              touches: Sequence[str] = (), estimate: Optional[int] = None,
              depends_on: Sequence[str] = (), by: str = "", id_hint: str = "",
              status: str = BACKLOG, sprint_id: str = "", source: str = "") -> Dict[str, Any]:
    """Add one story and return it. RAI stories must link a requirement."""
    if origin not in (RAI, PRODUCT):
        raise ValueError("A story is either an RAI story or a product story.")
    title = (title or "").strip()
    description = (description or "").strip()
    if not (title or description):
        raise ValueError("A story needs a title or a description.")
    evr_ids = [e for e in dict.fromkeys(str(x).strip() for x in evr_ids) if e]
    if origin == RAI and not evr_ids:
        raise ValueError("An RAI story must link at least one requirement.")
    sid = _allocate(bl, "RAI" if origin == RAI else "US", id_hint)
    s = {
        "id": sid, "origin": origin, "title": title[:200], "description": description[:2000],
        "criteria": _existing(existing_criteria, sid), "evr_ids": evr_ids,
        "touches": [t for t in touches if t and t != "none"],
        "estimate": _points(estimate), "depends_on": [d for d in depends_on if d and d != sid],
        "no_impact_reason": "", "status": status, "sprint": sprint_id,
        "sprints": [sprint_id] if sprint_id else [], "carried_over": 0,
        "needs_review_reason": "", "obsolete_proposed": False,
        "created_at": _now(), "created_by": by, "updated_at": _now(),
        "source": source, "jira": {}, "done": {}, "verified_in": "", "last_verdict": "",
        "history": [],
    }
    _log(s, by, f"created ({ORIGIN_LABELS[origin]} story)" + (f" from {source}" if source else ""))
    bl.setdefault("stories", []).append(s)
    return s


def _points(value: Any) -> Optional[int]:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


EDITABLE = ("title", "description", "estimate", "depends_on", "touches")


def update_story(bl: Dict[str, Any], sid: str, changes: Dict[str, Any], by: str = "") -> Dict[str, Any]:
    """Change what a person may edit on the board: text, estimate, dependencies, what it touches.

    Criteria and requirement links change only through the Refiner's gate (or,
    for a team's own criteria, by adding the story again), so an audit can
    rely on them.
    """
    s = require(bl, sid)
    changed = []
    for key in EDITABLE:
        if key not in changes:
            continue
        value = changes[key]
        if key == "estimate":
            value = _points(value)
        elif key in ("depends_on", "touches"):
            value = [v for v in (value or []) if v and v != sid]
        else:
            value = str(value or "").strip()[:2000 if key == "description" else 200]
        if value != s.get(key):
            s[key] = value
            changed.append(key)
    if "title" in changed and not (s["title"] or s["description"]):
        raise ValueError("A story needs a title or a description.")
    if changed:
        _log(s, by, "edited " + ", ".join(changed))
        s["jira"]["dirty"] = bool(s.get("jira", {}).get("key"))
    return s


# ---------------------------------------------------------------------------
# Sprints
# ---------------------------------------------------------------------------


def create_sprint(sp: Dict[str, Any], *, name: str = "", goal: str = "", start: str = "", end: str = "",
                  capacity: Optional[int] = None, unit: str = "stories", by: str = "") -> Dict[str, Any]:
    if open_sprint(sp):
        raise ValueError("Close the open sprint (its audit closes it) before planning the next one.")
    sp["counter"] = int(sp.get("counter", 0)) + 1
    n = sp["counter"]
    unit = unit if unit in ("stories", "points") else "stories"
    x = {
        "id": f"SPR-{n}", "number": n, "name": (name or f"Sprint {n}").strip()[:80],
        "goal": (goal or "").strip()[:300], "start": start or "", "end": end or "",
        "capacity": _points(capacity) or (5 if unit == "stories" else None), "unit": unit,
        "state": PLANNING, "created_by": by, "created_at": _now(),
        "started_at": "", "ended_at": "", "closed_at": "", "closed_by": "",
        "audit_commit": "", "opinion": "", "trend": "", "snapshot": {},
    }
    sp.setdefault("sprints", []).append(x)
    return x


def update_sprint(sp: Dict[str, Any], spr_id: str, changes: Dict[str, Any]) -> Dict[str, Any]:
    x = sprint(sp, spr_id)
    if x is None or x.get("state") == CLOSED:
        raise ValueError("Only an open sprint can be edited.")
    for key in ("name", "goal", "start", "end"):
        if key in changes:
            x[key] = str(changes[key] or "").strip()[:300]
    if "capacity" in changes:
        x["capacity"] = _points(changes["capacity"])
    if changes.get("unit") in ("stories", "points"):
        x["unit"] = changes["unit"]
    return x


def schedule(bl: Dict[str, Any], sp: Dict[str, Any], sid: str, by: str = "") -> Dict[str, Any]:
    """Put a story into the open sprint."""
    x = open_sprint(sp)
    if x is None or x["state"] not in (PLANNING, ACTIVE):
        raise ValueError("Plan a sprint first: stories go into a sprint that is planning or active.")
    s = require(bl, sid)
    if s["status"] not in (BACKLOG, NEEDS_REVIEW):
        raise ValueError(f"{sid} is {STATUS_LABELS.get(s['status'], s['status']).lower()}; only a backlog "
                         "story can be scheduled.")
    if s["status"] == NEEDS_REVIEW:
        raise ValueError(f"{sid} needs review first: a requirement it implements changed.")
    s["status"] = IN_SPRINT
    s["sprint"] = x["id"]
    if x["id"] not in s.setdefault("sprints", []):
        s["sprints"].append(x["id"])
    _log(s, by, f"scheduled into {x['id']}")
    return s


def unschedule(bl: Dict[str, Any], sp: Dict[str, Any], sid: str, by: str = "") -> Dict[str, Any]:
    s = require(bl, sid)
    x = open_sprint(sp)
    if not x or s.get("sprint") != x["id"] or s["status"] not in (IN_SPRINT, DONE):
        raise ValueError(f"{sid} is not in the open sprint.")
    s["status"] = BACKLOG
    s["sprint"] = ""
    if x["id"] in s.get("sprints", []) and x["state"] == PLANNING:
        s["sprints"].remove(x["id"])
    s["done"] = {}
    _log(s, by, f"taken out of {x['id']}")
    return s


def start_sprint(sp: Dict[str, Any], bl: Dict[str, Any], by: str = "") -> Dict[str, Any]:
    x = open_sprint(sp)
    if not x or x["state"] != PLANNING:
        raise ValueError("There is no sprint in planning to start.")
    if not in_sprint(bl, x["id"]):
        raise ValueError("Add at least one story before starting the sprint.")
    x["state"] = ACTIVE
    x["started_at"] = _now()
    x["started_by"] = by
    return x


def end_sprint(sp: Dict[str, Any], by: str = "") -> Dict[str, Any]:
    """The work stops; the audit that follows closes the sprint."""
    x = open_sprint(sp)
    if not x or x["state"] != ACTIVE:
        raise ValueError("There is no active sprint to end.")
    x["state"] = REVIEW
    x["ended_at"] = _now()
    x["ended_by"] = by
    return x


def reopen_sprint(sp: Dict[str, Any], by: str = "") -> Dict[str, Any]:
    x = open_sprint(sp)
    if not x or x["state"] != REVIEW:
        raise ValueError("Only a sprint awaiting its audit can be reopened.")
    x["state"] = ACTIVE
    x["ended_at"] = ""
    return x


def tick(bl: Dict[str, Any], sp: Dict[str, Any], sid: str, done: bool, by: str = "",
         source: str = "manual") -> Dict[str, Any]:
    """Mark a sprint story delivered (or not). Never sets ``verified``.

    ``source`` is ``manual`` for a person's tick and ``jira`` for a sync, and
    it is kept: a sync never undoes a manual change (see :func:`sync_status`).
    """
    s = require(bl, sid)
    x = open_sprint(sp)
    if not x or x["state"] not in (ACTIVE, REVIEW) or s.get("sprint") != x["id"]:
        raise ValueError(f"{sid} is not in an active sprint, so it cannot be ticked.")
    if done and s["status"] == IN_SPRINT:
        s["status"] = DONE
        s["done"] = {"at": _now(), "by": by, "source": source}
        _log(s, by, "marked done" + (" (from Jira)" if source == "jira" else ""))
    elif not done and s["status"] == DONE:
        s["status"] = IN_SPRINT
        s["done"] = {"undone_at": _now(), "by": by, "source": source}
        _log(s, by, "marked not done" + (" (from Jira)" if source == "jira" else ""))
    return s


# ---------------------------------------------------------------------------
# Approvals that write to the backlog
# ---------------------------------------------------------------------------


def _rename_ac(cid: str, old: str, new: str) -> str:
    return re.sub(rf"^AC-{re.escape(old)}-", f"AC-{new}-", str(cid or ""))


def _ethical(c: Dict[str, Any], old: str, new: str) -> Dict[str, Any]:
    return {"id": _rename_ac(c.get("id"), old, new), "kind": "ethical",
            "text": str(c.get("condition") or ""), "evr_ids": [str(e) for e in c.get("evr_ids") or []],
            "evidence_artifact": str(c.get("evidence_artifact") or ""),
            "owner_role": str(c.get("owner_role") or ""), "ms_goal": str(c.get("ms_goal") or ""),
            "stakeholder_group": str(c.get("stakeholder_group") or ""), "record_id": str(c.get("id") or "")}


def apply_generation(bl: Dict[str, Any], record: Dict[str, Any], by: str = "",
                     source: str = "") -> Dict[str, str]:
    """Approved generated stories enter the backlog as ``RAI-n``. Returns record id -> backlog id."""
    mapping: Dict[str, str] = {}
    for g in (record.get("extension") or {}).get("stories") or []:
        tmp = str(g.get("story_id") or "")
        evrs = [str(e) for e in g.get("evr_ids") or [] if str(e).strip()]
        if not evrs:
            continue  # a check fails the draft first; never enter an unlinked RAI story
        s = add_story(bl, origin=RAI, title=str(g.get("title") or ""), description=str(g.get("description") or ""),
                      evr_ids=evrs, touches=g.get("touches") or [], by=by, source=source or "generated")
        s["criteria"] = [_ethical(c, tmp, s["id"]) for c in g.get("criteria") or []]
        s["eccola_cards"] = [str(c) for c in g.get("eccola_cards") or []]
        s["record_id"] = tmp
        mapping[tmp] = s["id"]
    return mapping


def apply_refinement(bl: Dict[str, Any], sp: Dict[str, Any], record: Dict[str, Any],
                     given: Sequence[Dict[str, Any]], by: str = "", source: str = "") -> Dict[str, str]:
    """Approved refinement writes criteria and requirement links back to the backlog.

    Stories already in the backlog keep their id; a story typed in on the spot
    becomes ``US-n`` (in the open sprint when there is one). Existing criteria
    are the team's and are kept as written; new ethical criteria replace the
    story's earlier ethical criteria, which the refined version supersedes.
    Returns record id -> backlog id.
    """
    x = open_sprint(sp)
    target = x["id"] if x and x["state"] in (PLANNING, ACTIVE) else ""
    by_id = {str(g.get("id")): g for g in given or []}
    mapping: Dict[str, str] = {}
    for entry in (record.get("extension") or {}).get("stories") or []:
        rid = str(entry.get("story_id") or "")
        src = by_id.get(rid) or {}
        s = story(bl, rid)
        if s is None:
            s = add_story(bl, origin=PRODUCT, title=str(src.get("title") or ""),
                          description=str(src.get("description") or src.get("text") or rid),
                          existing_criteria=[c.get("text", "") for c in src.get("criteria") or []],
                          touches=src.get("capabilities") or [], by=by, id_hint=rid,
                          status=IN_SPRINT if target else BACKLOG, sprint_id=target,
                          source=source or "refined")
        new = [_ethical(c, rid, s["id"]) for c in entry.get("criteria") or []]
        keep = [c for c in s.get("criteria") or [] if c.get("kind") != "ethical"]
        s["criteria"] = keep + new
        links = [str(e) for e in entry.get("evr_ids") or []] + [e for c in new for e in c["evr_ids"]]
        if s["origin"] == PRODUCT:
            s["evr_ids"] = list(dict.fromkeys(links))
        else:
            s["evr_ids"] = list(dict.fromkeys(list(s.get("evr_ids") or []) + links))
        s["no_impact_reason"] = str(entry.get("no_impact_reason") or "").strip() if not new else ""
        s["eccola_cards"] = [str(c) for c in entry.get("eccola_cards") or []]
        s["jira"] = {**(s.get("jira") or {}), "dirty": bool((s.get("jira") or {}).get("key"))}
        _log(s, by, f"refined ({len(new)} ethical criteria)" if new else "refined (no ethical impact)")
        mapping[rid] = s["id"]
    return mapping


def apply_audit(bl: Dict[str, Any], sp: Dict[str, Any], spr_id: str, record: Dict[str, Any],
                data: Dict[str, Any], by: str = "", commit: str = "") -> Dict[str, Any]:
    """An approved sprint-close audit sets verified, carries the rest over and closes the sprint.

    A story is verified when it was delivered and every one of its ethical
    criteria ends the audit ``satisfied``. A story with no ethical criteria that
    was delivered simply leaves the sprint as done. Everything else goes back to
    the backlog as carried over, keeping the sprints it passed through.
    """
    x = sprint(sp, spr_id)
    if x is None or x["state"] != REVIEW:
        raise ValueError(f"{spr_id} is not awaiting its audit.")
    verdicts = {str(i.get("item_id")): i.get("verdict") for i in (record.get("extension") or {}).get("items") or []}
    verified, done_only, carried = [], [], []
    for s in in_sprint(bl, spr_id):
        crit = [c["id"] for c in ethical_criteria(s)]
        delivered = s["status"] == DONE
        ok = delivered and crit and all(verdicts.get(c) == "satisfied" for c in crit)
        worst = next((verdicts.get(c) for c in crit if verdicts.get(c) in ("not_verified", "at_risk")), "")
        s["last_verdict"] = "satisfied" if ok else (worst or ("" if not crit else "partially_satisfied"))
        if ok:
            s["status"] = VERIFIED
            s["verified_in"] = spr_id
            s["verified_at"] = _now()
            verified.append(s["id"])
            _log(s, by, f"verified by the {spr_id} audit")
        elif delivered and not crit:
            done_only.append(s["id"])
            s["closed_in"] = spr_id
            _log(s, by, f"done in {spr_id} (no ethical criteria to verify)")
        else:
            s["status"] = BACKLOG
            s["carried_over"] = int(s.get("carried_over") or 0) + 1
            carried.append(s["id"])
            _log(s, by, f"carried over from {spr_id}")
        s["sprint"] = ""
    x["state"] = CLOSED
    x["closed_at"] = _now()
    x["closed_by"] = by
    x["audit_commit"] = commit
    x["opinion"] = ((record.get("extension") or {}).get("opinion") or {}).get("rating", "")
    x["trend"] = ((data.get("progress") or {}).get("trend") or {}).get("direction", "")
    x["result"] = {"verified": verified, "done": done_only, "carried_over": carried}
    return x["result"]


# ---------------------------------------------------------------------------
# Requirements change control
# ---------------------------------------------------------------------------


def _wording(e: Dict[str, Any]) -> str:
    return " ".join(f"{e.get('statement', '')} {e.get('fit_criterion', '')}".split()).lower()


def compare_requirements(old: Sequence[Dict[str, Any]], new: Sequence[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Added, changed and removed requirement ids between two approved versions."""
    before = {str(e.get("id")): _wording(e) for e in old or [] if e.get("id")}
    after = {str(e.get("id")): _wording(e) for e in new or [] if e.get("id")}
    return {
        "added": [k for k in after if k not in before],
        "changed": [k for k in after if k in before and after[k] != before[k]],
        "removed": [k for k in before if k not in after],
    }


def change_control(bl: Dict[str, Any], diff: Dict[str, List[str]], by: str = "") -> Dict[str, List[str]]:
    """Flag only the stories a requirement change touches. Returns what was flagged.

    A changed requirement flags its linked stories for review. A removed one
    is unlinked; a story left with no requirement at all is proposed obsolete
    (an RAI story) and a person confirms. Added requirements need nothing here:
    the roadmap shows them as having no story yet.
    """
    changed, removed = set(diff.get("changed") or []), set(diff.get("removed") or [])
    flagged, proposed = [], []
    for s in live(bl):
        links = set(s.get("evr_ids") or [])
        hit_changed = sorted(links & changed)
        hit_removed = sorted(links & removed)
        if not (hit_changed or hit_removed):
            continue
        reasons = []
        if hit_changed:
            reasons.append("changed: " + ", ".join(hit_changed))
        if hit_removed:
            s["evr_ids"] = [e for e in s["evr_ids"] if e not in removed]
            reasons.append("removed: " + ", ".join(hit_removed))
            if s["origin"] == RAI and not s["evr_ids"]:
                s["obsolete_proposed"] = True
                proposed.append(s["id"])
        s["needs_review_reason"] = "Requirement " + "; ".join(reasons)
        s["review_from"] = s["status"] if s["status"] != NEEDS_REVIEW else s.get("review_from", BACKLOG)
        if s["status"] in (BACKLOG, VERIFIED, NEEDS_REVIEW):
            s["status"] = NEEDS_REVIEW
        # A story in the running sprint keeps running; the flag is shown on the board.
        flagged.append(s["id"])
        _log(s, by, s["needs_review_reason"])
    return {"flagged": flagged, "proposed_obsolete": proposed}


def resolve_review(bl: Dict[str, Any], sid: str, decision: str, by: str = "") -> Dict[str, Any]:
    """A person settles a flag: ``keep`` (back to where it was) or ``obsolete``."""
    s = require(bl, sid)
    if decision not in ("keep", "obsolete"):
        raise ValueError("Keep the story, or mark it obsolete.")
    if not s.get("needs_review_reason") and s["status"] != NEEDS_REVIEW:
        raise ValueError(f"{sid} is not flagged for review.")
    if decision == "obsolete":
        s["status"] = OBSOLETE
        s["sprint"] = ""
        _log(s, by, "confirmed obsolete")
    else:
        if s["origin"] == RAI and not s.get("evr_ids"):
            raise ValueError("An RAI story must link at least one requirement; mark it obsolete instead.")
        back = s.get("review_from") or BACKLOG
        if s["status"] == NEEDS_REVIEW:
            # A verified story whose requirement changed goes back to the backlog:
            # its verification was of the old wording.
            s["status"] = BACKLOG if back in (VERIFIED, NEEDS_REVIEW) else back
        _log(s, by, "reviewed and kept")
    s["needs_review_reason"] = ""
    s["obsolete_proposed"] = False
    return s


# ---------------------------------------------------------------------------
# Markdown views of the registers
# ---------------------------------------------------------------------------


def _cell(v: Any) -> str:
    if v in (None, "", []):
        return "—"
    if isinstance(v, (list, tuple)):
        return ", ".join(str(x) for x in v) or "—"
    return str(v).replace("|", "\\|").replace("\n", " ").strip()


def render_backlog(bl: Dict[str, Any]) -> str:
    stories = bl.get("stories") or []
    lines = [
        "<!--  RAIA register: backlog | maintained by code from approvals and board actions  -->",
        "",
        "# Backlog",
        "",
        "RAI stories come from the approved ethical requirements; product stories from product work. "
        "Only an approved audit marks a story verified.",
        "",
    ]
    for status in STATUSES:
        group = [s for s in stories if s.get("status") == status]
        if not group:
            continue
        lines += [f"## {STATUS_LABELS[status]} ({len(group)})", "",
                  "| Story | Origin | Title | Requirements | Sprint | Ethical criteria | Jira |",
                  "|---|---|---|---|---|---|---|"]
        for s in group:
            lines.append("| " + " | ".join(_cell(v) for v in (
                s["id"], ORIGIN_LABELS.get(s.get("origin"), s.get("origin")), s.get("title") or s.get("description", "")[:80],
                s.get("evr_ids"), s.get("sprint") or s.get("verified_in"),
                [c["id"] for c in ethical_criteria(s)] or (s.get("no_impact_reason") and "no ethical impact"),
                (s.get("jira") or {}).get("key"))) + " |")
        lines.append("")
    if not stories:
        lines.append("_No stories yet._")
    return "\n".join(lines)


def render_sprints(sp: Dict[str, Any]) -> str:
    lines = [
        "<!--  RAIA register: sprints | maintained by code; a sprint closes only on an approved audit  -->",
        "",
        "# Sprints",
        "",
        "| Sprint | Name | State | Dates | Goal | Opinion | Trend |",
        "|---|---|---|---|---|---|---|",
    ]
    for x in sp.get("sprints") or []:
        dates = " to ".join(d for d in (x.get("start"), x.get("end")) if d)
        lines.append("| " + " | ".join(_cell(v) for v in (
            x["id"], x.get("name"), SPRINT_STATE_LABELS.get(x.get("state"), x.get("state")), dates,
            x.get("goal"), str(x.get("opinion") or "").replace("_", " "), x.get("trend"))) + " |")
    if not sp.get("sprints"):
        lines.append("| — | — | — | — | — | — | — |")
    return "\n".join(lines)


def register_files(repo: Any, bl: Optional[Dict[str, Any]] = None,
                   sp: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """The files to commit for the registers that changed."""
    files: Dict[str, str] = {}
    if bl is not None:
        files.update(repo.register_files("backlog", bl, render_backlog(bl)))
    if sp is not None:
        files.update(repo.register_files("sprints", sp, render_sprints(sp)))
    return files


def load(repo: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    return normalize_backlog(repo.read_register("backlog")), normalize_sprints(repo.read_register("sprints"))
