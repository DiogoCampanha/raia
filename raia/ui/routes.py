"""
raia.ui.routes
==============

The page map. Every page is a file under ``views/`` registered once in
``app.py``; everything else links to pages through this module, so a route is
named in exactly one place.

=================  ===========================  ====================  ==========
Route              File                         Menu                  Sign-in
=================  ===========================  ====================  ==========
``/``              views/home.py                Home                  required
``/guide``         views/guide.py               Guide                 required
``/project``       views/project.py             hidden (from Home)    required
``/stage``         views/stage.py               hidden (from Project) required
``/agents``        views/agents.py              Agents                required
``/assessment``    views/assessment.py          Assessment            required
``/settings``      views/settings.py            Account > Settings    required
``/research``      views/research.py            Account (admins only) required
``/privacy``       views/legal.py               Account > Privacy     public
``/signout``       views/signout.py             Account > Sign out    required
=================  ===========================  ====================  ==========

*Sign out* is listed only when there is someone to sign out: the local
developer mode has one fixed identity and no sign-in.

``/project`` takes ``?id=<project id>``; ``/stage`` takes
``?project=<project id>&agent=<agent key>``. Query parameters keep links
shareable between members; every page re-checks membership when it loads.
"""

from __future__ import annotations

from typing import Dict, Optional

import streamlit as st

HOME = "home"
GUIDE = "guide"
PROJECT = "project"
STAGE = "stage"
AGENTS = "agents"
ASSESSMENT = "assessment"
SETTINGS = "settings"
RESEARCH = "research"
PRIVACY = "privacy"
LOGIN = "login"
SIGN_OUT = "signout"

FILES = {
    HOME: "views/home.py",
    GUIDE: "views/guide.py",
    PROJECT: "views/project.py",
    STAGE: "views/stage.py",
    AGENTS: "views/agents.py",
    ASSESSMENT: "views/assessment.py",
    SETTINGS: "views/settings.py",
    RESEARCH: "views/research.py",
    PRIVACY: "views/legal.py",
    LOGIN: "views/login.py",
    SIGN_OUT: "views/signout.py",
}

_PAGES: Dict[str, "st.Page"] = {}


def register(name: str, page: "st.Page") -> "st.Page":
    _PAGES[name] = page
    return page


def page(name: str) -> "st.Page":
    return _PAGES[name]


def go(name: str, **params: str) -> None:
    """Navigate now (from inside a button branch, never a callback)."""
    st.switch_page(_PAGES[name], query_params={k: v for k, v in params.items() if v} or None)


def link(name: str, label: str, icon: Optional[str] = None, **params: str) -> None:
    st.page_link(_PAGES[name], label=label, icon=icon,
                 query_params={k: v for k, v in params.items() if v} or None)
