"""
raia.ui.components
==================

The small set of building blocks every page is made of. Keeping them here is
what makes the pages look like one product: one page header, one stat tile,
one status badge, one stage tracker.
"""

from __future__ import annotations

import html
from typing import Any, Dict, Iterable, List, Optional, Tuple

import streamlit as st

from raia.lineage import next_steps

from . import routes
from .theme import I, LAYER_CLASS, RISK, ROLE, STATUS, look, look_key


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def page_header(title: str, subtitle: str = "", eyebrow: str = "",
                back: Optional[Tuple[str, str, Dict[str, str]]] = None) -> None:
    """Title block. ``back`` is (label, route, query params) for the parent page."""
    if back:
        label, route, params = back
        routes.link(route, label, icon=I.BACK, **params)
    st.html(
        '<header class="raia-header">'
        + (f'<p class="raia-eyebrow">{esc(eyebrow)}</p>' if eyebrow else "")
        + f'<h1 class="raia-title">{esc(title)}</h1>'
        + (f'<p class="raia-subtitle">{esc(subtitle)}</p>' if subtitle else "")
        + "</header>"
    )


def rule() -> None:
    """A thin separator for rows inside a card (st.divider is too tall there)."""
    st.html('<hr class="raia-rule">')


def artifact_body(markdown: str) -> str:
    """An approved artifact without its machine-readable provenance comment."""
    text = markdown or ""
    if text.lstrip().startswith("<!--"):
        end = text.find("-->")
        if end != -1:
            text = text[end + 3:]
    return text.lstrip()


def stat_tiles(tiles: Iterable[Tuple[str, object, str, bool]]) -> None:
    """Row of (label, value, hint, needs_attention) tiles."""
    cells = []
    for label, value, hint, attention in tiles:
        cls = "raia-stat is-attention" if attention else "raia-stat"
        cells.append(
            f'<div class="{cls}" role="group" aria-label="{esc(label)}">'
            f'<div class="raia-stat-label">{esc(label)}</div>'
            f'<div class="raia-stat-value">{esc(value)}</div>'
            + (f'<div class="raia-stat-hint">{esc(hint)}</div>' if hint else "")
            + "</div>"
        )
    st.html('<div class="raia-stats">' + "".join(cells) + "</div>")


def _md_badge(label: str, color: str, icon: Optional[str] = None) -> str:
    safe = label.replace("[", "(").replace("]", ")")
    return f":{color}-badge[{icon + ' ' if icon else ''}{safe}]"


def status_md(status: str) -> str:
    label, color, icon = STATUS[status]
    return _md_badge(label, color, icon)


def risk_md(risk: Dict[str, str]) -> str:
    color, icon = RISK.get(risk.get("level", "none"), RISK["none"])
    return _md_badge(risk.get("label", "Not assessed"), color, icon)


def role_md(role: str) -> str:
    label, icon = ROLE.get(role, (role, None))
    return _md_badge(label, "gray", icon)


def status_badge(status: str) -> None:
    label, color, icon = STATUS[status]
    st.badge(label, icon=icon, color=color)


def risk_badge(risk: Dict[str, str]) -> None:
    color, icon = RISK.get(risk.get("level", "none"), RISK["none"])
    st.badge(risk.get("label", "Not assessed"), icon=icon, color=color,
             help=("EU AI Act: " + risk["eu_tier"] + (" · PL 2338/2023: " + risk["br_tier"]
                                                       if risk.get("br_tier") else ""))
             if risk.get("eu_tier") else "No approved risk classification yet.")


def role_badge(role: str) -> None:
    label, icon = ROLE.get(role, (role, None))
    st.badge(label, icon=icon, color="gray")


def role_label(role: str) -> str:
    return ROLE.get(role, (role, None))[0]


def layer_tag(layer: str) -> str:
    return (f'<span class="raia-layer-tag {LAYER_CLASS.get(layer, "")}">'
            f'<span class="raia-dot"></span>{esc(layer)}</span>')


def empty_state(title: str, body: str) -> None:
    st.html(f'<div class="raia-empty"><h4>{esc(title)}</h4><p>{esc(body)}</p></div>')


def section(title: str, caption: str = "") -> None:
    st.subheader(title)
    if caption:
        st.caption(caption)


def icon_html(name: str) -> str:
    """A Material Symbols glyph inside HTML we draw ourselves (decorative)."""
    return f'<span class="raia-icon" aria-hidden="true">{esc(name)}</span>'


def stage_tracker(project_id: str, stages: List[Dict[str, object]], current: str = "",
                  key_prefix: str = "trk") -> None:
    """The five stages as a row of cards (project page). Each card opens its stage."""
    cols = st.columns(len(stages), gap="small")
    for i, (col, s) in enumerate(zip(cols, stages), start=1):
        agent = str(s["agent"])
        with col, st.container(border=True, key=look_key(agent, f"{key_prefix}-trk")):
            st.html(f'<div style="display:flex;justify-content:space-between;align-items:center">'
                    f'{layer_tag(str(s["layer"]))}'
                    f'<span class="raia-meta">{"Current" if agent == current else f"Step {i}"}</span></div>')
            if st.button(str(s["name"]), key=f"{key_prefix}_{agent}", type="tertiary", icon=look(agent).material,
                         help=f"Open the {s['name']} stage", disabled=agent == current):
                routes.go(routes.STAGE, project=project_id, agent=agent)
            status_badge(str(s["status"]))


# ---- Stage pages: identity and navigation ---------------------------------------------

def agent_header(agent_key: str, name: str, description: str, eyebrow: str, status: str = "",
                 back: Optional[Tuple[str, str, Dict[str, str]]] = None, compact: bool = False) -> None:
    """A stage's page header, in the agent's own colour, icon and pattern.

    The header carries its agent's class, so it needs no enclosing container.
    The status keeps its text label: colour is never the only cue. ``compact``
    draws it as a banner inside another page (the Agents page), without a title.
    """
    lk = look(agent_key)
    if back:
        label, route, params = back
        routes.link(route, label, icon=I.BACK, **params)
    chip = ""
    if status:
        label, _, _ = STATUS[status]
        tone = {"approved": "ok", "stale": "high", "in_review": "decision"}.get(status, "neutral")
        chip = f'<span class="rv-chip tone-{tone}">{esc(label)}</span>'
    title = "" if compact else f'<h1 class="raia-title">{esc(name)}</h1>'
    st.html(
        f'<header class="agent-hero raia-header look-{esc(agent_key)}{" is-compact" if compact else ""}"'
        f' data-agent="{esc(agent_key)}">'
        f'<div class="agent-hero-icon">{icon_html(lk.icon)}</div>'
        '<div class="agent-hero-text">'
        f'<div class="agent-hero-top"><p class="agent-hero-eyebrow">{esc(eyebrow)}</p>{chip}</div>'
        + title
        + (f'<p class="agent-hero-q">{esc(lk.question)}</p>' if lk.question else "")
        + (f'<p class="agent-hero-desc">{esc(description)}</p>' if description else "")
        + "</div></header>"
    )


def stage_rail(project_id: str, stages: List[Dict[str, Any]], current: str) -> None:
    """The five stages as a compact, always-visible stepper on a stage page."""
    cols = st.columns(len(stages), gap="small")
    for i, (col, s) in enumerate(zip(cols, stages), start=1):
        agent = str(s["agent"])
        here = agent == current
        label, _, _ = STATUS[str(s["status"])]
        with col, st.container(key=look_key(agent, "rail-current" if here else "rail"), gap=None):
            if here:
                st.html(f'<div class="rail-name">{icon_html(look(agent).icon)}{esc(s["name"])}</div>')
            elif st.button(str(s["name"]), key=f"rail_{agent}", type="tertiary", icon=look(agent).material,
                           help=f"Open the {s['name']} stage"):
                routes.go(routes.STAGE, project=project_id, agent=agent)
            st.html(f'<div class="rail-meta s-{esc(s["status"])}"><span class="raia-dot"></span>'
                    f'{"You are here · " if here else f"Step {i} · "}{esc(label)}</div>')


def step_verb(stage: Dict[str, Any], can_run: bool) -> str:
    """What going to a stage means for this person: the words on the button."""
    status = stage["status"]
    if status == "stale":
        return f"Re-check {stage['name']}"
    if status == "in_review":
        return f"Review {stage['name']}"
    if status == "ready" and can_run:
        return f"Continue to {stage['name']}"
    return f"Open {stage['name']}"


def step_reason(stage: Dict[str, Any]) -> str:
    status = stage["status"]
    if status == "stale":
        names = stage.get("stale_because_names") or []
        return ("Upstream work changed after it was approved"
                + (f" ({', '.join(names)})" if names else "") + ". Confirm it still holds, or revise it.")
    if status == "in_review":
        return "A draft is waiting for a human decision."
    if status == "ready":
        return "Its upstream work is approved, so it can run now."
    return ""


def next_step_card(project_id: str, stages: List[Dict[str, Any]], agent_key: str,
                   done: Dict[str, Any], can_run: bool) -> None:
    """Shown on a stage right after it is approved: what was recorded, and where to go next."""
    with st.container(border=True, key=look_key(agent_key, "done")):
        if not done.get("shown"):
            # The Approve button sat at the foot of a long draft, and Streamlit
            # keeps the scroll position across the redraw; bring the card into
            # view once, so the next step is the first thing the person sees.
            done["shown"] = True
            st.html("<script>setTimeout(() => document.querySelector('.next-head')"
                    "?.scrollIntoView({behavior: 'smooth', block: 'center'}), 350)</script>",
                    unsafe_allow_javascript=True)
        commit = str(done.get("commit") or "")
        st.html('<div class="next-head">' + icon_html("check_circle")
                + "<strong>Approved and committed</strong>"
                + (f"<code>{esc(commit)}</code>" if commit else "") + "</div>")
        flagged = done.get("flagged") or []
        if flagged:
            st.caption("These stages were approved against the previous version and are now flagged "
                       "for review: **" + "**, **".join(flagged) + "**. Nothing was re-run.")
        steps = next_steps(stages, after=agent_key)
        if not steps:
            st.markdown("**All five stages are approved.** When you are done, please complete the "
                        "**Assessment**: it is the evidence the study depends on.")
            row = st.container(horizontal=True, key=look_key(agent_key, "next-row"))
            if row.button("Complete the assessment", type="primary", icon=I.ASSESSMENT, key="next_assessment"):
                routes.go(routes.ASSESSMENT)
            if row.button("Back to the project", icon=I.BACK, key="next_project"):
                routes.go(routes.PROJECT, id=project_id)
            return
        first, others = steps[0], steps[1:3]
        st.html('<p class="next-label">What\'s next</p>')
        row = st.container(horizontal=True, vertical_alignment="center")
        with row, st.container(key=look_key(str(first["agent"]), "next"), width="content"):
            if st.button(step_verb(first, can_run), type="primary", icon=I.OPEN, icon_position="right",
                         key=f"next_{first['agent']}"):
                routes.go(routes.STAGE, project=project_id, agent=str(first["agent"]))
        for o in others:
            with row, st.container(key=look_key(str(o["agent"]), "next-alt"), width="content"):
                if st.button(step_verb(o, can_run), icon=look(str(o["agent"])).material,
                             key=f"next_{o['agent']}"):
                    routes.go(routes.STAGE, project=project_id, agent=str(o["agent"]))
        st.caption(step_reason(first) + (" Also open: " + ", ".join(str(o["name"]) for o in others) + "."
                                         if others else ""))


def stage_footer(project_id: str, stages: List[Dict[str, Any]], agent_key: str) -> None:
    """Previous and next stage at the foot of every stage page, whatever its status."""
    order = [str(s["agent"]) for s in stages]
    i = order.index(agent_key)
    prev = stages[i - 1] if i > 0 else None
    nxt = stages[i + 1] if i + 1 < len(stages) else None
    here = stages[i]
    st.html('<hr class="raia-rule" style="margin:1.5rem 0 .75rem">')
    c1, c2, c3 = st.columns([2, 1, 2], vertical_alignment="center")
    with c1:
        if prev is not None:
            with st.container(key=look_key(str(prev["agent"]), "foot-prev")):
                if st.button(f"Previous: {prev['name']}", icon=I.BACK, key="foot_prev",
                             help=STATUS[str(prev["status"])][0]):
                    routes.go(routes.STAGE, project=project_id, agent=str(prev["agent"]))
        elif st.button("Project overview", icon=I.BACK, key="foot_project_l"):
            routes.go(routes.PROJECT, id=project_id)
    c2.html(f'<div class="stage-foot-step">Step {i + 1} of {len(stages)}</div>')
    with c3, st.container(horizontal=True, horizontal_alignment="right"):
        if nxt is not None:
            onward = here["status"] == "approved" and nxt["status"] in ("ready", "in_review", "stale")
            with st.container(key=look_key(str(nxt["agent"]), "foot-next"), width="content"):
                if st.button(f"Next: {nxt['name']}", icon=I.OPEN, icon_position="right", key="foot_next",
                             type="primary" if onward else "secondary",
                             help=STATUS[str(nxt["status"])][0]):
                    routes.go(routes.STAGE, project=project_id, agent=str(nxt["agent"]))
        elif st.button("Project overview", icon=I.OPEN, icon_position="right", key="foot_project_r"):
            routes.go(routes.PROJECT, id=project_id)
