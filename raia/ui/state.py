"""
raia.ui.state
=============

Who is here, which project they are looking at, and the per-process services.

The open project comes from the URL (``?id=`` on the project page,
``?project=`` on a stage page), not from a sidebar selection, so a link to a
project or a stage can be shared with another member. Membership is looked up
again on every run: a person removed from a project loses access on their next
click.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from raia.pipeline import StageRunner
from raia.projects import AccessDenied, Project, ProjectService, User

from . import routes
from .theme import I


@st.cache_resource
def get_runner() -> StageRunner:
    """One StageRunner (and its graph checkpointer) per server process."""
    return StageRunner()


@st.cache_resource
def get_service() -> ProjectService:
    """One project service per server process (it holds the database pool)."""
    return ProjectService(runner=get_runner())


@st.cache_resource
def ensure_normative_index() -> bool:
    """Self-bootstrap the RAG index on hosted platforms."""
    from raia.rag import index_exists, ingest_corpus

    if not index_exists():
        ingest_corpus(verbose=False)
    return True


def current_user() -> User:
    return st.session_state["_user"]


def open_project(param: str = "id") -> Project:
    """The project named in the URL, or a clear dead end.

    Stops the page when the id is missing or the person is not a member; the
    answer is the same in both cases so an id cannot be used to probe.
    """
    pid = st.query_params.get(param) or st.session_state.get("project_id")
    project: Optional[Project] = None
    if pid:
        try:
            project = get_service().get_project(current_user(), pid)
        except AccessDenied:
            project = None
    if project is None:
        st.session_state.pop("project_id", None)
        from .components import empty_state

        empty_state("Project not available",
                    "It may have been deleted, or you are not a member of it.")
        if st.button("Back to projects", icon=I.BACK, key="notfound_home"):
            routes.go(routes.HOME)
        st.stop()
    st.session_state["project_id"] = project.id
    return project


def pkey(*parts: str) -> str:
    """Widget/session key scoped to the open project.

    Two projects open one after the other in the same browser must never share
    a draft, a form answer or a half-typed rejection note.
    """
    return "::".join([st.session_state.get("project_id", "-"), *parts])


def flash(message: str) -> None:
    st.session_state["flash"] = message


def show_flash() -> None:
    msg = st.session_state.pop("flash", None)
    if msg:
        st.success(msg, icon=I.OK)
