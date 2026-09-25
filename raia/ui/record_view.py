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
from typing import Any, Dict, List, Optional, Sequence, Tuple

import streamlit as st

from raia.contract import digest as D
from raia.contract import vocab as V
from raia.contract.render import table as md_table

from .theme import I, look


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
    elif kind == "series":
        pts = sig["points"]
        thr = sig.get("threshold")
        top = max([p["value"] for p in pts] + ([thr] if isinstance(thr, (int, float)) else [])) * 1.2 or 1
        bars = "".join(f'<div class="sig-bar tone-{esc(p["tone"])}" style="height:{max(p["value"] / top * 100, 2):.1f}%"'
                       f' title="{esc(p["label"])}: {p["value"]:g}"></div>' for p in pts)
        line = (f'<div class="sig-thr" style="bottom:{thr / top * 100:.1f}%"><span>threshold {thr:g}</span></div>'
                if isinstance(thr, (int, float)) else "")
        labels = "".join(f'<div class="sig-x"><b>{p["value"]:g}</b> {esc(p["label"])}'
                         + (f' · <span class="flag">{esc(p["note"])}</span>' if p["note"] else "") + "</div>"
                         for p in pts)
        out.append(f'<div class="sig-plot">{line}{bars}</div><div class="sig-xs">{labels}</div>')
    if sig.get("caption"):
        out.append(f'<p class="rv-sig-cap">{esc(sig["caption"])}</p>')
    out.append("</div>")
    return "".join(out)


def _summary(dg: Dict[str, Any]) -> None:
    status = dg["status"]
    parts = [
        f'<div class="rv rv-status tone-{status["tone"]}">',
        chip(status["label"], status["tone"]),
        f'<p class="rv-headline">{esc(dg["headline"])}</p>' if dg["headline"] else "",
        f'<p class="rv-summary">{esc(dg["summary"])}</p>' if dg["summary"] else "",
        "</div>",
        _signature(dg),
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
# User Story Refiner — the refined stories first
# ---------------------------------------------------------------------------


def _counts_strip(dg: Dict[str, Any]) -> str:
    c = dg["story_counts"]
    status = dg["status"]
    tags = [chip(f"{c.get('changed', 0)} of {c.get('total', 0)} stories changed", "neutral", quiet=True),
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


def _story_card(v: Dict[str, Any]) -> str:
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
        + '<div class="rv-story-lbl">Acceptance criteria</div>'
        + '<ul class="rv-crits">' + "".join(_criterion(l) for l in v["lines"]) + "</ul>"
        + (f'<div class="rv-story-why"><b>Why</b> {esc(v["why"])}</div>' if v["why"] else "")
        + (f'<div class="rv-tags">{cards}</div>' if cards else "")
        + "</div>"
    )


def _story_choices(v: Dict[str, Any], key: str) -> Dict[str, str]:
    """One choice per conflict that has a rewrite: which version goes in the copy."""
    choices: Dict[str, str] = {}
    for l in v["lines"]:
        if l["kind"] != "conflict" or not l["rewrite"]:
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
    if dg["top_issues"]:
        st.html('<div class="rv-h"><h4>Main risks the new criteria answer</h4></div><div class="rv-issues">'
                + "".join(
                    f'<div class="rv-issue tone-{D.tone_of_priority(f.get("priority"))}">'
                    + chip(V.PRIORITY_LABELS.get(f.get("priority"), D.label(f.get("priority"))), D.tone_of_priority(f.get("priority")))
                    + f'<span class="t">{esc(str(f.get("title") or "").rstrip("."))}</span>'
                    + chip(D.principle_name(f.get("principle")), "neutral", quiet=True)
                    + f'<span class="rv-id">{esc(f.get("id"))}</span></div>' for f in dg["top_issues"])
                + "</div>")
    _actions(dg, key)
    log = next((sec for sec in dg["deep"] if sec.get("key") == "log"), None)
    if log and log["blocks"] and log["blocks"][0].get("type") == "bullets":
        st.html('<div class="rv-h"><h4>Sprint ethics log</h4></div>')
        _blocks(log["blocks"])
    st.html('<div class="rv-h"><h4>The analysis</h4><span class="rv-muted">Each risk in full, and the traceability '
            'behind the record</span></div>')
    _deep({**dg, "deep": [sec for sec in dg["deep"] if sec.get("key") not in ("log", "no_impact")]})


def _story_layout(dg: Dict[str, Any], key: str, nested: bool) -> None:
    st.html(_counts_strip(dg))
    changed = [v for v in dg["stories"] if v["changed"]]
    plain = [v for v in dg["stories"] if not v["changed"]]
    st.html('<div class="rv-h"><h4>Refined stories</h4><span class="rv-muted">Changes marked; copy each '
            'new version back to your tracker</span></div>')
    if not changed:
        st.html('<div class="rv-empty">No story needed changes.</div>')
    all_choices: Dict[str, Dict[str, str]] = {}
    for v in changed:
        with st.container(border=True):
            st.html(_story_card(v))
            left, right = st.columns([3, 1], vertical_alignment="bottom")
            with left:
                all_choices[v["id"]] = _story_choices(v, key)
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


def _report_html(dg: Dict[str, Any]) -> str:
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

    # 2. Strengths
    out.append(_sec(2, "Strengths", "Each rests on verified evidence or an approval on record"))
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

    # 3. Risks
    out.append(_sec(3, "Risks", "What the audit found, and what to do about it"))
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
        out.append('<div class="rv-cards one">' + "".join(cards) + "</div>")
    else:
        out.append('<div class="rv-empty">No risks were identified.</div>')

    # 4. Opportunities
    out.append(_sec(4, "Opportunities", "Improvements beyond closing the gaps"))
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
    out.append(_sec(5, "Pathway forward", "In the order to take it"))
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


def _audit_layout(dg: Dict[str, Any], key: str, nested: bool) -> None:
    st.html(_report_html(dg))
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
                *, key: str, nested: bool = False, fallback_markdown: str = "") -> None:
    """Draw one record in the three tiers. ``key`` makes widget keys unique on the page."""
    if not record:
        # An artifact written before the standard record existed: shown as it was approved.
        st.markdown(fallback_markdown or "_Nothing to show._")
        return
    dg = D.build(agent_key, record, computed_data or {})
    for n in dg["notices"]:
        st.html(f'<div class="rv-notice">{esc(n)}</div>')
    # A reply that could not be read as a record has no stories and no report to
    # lead with: it is shown in the shared layout, with the notice above.
    if agent_key == "story_refiner" and not record.get("schema_errors"):
        _story_layout(dg, key, nested)
        return
    if agent_key == "auditor" and not record.get("schema_errors"):
        _audit_layout(dg, key, nested)
        return
    _summary(dg)
    _actions(dg, key)
    _deep_dive(dg, key, nested)


def record_from_data(data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """(record, computed data) from what the repository stores beside an approved artifact."""
    structured = (data or {}).get("structured", data or {}) or {}
    return structured.get("record") or {}, structured


__all__ = ["record_view", "record_from_data", "I"]
