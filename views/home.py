"""Home: what needs attention across every project, and the project list."""

import streamlit as st

from raia.agents import AGENTS
from raia.examples import EXAMPLES
from raia.ui import routes
from raia.ui.components import (empty_state, page_header, risk_badge, role_badge, rule, stat_tiles,
                                status_badge)
from raia.ui.state import current_user, flash, get_service, show_flash
from raia.ui.theme import I

user = current_user()
svc = get_service()

page_header(
    "Projects",
    "Each project keeps its own stages, drafts, answers, open issues and audit trail. "
    "Open one to continue where you left off.",
)
show_flash()


def _seed_demo():
    proj = svc.create_project(
        user, "Demo — resume screening",
        "A worked example: an AI system that ranks job applicants. Every stage's form is "
        "pre-filled, so you can walk the whole pipeline in about 20 minutes.",
    )
    for agent_key, values in EXAMPLES.items():
        if agent_key in AGENTS:
            svc.save_intake(user, proj.id, agent_key, values)
    return proj


# ---- Invitations -----------------------------------------------------------

for inv in svc.my_invitations(user):
    with st.container(border=True):
        c1, c2, c3 = st.columns([6, 1, 1], vertical_alignment="center")
        who = inv.get("invited_by_name") or inv.get("invited_by_email") or "Someone"
        c1.markdown(f"{I.MAIL} **{who}** invited you to **{inv['project_name']}** "
                    f"as {inv['role']}.")
        if c2.button("Accept", type="primary", key=f"inv_ok_{inv['id']}"):
            p = svc.respond_to_invitation(user, inv["id"], True)
            flash(f"You joined “{p.name}”.")
            routes.go(routes.PROJECT, id=p.id)
        if c3.button("Decline", key=f"inv_no_{inv['id']}"):
            svc.respond_to_invitation(user, inv["id"], False)
            st.rerun()

# ---- Data ------------------------------------------------------------------

show_archived = st.session_state.get("show_archived", False)
projects = svc.list_projects(user, include_archived=show_archived)
summaries = {p.id: svc.stage_summary(user, p.id) for p in projects}
active = [p for p in projects if not p.archived_at]

# ---- Assessment prompt -------------------------------------------------------

if svc.my_latest_rating(user) is None and any(summaries[p.id]["approved"] for p in projects):
    with st.container(border=True):
        c1, c2 = st.columns([5, 1], vertical_alignment="center")
        c1.markdown(f"{I.ASSESSMENT} **Share your assessment.** It takes about ten minutes and "
                    "is the evidence the study depends on.")
        if c2.button("Open", key="home_assessment", type="primary"):
            routes.go(routes.ASSESSMENT)

# ---- Overview tiles ------------------------------------------------------------

awaiting = sum(len(summaries[p.id]["in_review"]) for p in active)
stale = sum(len(summaries[p.id]["stale"]) for p in active)
issues = sum(summaries[p.id]["open_issues"] for p in active)
stat_tiles([
    ("Active projects", len(active), "", False),
    ("Awaiting review", awaiting, "Drafts waiting for a human decision", awaiting > 0),
    ("Needs review", stale, "Approved stages whose upstream changed", stale > 0),
    ("Open issues", issues, "Conflicts only a person can settle", issues > 0),
])

# ---- Needs your attention ------------------------------------------------------

attention = []
for p in active:
    s = summaries[p.id]
    for stg in s["stages"]:
        if stg["status"] == "in_review":
            attention.append((p, stg, "A draft is waiting for review"))
        elif stg["status"] == "stale":
            attention.append((p, stg, "Upstream changed: " + ", ".join(stg["stale_because_names"])))
if attention:
    st.subheader("Needs your attention", anchor=False)
    with st.container(border=True):
        for i, (p, stg, why) in enumerate(attention):
            c1, c2, c3 = st.columns([4, 2, 1], vertical_alignment="center")
            c1.markdown(f"**{stg['name']}** · {p.name}")
            c1.caption(why)
            with c2:
                status_badge(stg["status"])
            if c3.button("Open", key=f"att_{p.id}_{stg['agent']}", icon=I.OPEN):
                routes.go(routes.STAGE, project=p.id, agent=stg["agent"])
            if i < len(attention) - 1:
                rule()

# ---- Projects ------------------------------------------------------------------

head_l, head_r = st.columns([3, 2], vertical_alignment="bottom")
head_l.subheader("All projects", anchor=False)
with head_r:
    st.toggle("Show archived", key="show_archived")

with st.expander("New project", icon=I.ADD, expanded=not projects):
    with st.form("new_project", clear_on_submit=True, border=False):
        name = st.text_input("Project name", placeholder="e.g. Credit-limit recommender")
        description = st.text_area("Description (optional)", height=80)
        if st.form_submit_button("Create project", type="primary"):
            try:
                p = svc.create_project(user, name, description)
                flash(f"Project “{p.name}” created.")
                routes.go(routes.PROJECT, id=p.id)
            except ValueError as exc:
                st.error(str(exc))
    st.caption("New to RAIA? Start from a pre-filled example instead.")
    if st.button("Create the demo project", key="demo_project", icon=I.DEMO):
        p = _seed_demo()
        flash("Demo project created. Every form is pre-filled.")
        routes.go(routes.PROJECT, id=p.id)

if not projects:
    empty_state("No projects yet", "Create a project or the demo project above, or accept an "
                "invitation from a colleague.")
    st.stop()

with st.container(border=True):
    widths = [4, 2, 2, 3, 1.4]
    h = st.columns(widths, vertical_alignment="center")
    for col, label in zip(h, ["Project", "Risk", "Progress", "Next step", "Role"]):
        col.caption(f"**{label}**")
    for p in projects:
        s = summaries[p.id]
        rule()
        c = st.columns(widths, vertical_alignment="center")
        with c[0]:
            if st.button(p.name + (" (archived)" if p.archived_at else ""), key=f"open_{p.id}",
                         type="tertiary", help="Open this project"):
                routes.go(routes.PROJECT, id=p.id)
            st.caption(f"Updated {p.updated_at[:10]}")
        with c[1]:
            risk_badge(s["risk"])
        with c[2]:
            st.progress(s["approved"] / s["total"], text=f"{s['approved']}/{s['total']} approved")
        with c[3]:
            if s["in_review"]:
                st.markdown(f"Review **{s['in_review'][0]}**")
            elif s["stale"]:
                st.markdown(f"Re-check **{s['stale'][0]}**")
            elif s["next"]:
                st.markdown(f"Run **{s['next']}**")
            else:
                st.markdown("All stages approved")
            if s["open_issues"]:
                st.caption(f"{s['open_issues']} open issue(s)")
        with c[4]:
            role_badge(p.role)
