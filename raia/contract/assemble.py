"""
raia.contract.assemble
======================

From a model reply to a finished RAIA record.

1. **Parse** — the reply must contain one JSON object that validates against
   the agent's record schema. A reply that does not is sent back once with the
   validation errors (a bounded repair); if it still fails, a *fallback record*
   is produced that says so plainly, keeps the raw reply for the reviewer, and
   carries the rule engine's facts and open issues — the gate still shows
   something honest, and the checks report the failure.
2. **Finalise** — code does everything that must not vary between runs:
   assigns stable identifiers, computes risk level and priority
   (:mod:`raia.contract.rubric`), carries every rule-engine issue forward with
   its type and owner, opens an issue for every disagreement and every
   accepted risk, restores evidence discipline where the model overreached,
   and stamps the record with its schema version and grounding.

Nothing here calls a model, and nothing here persists anything.
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from pydantic import ValidationError

from .. import config
from ..rationale import traceability
from ..rationale.types import RationaleResult
from . import rubric
from . import vocab as V
from .schema import record_model

#: Identifier prefix per agent, so an id is unique across a project.
PREFIX: Dict[str, str] = {
    "risk_classifier": "RC",
    "requirements_reviewer": "RR",
    "story_refiner": "SR",
    "story_generate": "SG",
    "auditor": "AU",
}

#: What each agent's record is called, in the rendered document and exports.
RECORD_TYPES: Dict[str, str] = {
    "risk_classifier": "Risk classification record",
    "requirements_reviewer": "Requirements review record",
    "story_refiner": "Refined stories record",
    "story_generate": "RAI backlog record",
    "auditor": "Audit record",
}

FENCE_RE = re.compile(r"```(?:json|raia-record)?\s*\n(?P<body>\{.*?\})\s*```", re.S)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def extract_json(text: str) -> Dict[str, Any]:
    """Find the one JSON object in a reply (fenced, or bare)."""
    text = text or ""
    m = FENCE_RE.search(text)
    candidates = [m.group("body")] if m else []
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start:end + 1])
    last: Exception = ValueError("the reply contains no JSON object")
    for c in candidates:
        try:
            value = json.loads(c)
        except ValueError as exc:
            last = exc
            continue
        if isinstance(value, dict):
            return value
    raise ValueError(f"the reply is not a JSON object ({last})")


LENGTH_ERRORS = ("string_too_long", "too_long")


def shorten_text(text: str, limit: int) -> str:
    """Cut text to ``limit`` characters at a sentence end, or else a word end with an ellipsis."""
    text = str(text or "").strip()
    if len(text) <= limit:
        return text
    head = text[:limit]
    ends = [m.end() for m in re.finditer(r"[.!?](?=\s|$)", head)]
    if ends and ends[-1] >= limit * 0.5:
        return head[: ends[-1]].strip()
    cut = head[: max(1, limit - 1)]
    space = cut.rfind(" ")
    if space >= limit * 0.5:
        cut = cut[:space]
    return cut.rstrip(" ,;:—-") + "…"


def _shorten(raw: Any, errors: Sequence[Dict[str, Any]]) -> List[str]:
    """Bring every over-length value back within its limit, in place. Returns what was changed.

    A length limit is a readability rule. A reply whose only fault is a field a
    few characters over it carries a complete analysis, and throwing that away —
    or spending a repair round trip on it — costs the reviewer far more than a
    trimmed sentence. The trim is recorded and reported, never silent.
    """
    notes: List[str] = []
    for e in errors:
        if e.get("type") not in LENGTH_ERRORS:
            continue
        loc, limit = list(e.get("loc", ())), int((e.get("ctx") or {}).get("max_length") or 0)
        if not loc or limit <= 0:
            continue
        parent: Any = raw
        try:
            for part in loc[:-1]:
                parent = parent[part]
            value = parent[loc[-1]]
        except (KeyError, IndexError, TypeError):
            continue
        where = ".".join(str(p) for p in loc)
        if isinstance(value, str):
            parent[loc[-1]] = shorten_text(value, limit)
            notes.append(f"{where} was {len(value)} characters (limit {limit}); shortened by code.")
        elif isinstance(value, list):
            parent[loc[-1]] = value[:limit]
            notes.append(f"{where} had {len(value)} entries (limit {limit}); the first {limit} were kept.")
    return notes


def parse_record(agent_key: str, text: str) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Validate a reply against the agent's schema. Returns (record, errors).

    Values over a length limit are shortened by code (and reported in the
    record's ``shortened`` list) rather than failing the reply; every other
    error is returned for the bounded repair.
    """
    try:
        raw = extract_json(text)
    except ValueError as exc:
        return None, [str(exc)]
    shortened: List[str] = []
    for _ in range(4):
        try:
            model = record_model(agent_key).model_validate(raw)
        except ValidationError as exc:
            details = exc.errors()
            fixed = _shorten(raw, details)
            shortened += fixed
            if fixed:
                continue
            errors = []
            for e in details[:30]:
                loc = ".".join(str(p) for p in e.get("loc", ()))
                errors.append(f"{loc or '(root)'}: {e.get('msg', 'invalid')}")
            return None, errors
        record = model.model_dump()
        if shortened:
            record["shortened"] = shortened
        return record, []
    return None, ["the reply kept exceeding its length limits after shortening"]


TRUNCATED_REASONS = ("max_tokens", "length")


def was_truncated(finish_reason: Optional[str]) -> bool:
    return (finish_reason or "").lower() in TRUNCATED_REASONS


def compact_prompt(budget: int) -> str:
    """Asked for after a reply was cut off at the token limit.

    The cure is a shorter record, not a longer reply: a record a reviewer can
    read at the gate is the point, and the budget is finite on any provider.
    """
    return (
        f"Your previous reply was cut off at the token limit ({budget} tokens), so it could not "
        "be read as a record. Send the whole record again, complete and compact:\n"
        "- one or two sentences per free-text field, conclusion first, and one for each obligation note;\n"
        "- keep every required identifier and every required field, and drop nothing;\n"
        "- where several obligations are met by the same work, say so once and refer back to it;\n"
        "- no text outside the single ```json fence."
    )


def repair_prompt(errors: Sequence[str]) -> str:
    return (
        "Your reply did not validate against the RAIA record schema. Errors:\n"
        + "\n".join(f"- {e}" for e in errors)
        + "\n\nReturn the complete corrected record as ONE JSON object in a ```json fence, "
          "and nothing else. Keep every value that was valid."
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("—", "-").replace("–", "-").replace("−", "-")
    return re.sub(r"\s+", " ", text).strip().lower().rstrip(".")


def normalize_citation(tag: str) -> str:
    tag = (tag or "").strip()
    if not tag:
        return ""
    if not tag.startswith("["):
        tag = "[" + (tag if tag.lower().startswith("source") else "Source: " + tag) + "]"
    return tag


def authority_index(evidence: Iterable[Dict[str, Any]]) -> Dict[str, str]:
    return {_norm(e.get("citation", "")): e.get("authority", "") for e in evidence}


def _authorities(citations: Iterable[str], index: Dict[str, str]) -> List[str]:
    out = []
    for c in citations:
        a = index.get(_norm(c))
        if a:
            out.append(a)
        elif "authority: legal" in (c or "").lower():
            out.append("legal")
    return out


class _Pruner:
    """Removes citation tags that match no excerpt retrieved for the run.

    A tag that resolves to nothing is a fabricated ground. It is not shown to
    the reviewer as a warning: code takes it out of the record and records
    what it took, in ``pruned_citations`` (kept across re-finalisation) and in
    the contract notes that reach provenance and the research export. With no
    evidence to check against (a record finalised outside a run), nothing is
    removed.
    """

    def __init__(self, evidence: Sequence[Dict[str, Any]], already: Sequence[str]) -> None:
        self.allowed = [e.get("citation", "") for e in evidence or [] if e.get("citation")]
        self.removed: List[str] = list(already or [])

    def __call__(self, where: str, tags: Iterable[str]) -> List[str]:
        tags = [normalize_citation(c) for c in tags or [] if c]
        if not self.allowed:
            return tags
        from ..validators import resolve_citations

        kept, dropped = resolve_citations(tags, self.allowed)
        for d in dropped:
            line = f"{where}: {d}"
            if line not in self.removed:
                self.removed.append(line)
        return kept


def frameworks_for(sources: Sequence[str]) -> List[Dict[str, str]]:
    return [
        {"id": s, "name": config.SOURCE_NAMES.get(s, s), "authority": config.AUTHORITY_LEVELS.get(s, "")}
        for s in sources
    ]


# ---------------------------------------------------------------------------
# Floors the normative sources impose (see rubric)
# ---------------------------------------------------------------------------


def _numberer(prefix: str, kind: str, ids: Sequence[Any]):
    """Assign record ids: keep ``<prefix>-<kind><n>`` ids already given (once each), number the rest after them."""
    pattern = re.compile(rf"^{re.escape(prefix)}-{kind}(\d+)$")
    kept = [str(i) for i in ids if i and pattern.match(str(i))]
    taken = {k for k in kept if kept.count(k) == 1}
    used: set = set()
    counter = [max([int(pattern.match(k).group(1)) for k in taken] + [0])]

    def assign(current: Any) -> str:
        c = str(current or "")
        if c in taken and c not in used:
            used.add(c)
            return c
        counter[0] += 1
        return f"{prefix}-{kind}{counter[0]}"
    return assign


def priority_floors(agent_key: str, rationale: RationaleResult) -> Dict[str, rubric.Floor]:
    data = rationale.data or {}
    verdict = rationale.verdict or {}
    floors: Dict[str, rubric.Floor] = {}

    if agent_key == "risk_classifier":
        for o in data.get("obligations") or []:
            code = str(o.get("code", ""))
            if code.startswith(("eu.", "br.")):
                floors[code] = ("high", f"legal obligation {code}")
        prohibited = any(m["type"] == "prohibited_practice" for m in rationale.typed_issues())
        if prohibited:
            for link in ["prohibited_screen", *(data.get("prohibited_practices") or [])]:
                floors[link] = ("critical", "prohibited or excessive-risk practice declared")

    elif agent_key == "requirements_reviewer":
        for g in data.get("gaps") or []:
            ref = str(g.get("ref", ""))
            if g.get("kind") != "principle" and ref.startswith(("eu.", "br.")) and g.get("evr_id"):
                floors[g["evr_id"]] = ("high", f"requirement closes a legal obligation gap ({ref})")

    elif agent_key == "auditor":
        risk_high = bool(data.get("high_risk"))
        for item in verdict.get("not_verified") or []:
            floors[item] = (("high", "unverified ethical item on a high-risk system") if risk_high
                            else ("medium", "unverified ethical item"))
        for g in (data.get("backlog_coverage") or {}).get("gaps") or []:
            if g.get("kind") in ("legal_without_story", "risk_without_story"):
                floors.setdefault(str(g.get("ref")), ("high", g.get("title", "backlog gap")))


    return floors


# ---------------------------------------------------------------------------
# Finalisation
# ---------------------------------------------------------------------------


def _engine_issues(rationale: RationaleResult) -> List[Dict[str, Any]]:
    return [
        {"type": m["type"], "description": m["text"],
         "options": list(m.get("options") or V.DEFAULT_ISSUE_OPTIONS.get(m["type"], ())),
         "decision_owner": m["decision_owner"], "blocking": bool(m["blocking"]),
         "links": [], "origin": "engine"}
        for m in rationale.typed_issues()
    ]


def _audit_opinion(ext: Dict[str, Any], rationale: RationaleResult, findings: Sequence[Dict[str, Any]],
                   issues: Sequence[Dict[str, Any]], notes: List[str]) -> None:
    """Hold strengths to the evidence and rate the audit — both by code.

    The rule against ethics-washing covers praise too: a strength must rest on
    an item whose final verdict is satisfied or partially satisfied, or on the
    approval record of an upstream artifact. Anything else is removed. The
    opinion follows :func:`raia.rationale.traceability.rate` over the final
    verdicts, the computed priorities and the open decisions, and never rises
    above the ceiling the engine set before the model was asked anything.
    """
    data = rationale.data or {}
    items = ext.get("items") or []
    verified = {str(i.get("item_id")) for i in items if i.get("verdict") in ("satisfied", "partially_satisfied")}
    approved = {str(b.get("artifact")) for b in data.get("baseline") or []}
    kept = []
    for strength in ext.get("strengths") or []:
        refs = [str(r) for r in strength.get("refs") or []]
        good = [r for r in refs if r in verified or r in approved]
        text = str(strength.get("statement") or "")[:90]
        if not good:
            notes.append(f"STRENGTH: removed “{text}” — it rests on no satisfied item and no approval on record.")
            continue
        if len(good) < len(refs):
            notes.append(f"STRENGTH: “{text}” kept without {', '.join(r for r in refs if r not in good)}, "
                         "which are not verified.")
        strength["refs"] = good
        kept.append(strength)
    ext["strengths"] = kept

    audited = data.get("audited_items") or []
    total = len(audited) or len(items)
    count = lambda v: sum(1 for i in items if i.get("verdict") == v)  # noqa: E731
    rating, reasons = traceability.rate(
        total, count("satisfied"),
        evidence_declared=bool((rationale.verdict or {}).get("evidence_declared", bool(data.get("evidence_types")))),
        at_risk=count("at_risk"),
        critical=sum(1 for f in findings if f.get("priority") == "critical"),
        high=sum(1 for f in findings if f.get("priority") == "high"),
        blocking=sum(1 for i in issues if i.get("blocking")) + sum(1 for f in findings if f.get("blocking")),
    )
    ceiling = (rationale.verdict or {}).get("opinion_ceiling") or traceability.OPINIONS[-1]
    final = traceability.at_most(rating, ceiling)
    if final != rating:
        reasons = reasons + [f"capped at the best the declared evidence allows ({ceiling.replace('_', ' ')})"]
    ext["opinion"] = {"rating": final, "reasons": reasons, "ceiling": ceiling}


def _audit_project(ext: Dict[str, Any], rationale: RationaleResult, notes: List[str]) -> None:
    """The project-wide parts of the audit, held to what code computed.

    The backlog judgement follows the verdicts' one-way rule: code's "not
    covered" stands, and "covered" may only be lowered. Where the project
    stands and how it is moving are computed from the final verdicts, exactly
    as the approval that closes the sprint will record them.
    """
    data = rationale.data or {}
    if not data.get("project_mode"):
        return
    from .. import roadmap as R

    coverage = data.get("backlog_coverage") or {}
    computed = {str(c.get("ref")): "covered" for c in coverage.get("covered") or []}
    computed.update({str(g.get("ref")): "not_covered" for g in coverage.get("gaps") or []
                     if g.get("kind") in ("legal_without_story", "requirement_without_story")})
    order = ("not_covered", "weakly_covered", "covered")
    kept = []
    for j in ext.get("backlog_assessment") or []:
        ref = str(j.get("ref"))
        base = computed.get(ref)
        j["computed"] = base
        if base and order.index(j.get("judgement", "covered")) > order.index(base):
            notes.append(f"UPGRADE: {ref} was judged {j.get('judgement')}; code found it {base}. Restored.")
            j["judgement"] = base
        kept.append(j)
    ext["backlog_assessment"] = kept

    board = data.get("board") or {}
    verdicts = {str(i.get("item_id")): i.get("verdict") for i in ext.get("items") or []}
    closing = str(data.get("sprint_close") or "")
    review = board.get("review") or {}
    if closing:
        projection = R.project_close(board.get("backlog") or {}, board.get("sprints") or {}, review, closing, verdicts)
        series, tr = projection.get("series") or [], projection.get("trend") or {}
        state_rows = projection.get("requirements") or []
    else:
        series = list(data.get("history") or [])
        tr = R.trend(series)
        state_rows = (data.get("project_state") or {}).get("requirements") or []
    open_rai = (series[-1].get("open_rai_stories") if series else (data.get("next") or {}).get("open_rai")) or 0
    ext["progress"] = {"series": series, "trend": tr, "projected": bool(closing),
                       "sprints_left": R.sprints_left(series, int(open_rai))}
    ext["project_state"] = {"counts": R.state_counts(state_rows), "requirements": [
        {k: x.get(k) for k in ("id", "statement", "state", "stories", "legal", "obligation", "priority", "verified_in")}
        for x in state_rows]}


def finalize(
    agent_key: str,
    record: Dict[str, Any],
    rationale: RationaleResult,
    evidence: Sequence[Dict[str, Any]],
    spec: Any,
    attempt: int = 1,
) -> Dict[str, Any]:
    """Apply everything code decides. Idempotent: finalising twice is harmless."""
    rec = json.loads(json.dumps(record, default=str))
    prefix = PREFIX.get(agent_key, "RAIA")
    notes: List[str] = []
    index = authority_index(evidence)
    floors = priority_floors(agent_key, rationale)
    prune = _Pruner(evidence, rec.get("pruned_citations") or [])

    # -- the parts of the core this stage does not write ------------------------
    for part, writes in (("findings", V.writes_findings(agent_key)), ("actions", V.writes_actions(agent_key))):
        if not writes and rec.get(part):
            notes.append(f"{len(rec[part])} {part} removed: this stage does not write {part}.")
        if not writes:
            rec[part] = []

    # -- findings -------------------------------------------------------------
    # An id code already assigned is kept, so a card a reviewer accepted or
    # rejected keeps its name when the record is finalised again; anything else
    # gets the next free number.
    fmap: Dict[str, str] = {}
    findings = rec.get("findings") or []
    next_f = _numberer(prefix, "F", [f.get("id") for f in findings])
    for f in findings:
        new = next_f(f.get("id"))
        fmap[str(f.get("id") or new)] = new
        fmap[new] = new
        f["id"] = new
        f["citations"] = prune(new, f.get("citations"))
        f.update(rubric.prioritise(
            f.get("magnitude", ""), f.get("likelihood", ""), f.get("links") or [],
            _authorities(f["citations"], index), floors,
        ))
    priority_by_id = {f["id"]: f["priority"] for f in findings}

    # -- actions --------------------------------------------------------------
    amap: Dict[str, str] = {}
    actions = rec.get("actions") or []
    next_a = _numberer(prefix, "A", [a.get("id") for a in actions])
    for a in actions:
        new = next_a(a.get("id"))
        amap[str(a.get("id") or new)] = new
        a["id"] = new
        linked, unknown = [], []
        for fid in a.get("finding_ids") or []:
            (linked if str(fid) in fmap else unknown).append(fmap.get(str(fid), str(fid)))
        if unknown:
            notes.append(f"{new} referenced unknown finding id(s) {', '.join(unknown)}; removed.")
        a["finding_ids"] = linked
        a["citations"] = prune(new, a.get("citations"))
        a["priority"] = rubric.action_priority([priority_by_id[x] for x in linked])
        for link in a.get("links") or []:
            if link in floors:
                a["priority"] = rubric.higher(a["priority"], floors[link][0])

    # -- open issues: engine first, then the agent's, then what code must add --
    issues: List[Dict[str, Any]] = _engine_issues(rationale)
    seen = {_norm(i["description"]) for i in issues}
    for issue in rec.get("open_issues") or []:
        # Issues the engine or code raised are recomputed below from the record as
        # it is now, so one a reviewer's edit has resolved does not linger.
        if issue.get("origin") in ("engine", "code") or _norm(issue.get("description", "")) in seen:
            continue
        seen.add(_norm(issue.get("description", "")))
        issue["origin"] = "agent"
        issue["links"] = [fmap.get(str(l), amap.get(str(l), str(l))) for l in issue.get("links") or []]
        issues.append(issue)

    if not rec.get("agrees_with_rule_engine", True) and not any(
        i.get("type") == "engine_disagreement" for i in issues
    ):
        issues.append({
            "type": "engine_disagreement",
            "description": "The agent disagrees with the rule engine's verdict: "
                           + (rec.get("disagreement_rationale") or "no rationale was given."),
            "options": ["Keep the computed verdict", "Adopt the agent's verdict and record why"],
            "decision_owner": "legal_compliance" if agent_key == "risk_classifier" else "product",
            "blocking": False, "links": [], "origin": "code",
        })
        if not (rec.get("disagreement_rationale") or "").strip():
            notes.append("The agent declared a disagreement without a rationale.")

    for a in actions:
        if a.get("response") == "accept" and not any(a["id"] in (i.get("links") or []) for i in issues):
            issues.append({
                "type": "risk_acceptance",
                "description": f"{a['id']} proposes to accept a risk: {a.get('action', '')}",
                "options": ["Accept the risk and record the decision", "Require a treatment"],
                "decision_owner": "leadership" if a.get("priority") in ("high", "critical") else a.get("owner_role", "product"),
                "blocking": False, "links": [a["id"], *a.get("finding_ids", [])], "origin": "code",
            })

    if agent_key == "story_refiner":
        # An existing acceptance criterion that conflicts with an approved
        # requirement is the team's call, not the agent's: it becomes a decision.
        for story in (rec.get("extension") or {}).get("stories") or []:
            for c in story.get("conflicts") or []:
                against = ", ".join(c.get("conflicts_with") or []) or "an ethical requirement"
                description = (f"{c.get('criterion_id')} ({story.get('story_id')}) conflicts with "
                               f"{against}: {c.get('problem', '')}")
                if _norm(description) in seen:
                    continue
                seen.add(_norm(description))
                rewrite = (c.get("suggested_rewrite") or "").strip()
                issues.append({
                    "type": "value_tradeoff", "description": description,
                    "options": ([f"Rewrite it: {rewrite}"] if rewrite else ["Rewrite the criterion"])
                               + ["Keep it and record why"],
                    "decision_owner": "product", "blocking": False,
                    "links": [str(c.get("criterion_id")), str(story.get("story_id"))], "origin": "code",
                })

    for i, issue in enumerate(issues, 1):
        issue["id"] = f"{prefix}-I{i}"
    rec["open_issues"] = issues

    # -- agent-specific discipline -----------------------------------------------
    ext = rec.get("extension") or {}
    if agent_key == "auditor":
        computed = {str(x.get("id")): x.get("computed_verdict") for x in (rationale.data or {}).get("audited_items") or []}
        not_verified = set((rationale.verdict or {}).get("not_verified") or [])
        for item in ext.get("items") or []:
            iid = str(item.get("item_id"))
            item["computed_verdict"] = computed.get(iid)
            if iid in not_verified and item.get("verdict") in ("satisfied", "partially_satisfied"):
                notes.append(f"UPGRADE: {iid} was reported {item['verdict']} with no evidence; "
                             "restored to not_verified by code.")
                item["downgrade_reason"] = ("Restored to not_verified by code: no evidence was found "
                                            "for this item. A verdict may be downgraded, never upgraded.")
                item["verdict"] = "not_verified"
    if agent_key == "requirements_reviewer":
        # Each requirement takes the priority of the approved risks behind its
        # gap (computed by the rule engine); a re-finalise without the engine's
        # data keeps what was computed at the run.
        by_id = {str(g.get("evr_id")): g for g in (rationale.data or {}).get("gaps") or [] if g.get("evr_id")}
        for e in ext.get("evrs") or []:
            g = by_id.get(str(e.get("id")))
            if g is not None:
                e["priority"] = g.get("priority") or "low"
                e["priority_basis"] = g.get("priority_basis") or ""
                e["answers_risks"] = list(g.get("risks") or [])
    if agent_key == "auditor" and isinstance(rec.get("extension"), dict):
        _audit_project(ext, rationale, notes)
        _audit_opinion(ext, rationale, findings, issues, notes)
    for key in ("obligations", "gap_analysis", "evrs", "items"):
        for entry in ext.get(key) or []:
            if isinstance(entry, dict) and "citations" in entry:
                where = str(entry.get("code") or entry.get("id") or entry.get("evr_id") or entry.get("item_id") or key)
                entry["citations"] = prune(where, entry["citations"])

    # -- overall status floor --------------------------------------------------
    floor = "on_track"
    if any(f.get("priority") == "high" for f in findings) or any(i for i in issues):
        floor = "needs_attention"
    if any(f.get("blocking") for f in findings) or any(i.get("blocking") for i in issues):
        floor = "blocked"
    declared = rec.get("overall_status", "on_track")
    if V.rank(V.OVERALL_STATUSES, floor) > V.rank(V.OVERALL_STATUSES, declared):
        notes.append(f"Overall status raised from {declared} to {floor} by code.")
        rec["overall_status"] = floor

    notes += [f"SHORTENED: {n}" for n in rec.get("shortened") or []]
    if prune.removed:
        rec["pruned_citations"] = prune.removed
    notes += [f"PRUNED_CITATION: {n}" for n in prune.removed]

    rec["meta"] = {
        "schema_version": V.SCHEMA_VERSION,
        "record_type": RECORD_TYPES.get(agent_key, "RAIA record"),
        "agent_key": agent_key,
        "agent_name": getattr(spec, "name", agent_key),
        "layer": getattr(spec, "layer", ""),
        "sdlc_phase": getattr(spec, "sdlc_phase", ""),
        "frameworks": frameworks_for(getattr(spec, "grounding_sources", []) or []),
        "attempt": attempt,
    }
    rec["computed_verdict"] = {k: v for k, v in (rationale.verdict or {}).items()}
    rec["contract_notes"] = notes
    return rec


def fallback_record(agent_key: str, rationale: RationaleResult, errors: Sequence[str],
                    raw_text: str, truncated: bool = False, budget: int = 0) -> Dict[str, Any]:
    """An honest record for a reply that could not be read as one."""
    if truncated:
        summary = (
            f"The model's reply was cut off at the token limit ({budget} tokens) and could not be "
            "read as a RAIA record, so no analysis is shown. The rule engine's facts and open "
            "issues are below. Reject this draft to regenerate it; if it keeps happening, raise "
            "RAIA_LLM_MAX_TOKENS or reduce how much the form asks the agent to cover at once."
        )
    else:
        summary = ("The model's reply could not be read as a RAIA record, so no analysis is "
                   "shown. The rule engine's facts and open issues are below. Reject this draft "
                   "to regenerate it.")
    return {
        "headline": "The agent's reply could not be read — reject this draft to regenerate it.",
        "summary": summary,
        "overall_status": "needs_attention",
        "declared_verdict": {},
        "agrees_with_rule_engine": True,
        "disagreement_rationale": "",
        "findings": [], "actions": [], "open_issues": [], "not_grounded": [], "coverage": [],
        "extension": {},
        "unparsed_response": (raw_text or "")[:20000],
        "schema_errors": list(errors),
        "truncated": bool(truncated),
    }


def model_link_ids(record: Dict[str, Any]) -> List[str]:
    return [l for f in record.get("findings") or [] for l in f.get("links") or []]
