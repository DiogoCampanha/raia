"""
raia.ui.record_view
===================

How a RAIA record looks on screen, for every agent, wherever it is shown — a
draft at the approval gate, the approved version on a stage page, a document
in the project.

RAIA is a work tool. The record is read top to bottom and can be put down at
any point:

1. **Summary** — status and headline, four numbers, the main issues and the
   principles they touch.
2. **What to do** — action cards grouped Do now / Plan / Track, then the
   decisions only a person can take; a filter shows one owner's share.
3. **Deep dive** — behind a dropdown, one tab per topic, each opening with its
   conclusion; the traceability appendix last.

The content comes from :func:`raia.contract.digest.build`, the same digest the
exported Markdown is written from, so the screen and the document agree.
Static parts are drawn as HTML with the classes in ``theme.css``; everything a
person clicks is a native Streamlit widget.
"""

from __future__ import annotations

import html
from typing import Any, Dict, List, Optional, Sequence, Tuple

import streamlit as st

from raia.contract import digest as D
from raia.contract import vocab as V
from raia.contract.render import table as md_table

from .theme import I


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


def _summary(dg: Dict[str, Any]) -> None:
    status = dg["status"]
    parts = [
        f'<div class="rv rv-status tone-{status["tone"]}">',
        chip(status["label"], status["tone"]),
        f'<p class="rv-headline">{esc(dg["headline"])}</p>' if dg["headline"] else "",
        f'<p class="rv-summary">{esc(dg["summary"])}</p>' if dg["summary"] else "",
        "</div>",
        '<div class="rv-kpis">',
    ]
    for k in dg["kpis"]:
        parts.append(
            f'<div class="rv-kpi tone-{esc(k["tone"])}" role="group" aria-label="{esc(k["label"])}">'
            f'<div class="rv-kpi-label">{esc(k["label"])}</div>'
            f'<div class="rv-kpi-value">{esc(k["value"])}</div>'
            f'<div class="rv-kpi-hint">{esc(k["hint"])}</div></div>'
        )
    parts.append("</div>")

    if dg["top_issues"]:
        parts.append('<div class="rv-h"><h4>Main issues</h4></div><div class="rv-issues">')
        for f in dg["top_issues"]:
            tone = D.tone_of_priority(f.get("priority"))
            parts.append(
                f'<div class="rv-issue tone-{tone}">'
                + chip(V.PRIORITY_LABELS.get(f.get("priority"), D.label(f.get("priority"))), tone)
                + (chip("Blocking", "critical") if f.get("blocking") else "")
                + f'<span class="t">{esc(str(f.get("title") or "").rstrip("."))}</span>'
                + chip(D.principle_name(f.get("principle")), "neutral", quiet=True)
                + f'<span class="rv-id">{esc(f.get("id"))}</span></div>'
            )
        parts.append("</div>")
    if dg["principles"]:
        parts.append('<div class="rv-tags"><span class="lbl">Risk areas</span>'
                     + "".join(chip(name, "neutral", quiet=True, n=count) for name, count in dg["principles"])
                     + "</div>")
    st.html("".join(parts))


# ---------------------------------------------------------------------------
# Tier 2 — What to do
# ---------------------------------------------------------------------------


def _action_card(a: Dict[str, Any]) -> str:
    return (
        f'<div class="rv-card tone-{a["tone"]}">'
        '<div class="rv-card-top">'
        + chip(V.PRIORITY_LABELS.get(a["priority"], a["priority"]), a["tone"])
        + (chip("Blocking", "critical") if a["blocking"] else "")
        + chip(a["owner_label"], "neutral", quiet=True)
        + f'<span class="rv-id">{esc(a["id"])}</span></div>'
        f'<div class="rv-card-title">{esc(a["text"])}</div>'
        '<dl class="rv-meta">'
        f'<dt>When</dt><dd>{esc(a["when"])}</dd>'
        f'<dt>Done when</dt><dd>{esc(a["done_when"])}</dd>'
        "</dl>"
        '<div class="rv-card-foot">'
        + (f'Answers {esc(", ".join(a["findings"]))} · ' if a["findings"] else "")
        + f'Response: {esc(a["response"])}</div>'
        + (f'<div class="rv-card-foot">{_cites(a["cites"])}</div>' if a["cites"] else "")
        + "</div>"
    )


def _decision_card(d: Dict[str, Any]) -> str:
    return (
        f'<div class="rv-card tone-{d["tone"]}">'
        '<div class="rv-card-top">'
        + chip("Decision needed", "decision")
        + (chip("Blocking", "critical") if d["blocking"] else "")
        + chip(d["owner_label"], "neutral", quiet=True)
        + f'<span class="rv-id">{esc(d["id"])}</span></div>'
        f'<div class="rv-card-text">{esc(d["text"])}</div>'
        + ('<div class="rv-options">' + "".join(f'<span class="opt">{esc(o)}</span>' for o in d["options"]) + "</div>"
           if d["options"] else "")
        + f'<div class="rv-card-foot">{esc(d["type_label"])} · raised by {esc(d["origin"])}</div>'
        "</div>"
    )


def _group_head(title: str, hint: str, tone: str, count: int) -> str:
    return (f'<div class="rv-group tone-{tone}"><span class="dot"></span><span class="name">{esc(title)}</span>'
            f'<span class="rv-chip quiet tone-{tone}">{count}</span><span class="rv-muted">{esc(hint)}</span></div>')


def _actions(dg: Dict[str, Any], key: str) -> None:
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
    for g in dg["action_groups"]:
        items = [a for a in g["actions"] if keep(a["owner"])]
        if not items:
            continue
        shown_any = True
        st.html(_group_head(g["title"], g["hint"], g["tone"], len(items))
                + '<div class="rv-cards">' + "".join(_action_card(a) for a in items) + "</div>")
    if not shown_any:
        st.html('<div class="rv-empty">'
                + ("No actions for the selected owners." if picked and dg["actions"] else "No actions at this stage.")
                + "</div>")

    decisions = [d for d in dg["decisions"] if keep(d["owner"])]
    if decisions:
        st.html(_group_head("Decisions for a person", "Open issues the software will not settle", "decision",
                            len(decisions))
                + '<div class="rv-cards">' + "".join(_decision_card(d) for d in decisions) + "</div>")

    if dg.get("paste"):
        with st.popover("Updated stories, ready to paste", icon=":material/content_copy:"):
            st.caption("Each story with its own criteria, conflicts marked for review, and the new "
                       "ethical criteria added. Use the copy button in the corner.")
            st.code(dg["paste"], language=None, wrap_lines=True)


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


def _deep(dg: Dict[str, Any]) -> None:
    analysis = [s for s in dg["deep"] if s.get("group") != "trace"]
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
            _deep(dg)
        return
    with st.expander(label, icon=":material/manage_search:", expanded=False):
        _deep(dg)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def record_view(agent_key: str, record: Dict[str, Any], computed_data: Optional[Dict[str, Any]] = None,
                *, key: str, nested: bool = False, fallback_markdown: str = "") -> None:
    """Draw one record in the three tiers. ``key`` makes widget keys unique on the page."""
    if not record:
        # An artifact written before the standard record existed: shown as it was approved.
        st.markdown(fallback_markdown or "_Nothing to show._")
        return
    dg = D.build(agent_key, record, computed_data or {})
    for n in dg["notices"]:
        st.html(f'<div class="rv-notice">{esc(n)}</div>')
    _summary(dg)
    _actions(dg, key)
    _deep_dive(dg, key, nested)


def record_from_data(data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """(record, computed data) from what the repository stores beside an approved artifact."""
    structured = (data or {}).get("structured", data or {}) or {}
    return structured.get("record") or {}, structured


__all__ = ["record_view", "record_from_data", "I"]
