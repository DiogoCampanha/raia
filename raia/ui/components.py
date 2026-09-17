"""
raia.ui.components
==================

The small set of building blocks every page is made of. Keeping them here is
what makes the pages look like one product: one page header, one stat tile,
one status badge, one stage tracker.
"""

from __future__ import annotations

import html
from typing import Dict, Iterable, List, Optional, Tuple

import streamlit as st

from . import routes
from .theme import I, LAYER_CLASS, RISK, ROLE, STATUS


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


def stage_tracker(project_id: str, stages: List[Dict[str, object]], current: str = "",
                  key_prefix: str = "trk") -> None:
    """The five stages as a horizontal stepper. Each step opens its stage page."""
    cols = st.columns(len(stages), gap="small")
    for i, (col, s) in enumerate(zip(cols, stages), start=1):
        with col, st.container(border=True):
            st.html(f'<div style="display:flex;justify-content:space-between;align-items:center">'
                    f'{layer_tag(str(s["layer"]))}'
                    f'<span class="raia-meta">{"Current" if s["agent"] == current else f"Step {i}"}</span></div>')
            if st.button(str(s["name"]), key=f"{key_prefix}_{s['agent']}", type="tertiary",
                         help=f"Open the {s['name']} stage", disabled=s["agent"] == current):
                routes.go(routes.STAGE, project=project_id, agent=str(s["agent"]))
            status_badge(str(s["status"]))
