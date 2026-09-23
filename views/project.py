"""Project: where one project stands, its documents, issues, activity and people."""

import json

import streamlit as st

from raia.contract import actions as action_plan
from raia.contract import vocab as V
from raia.export import bundle_name, session_bundle
from raia.projects import EDITOR, OWNER, REVIEWER, ROLE_LABELS
from raia.repository import ACCEPTED, ARTIFACT_FILES, OPEN, RESOLVED
from raia.ui import routes
from raia.ui.components import (artifact_body, empty_state, page_header, risk_md, role_badge,
                                role_label, role_md, stage_tracker, stat_tiles)
from raia.ui.state import current_user, flash, get_service, open_project, pkey, show_flash
from raia.ui.theme import I

user = current_user()
svc = get_service()
proj = open_project("id")
repo = svc.repository(user, proj.id, "view")
summary = svc.stage_summary(user, proj.id)


def _bundle() -> bytes:
    """Built when the button is pressed, not on every redraw of the page.

    Zipping the project reads its whole history and re-verifies the hash chain;
    doing that on each click anywhere on the page made every click slow. It
    re-opens the repository, so membership is checked again at download time.
    """
    return session_bundle(svc.repository(user, proj.id, "view"), proj.name)

stages = summary["stages"]

page_header(proj.name, proj.description,
            eyebrow="Project" + (" · archived" if proj.archived_at else ""),
            back=("All projects", routes.HOME, {}))

st.markdown(f"{risk_md(summary['risk'])} &nbsp; {role_md(proj.role)}")
show_flash()

# ---- Primary action -------------------------------------------------------------

focus = (next((s for s in stages if s["status"] == "in_review"), None)
         or next((s for s in stages if s["status"] == "stale"), None)
         or next((s for s in stages if s["status"] == "ready"), None))
with st.container(border=True):
    c1, c2 = st.columns([4, 1.4], vertical_alignment="center")
    if focus is None:
        c1.markdown(f"{I.OK} **All five stages are approved.** Revisit any stage from the "
                    "tracker below, or download the project.")
        c2.download_button("Download project", data=_bundle,
                           file_name=bundle_name(proj.name), mime="application/zip",
                           icon=I.DOWNLOAD, key="cta_export", width="stretch")
    else:
        verb = {"in_review": "Review", "stale": "Re-check", "ready": "Continue with"}[focus["status"]]
        why = {"in_review": "A draft is waiting for a human decision.",
               "stale": "Upstream work changed after this stage was approved: "
                        + ", ".join(focus["stale_because_names"]) + ".",
               "ready": "This is the next stage in the pipeline."}[focus["status"]]
        c1.markdown(f"**Next: {verb} {focus['name']}**")
        c1.caption(why)
        if c2.button(f"{verb} {focus['name']}", type="primary", key="cta_stage", icon=I.OPEN,
                     width="stretch"):
            routes.go(routes.STAGE, project=proj.id, agent=focus["agent"])

plan_rows = action_plan.project_actions(repo)

tab_overview, tab_docs, tab_plan, tab_issues, tab_activity, tab_people = st.tabs([
    ":material/dashboard: Overview",
    ":material/description: Documents",
    f":material/checklist: Action plan ({len(plan_rows)})" if plan_rows else ":material/checklist: Action plan",
    f":material/gavel: Open issues ({summary['open_issues']})" if summary["open_issues"]
    else ":material/gavel: Open issues",
    ":material/history: Activity",
    ":material/group: People and settings",
])

# ---- Overview ----------------------------------------------------------------------

with tab_overview:
    stat_tiles([
        ("Stages approved", f"{summary['approved']}/{summary['total']}", "", False),
        ("Awaiting review", len(summary["in_review"]), "", bool(summary["in_review"])),
        ("Needs review", len(summary["stale"]), "Upstream changed", bool(summary["stale"])),
        ("Open issues", summary["open_issues"], "", summary["open_issues"] > 0),
    ])
    st.subheader("Stages", anchor=False)
    st.caption("Every stage ends at a mandatory human approval gate. Open a stage to run it, "
               "review its draft, or read and revise what was approved.")
    stage_tracker(proj.id, stages, key_prefix="ov")
    if summary["risk"]["eu_tier"]:
        st.subheader("Risk classification", anchor=False)
        with st.container(border=True):
            r1, r2 = st.columns(2)
            r1.caption("EU AI Act")
            r1.markdown(f"**{summary['risk']['eu_tier']}**")
            r2.caption("Brazil PL 2338/2023")
            r2.markdown(f"**{summary['risk']['br_tier'] or '—'}**")
    if summary["approved"] == 0:
        st.info("**Start here (about 20 minutes):** open the **Risk Classifier**, load the "
                "example if the form is empty, and run it. Approve each stage in order, then "
                "complete the **Assessment**.", icon=I.INFO)
    routes.link(routes.AGENTS, "How RAIA works", icon=I.AGENTS)

# ---- Documents ---------------------------------------------------------------------

with tab_docs:
    c1, c2 = st.columns([4, 1.4], vertical_alignment="center")
    c1.caption("Approved artifacts with their provenance. The project download contains "
               "every artifact, structured record, version history and pseudonymized events.")
    c2.download_button("Download project", data=_bundle,
                       file_name=bundle_name(proj.name), mime="application/zip",
                       icon=I.DOWNLOAD, key="docs_export", width="stretch")
    existing = repo.existing_artifacts()
    if not existing:
        empty_state("No approved documents yet",
                    "Approve a stage's draft and its document appears here.")
    for key in existing:
        content = repo.read_artifact(key) or ""
        data = repo.read_data(key)
        with st.expander(ARTIFACT_FILES[key], icon=I.DOCS):
            prov = data.get("provenance") or {}
            if prov:
                model = prov.get("model", {})
                corpus = prov.get("corpus", {})
                approval = prov.get("approval", {})
                cols = st.columns(4)
                cols[0].metric("Attempt approved", prov.get("attempt", "—"))
                cols[1].metric("Excerpts in prompt", len(corpus.get("excerpts", [])) or "—")
                cols[2].metric("Edited by hand", "yes" if approval.get("human_edited_draft") else "no")
                cols[3].metric("Checks", (prov.get("validation") or {}).get("level", "—"))
                st.caption(
                    f"Approved by **{approval.get('approved_by', '?')}** · "
                    f"model `{model.get('provider', '?')}/{model.get('name', '?')}` · "
                    f"temperature {model.get('temperature', '?')} · "
                    f"corpus `{corpus.get('version', '?')}` · "
                    f"prompt `{prov.get('prompt_sha256_16', '?')}` · "
                    f"engine `{prov.get('rationale_engine') or 'none'}`"
                )
            st.markdown(artifact_body(content))
            d1, d2, _ = st.columns([1, 1, 2])
            d1.download_button("Markdown", content, file_name=ARTIFACT_FILES[key],
                               mime="text/markdown", key=pkey("dl", key), icon=I.DOWNLOAD)
            if data:
                d2.download_button(
                    "Structured record (JSON)",
                    json.dumps(data, indent=2, ensure_ascii=False, default=str),
                    file_name=ARTIFACT_FILES[key].replace(".md", ".json"),
                    mime="application/json", key=pkey("dlj", key), icon=I.DOWNLOAD,
                )

# ---- Action plan ------------------------------------------------------------------

with tab_plan:
    st.caption("Every action from every approved stage, in one list sorted by priority. Priority is "
               "computed by the software from each finding's likelihood and magnitude (NIST AI RMF), "
               "raised where a legal obligation, a prohibited practice or a measured severity "
               "requires it. Drafts under review contribute nothing.")
    if not plan_rows:
        empty_state("No actions yet", "Approve a stage and its actions appear here.")
    else:
        counts = action_plan.summary(plan_rows)
        stat_tiles([(p.capitalize(), n, "", p in ("critical", "high") and n > 0) for p, n in counts.items()])
        f1, f2, f3 = st.columns(3)
        pick_p = f1.multiselect("Priority", list(reversed(V.PRIORITIES)), key=pkey("plan_p"))
        pick_o = f2.multiselect("Owner", list(V.OWNER_ROLES), format_func=V.OWNER_LABELS.get, key=pkey("plan_o"))
        pick_s = f3.multiselect("Stage", sorted({r["stage"] for r in plan_rows}), key=pkey("plan_s"))
        shown = [r for r in plan_rows if (not pick_p or r["priority"] in pick_p)
                 and (not pick_o or r["owner_role"] in pick_o) and (not pick_s or r["stage"] in pick_s)]
        st.dataframe(
            [{
                "ID": r["id"], "Priority": r["priority"], "Blocking": "yes" if r["blocking"] else "",
                "Action": r["action"], "Response": r["response"],
                "Owner": V.OWNER_LABELS.get(r["owner_role"], r["owner_role"]),
                "Lifecycle stage": V.LIFECYCLE_LABELS.get(r["lifecycle_stage"], r["lifecycle_stage"]),
                "Review cadence": r["review_cadence"].replace("_", " "),
                "Verification": r["verification_method"], "Evidence artifact": r["evidence_artifact"],
                "Findings": r["findings"], "Principles": r["principles"],
                "NIST AI RMF": r["nist_categories"], "Stage": r["stage"],
            } for r in shown],
            width="stretch", hide_index=True,
        )
        d1, d2, _ = st.columns([1, 1, 2])
        d1.download_button("Action plan (CSV)", action_plan.to_csv(plan_rows), file_name="action_plan.csv",
                           mime="text/csv", key=pkey("plan_csv"), icon=I.DOWNLOAD)
        d2.download_button("Action plan (JSON)", action_plan.to_json(plan_rows), file_name="action_plan.json",
                           mime="application/json", key=pkey("plan_json"), icon=I.DOWNLOAD)

# ---- Open issues -------------------------------------------------------------------

with tab_issues:
    st.caption("Conflicts the system refused to resolve on its own: normative conflicts at the "
               "same authority level, disagreements between a rule engine and an agent, and gaps "
               "only a person can close. Nothing here is settled by the software.")
    issues = repo.open_issues()
    if not issues:
        empty_state("No open issues",
                    "They are raised when a decision procedure or an agent finds a conflict, and "
                    "recorded when you approve the stage that raised them.")
    groups = [(OPEN, "Open", "red"), (ACCEPTED, "Accepted risk", "orange"),
              (RESOLVED, "Resolved", "green")]
    for status, title, color in groups:
        group = [i for i in issues if i.get("status") == status]
        if not group:
            continue
        st.markdown(f"**{title}** · {len(group)}")
        for issue in group:
            with st.container(border=True):
                st.badge(issue["id"], color=color)
                st.markdown(issue["text"])
                st.caption(
                    V.ISSUE_TYPE_LABELS.get(issue.get("type"), "Needs a human decision")
                    + f" · decided by {V.OWNER_LABELS.get(issue.get('decision_owner'), 'the team')}"
                    + (" · **blocking**" if issue.get("blocking") else "")
                    + (f" · options: {'; '.join(issue['options'])}" if issue.get("options") else "")
                )
                st.caption(
                    f"Raised by {issue.get('raised_by', '?')} · {issue.get('raised_at', '?')}"
                    + (f" · artifact `{issue['artifact']}`" if issue.get("artifact") else "")
                    + (f" · commit `{issue['commit']}`" if issue.get("commit") else "")
                )
                if issue.get("resolution_note"):
                    st.caption(f"_{issue['resolution_note']}_ — {issue.get('resolved_by', '')}")
                if status == OPEN and proj.can("review"):
                    with st.expander("Arbitrate this issue"):
                        note = st.text_input(
                            "What was decided, and on what basis?", key=pkey("note", issue["id"]),
                            placeholder="e.g. Legal confirmed the exemption does not apply",
                        )
                        st.caption(f"Recorded as decided by **{user.label}**.")
                        a1, a2 = st.columns(2)
                        if a1.button("Mark resolved", key=pkey("res", issue["id"]),
                                     disabled=not note.strip()):
                            svc.set_issue_status(user, proj.id, issue["id"], RESOLVED, note)
                            flash(f"{issue['id']} marked resolved.")
                            st.rerun()
                        if a2.button("Accept the risk", key=pkey("acc", issue["id"]),
                                     disabled=not note.strip()):
                            svc.set_issue_status(user, proj.id, issue["id"], ACCEPTED, note)
                            flash(f"{issue['id']} recorded as accepted risk.")
                            st.rerun()

# ---- Activity ----------------------------------------------------------------------

with tab_activity:
    integrity = repo.verify_history()
    if integrity["ok"]:
        st.success("History integrity verified — " + integrity["detail"], icon=":material/verified:")
    else:
        st.error("History integrity FAILED — " + integrity["detail"], icon=I.ERROR)
    st.caption("Every approval is a recorded version that cannot be silently changed afterwards.")
    st.subheader("Version history", anchor=False)
    history = repo.history()
    if history:
        st.dataframe(history, width="stretch", hide_index=True)
    else:
        empty_state("No versions yet", "Each approval creates one.")
    events = repo.events()
    if events:
        names = {m["user_id"]: (m["name"] or m["email"]) for m in svc.members(user, proj.id)}
        st.subheader("Project log", anchor=False)
        st.caption("Runs, rejections with their reasons, approvals, revisions, re-confirmations, "
                   "restores and arbitrations. Research exports replace names with participant codes.")
        st.dataframe(
            [{
                "When (UTC)": str(e.get("at", ""))[:19].replace("T", " "),
                "Who": names.get(e.get("user", ""), "former member" if e.get("user") else ""),
                "Event": str(e.get("kind", "")).replace("_", " "),
                "Stage": e.get("agent", ""),
                "Detail": e.get("reason_code") or e.get("validation") or e.get("status") or "",
            } for e in reversed(events)],
            width="stretch", hide_index=True,
        )

# ---- People and settings -----------------------------------------------------------

with tab_people:
    manage = proj.can("manage")
    st.subheader("Members", anchor=False)
    for m in svc.members(user, proj.id):
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 1], vertical_alignment="center")
            who = (m["name"] or m["email"]) + (" (you)" if m["user_id"] == user.id else "")
            c1.markdown(f"**{who}**  \n{m['email']}")
            if manage:
                roles = [OWNER, EDITOR, REVIEWER]
                new_role = c2.selectbox("Role", roles, index=roles.index(m["role"]),
                                        format_func=role_label, key=pkey("role", m["user_id"]),
                                        label_visibility="collapsed")
                if new_role != m["role"]:
                    try:
                        svc.change_role(user, proj.id, m["user_id"], new_role)
                        flash(f"{m['email']} is now {new_role}.")
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        st.rerun()
            else:
                with c2:
                    role_badge(m["role"])
            if (manage and m["user_id"] != user.id) and c3.button("Remove", key=pkey("rm", m["user_id"])):
                try:
                    svc.remove_member(user, proj.id, m["user_id"])
                    flash(f"{m['email']} was removed from the project.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

    with st.expander("What each role can do"):
        for role in (OWNER, EDITOR, REVIEWER):
            st.markdown(f"- **{role_label(role)}** — {ROLE_LABELS[role].split('— ', 1)[1]}")

    if manage:
        st.subheader("Invite someone", anchor=False)
        st.caption("Invite people by the Google address they sign in with. No email is sent: "
                   "share the app's address, and the invitation is waiting on their Home page.")
        with st.form(pkey("invite"), clear_on_submit=True):
            email = st.text_input("Email address", placeholder="name@example.com")
            role = st.selectbox("Role", [REVIEWER, EDITOR, OWNER], format_func=ROLE_LABELS.get)
            if st.form_submit_button("Send invitation", type="primary"):
                try:
                    inv = svc.invite(user, proj.id, email, role)
                    flash(f"Invitation for {inv['email']} ({inv['role']}) created.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        invites = svc.project_invitations(user, proj.id)
        if invites:
            st.markdown("**Pending invitations**")
            for inv in invites:
                c1, c2 = st.columns([4, 1], vertical_alignment="center")
                c1.markdown(f"{inv['email']} · {role_label(inv['role'])} · _{inv['created_at'][:10]}_")
                if c2.button("Revoke", key=pkey("revoke", inv["id"])):
                    svc.revoke_invitation(user, proj.id, inv["id"])
                    st.rerun()

        st.subheader("Project settings", anchor=False)
        with st.form(pkey("settings")):
            name = st.text_input("Name", value=proj.name)
            description = st.text_area("Description", value=proj.description, height=90)
            second = st.checkbox(
                "Require a second approver", value=proj.require_second_approver,
                help="The person who ran a stage cannot approve that stage's draft. "
                     "Separation of duties, enforced by the software.",
            )
            if st.form_submit_button("Save settings"):
                try:
                    svc.update_project(user, proj.id, name=name, description=description,
                                       require_second_approver=second)
                    flash("Settings saved.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

        st.subheader("Danger zone", anchor=False)
        with st.container(border=True):
            c1, c2 = st.columns(2, gap="large")
            with c1:
                st.markdown("**Archive**")
                st.caption("Hidden from the project list; nothing is deleted.")
                if proj.archived_at:
                    if st.button("Unarchive project", key=pkey("unarchive")):
                        svc.set_archived(user, proj.id, False)
                        st.rerun()
                elif st.button("Archive project", key=pkey("archive")):
                    svc.set_archived(user, proj.id, True)
                    flash(f"“{proj.name}” was archived.")
                    routes.go(routes.HOME)
            with c2:
                st.markdown("**Delete permanently**")
                confirm = st.text_input("Type the project name to confirm", key=pkey("delete_confirm"))
                if st.button("Delete project", key=pkey("delete"), disabled=confirm.strip() != proj.name,
                             icon=I.DISCARD):
                    svc.delete_project(user, proj.id)
                    st.session_state.pop("project_id", None)
                    flash(f"Project “{proj.name}” and all its data were deleted.")
                    routes.go(routes.HOME)
    else:
        st.divider()
        if st.button("Leave this project", key=pkey("leave")):
            try:
                svc.remove_member(user, proj.id, user.id)
                st.session_state.pop("project_id", None)
                routes.go(routes.HOME)
            except ValueError as exc:
                st.error(str(exc))
