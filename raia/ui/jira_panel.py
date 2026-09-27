"""
raia.ui.jira_panel
==================

The optional Jira actions on the Board, beside the manual controls.

Nothing on the board waits for Jira. This panel offers three extras for teams
that plan there: download a Jira-ready CSV (no setup), push the sprint with the
person's own Jira Cloud connection, and read status back. A sync never
overwrites a manual change; disagreements are shown on the story for a person
to settle.
"""

from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

from raia import jira as J
from raia.projects import AccessDenied

from . import routes
from .state import flash, pkey
from .theme import I

TOKEN_KEY = "jira_session_token"


def _token() -> str:
    """The token typed in this session (either tab), when the deployment does not store it."""
    for k in (TOKEN_KEY, TOKEN_KEY + "push", TOKEN_KEY + "sync"):
        if st.session_state.get(k):
            return st.session_state[k]
    return ""


def _token_input(conn: Dict[str, Any], key: str) -> bool:
    """Ask for the token when this deployment does not store it. Returns whether one is available."""
    if conn.get("has_token"):
        return True
    st.text_input("Jira API token (kept for this session only)", type="password", key=TOKEN_KEY + key)
    return bool(_token())


def jira_actions(proj, user, svc, sprint: Dict[str, Any], stories: List[Dict[str, Any]]) -> None:
    conn = svc.jira_connection(user)
    with st.expander("Jira (optional): send this sprint, or read its status back", icon=":material/sync_alt:"):
        st.caption("The board works without Jira: tick stories done here and the audit closes the sprint. "
                   "If your team plans in Jira, these keep both in step.")
        tab_csv, tab_push, tab_sync = st.tabs(["Download a CSV", "Push to Jira Cloud", "Sync status"])
        with tab_csv:
            issue_type = st.text_input("Issue type", value=conn.get("issue_type") or "Story", key=pkey("jcsv_type"))
            scope = st.radio("Stories", ["sprint", "backlog"], horizontal=True, key=pkey("jcsv_scope"),
                             format_func=lambda v: f"This sprint ({len(stories)})" if v == "sprint"
                             else "The whole open backlog")
            st.download_button("Download the Jira CSV", data=lambda: svc.jira_csv(user, proj.id, scope, issue_type),
                               file_name=f"raia_{sprint['id'] if scope == 'sprint' else 'backlog'}_jira.csv",
                               mime="text/csv", icon=I.DOWNLOAD, key=pkey("jcsv_dl"))
            st.markdown("\n".join(f"{i}. {step}" for i, step in enumerate(J.CSV_STEPS, 1)))
        with tab_push:
            _push(proj, user, svc, sprint, stories, conn)
        with tab_sync:
            _sync(proj, user, svc, conn)


def _push(proj, user, svc, sprint, stories, conn) -> None:
    if not conn:
        st.caption("Connect your Jira Cloud account once, in Settings, to push with one click.")
        routes.link(routes.SETTINGS, "Open Settings", icon=I.SETTINGS)
        return
    if not proj.can("run"):
        st.caption("Owners and editors push to Jira.")
        return
    saved = ((svc.board(user, proj.id).get("sprints") or {}).get("settings") or {}).get("jira") or {}
    c1, c2 = st.columns(2)
    key = c1.text_input("Jira project key", value=saved.get("project_key") or conn.get("project_key") or "",
                        key=pkey("jpush_key"), placeholder="e.g. RAIA")
    itype = c2.text_input("Issue type", value=saved.get("issue_type") or conn.get("issue_type") or "Story",
                          key=pkey("jpush_type"))
    has_token = _token_input(conn, "push")
    jira_sprint = _pick_sprint(user, svc, key, has_token)
    new = sum(1 for s in stories if not (s.get("jira") or {}).get("key"))
    st.caption(f"{new} new story(ies) will be created; stories already in Jira are updated if they changed.")
    if st.button("Push to Jira", type="primary", icon=":material/upload:", key=pkey("jpush"),
                 disabled=not (key.strip() and has_token)):
        try:
            with st.spinner("Sending the sprint to Jira"):
                result = svc.jira_push(user, proj.id, project_key=key, issue_type=itype,
                                       jira_sprint=jira_sprint, token=_token())
        except (ValueError, AccessDenied, J.JiraError) as exc:
            st.error(str(exc), icon=I.WARN)
            return
        msg = f"{len(result['created'])} created, {len(result['updated'])} updated in Jira."
        if result["errors"]:
            msg += " Not sent: " + "; ".join(f"{k}: {v}" for k, v in result["errors"].items())
        flash(msg)
        st.rerun()


def _pick_sprint(user, svc, project_key: str, has_token: bool):
    """Optionally, a Jira sprint to add the issues to."""
    boards_key = pkey("jboards")
    if st.button("Choose a Jira sprint (optional)", key=pkey("jload"), type="tertiary", icon=":material/list:",
                 disabled=not (project_key.strip() and has_token)):
        try:
            st.session_state[boards_key] = svc.jira_boards(user, project_key, token=_token())
        except (ValueError, J.JiraError) as exc:
            st.error(str(exc), icon=I.WARN)
    boards = st.session_state.get(boards_key) or []
    if not boards:
        return None
    board = st.selectbox("Board", boards, format_func=lambda b: b["name"], key=pkey("jboard"))
    sprints_key = pkey("jsprints", str(board["id"]))
    if sprints_key not in st.session_state:
        try:
            st.session_state[sprints_key] = svc.jira_sprints(user, board["id"], token=_token())
        except (ValueError, J.JiraError) as exc:
            st.error(str(exc), icon=I.WARN)
            st.session_state[sprints_key] = []
    options = [None] + st.session_state[sprints_key]
    pick = st.selectbox("Jira sprint", options, key=pkey("jsprint"),
                        format_func=lambda s: "Do not add to a sprint" if s is None else f"{s['name']} ({s['state']})")
    return pick["id"] if pick else None


def _sync(proj, user, svc, conn) -> None:
    st.caption("Reads each story's status from Jira. Done in Jira marks it done here (delivered, not verified). "
               "A sync never undoes what a person changed on the board: disagreements are shown on the story.")
    if not conn:
        st.caption("Connect Jira in Settings to sync. Without it, tick stories done on the board.")
        return
    has_token = _token_input(conn, "sync")
    if st.button("Sync from Jira", icon=":material/sync:", key=pkey("jsync"),
                 disabled=not (has_token and proj.can("review"))):
        try:
            with st.spinner("Reading the sprint's status from Jira"):
                result = svc.jira_sync(user, proj.id, token=_token())
        except (ValueError, AccessDenied, J.JiraError) as exc:
            st.error(str(exc), icon=I.WARN)
            return
        flash("Synced from Jira: " + J.summary_line(result) + "."
              + (f" {len(result['disagreements'])} disagreement(s) to settle on the board."
                 if result["disagreements"] else ""))
        st.rerun()


def disagreement(proj, user, svc, story: Dict[str, Any]) -> None:
    """On a sprint story: Jira and the board disagree, and a person picks."""
    note = (story.get("jira") or {}).get("disagreement")
    if not note:
        return
    st.caption(f"{I.WARN} {note}")
    if proj.can("review"):
        row = st.container(horizontal=True)
        for keep, label in (("raia", "Keep the board's"), ("jira", "Use Jira's")):
            if row.button(label, key=pkey("jres", story["id"], keep), type="tertiary"):
                try:
                    svc.jira_resolve(user, proj.id, story["id"], keep)
                except (ValueError, AccessDenied) as exc:
                    st.error(str(exc))
                    return
                st.rerun()
