"""
raia.contract.review
====================

A reviewer's decision on each card of a draft, and what it does to the record.

At the approval gate every reviewable card — a risk (finding), an action, an
ethical value requirement, a new acceptance criterion, an audit observation —
can be accepted or rejected, and a rejection carries a reason. Decisions
("Decisions for a person") are taken, not accepted or rejected: they are kept
beside the card reviews and reach the Open Issues register on approval.

What a rejection does depends on where the card came from:

* **written by the model** (findings, actions, criteria) — the card leaves the
  record's active lists and is kept in the record's ``review.rejected`` block
  with the reason, the reviewer and the time;
* **computed by a rule engine** (an ethical value requirement exists because
  the coverage matrix found a gap) — the card stays in the record, marked as
  overridden by that person with that reason, and the override is recorded in
  the register as a resolved decision. A computed fact is never deleted, and a
  disagreement with code is recorded, not averaged away.

Cards nobody marked are accepted as they are when the draft is approved.

Nothing here touches storage: the gate keeps the state in the pending draft,
and the pipeline applies it only when a person approves.
"""

from __future__ import annotations

import copy
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

ACCEPTED = "accepted"
REJECTED = "rejected"

FINDING = "finding"
ACTION = "action"
EVR = "evr"
CRITERION = "criterion"

KIND_LABELS = {FINDING: "risk", ACTION: "action", EVR: "requirement", CRITERION: "acceptance criterion"}

#: Where each kind of card comes from: written by the model, or computed.
ORIGIN = {FINDING: "model", ACTION: "model", EVR: "engine", CRITERION: "model"}

#: Structured reasons a card can be rejected for (a reason in words is also required).
CARD_REASONS: List[Tuple[str, str]] = [
    ("wrong", "Wrong for this product"),
    ("duplicate", "Repeats another card"),
    ("unsupported", "Not supported by the evidence"),
    ("not_actionable", "Too vague to act on"),
    ("out_of_scope", "Out of scope for this stage"),
    ("other", "Something else"),
]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def empty() -> Dict[str, Any]:
    return {"cards": {}, "decisions": {}}


def issue_key(issue: Dict[str, Any]) -> str:
    """A decision's stable name: its wording, normalised (ids are renumbered, wording is not)."""
    text = unicodedata.normalize("NFKC", str(issue.get("description") or issue.get("text") or ""))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()[:160]


# ---------------------------------------------------------------------------
# Which cards a record has
# ---------------------------------------------------------------------------


def cards(agent_key: str, record: Dict[str, Any]) -> List[Dict[str, str]]:
    """Every reviewable card in a record: ``{id, kind, origin, title}``, in reading order."""
    out: List[Dict[str, str]] = []
    for f in (record or {}).get("findings") or []:
        out.append({"id": str(f.get("id", "")), "kind": FINDING, "origin": ORIGIN[FINDING],
                    "title": str(f.get("title") or "")})
    for a in (record or {}).get("actions") or []:
        out.append({"id": str(a.get("id", "")), "kind": ACTION, "origin": ORIGIN[ACTION],
                    "title": str(a.get("action") or "")})
    ext = (record or {}).get("extension") or {}
    if agent_key == "requirements_reviewer":
        for e in ext.get("evrs") or []:
            out.append({"id": str(e.get("id", "")), "kind": EVR, "origin": ORIGIN[EVR],
                        "title": str(e.get("statement") or "")})
    if agent_key in ("story_refiner", "story_generate"):
        for s in ext.get("stories") or []:
            for c in s.get("criteria") or []:
                out.append({"id": str(c.get("id", "")), "kind": CRITERION, "origin": ORIGIN[CRITERION],
                            "title": str(c.get("condition") or c.get("text") or "")})
    return [c for c in out if c["id"]]


def tally(agent_key: str, record: Dict[str, Any], review: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Counts for the approval button: accepted, rejected, left as they are, reasons missing."""
    state = (review or {}).get("cards") or {}
    ids = [c["id"] for c in cards(agent_key, record)]
    accepted = [i for i in ids if (state.get(i) or {}).get("verdict") == ACCEPTED]
    rejected = [i for i in ids if (state.get(i) or {}).get("verdict") == REJECTED]
    missing = [i for i in rejected if not str((state.get(i) or {}).get("reason") or "").strip()]
    return {"total": len(ids), "accepted": len(accepted), "rejected": len(rejected),
            "unmarked": len(ids) - len(accepted) - len(rejected), "missing_reason": missing}


# ---------------------------------------------------------------------------
# Applying the review
# ---------------------------------------------------------------------------


def apply(agent_key: str, record: Dict[str, Any], review: Optional[Dict[str, Any]],
          by: str = "") -> Dict[str, Any]:
    """The record as it will be approved: rejected model cards out, computed ones overridden.

    Idempotent: applying the same review twice gives the same record. The
    ``review`` block it writes keeps every explicit verdict, so the approved
    record says what a person accepted, rejected and overrode, and why.
    """
    rec = copy.deepcopy(record or {})
    state = (review or {}).get("cards") or {}
    known = {c["id"]: c for c in cards(agent_key, record)}
    prior = rec.get("review") or {}
    block: Dict[str, List[Dict[str, Any]]] = {
        "accepted": [], "rejected": list(prior.get("rejected") or []), "overridden": list(prior.get("overridden") or [])}
    done = {x["id"] for x in block["rejected"] + block["overridden"]}

    def entry(cid: str, s: Dict[str, Any]) -> Dict[str, Any]:
        c = known[cid]
        return {"id": cid, "kind": c["kind"], "origin": c["origin"], "title": c["title"][:200],
                "reason_code": s.get("reason_code") or "other", "reason": str(s.get("reason") or "").strip()[:500],
                "by": s.get("by") or by, "at": s.get("at") or _now()}

    reject: Set[str] = set()
    for cid, s in state.items():
        if cid not in known:
            continue
        if s.get("verdict") == ACCEPTED:
            block["accepted"].append({"id": cid, "kind": known[cid]["kind"], "by": s.get("by") or by,
                                      "at": s.get("at") or _now()})
        elif s.get("verdict") == REJECTED:
            reject.add(cid)
            if cid in done:
                continue
            if known[cid]["origin"] == "engine":
                block["overridden"].append(entry(cid, s))
            else:
                block["rejected"].append(entry(cid, s))

    model_out = {cid for cid in reject if known[cid]["origin"] != "engine"}
    rec["findings"] = [f for f in rec.get("findings") or [] if str(f.get("id")) not in model_out]
    rec["actions"] = [a for a in rec.get("actions") or [] if str(a.get("id")) not in model_out]
    gone = {str(f) for f in model_out}
    for a in rec["actions"]:
        a["finding_ids"] = [x for x in a.get("finding_ids") or [] if str(x) not in gone]
    for i in rec.get("open_issues") or []:
        i["links"] = [x for x in i.get("links") or [] if str(x) not in gone]
    ext = rec.get("extension")
    if isinstance(ext, dict):
        for s in ext.get("stories") or []:
            if isinstance(s, dict) and s.get("criteria"):
                s["criteria"] = [c for c in s["criteria"] if str(c.get("id")) not in model_out]
        overridden = {x["id"]: x for x in block["overridden"]}
        for e in ext.get("evrs") or []:
            if isinstance(e, dict) and str(e.get("id")) in overridden:
                o = overridden[str(e.get("id"))]
                e["review"] = {"status": "overridden", "reason": o["reason"], "by": o["by"], "at": o["at"]}
    if any(block.values()):
        rec["review"] = block
    return rec


def excluded_ids(record: Dict[str, Any]) -> List[str]:
    """Ids a person rejected or overrode in an approved record."""
    r = (record or {}).get("review") or {}
    return [x["id"] for x in (r.get("rejected") or []) + (r.get("overridden") or [])]


def override_issues(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """One already-decided register entry per computed card a person overrode."""
    out = []
    for o in ((record or {}).get("review") or {}).get("overridden") or []:
        out.append({
            "type": "engine_disagreement",
            "description": f"A reviewer overrode {o['id']} ({o['kind']}): {o['reason'] or 'no reason given'}",
            "options": [], "decision_owner": "product", "blocking": False, "links": [o["id"]],
            "origin": "code",
            "decision": {"choice": f"Override {o['id']}", "rationale": o["reason"], "by": o["by"], "at": o["at"]},
        })
    return out


# ---------------------------------------------------------------------------
# Decisions and the status they change
# ---------------------------------------------------------------------------


def decided_keys(review: Optional[Dict[str, Any]], register: Sequence[Dict[str, Any]] = ()) -> Set[str]:
    """Decisions taken, by wording: in the draft's review, or settled in the register."""
    keys = {k for k, v in ((review or {}).get("decisions") or {}).items() if (v or {}).get("choice")}
    keys |= {issue_key(i) for i in register or [] if i.get("status") not in (None, "", "open")}
    return keys


def effective_status(record: Dict[str, Any], decided: Set[str]) -> Tuple[str, str]:
    """The status as it stands now, and what changed it.

    A record is blocked by blocking findings or blocking decisions. Once every
    blocking decision is taken, it is no longer blocked in its current form: the
    risks travel on as needing attention. A blocking risk with no decision to
    take stays blocked until the stage is revised.
    """
    status = (record or {}).get("overall_status") or "needs_attention"
    if status != "blocked":
        return status, ""
    issues = (record or {}).get("open_issues") or []
    blocking = [i for i in issues if i.get("blocking")]
    if not blocking:
        return status, ""
    if any(issue_key(i) not in decided for i in blocking):
        return status, ""
    ids = ", ".join(str(i.get("id", "")) for i in blocking)
    return "needs_attention", f"Was blocked in its current form; unblocked once {ids} {'was' if len(blocking) == 1 else 'were'} decided."
