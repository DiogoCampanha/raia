"""
raia.ui.theme
=============

Visual vocabulary shared by every page: the CSS layer, Material Symbols icon
names, and the one mapping from a stage status or risk level to a label and a
colour. No emoji anywhere in the interface: icons are Material Symbols, which
Streamlit renders natively and which read consistently across platforms.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).parent / "assets"
LOGO = str(ASSETS / "logo.svg")
ICON = str(ASSETS / "icon.svg")


class I:  # noqa: E742 - short on purpose: I.HOME reads well at call sites
    HOME = ":material/space_dashboard:"
    PROJECT = ":material/folder_open:"
    AGENTS = ":material/hub:"
    ASSESSMENT = ":material/fact_check:"
    SETTINGS = ":material/settings:"
    PRIVACY = ":material/policy:"
    RESEARCH = ":material/analytics:"
    ADD = ":material/add:"
    DEMO = ":material/science:"
    OPEN = ":material/arrow_forward:"
    BACK = ":material/arrow_back:"
    RUN = ":material/play_arrow:"
    APPROVE = ":material/check:"
    REJECT = ":material/refresh:"
    REVISE = ":material/edit:"
    CONFIRM = ":material/task_alt:"
    DOWNLOAD = ":material/download:"
    EXAMPLE = ":material/content_paste:"
    RESTORE = ":material/restore:"
    DISCARD = ":material/delete:"
    LOCK = ":material/lock:"
    WARN = ":material/warning:"
    ERROR = ":material/error:"
    INFO = ":material/info:"
    OK = ":material/check_circle:"
    MAIL = ":material/mail:"
    PERSON = ":material/person:"
    GROUP = ":material/group:"
    ISSUE = ":material/gavel:"
    HISTORY = ":material/history:"
    DOCS = ":material/description:"
    OVERVIEW = ":material/dashboard:"
    LOGOUT = ":material/logout:"
    SAVE = ":material/save:"
    SHIELD = ":material/verified_user:"
    EVIDENCE = ":material/menu_book:"
    COMPUTE = ":material/calculate:"
    READ = ":material/visibility:"
    MOCK = ":material/science:"


#: status -> (label, badge colour, icon)
STATUS = {
    "approved": ("Approved", "green", ":material/check_circle:"),
    "stale": ("Needs review", "orange", ":material/sync_problem:"),
    "in_review": ("Awaiting review", "violet", ":material/rate_review:"),
    "ready": ("Ready to run", "blue", ":material/play_circle:"),
    "blocked": ("Waiting on upstream", "gray", ":material/lock:"),
}

#: risk level (see raia.projects.risk_summary) -> (badge colour, icon)
RISK = {
    "critical": ("red", ":material/block:"),
    "high": ("orange", ":material/priority_high:"),
    "medium": ("yellow", ":material/visibility:"),
    "low": ("green", ":material/check:"),
    "none": ("gray", ":material/remove:"),
}

LAYER_CLASS = {"Product": "product", "Dev": "dev", "Ops": "ops"}

ROLE = {"owner": ("Owner", ":material/shield_person:"),
        "editor": ("Editor", ":material/edit:"),
        "reviewer": ("Reviewer", ":material/rate_review:")}

CHECK = {"pass": ":material/check_circle:", "warn": ":material/warning:", "fail": ":material/cancel:"}


@lru_cache(maxsize=1)
def _css() -> str:
    return (Path(__file__).parent / "theme.css").read_text(encoding="utf-8")


def apply() -> None:
    """Inject the RAIA CSS layer. Call once per run, before any page renders."""
    st.html(f"<style>{_css()}</style>")
