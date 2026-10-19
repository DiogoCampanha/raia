"""
raia.ui.record_view
===================

How a RAIA record looks on screen, for every agent, wherever it is shown — a
draft at the approval gate, the approved version on a stage page, a document
in the project.

RAIA is a work tool. The record is read top to bottom and can be put down at
any point:

1. **Summary** — the status with what it means here (and, when blocked, a
   link to the gaps), the headline, the agent's picture, a few numbers, and
   **Gaps to close** when something blocks; then the risks found as compact
   cards, most pressing first.
2. **What to do** — action cards grouped Do now / Plan / Track (the first
   group open), then the decisions only a person can take; a filter shows one
   owner's share. A stage that writes no actions shows only its decisions:
   the Risk Classifier, an analysis, shows the risks, the *Decisions on this
   classification* and its legal obligations by instrument; the Requirements
   Reviewer leads with its requirements (most pressing first, each with the
   risks it answers), then its decisions.

Everything a person changes keeps the page still: a decision is a form sent
by one button, every element that comes and goes sits in a slot drawn on
every redraw, so Streamlit never rebuilds the elements below it (which would
drop the person at the end of the page and close an open popover).
3. **Deep dive** — behind a dropdown, one tab per topic, each opening with its
   conclusion; the traceability appendix last.

Every card is compact: one line of main information, the rest on a click.

Two agents lead with what their users take away instead:

- **User Story Refiner** — the refined stories first, one card per story with
  its changes marked (kept, in conflict with the suggested rewrite, new), a
  choice per conflict and a copy of the story's new version; then the stories
  that need no change; the risks, actions and decisions behind the changes sit
  in "Why these changes", closed until wanted.
- **Auditor** — an audit report: header (scope, evidence, baseline), the
  opinion code rated, strengths, risks as audit observations, opportunities
  and the pathway forward; the decisions register, verdict register,
  accountability documentation and traceability are appendices.

The content comes from :func:`raia.contract.digest.build`, the same digest the
exported Markdown is written from, so the screen and the document agree.
Static parts are drawn as HTML with the classes in ``theme.css``; everything a
person clicks is a native Streamlit widget.
"""

from __future__ import annotations

import html
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import streamlit as st

from raia.contract import digest as D
from raia.contract import review as RV
from raia.contract import vocab as V
from raia.contract.render import table as md_table

from .theme import I, look


# ---------------------------------------------------------------------------
# What a person can do on a record: review its cards, take its decisions
# ---------------------------------------------------------------------------


@dataclass
class CardReview:
    """Accept / Reject on each card of a draft at the gate.

    ``state`` maps a card id to its verdict (``raia.contract.review``) and is
    changed in place by the widgets; ``on_change`` keeps it with the draft.
    """
    state: Dict[str, Dict[str, Any]]
    key: str
    on_change: Callable[[], None]
    by: str = ""
    enabled: bool = True
    titles: Dict[str, str] = field(default_factory=dict)


@dataclass
class Decisions:
    """The decisions on a record, taken where they are shown.

    ``taken`` maps a decision's wording key to what was decided; ``record``
    takes one (returns an error message, or ``None``); ``reopen`` undoes one
    (owners, approved records only).
    """
    taken: Dict[str, Dict[str, Any]]
    key: str
    can_decide: bool
    record: Callable[[Dict[str, Any], str, str], Optional[str]]
    reopen: Optional[Callable[[Dict[str, Any]], None]] = None
    where: str = "draft"


_CTX = threading.local()


def _rv() -> Optional[CardReview]:
    return getattr(_CTX, "review", None)


def _dc() -> Optional[Decisions]:
    return getattr(_CTX, "decide", None)


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def chip(text: str, tone: str = "neutral", quiet: bool = False, n: Optional[int] = None) -> str:
    extra = f' <span class="n">{n}</span>' if n is not None else ""
    return f'<span class="rv-chip tone-{esc(tone)}{" quiet" if quiet else ""}">{esc(text)}{extra}</span>'


def _cite_label(tag: str) -> str:
    body = str(tag).strip().lstrip("[").rstrip("]")
    if body.lower().startswith("source:"):
        body = body[7:].strip()
    return body.split("|")[0].strip()


def _cites(cites: Sequence[str]) -> str:
    return "".join(f'<span class="rv-cite" title="{esc(c)}">{esc(_cite_label(c))}</span>' for c in cites)


def _lead_split(text: str) -> str:
    """A paragraph with its first sentence (the conclusion) set in bold."""
    lead = D.first_sentence(text)
    rest = D.rest_after_first(text)
    if not lead:
        return ""
    return f'<span class="lead">{esc(lead)}</span>' + (f" {esc(rest)}" if rest else "")


# ---------------------------------------------------------------------------
# Tier 1 — Summary
# ---------------------------------------------------------------------------


def _signature(dg: Dict[str, Any]) -> str:
    """The agent's own picture (``digest.signature``), drawn in its identity."""
    sig = dg.get("signature")
    if not sig:
        return ""
    agent = str(dg.get("agent_key") or "")
    kind = sig["kind"]
    out = [f'<div class="rv-sig look-{esc(agent)}" data-kind="{esc(kind)}">',
           f'<div class="rv-sig-h"><span class="raia-icon" aria-hidden="true">{esc(look(agent).icon)}</span>'
           f'{esc(sig["title"])}</div>']
    if kind == "scale":
        for r in sig["rows"]:
            on = f' is-on tone-{esc(r["tone"])}" aria-current="true'
            steps = "".join(f'<span class="sig-step{on if i == r["active"] else ""}">{esc(step)}</span>'
                            for i, step in enumerate(r["steps"]))
            out.append(f'<div class="sig-scale"><span class="sig-row-label">{esc(r["label"])}</span>'
                       f'<div class="sig-steps">{steps}</div>'
                       f'<span class="rv-muted sig-note">{esc(r["note"])}</span></div>')
    elif kind == "cells":
        out.append('<div class="sig-cells">' + "".join(
            f'<div class="sig-cell tone-{esc(c["tone"])}"><div class="l">{esc(c["label"])}</div>'
            f'<div class="s">{esc(c["state"])}</div></div>' for c in sig["cells"]) + "</div>")
    elif kind == "split":
        segs = [x for x in sig["segments"] if x["value"]]
        out.append('<div class="sig-split" role="img" aria-label="'
                   + esc(", ".join(f'{x["label"]} {x["value"]}' for x in sig["segments"])) + '">'
                   + "".join(f'<span class="seg tone-{esc(x["tone"])}" style="flex-grow:{int(x["value"])}"></span>'
                             for x in segs) + "</div>")
        out.append('<div class="rv-tags">' + "".join(chip(x["label"], x["tone"], n=x["value"])
                                                     for x in sig["segments"]) + "</div>")
    if sig.get("caption"):
        out.append(f'<p class="rv-sig-cap">{esc(sig["caption"])}</p>')
    out.append("</div>")
    return "".join(out)


def _status_html(dg: Dict[str, Any]) -> str:
    """The status banner: what the status is, what it means here, and where to go."""
    status = dg["status"]
    jump = ('<a class="rv-jump" href="#gaps-to-close">Go to the gaps</a>' if dg.get("gaps") else "")
    out = [f'<div class="rv rv-status tone-{esc(status["tone"])}">',
           '<div class="rv-status-top">' + chip(status["label"], status["tone"])
           + (f'<span class="rv-status-help">{esc(status.get("help", ""))}</span>' if status.get("help") else "")
           + jump + "</div>"]
    if status.get("was"):
        out.append(f'<p class="rv-status-was">{esc(status["was"])}</p>')
    if dg["headline"]:
        out.append(f'<p class="rv-headline">{esc(dg["headline"])}</p>')
    if dg["summary"]:
        out.append('<details class="rv-more-summary"><summary>Read the full summary</summary>'
                   f'<p class="rv-summary">{esc(dg["summary"])}</p></details>')
    out.append("</div>")
    return "".join(out)


def _kpis_html(dg: Dict[str, Any]) -> str:
    return '<div class="rv-kpis">' + "".join(
        f'<div class="rv-kpi tone-{esc(k["tone"])}" role="group" aria-label="{esc(k["label"])}">'
        f'<div class="rv-kpi-label">{esc(k["label"])}</div>'
        f'<div class="rv-kpi-value">{esc(k["value"])}</div>'
        f'<div class="rv-kpi-hint">{esc(k["hint"])}</div></div>' for k in dg["kpis"]) + "</div>"


def _gaps_html(dg: Dict[str, Any]) -> str:
    if not dg.get("gaps"):
        return ""
    rows = "".join(
        f'<li class="rv-gap tone-{esc(g["tone"])}"><a class="rv-id" href="#card-{esc(g["id"])}">{esc(g["id"])}</a>'
        f'<span class="t">{esc(g["title"])}</span><span class="u"><b>Unblocks it:</b> {esc(g["unblock"])}</span></li>'
        for g in dg["gaps"])
    return ('<div class="rv-gaps" id="gaps-to-close"><div class="rv-h"><h4>Gaps to close</h4>'
            '<span class="rv-muted">Why this is blocked in its current form, and what unblocks each item</span></div>'
            f'<ul>{rows}</ul></div>')


# ---- Compact cards ----------------------------------------------------------
#
# A card shows one line of main information and opens on click. It is a native
# <details> element, so opening it costs no rerun. Every card carries an anchor
# (``#card-<id>``) the gaps, the checks and the hand-off link to.


def _dcard(cid: str, tone: str, chips: str, title: str, body: str, sub: str = "",
           cls: str = "", open_: bool = False) -> str:
    return (f'<details class="rv-card rv-dcard tone-{esc(tone)} {cls}" id="card-{esc(cid)}"'
            + (" open" if open_ else "") + ">"
            f'<summary><div class="rv-card-top">{chips}<span class="rv-id">{esc(cid)}</span></div>'
            f'<div class="rv-card-title">{title}</div>'
            + (f'<div class="rv-card-sub">{sub}</div>' if sub else "")
            + f'</summary><div class="rv-dbody">{body}</div></details>')


def _meta(rows: Sequence[Tuple[str, Any]]) -> str:
    cells = "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in rows if v not in (None, "", []))
    return f'<dl class="rv-meta">{cells}</dl>' if cells else ""


def finding_card(f: Dict[str, Any]) -> str:
    tone = D.tone_of_priority(f.get("priority"))
    chips = (chip(V.PRIORITY_LABELS.get(f.get("priority"), D.label(f.get("priority"))), tone)
             + (chip("Blocking", "critical") if f.get("blocking") else "")
             + chip(D.principle_name(f.get("principle")), "neutral", quiet=True))
    basis = str(f.get("priority_basis") or "")
    body = (f'<p class="rv-card-text">{esc(f.get("statement") or "")}</p>'
            + _meta([("Affected", ", ".join(f.get("stakeholders") or [])),
                     ("Why this priority", f"{D.label(f.get('magnitude')).capitalize()} impact, "
                                           f"{D.label(f.get('likelihood'))} — {str(f.get('placement_rationale') or '').strip()}".rstrip(" —")),
                     ("Raised because", basis.split(";", 1)[1].strip() if ";" in basis else ""),
                     ("Concerns", ", ".join(f.get("links") or [])),
                     ("NIST AI RMF", f.get("nist_category"))])
            + (f'<div class="rv-card-foot">{_cites(f["citations"])}</div>' if f.get("citations")
               else '<div class="rv-card-foot">No source in the retrieved norms</div>'))
    return _dcard(f.get("id", ""), tone, chips, esc(str(f.get("title") or "").rstrip(".")), body)


def action_card(a: Dict[str, Any]) -> str:
    chips = (chip(V.PRIORITY_LABELS.get(a["priority"], a["priority"]), a["tone"])
             + (chip("Blocking", "critical") if a["blocking"] else "")
             + chip(a["owner_label"], "neutral", quiet=True))
    body = (_meta([("Done when", a["done_when"]), ("Answers", ", ".join(a["findings"])), ("Response", a["response"])])
            + (f'<div class="rv-card-foot">{_cites(a["cites"])}</div>' if a["cites"] else ""))
    return _dcard(a["id"], a["tone"], chips, esc(a["text"]), body, sub=esc(a["when"]))


def obligation_card(o: Dict[str, Any], where: str) -> str:
    body = ((f'<p class="rv-card-text">{esc(o["meaning"])}</p>' if o.get("meaning")
             else '<p class="rv-muted">No note from the agent for this obligation.</p>')
            + (f'<div class="rv-card-foot">{_cites(o["cites"])}</div>' if o.get("cites") else ""))
    return _dcard(o["code"], "neutral", chip(where, "neutral", quiet=True), esc(o.get("title") or o["code"]), body,
                  cls="rv-slim")


def evr_card(e: Dict[str, Any]) -> str:
    over = (e.get("review") or {}).get("status") == "overridden"
    tone = D.tone_of_priority(e.get("priority")) if e.get("priority") and not over else "neutral"
    chips = ((chip("Overridden by " + str((e.get("review") or {}).get("by") or "a reviewer"), "neutral") if over else "")
             + (chip(V.PRIORITY_LABELS.get(e["priority"], D.label(e["priority"])), tone) if e.get("priority") and not over else "")
             + chip(D.principle_name(e.get("value")), "neutral", quiet=True)
             + "".join(chip(t, "neutral", quiet=True) for t in (e.get("traces_to") or [])[:3]))
    body = (_meta([("Fit criterion", e.get("fit_criterion")),
                   ("Verified by", str(e.get("verification_method") or "").capitalize()),
                   ("Stakeholders", ", ".join(e.get("stakeholders") or [])),
                   ("Answers", ", ".join(e.get("answers_risks") or [])),
                   ("Why this priority", e.get("priority_basis"))])
            + (f'<div class="rv-card-foot">{_cites(e["citations"])}</div>' if e.get("citations") else "")
            + (f'<p class="rv-muted">Overridden: {esc((e.get("review") or {}).get("reason") or "")}</p>' if over else ""))
    return _dcard(e.get("id", ""), tone, chips, esc(e.get("statement") or ""), body,
                  cls="rv-overridden" if over else "")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _on_verdict(rv: CardReview, cid: str, k: str) -> None:
    value = st.session_state.get(k)
    if value is None:
        rv.state.pop(cid, None)
    else:
        s = dict(rv.state.get(cid) or {})
        s.update(verdict=value, by=rv.by, at=_now())
        rv.state[cid] = s
    rv.on_change()


def _on_reason(rv: CardReview, cid: str, k_code: str, k_why: str) -> None:
    s = dict(rv.state.get(cid) or {})
    s["reason_code"] = st.session_state.get(k_code) or "other"
    s["reason"] = " ".join(str(st.session_state.get(k_why) or "").split())
    rv.state[cid] = s
    rv.on_change()


def _reject_too(rv: CardReview, ids: Sequence[str], because: str) -> None:
    for cid in ids:
        rv.state[cid] = {"verdict": RV.REJECTED, "reason_code": "other", "reason": because, "by": rv.by, "at": _now()}
    rv.on_change()


def _rejected_html(cid: str, title: str, s: Dict[str, Any]) -> str:
    reason = str(s.get("reason") or "").strip()
    return (f'<div class="rv-card rv-rejected tone-neutral" id="card-{esc(cid)}"><div class="rv-card-top">'
            + chip("Rejected", "neutral") + f'<span class="rv-id">{esc(cid)}</span></div>'
            f'<div class="rv-card-title"><s>{esc(title)}</s></div>'
            + (f'<div class="rv-card-sub">Why: {esc(reason)}</div>' if reason else
               '<div class="rv-card-sub rv-need">Say why below: a rejection needs a reason.</div>')
            + "</div>")


def review_card(cid: str, card_html: str, title: str = "", extra: Optional[Callable[[], None]] = None) -> None:
    """One card with Accept / Reject beside it (a reason under it, once rejected)."""
    rv = _rv()
    if rv is None:
        st.html(card_html)
        return
    s = rv.state.get(cid) or {}
    verdict = s.get("verdict")
    k = f"{rv.key}::v::{cid}"
    if k not in st.session_state:
        st.session_state[k] = verdict
    with st.container(key=f"{rv.key}::box::{cid}"):
        left, right = st.columns([6, 1.45], vertical_alignment="top", gap="small")
        with left:
            st.html(_rejected_html(cid, title or rv.titles.get(cid, cid), s) if verdict == RV.REJECTED else card_html)
        with right:
            st.segmented_control(
                f"Your review of {cid}", [RV.ACCEPTED, RV.REJECTED], key=k, label_visibility="collapsed",
                format_func=lambda o: "Accept" if o == RV.ACCEPTED else "Reject", disabled=not rv.enabled,
                on_change=_on_verdict, args=(rv, cid, k), width="stretch")
        if verdict == RV.REJECTED:
            k_code, k_why = f"{rv.key}::rc::{cid}", f"{rv.key}::why::{cid}"
            if k_code not in st.session_state:
                st.session_state[k_code] = s.get("reason_code") or RV.CARD_REASONS[0][0]
            if k_why not in st.session_state:
                st.session_state[k_why] = s.get("reason") or ""
            c1, c2 = st.columns([1.4, 3], gap="small")
            c1.selectbox("Reason", [c for c, _ in RV.CARD_REASONS], key=k_code, format_func=dict(RV.CARD_REASONS).get,
                         on_change=_on_reason, args=(rv, cid, k_code, k_why), disabled=not rv.enabled)
            c2.text_input("Why? (required)", key=k_why, placeholder="One line is enough",
                          on_change=_on_reason, args=(rv, cid, k_code, k_why), disabled=not rv.enabled)
            if extra:
                extra()


def _draw_cards(cards: Sequence[Tuple[str, str, str]], more_after: int, noun: str = "",
                flat: bool = False, extra: Optional[Callable[[str], Optional[Callable[[], None]]]] = None) -> None:
    """Cards as ``(id, html, title)``: plain HTML to read, or with Accept / Reject at the gate.

    ``flat`` draws them all (inside an expander, where another cannot open).
    """
    if _rv() is None:
        st.html(_cards_html([h for _, h, _ in cards], more_after, noun))
        return
    head, rest = (list(cards), []) if flat else (list(cards[:more_after]), list(cards[more_after:]))
    for cid, h, title in head:
        review_card(cid, h, title, extra(cid) if extra else None)
    if rest:
        with st.expander(f"Show {len(rest)} more{(' ' + noun) if noun else ''}"):
            for cid, h, title in rest:
                review_card(cid, h, title, extra(cid) if extra else None)


def _cards_html(cards: Sequence[str], more_after: int, noun: str = "") -> str:
    """Cards one under the other; past ``more_after``, the rest behind one click."""
    head, rest = list(cards[:more_after]), list(cards[more_after:])
    out = '<div class="rv-cards one">' + "".join(head) + "</div>"
    if rest:
        out += (f'<details class="rv-showmore"><summary>Show {len(rest)} more{(" " + noun) if noun else ""}</summary>'
                f'<div class="rv-cards one">{"".join(rest)}</div></details>')
    return out


def _section_head(title: str, hint: str = "", count: Optional[int] = None) -> str:
    return (f'<div class="rv-h"><h4>{esc(title)}</h4>'
            + (f'<span class="rv-chip quiet tone-neutral">{count}</span>' if count is not None else "")
            + (f'<span class="rv-muted">{esc(hint)}</span>' if hint else "") + "</div>")


# ---------------------------------------------------------------------------
# Tier 1 — Summary
# ---------------------------------------------------------------------------


def _summary(dg: Dict[str, Any], before=None) -> None:
    st.html(_status_html(dg))
    if before:
        before(dg)
    st.html(_signature(dg) + _kpis_html(dg) + _gaps_html(dg))


def _only_answers(dg: Dict[str, Any], fid: str) -> List[str]:
    """Actions that answer this finding and no other."""
    return [a["id"] for a in dg["actions"] if a["findings"] == [fid]]


def _findings(dg: Dict[str, Any], key: str, flat: bool = False, title: str = "Risks found") -> None:
    findings = dg.get("findings") or []
    if not findings:
        return
    st.html(_section_head(title, "Most pressing first; open a card for the detail", len(findings)))
    rv = _rv()

    def extra(fid: str):
        if rv is None:
            return None
        others = [a for a in _only_answers(dg, fid) if (rv.state.get(a) or {}).get("verdict") != RV.REJECTED]
        if not others:
            return None

        def draw() -> None:
            st.caption(f"{', '.join(others)} answer{'s' if len(others) == 1 else ''} only this risk.")
            st.button(f"Reject {', '.join(others)} too", key=f"{rv.key}::too::{fid}", type="tertiary",
                      on_click=_reject_too, args=(rv, others, f"Answers only {fid}, which was rejected"))
        return draw

    _draw_cards([(f.get("id", ""), finding_card(f), str(f.get("title") or "")) for f in findings], 3, "risks",
                flat=flat, extra=extra)
    if dg["principles"]:
        st.html('<div class="rv-tags"><span class="lbl">Risk areas</span>'
                + "".join(chip(name, "neutral", quiet=True, n=count) for name, count in dg["principles"]) + "</div>")


# ---------------------------------------------------------------------------
# Tier 2 — What to do
# ---------------------------------------------------------------------------


def _decision_card(d: Dict[str, Any], interactive: bool = False) -> str:
    taken = d.get("taken")
    if taken:
        return (
            f'<div class="rv-card tone-ok rv-decided" id="card-{esc(d["id"])}">'
            '<div class="rv-card-top">' + chip("Decided", "ok")
            + (chip("Was blocking", "neutral", quiet=True) if d["blocking"] else "")
            + chip(d["owner_label"], "neutral", quiet=True) + f'<span class="rv-id">{esc(d["id"])}</span></div>'
            f'<div class="rv-card-text">{esc(d["text"])}</div>'
            f'<div class="rv-decision"><b>{esc(taken.get("choice", ""))}</b>'
            + (f' — {esc(taken.get("rationale", ""))}' if taken.get("rationale") else "")
            + f'<span class="rv-muted"> · {esc(taken.get("by", ""))}'
            + (f', {esc(str(taken.get("at", ""))[:10])}' if taken.get("at") else "") + "</span></div></div>")
    return (
        f'<div class="rv-card tone-{d["tone"]}" id="card-{esc(d["id"])}">'
        '<div class="rv-card-top">'
        + chip("Decision needed", "decision")
        + (chip("Blocking", "critical") if d["blocking"] else "")
        + chip(d["owner_label"], "neutral", quiet=True)
        + f'<span class="rv-id">{esc(d["id"])}</span></div>'
        f'<div class="rv-card-text">{esc(d["text"])}</div>'
        + ('<div class="rv-options">' + "".join(f'<span class="opt">{esc(o)}</span>' for o in d["options"]) + "</div>"
           if d["options"] and not interactive else "")
        + f'<div class="rv-card-foot">{esc(d["type_label"])} · raised by {esc(d["origin"])}</div>'
        "</div>"
    )


OTHER = "Something else"


def decision_block(d: Dict[str, Any]) -> None:
    """A decision card a person can act on: pick an option, say why, record it.

    Open or decided, a decision is one container on the page, so taking it
    changes what is inside that container and nothing after it moves.
    """
    dc = _dc()
    if dc is None or (not dc.can_decide and not d.get("taken")):
        st.html(_decision_card(d))
        return
    with st.container(border=not d.get("taken"), key=f"{dc.key}::dbox::{d['id']}"):
        if d.get("taken"):
            st.html(_decision_card(d))
            if dc.reopen is not None and dc.can_decide:
                if st.button("Reopen this decision", key=f"{dc.key}::reopen::{d['id']}", type="tertiary",
                             icon=":material/undo:"):
                    dc.reopen(d)
                    st.rerun()
            return
        st.html(_decision_card(d, interactive=True))
        k = f"{dc.key}::d::{d['key'][:60]}"
        if d["blocking"]:
            _decision_form(d, dc, k)
        else:
            # A decision that blocks nothing waits one click away, so a long list
            # of them does not bury the rest of the record.
            with st.popover("Take this decision", icon=":material/gavel:"):
                _decision_form(d, dc, k)


def decision_form(options: Sequence[str], key: str, record: Callable[[str, str], Optional[str]],
                  note: str = "", allow_other: bool = True) -> None:
    """Pick an option, say why, record — as one form.

    Nothing reaches the app until "Record decision" is pressed: choosing an
    option or typing the reason does not redraw the page, so the page stays
    where it is, a popover stays open, and the button is never greyed out by
    an answer the app has not received yet. The answers are checked when the
    button is pressed. ``record(choice, why)`` returns an error, or ``None``.
    """
    with st.form(key + "::form", border=False, enter_to_submit=False):
        opts = list(options) + ([OTHER] if allow_other else [])
        choice = st.radio("Your decision", opts, key=key + "::choice", index=None)
        own = (st.text_input("Or your own decision, in a few words", key=key + "::own",
                             placeholder=f"Only if you chose \"{OTHER}\"") if allow_other else "")
        why = st.text_input("Why? (required)", key=key + "::why", placeholder="The reason, recorded with the decision")
        go = st.form_submit_button("Record decision", key=key + "::go", type="primary", icon=":material/gavel:")
        if note:
            st.caption(note)
    if go:
        final = (own or "").strip() if choice == OTHER else (choice or "")
        if not final:
            st.error("Choose an option" + (", or write the decision." if allow_other else "."))
        elif not (why or "").strip():
            st.error("Say why: one line is enough.")
        else:
            err = record(final, why.strip())
            if err:
                st.error(err)
            else:
                st.rerun()


def _decision_form(d: Dict[str, Any], dc: "Decisions", k: str) -> None:
    decision_form(d["options"], k, lambda choice, why: dc.record(d, choice, why),
                  note=("Recorded with the draft, and written to the project's open issues when it is approved."
                        if dc.where == "draft" else ""))


def _group_head(title: str, hint: str, tone: str, count: int) -> str:
    return (f'<div class="rv-group tone-{tone}"><span class="dot"></span><span class="name">{esc(title)}</span>'
            f'<span class="rv-chip quiet tone-{tone}">{count}</span><span class="rv-muted">{esc(hint)}</span></div>')


#: What a stage that writes no actions calls its decisions.
DECISIONS_TITLE = {"risk_classifier": "Decisions on this classification"}


def _actions(dg: Dict[str, Any], key: str, flat: bool = False) -> None:
    if not V.writes_actions(dg["agent_key"]):
        # An analysis (Risk Classifier) or a set of requirements (Requirements
        # Reviewer): what to do comes at the next stage. Only the decisions a
        # person must take on this record are shown, under their own heading.
        _decisions(dg, dg["decisions"], DECISIONS_TITLE.get(dg["agent_key"], "Decisions for a person"))
        return
    st.html('<div class="rv-h"><h4>What to do</h4>'
            '<span class="rv-muted">Grouped by the priority the software computed</span></div>')
    counts = D.owner_counts(dg)
    picked: List[str] = []
    if len(dg["owners"]) > 1:
        picked = st.pills(
            "Show the work of", dg["owners"], selection_mode="multi", key=f"{key}::owners",
            format_func=lambda o: f"{V.OWNER_LABELS.get(o, D.label(o))} ({counts.get(o, 0)})",
            label_visibility="collapsed",
        ) or []
    keep = (lambda owner: owner in picked) if picked else (lambda owner: True)

    shown_any = False
    groups = []
    for g in dg["action_groups"]:
        items = [a for a in g["actions"] if keep(a["owner"])]
        if not items:
            continue
        shown_any = True
        if _rv() is not None:
            # At the gate each card carries widgets, so groups are drawn with
            # Streamlit, not inside an HTML <details>: the first open, the rest
            # a click away.
            cards = [(a["id"], action_card(a), a["text"]) for a in items]
            if not groups or flat:
                st.html(_group_head(g["title"], g["hint"], g["tone"], len(items)))
                _draw_cards(cards, 5, "actions", flat=flat)
            else:
                with st.expander(f"{g['title']} ({len(items)}) — {g['hint'].lower()}"):
                    _draw_cards(cards, 5, "actions", flat=True)
            groups.append(g["key"])
            continue
        # The first group with work in it is open; later groups are a click away.
        groups.append(f'<details class="rv-grp"{" open" if len(groups) == 0 else ""}><summary>'
                      + _group_head(g["title"], g["hint"], g["tone"], len(items)) + "</summary>"
                      + _cards_html([action_card(a) for a in items], 5, "actions") + "</details>")
    if groups and _rv() is None:
        st.html("".join(groups))
    if not shown_any:
        st.html('<div class="rv-empty">'
                + ("No actions for the selected owners." if picked and dg["actions"] else "No actions at this stage.")
                + "</div>")

    _decisions(dg, [d for d in dg["decisions"] if keep(d["owner"])], "Decisions for a person")


def _decisions(dg: Dict[str, Any], decisions: List[Dict[str, Any]], title: str) -> None:
    if not decisions:
        return
    open_n = sum(1 for d in decisions if not d.get("taken"))
    hint = ("Choose an option and say why; the decision is recorded under your name"
            if _dc() is not None and _dc().can_decide else "Open issues the software will not settle")
    st.html(_group_head(title, hint, "decision", open_n if open_n else len(decisions)))
    if _dc() is None:
        st.html('<div class="rv-cards">' + "".join(_decision_card(d) for d in decisions) + "</div>")
    else:
        for d in decisions:
            decision_block(d)


def _agent_lists(dg: Dict[str, Any]) -> None:
    """What an agent produces besides risks and actions: obligations, requirements."""
    if dg.get("obligations"):
        body = _section_head("Legal obligations", "Computed from your answers; open one for what it means here",
                             sum(len(g["items"]) for g in dg["obligations"]))
        for g in dg["obligations"]:
            body += (f'<details class="rv-grp"><summary><div class="rv-group tone-neutral"><span class="dot"></span>'
                     f'<span class="name">{esc(g["title"])}</span><span class="rv-chip quiet tone-neutral">'
                     f'{len(g["items"])}</span></div></summary><div class="rv-cards one">'
                     + "".join(obligation_card(o, g["title"]) for o in g["items"]) + "</div></details>")
        st.html(body)
    if dg.get("evrs"):
        st.html(_section_head("Ethical value requirements", "Most pressing first; open one for its fit criterion and the risks it answers",
                              len(dg["evrs"])))
        if _rv() is not None:
            st.caption("Each requirement closes a gap the rule engine computed. Rejecting one does not delete it: "
                       "it is kept, marked as overridden by you with your reason, and recorded in the open issues.")
        _draw_cards([(e.get("id", ""), evr_card(e), str(e.get("statement") or "")) for e in dg["evrs"]], 6,
                    "requirements")


#: Deep-dive sections already drawn above the dropdown, so not repeated in it.
_SHOWN_ABOVE = {"findings", "obligations", "evrs"}


# ---------------------------------------------------------------------------
# Tier 3 — Deep dive
# ---------------------------------------------------------------------------


def _card_html(c: Dict[str, Any]) -> str:
    fields = []
    for lbl, value in c.get("fields") or []:
        if isinstance(value, (list, tuple)):
            items = []
            for v in value:
                cls = "flag" if "CONFLICT" in str(v) else ("new" if lbl.startswith("New") else "")
                items.append(f'<li class="{cls}">{esc(v)}</li>')
            fields.append(f"<dt>{esc(lbl)}</dt><dd><ul>{''.join(items)}</ul></dd>")
        else:
            fields.append(f"<dt>{esc(lbl)}</dt><dd>{esc(value)}</dd>")
    return (
        f'<div class="rv-card tone-{esc(c.get("tone") or "neutral")}">'
        '<div class="rv-card-top">'
        + "".join(chip(t, tone) for t, tone in c.get("tags") or [])
        + (f'<span class="rv-id">{esc(c["id"])}</span>' if c.get("id") else "")
        + "</div>"
        + (f'<div class="rv-card-title">{esc(c["title"])}</div>' if c.get("title") else "")
        + (f'<div class="rv-card-lead">{esc(c["lead"])}</div>' if c.get("lead") else "")
        + (f'<div class="rv-card-text">{_lead_split(c["body"])}</div>' if c.get("body") else "")
        + (f'<dl class="rv-meta">{"".join(fields)}</dl>' if fields else "")
        + (f'<div class="rv-card-foot">{_cites(c["cites"])}</div>' if c.get("cites") else "")
        + "</div>"
    )


def _blocks(blocks: List[Dict[str, Any]]) -> None:
    for b in blocks:
        t = b.get("type")
        if t == "text":
            body = _lead_split(b.get("text") or "")
            st.html(f'<div class="rv-text"><span class="lbl">{esc(b["label"])}</span>{body}</div>')
        elif t == "table":
            if b["rows"]:
                st.markdown(md_table(b["headers"], b["rows"]))
            else:
                st.html('<div class="rv-empty">None.</div>')
        elif t == "cards":
            st.html('<div class="rv-cards one">' + "".join(_card_html(c) for c in b["items"]) + "</div>")
        elif t == "bullets":
            if b["items"]:
                st.markdown("\n".join(f"- {str(x).replace(chr(10), ' ')}" for x in b["items"]))
        elif t == "note":
            st.caption(b["text"])


def _section(sec: Dict[str, Any]) -> None:
    st.html(f'<div class="rv-conclusion"><b>Conclusion</b>{esc(sec["conclusion"])}</div>')
    _blocks(sec["blocks"])


def _deep(dg: Dict[str, Any], skip: Sequence[str] = ()) -> None:
    analysis = [s for s in dg["deep"] if s.get("group") != "trace" and s.get("key") not in skip]
    trace = [s for s in dg["deep"] if s.get("group") == "trace"]
    tabs = st.tabs([s["title"] for s in analysis] + ["Traceability"])
    for tab, sec in zip(tabs, analysis):
        with tab:
            _section(sec)
    with tabs[-1]:
        st.caption("What the retrieved norms do not support, what was declared covered, and whether "
                   "the agent agrees with the rule engine.")
        for sec in trace:
            st.markdown(f"**{sec['title']}**")
            _section(sec)
    if dg.get("unparsed"):
        with st.container(border=True):
            st.markdown("**Unparsed model reply**")
            st.code(dg["unparsed"][:6000], language=None, wrap_lines=True)


def _deep_dive(dg: Dict[str, Any], key: str, nested: bool) -> None:
    label = "Deep dive — the analysis behind each point"
    if nested:
        # Streamlit does not nest expanders; inside one, a toggle opens the deep dive.
        if st.toggle(label, key=f"{key}::deep"):
            _deep(dg, _SHOWN_ABOVE)
        return
    with st.expander(label, icon=":material/manage_search:", expanded=False):
        _deep(dg, _SHOWN_ABOVE)


# ---------------------------------------------------------------------------
# User Story Refiner — the refined stories first
# ---------------------------------------------------------------------------


def _counts_strip(dg: Dict[str, Any]) -> str:
    c = dg["story_counts"]
    status = dg["status"]
    first = (D.plural(c.get("total", 0), "story", "stories") + " generated" if dg["agent_key"] == "story_generate"
             else f"{c.get('changed', 0)} of {c.get('total', 0)} stories changed")
    tags = [chip(first, "neutral", quiet=True),
            chip(D.plural(c.get("new", 0), "new criterion", "new criteria"), "ok" if c.get("new") else "neutral", quiet=True)]
    if c.get("conflicts"):
        tags.append(chip(D.plural(c["conflicts"], "conflict") + " to decide", "high"))
    return (f'<div class="rv rv-status tone-{status["tone"]}">' + chip(status["label"], status["tone"])
            + (f'<p class="rv-headline">{esc(dg["headline"])}</p>' if dg["headline"] else "")
            + '<div class="rv-tags">' + "".join(tags) + "</div></div>")


def _criterion(l: Dict[str, Any]) -> str:
    if l["kind"] == "kept":
        return (f'<li class="crit kept"><span class="mark" aria-hidden="true"></span>'
                f'<span class="cid">{esc(l["id"])}</span><span class="txt">{esc(l["text"])}</span></li>')
    if l["kind"] == "conflict":
        against = ", ".join(l["conflicts_with"]) or "an ethical requirement"
        return ('<li class="crit conflict"><span class="mark" aria-hidden="true">!</span>'
                f'<span class="cid">{esc(l["id"])}</span><span class="txt">'
                + (f'<del>{esc(l["text"])}</del>' if l["text"] else '<span class="rv-muted">Criterion not found</span>')
                + (f'<span class="rewrite"><b>Suggested</b> {esc(l["rewrite"])}</span>' if l["rewrite"] else "")
                + f'<span class="why">Conflicts with {esc(against)}: {esc(l["problem"] or "no reason given")}'
                + (f' · decision {esc(l["decision"])}' if l.get("decision") else "") + "</span></span></li>")
    meta = " · ".join(x for x in (f"Evidence: {l['evidence']}" if l["evidence"] else "", l["owner"], l["goal"],
                                  f"implements {', '.join(l['evr_ids'])}" if l["evr_ids"] else "") if x)
    return ('<li class="crit new"><span class="mark" aria-hidden="true">+</span>'
            f'<span class="cid">{esc(l["id"])}</span><span class="txt">{esc(l["text"])}'
            f'<span class="why">{esc(meta)}</span></span></li>')


def _story_card(v: Dict[str, Any], skip_new: bool = False) -> str:
    tags = []
    if v["n_conflicts"]:
        tags.append(chip(D.plural(v["n_conflicts"], "conflict"), "high"))
    if v["n_new"]:
        tags.append(chip(D.plural(v["n_new"], "new criterion", "new criteria"), "ok"))
    cards = "".join(chip(f"{c} {n}".strip(), "neutral", quiet=True) for c, n in v["cards"])
    return (
        f'<div class="rv-story tone-{esc(v["tone"])}">'
        '<div class="rv-story-head">'
        f'<span class="rv-story-id">{esc(v["id"])}</span>'
        f'<span class="rv-story-title">{esc(v["title"] or D.first_sentence(v["description"]) or v["id"])}</span>'
        + "".join(tags) + "</div>"
        + (f'<p class="rv-story-desc">{esc(v["description"])}</p>' if v["description"] else "")
        + (f'<div class="rv-muted">Implements {esc(", ".join(v.get("evr_ids") or []))}</div>' if v.get("evr_ids") else "")
        + '<div class="rv-story-lbl">Acceptance criteria</div>'
        + '<ul class="rv-crits">' + "".join(_criterion(l) for l in v["lines"]
                                           if not (skip_new and l["kind"] == "new")) + "</ul>"
        + (f'<div class="rv-story-why"><b>Why</b> {esc(v["why"])}</div>' if v["why"] else "")
        + (f'<div class="rv-tags">{cards}</div>' if cards else "")
        + "</div>"
    )


def _story_choices(v: Dict[str, Any], key: str, dg: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """One choice per conflict that has a rewrite: which version goes in the copy.

    When the conflict's decision can be taken here, the decision is the choice:
    choosing "Rewrite it" puts the rewrite in the copy, anything else keeps the
    original. One control, not two.
    """
    choices: Dict[str, str] = {}
    by_id = {d["id"]: d for d in (dg or {}).get("decisions") or []}
    for l in v["lines"]:
        if l["kind"] != "conflict" or not l["rewrite"]:
            continue
        d = by_id.get(l.get("decision") or "")
        if d is not None and _dc() is not None:
            taken = d.get("taken")
            if taken:
                choices[l["id"]] = "rewrite" if str(taken.get("choice", "")).lower().startswith("rewrite") else "keep"
                st.markdown(f"**{l['id']}** — decided; the copy follows the decision:")
            else:
                st.markdown(f"**{l['id']}** — decide which version stands (the copy follows your decision):")
                choices[l["id"]] = "rewrite"
            decision_block(d)
            continue
        picked = st.radio(
            f"In the copy, {l['id']} reads", ["rewrite", "keep"], horizontal=True,
            format_func=lambda o: "The suggested rewrite" if o == "rewrite" else "The original",
            key=f"{key}::copy::{v['id']}::{l['id']}",
        )
        choices[l["id"]] = picked or "rewrite"
    return choices


def _why(dg: Dict[str, Any], key: str) -> None:
    """The risks, actions and decisions behind the changes — secondary, on request."""
    if dg["summary"]:
        st.html(f'<div class="rv-text">{_lead_split(dg["summary"])}</div>')
    if _rv() is not None:
        # At the gate the risks are cards to review, like every other stage's.
        _findings(dg, key, flat=True, title="Risks the new criteria answer")
    elif dg["top_issues"]:
        st.html('<div class="rv-h"><h4>Main risks the new criteria answer</h4></div><div class="rv-issues">'
                + "".join(
                    f'<div class="rv-issue tone-{D.tone_of_priority(f.get("priority"))}">'
                    + chip(V.PRIORITY_LABELS.get(f.get("priority"), D.label(f.get("priority"))), D.tone_of_priority(f.get("priority")))
                    + f'<span class="t">{esc(str(f.get("title") or "").rstrip("."))}</span>'
                    + chip(D.principle_name(f.get("principle")), "neutral", quiet=True)
                    + f'<span class="rv-id">{esc(f.get("id"))}</span></div>' for f in dg["top_issues"])
                + "</div>")
    conflicts = {l.get("decision") for v in dg["stories"] for l in v["lines"] if l["kind"] == "conflict"}
    _actions({**dg, "decisions": [d for d in dg["decisions"] if not (_dc() and d["id"] in conflicts)]}, key,
             flat=True)
    log = next((sec for sec in dg["deep"] if sec.get("key") == "log"), None)
    if log and log["blocks"] and log["blocks"][0].get("type") == "bullets":
        st.html('<div class="rv-h"><h4>Sprint ethics log</h4></div>')
        _blocks(log["blocks"])
    st.html('<div class="rv-h"><h4>The analysis</h4><span class="rv-muted">Each risk in full, and the traceability '
            'behind the record</span></div>')
    _deep({**dg, "deep": [sec for sec in dg["deep"] if sec.get("key") not in ("log", "no_impact")]})


def _new_criteria_review(v: Dict[str, Any]) -> None:
    """The story's new criteria, one row each, with Accept / Reject."""
    new = [l for l in v["lines"] if l["kind"] == "new"]
    if not new:
        return
    st.caption("New ethical criteria — accept or reject each one")
    for l in new:
        review_card(l["id"], '<ul class="rv-crits rv-crit-row">' + _criterion(l) + "</ul>", l["text"])


def _story_layout(dg: Dict[str, Any], key: str, nested: bool, before=None) -> None:
    st.html(_counts_strip(dg))
    if before:
        before(dg)
    changed = [v for v in dg["stories"] if v["changed"]]
    plain = [v for v in dg["stories"] if not v["changed"]]
    if dg["agent_key"] == "story_generate":
        st.html('<div class="rv-h"><h4>Generated stories</h4><span class="rv-muted">They enter the backlog as '
                'RAI-n when approved; each implements the requirements it names</span></div>')
    else:
        st.html('<div class="rv-h"><h4>Refined stories</h4><span class="rv-muted">Changes marked; copy each '
                'new version back to your tracker</span></div>')
    if not changed:
        st.html('<div class="rv-empty">No story needed changes.</div>')
    all_choices: Dict[str, Dict[str, str]] = {}
    for v in changed:
        with st.container(border=True):
            st.html(_story_card(v, skip_new=_rv() is not None))
            _new_criteria_review(v) if _rv() is not None else None
            left, right = st.columns([3, 1], vertical_alignment="bottom")
            with left:
                all_choices[v["id"]] = _story_choices(v, key, dg)
            with right:
                with st.popover(f"Copy {v['id']}", icon=":material/content_copy:", width="stretch"):
                    st.caption("The story's new version. Use the copy button in the corner.")
                    st.code(D.story_text(v, all_choices[v["id"]]), language=None, wrap_lines=True)
    if plain:
        st.html('<div class="rv-h"><h4>No changes needed</h4></div><ul class="rv-plain">'
                + "".join(f'<li><span class="rv-story-id">{esc(v["id"])}</span>'
                          f'<b>{esc(v["title"] or D.first_sentence(v["description"]))}</b>'
                          + (f' <span class="rv-muted">— {esc(v["no_impact_reason"])}</span>' if v["no_impact_reason"] else "")
                          + "</li>" for v in plain) + "</ul>")
    if dg["stories"]:
        with st.popover("Copy all stories", icon=":material/content_copy:"):
            st.caption("Every story's new version, with your choices for each conflict.")
            st.code("\n\n".join(D.story_text(v, all_choices.get(v["id"])) for v in dg["stories"]),
                    language=None, wrap_lines=True)

    label = "Why these changes — the risks, actions and decisions behind them"
    if nested:
        if st.toggle(label, key=f"{key}::why"):
            _why(dg, key)
        return
    with st.expander(label, icon=":material/help:", expanded=False):
        _why(dg, key)


# ---------------------------------------------------------------------------
# Auditor — the audit report
# ---------------------------------------------------------------------------


def _sec(num: int, title: str, hint: str = "") -> str:
    return (f'<div class="rv-sec"><span class="num">{num}</span><h4>{esc(title)}</h4>'
            + (f'<span class="rv-muted">{esc(hint)}</span>' if hint else "") + "</div>")


def _blocks_html(blocks: List[Dict[str, Any]]) -> str:
    """Deep-dive blocks as HTML, for sections drawn inside the report."""
    out = []
    for b in blocks:
        t = b.get("type")
        if t == "text" and (b.get("text") or "").strip():
            out.append(f'<div class="rv-text"><span class="lbl">{esc(b["label"])}</span>{esc(b["text"])}</div>')
        elif t == "table":
            if b["rows"]:
                head = "".join(f"<th>{esc(h)}</th>" for h in b["headers"])
                body = "".join("<tr>" + "".join(f"<td>{esc(D.label(c) if c in (None, '') else c)}</td>" for c in r)
                               + "</tr>" for r in b["rows"])
                out.append(f'<table class="rv-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>')
            else:
                out.append('<div class="rv-empty">None.</div>')
        elif t == "note":
            out.append(f'<p class="rv-muted">{esc(b["text"])}</p>')
    return "".join(out)


def _report_html(dg: Dict[str, Any], split: bool = False):
    rp = dg["report"]
    op = rp["opinion"]
    out = ['<div class="rv-report look-auditor">',
           '<div class="rv-report-head"><div class="eyebrow">'
           f'<span class="raia-icon" aria-hidden="true">{esc(look("auditor").icon)}</span>Audit report</div>'
           f'<div class="title">{esc(rp["header"]["title"])}</div>'
           '<dl class="rv-report-meta">'
           + "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in rp["header"]["fields"])
           + "</dl></div>"]

    # 1. Opinion
    out.append(_sec(1, "Audit opinion", "Rated by code from the evidence"))
    out.append(f'<div class="rv-opinion tone-{esc(op["tone"])}">'
               f'<div class="rv-seal"><span class="k">Opinion</span><span class="v">{esc(op["label"])}</span></div>'
               '<div class="body">'
               + (f'<p class="rv-headline">{esc(dg["headline"])}</p>' if dg["headline"] else "")
               + (f'<p class="rv-summary">{esc(dg["summary"])}</p>' if dg["summary"] else "")
               + (f'<p class="rv-rule"><b>Why this rating</b> {esc("; ".join(op["reasons"]))}. '
                  f'<span class="rv-muted">{esc(op["rule"])}</span></p>' if op["computed"] else "")
               + "</div></div>")
    out.append(_signature(dg))

    # 2-5. The project as a whole (when it has a backlog)
    n = 1
    for sec in rp.get("project") or []:
        n += 1
        out.append(_sec(n, sec["title"]))
        out.append(f'<div class="rv-conclusion tone-{esc(sec.get("tone", "neutral"))}"><b>Conclusion</b>'
                   f'{esc(sec["conclusion"])}</div>')
        out.append(_blocks_html(sec["blocks"]))

    # Strengths
    n += 1
    out.append(_sec(n, "Strengths", "Each rests on verified evidence or an approval on record"))
    if rp["strengths"]:
        out.append('<ul class="rv-points ok">' + "".join(
            f'<li><span class="raia-icon" aria-hidden="true">check_circle</span><div><b>{esc(x["statement"])}</b>'
            + (f'<span class="rv-muted"> {esc(x["evidence"])}</span>' if x["evidence"] else "")
            + (f' <span class="rv-id">{esc(", ".join(x["refs"]))}</span>' if x["refs"] else "") + "</div></li>"
            for x in rp["strengths"]) + "</ul>")
    else:
        out.append('<div class="rv-empty">' + ("None the evidence supports yet: a strength needs a satisfied item or an "
                                                "approval on record." if rp["has_strength_field"]
                                                else "Not assessed in this record version.") + "</div>")

    # Risks
    n += 1
    out.append(_sec(n, "Risks", "What the audit found, and what to do about it"))
    risk_cards: List[Tuple[str, str, str]] = []
    if rp["risks"]:
        cards = []
        for r in rp["risks"]:
            required = "".join(f'<div class="ln"><b>{esc(i)}</b> {esc(t)}' + (f' <span class="rv-muted">({esc(v.lower())})</span>' if v else "")
                               + "</div>" for i, t, v in r["required"])
            recs = "".join(f'<div class="ln"><b>{esc(a["id"])}</b> {esc(a["text"])} <span class="rv-muted">— {esc(a["owner"])}, '
                           f'{esc(a["when"])}</span></div>' for a in r["recommendation"])
            cards.append(
                f'<div class="rv-obs tone-{esc(r["tone"])}"><div class="rv-card-top">'
                + chip(V.PRIORITY_LABELS.get(r["priority"], D.label(r["priority"])), r["tone"])
                + (chip("Blocking", "critical") if r["blocking"] else "")
                + chip(r["principle"], "neutral", quiet=True) + f'<span class="rv-id">{esc(r["id"])}</span></div>'
                f'<div class="rv-card-title">{esc(r["title"])}</div><dl class="rv-meta">'
                f'<dt>Found</dt><dd>{esc(r["found"])}</dd>'
                + (f"<dt>Required</dt><dd>{required}</dd>" if required else "")
                + (f'<dt>Affects</dt><dd>{esc(r["matters"])}</dd>' if r["matters"] else "")
                + (f"<dt>Recommendation</dt><dd>{recs}</dd>" if recs else
                   "<dt>Recommendation</dt><dd>Decided by a person — see Decisions required.</dd>")
                + "</dl>" + (f'<div class="rv-card-foot">{_cites(r["cites"])}</div>' if r["cites"] else "") + "</div>")
            risk_cards.append((r["id"], cards[-1].replace('<div class="rv-obs', f'<div id="card-{esc(r["id"])}" class="rv-obs', 1),
                               r["title"]))
        out.append("<!--RISKS-->" if split else '<div class="rv-cards one">' + "".join(c for _, c, _ in risk_cards) + "</div>")
    else:
        out.append('<div class="rv-empty">No risks were identified.</div>')

    # Opportunities
    n += 1
    out.append(_sec(n, "Opportunities", "Improvements beyond closing the gaps"))
    if rp["opportunities"]:
        out.append('<ul class="rv-points idea">' + "".join(
            f'<li><span class="raia-icon" aria-hidden="true">lightbulb</span><div><b>{esc(x["statement"])}</b>'
            + (f'<span class="rv-muted"> {esc(x["benefit"])}</span>' if x["benefit"] else "")
            + (f' <span class="rv-id">{esc(", ".join(x["refs"]))}</span>' if x["refs"] else "") + "</div></li>"
            for x in rp["opportunities"]) + "</ul>")
    else:
        out.append('<div class="rv-empty">' + ("None stated." if rp["has_strength_field"]
                                                else "Not assessed in this record version.") + "</div>")

    # 5. Pathway
    pw = rp["pathway"]
    n += 1
    out.append(_sec(n, "Pathway forward", "In the order to take it"))
    if pw["summary"]:
        out.append(f'<p class="rv-path-sum">{esc(pw["summary"])}</p>')
    if pw["phases"]:
        out.append('<ol class="rv-path">')
        for ph in pw["phases"]:
            entries = "".join(
                '<li class="e">' + (f'<span class="rv-id">{esc(e["id"])}</span>' if e["id"] else "")
                + f'<span class="t">{esc(e["text"])}</span>'
                + '<span class="m">' + esc(" · ".join(x for x in (e["owner"], e["when"]) if x))
                + (f' · done when {esc(e["done"])}' if e["done"] and e["kind"] == "action" else "")
                + (f' · options: {esc(e["done"])}' if e["done"] and e["kind"] == "decision" else "")
                + (f' · {esc(e["done"])}' if e["done"] and e["kind"] == "checkpoint" else "")
                + "</span></li>" for e in ph["entries"])
            out.append(f'<li class="phase tone-{esc(ph["tone"])}"><div class="ph"><span class="dot"></span>'
                       f'<span class="name">{esc(ph["title"])}</span>'
                       f'<span class="rv-chip quiet tone-{esc(ph["tone"])}">{len(ph["entries"])}</span>'
                       f'<span class="rv-muted">{esc(ph["hint"])}</span></div><ul>{entries}</ul></li>')
        out.append("</ol>")
    else:
        out.append('<div class="rv-empty">Nothing to do: the audit found no gap.</div>')
    out.append("</div>")
    if split:
        # The observations are drawn with Streamlit between the two halves, each
        # half closed and reopened so both stay well-formed.
        head, _, tail = "".join(out).partition("<!--RISKS-->")
        return (head + "</div>", risk_cards, '<div class="rv-report look-auditor rv-report-cont">' + tail)
    return "".join(out)


def _appendices(dg: Dict[str, Any]) -> None:
    by_key = {sec["key"]: sec for sec in dg["deep"]}
    tabs = st.tabs(["Decisions", "Verdict register", "Accountability", "Traceability"])
    with tabs[0]:
        if dg["decisions"]:
            st.html('<div class="rv-cards one">' + "".join(_decision_card(d) for d in dg["decisions"]) + "</div>")
        else:
            st.html('<div class="rv-empty">No decision is open.</div>')
    for tab, k in ((tabs[1], "register"), (tabs[2], "accountability")):
        with tab:
            if k in by_key:
                _section(by_key[k])
    with tabs[3]:
        st.caption("What the retrieved norms do not support, what was declared covered, and whether "
                   "the agent agrees with the rule engine.")
        for sec in dg["deep"]:
            if sec.get("group") == "trace":
                st.markdown(f"**{sec['title']}**")
                _section(sec)
    if dg.get("unparsed"):
        with st.container(border=True):
            st.markdown("**Unparsed model reply**")
            st.code(dg["unparsed"][:6000], language=None, wrap_lines=True)


def _audit_layout(dg: Dict[str, Any], key: str, nested: bool, before=None) -> None:
    if before:
        before(dg)
    if _rv() is None:
        st.html(_report_html(dg))
    else:
        head, risks, tail = _report_html(dg, split=True)
        st.html(head)
        _draw_cards(risks, 50, "observations", flat=True)
        st.html(tail)
    label = "Appendices — decisions, verdict register, accountability, traceability"
    if nested:
        if st.toggle(label, key=f"{key}::appx"):
            _appendices(dg)
        return
    with st.expander(label, icon=":material/folder_open:", expanded=False):
        _appendices(dg)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def record_view(agent_key: str, record: Dict[str, Any], computed_data: Optional[Dict[str, Any]] = None,
                *, key: str, nested: bool = False, fallback_markdown: str = "",
                review: Optional[CardReview] = None, decide: Optional[Decisions] = None,
                before: Optional[Callable[[Dict[str, Any]], None]] = None) -> None:
    """Draw one record in the three tiers. ``key`` makes widget keys unique on the page.

    ``review`` puts Accept / Reject on every reviewable card (the gate);
    ``decide`` lets a person take each decision where it is shown; ``before``
    draws something between the status and the rest (the hand-off strip).
    """
    if not record:
        # An artifact written before the standard record existed: shown as it was approved.
        st.markdown(fallback_markdown or "_Nothing to show._")
        return
    if review is not None:
        review.titles = {c["id"]: c["title"] for c in RV.cards(agent_key, record)}
    _CTX.review, _CTX.decide = review, decide
    try:
        _record_view(agent_key, record, computed_data, key, nested, decide, before)
    finally:
        _CTX.review, _CTX.decide = None, None


def _record_view(agent_key: str, record: Dict[str, Any], computed_data: Optional[Dict[str, Any]], key: str,
                 nested: bool, decide: Optional[Decisions], before) -> None:
    dg = D.build(agent_key, record, computed_data or {}, taken=decide.taken if decide else None)
    for n in dg["notices"]:
        st.html(f'<div class="rv-notice">{esc(n)}</div>')
    # A reply that could not be read as a record has no stories and no report to
    # lead with: it is shown in the shared layout, with the notice above.
    if agent_key in D.STORY_KEYS and not record.get("schema_errors"):
        _story_layout(dg, key, nested, before)
        return
    if agent_key == "auditor" and not record.get("schema_errors"):
        _audit_layout(dg, key, nested, before)
        return
    _summary(dg, before)
    if not V.writes_findings(agent_key):
        # Requirements, not risks: the requirements lead, then the decisions.
        _agent_lists(dg)
        _actions(dg, key)
    elif not V.writes_actions(agent_key):
        # An analysis: the risks, the decisions on it, then its own lists.
        _findings(dg, key)
        _actions(dg, key)
        _agent_lists(dg)
    else:
        _findings(dg, key)
        _actions(dg, key)
        _agent_lists(dg)
    _deep_dive(dg, key, nested)


def record_from_data(data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """(record, computed data) from what the repository stores beside an approved artifact."""
    structured = (data or {}).get("structured", data or {}) or {}
    return structured.get("record") or {}, structured


__all__ = ["record_view", "record_from_data", "I"]
