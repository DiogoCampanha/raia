"""Settings: profile, legal documents, personal data and account deletion.

Signing out is in the Account menu, next to this page.
"""

import streamlit as st

from raia import auth
from raia.ui import routes
from raia.ui.components import page_header
from raia.ui.state import current_user, get_service, show_flash
from raia.ui.theme import I

user = current_user()
svc = get_service()

page_header("Settings", "Your profile, your data and your account.", eyebrow="Account")
show_flash()

st.subheader("Profile", anchor=False)
with st.container(border=True):
    c1, c2 = st.columns(2, gap="large")
    c1.caption("Name")
    c1.markdown(user.name or "—")
    c2.caption("Email")
    c2.markdown(user.email)
    c1.caption("Sign-in")
    c1.markdown("Google" if auth.mode() != "dev" else "Local developer mode")
    c2.caption("Agreement accepted")
    c2.markdown((user.consented_at or "—")[:10])
    st.caption("Your name and email come from your Google account; change them there.")

st.subheader("Privacy and terms", anchor=False)
with st.container(border=True):
    st.markdown("How RAIA handles your information, the confidentiality commitments, and the "
                "terms of use.")
    routes.link(routes.PRIVACY, "Read the Privacy Policy and User Agreement", icon=I.PRIVACY)

st.subheader("Jira connection (optional)", anchor=False)
with st.container(border=True):
    st.markdown("RAIA's board runs sprints on its own. If your team plans in Jira, connect your Jira Cloud "
                "account to push a sprint in one click and read its status back. Nothing else needs it.")
    conn = svc.jira_connection(user)
    if conn:
        st.caption(f"Connected to **{conn['site']}** as {conn['email']}"
                   + (f" · default project {conn['project_key']}" if conn.get("project_key") else "")
                   + (" · token stored encrypted" if conn.get("has_token") else " · token asked for each session"))
    with st.form("jira_connection", border=False):
        c1, c2 = st.columns(2)
        site = c1.text_input("Jira site", value=conn.get("site", ""), placeholder="https://your-team.atlassian.net")
        email = c2.text_input("Your Jira email", value=conn.get("email", ""))
        token = st.text_input(
            "API token" + (" (leave empty to keep the stored one)" if conn.get("has_token") else ""),
            type="password",
            help="Create one at id.atlassian.com > Security > API tokens. It acts as you in Jira.")
        c3, c4 = st.columns(2)
        pkey_ = c3.text_input("Default project key (optional)", value=conn.get("project_key") or "", placeholder="RAIA")
        itype = c4.text_input("Issue type", value=conn.get("issue_type") or "Story")
        if not svc.jira_can_store_token():
            st.caption("This deployment does not store tokens: you will be asked for it when you push or sync.")
        if st.form_submit_button("Save connection", icon=I.SAVE):
            try:
                svc.save_jira_connection(user, site=site, email=email, token=token, project_key=pkey_,
                                         issue_type=itype)
                if token and not svc.jira_can_store_token():
                    st.session_state["jira_session_token"] = token
                st.session_state["flash"] = "Jira connection saved."
                st.rerun()
            except ValueError as exc:
                st.error(str(exc), icon=I.WARN)
    if conn:
        row = st.container(horizontal=True)
        if row.button("Test the connection", icon=":material/wifi_tethering:", key="jira_test"):
            try:
                who = svc.jira_test(user, token=st.session_state.get("jira_session_token", ""))
                st.success(f"Connected: Jira knows you as {who}.", icon=I.OK)
            except Exception as exc:  # noqa: BLE001 - shown to the person
                st.error(str(exc), icon=I.WARN)
        if row.button("Disconnect Jira", icon=I.DISCARD, key="jira_delete"):
            svc.delete_jira_connection(user)
            st.session_state.pop("jira_session_token", None)
            st.session_state["flash"] = "Jira disconnected. The stored token was deleted."
            st.rerun()

st.subheader("Your data", anchor=False)
with st.container(border=True):
    st.markdown("Download everything RAIA holds about you: account, memberships, invitations "
                "and assessment answers. Project content is downloaded from each project.")
    st.download_button("Download my data (JSON)", data=lambda: svc.my_data_export(user),
                       file_name="raia-my-data.json", mime="application/json",
                       icon=I.DOWNLOAD, key="my_data")

st.subheader("Delete account", anchor=False)
with st.container(border=True):
    st.markdown("Deletes your account, your assessment answers, your memberships and every "
                "project you are the only owner of, with all its data. Approvals you recorded on "
                "projects that other people own stay in those projects' audit trails. "
                "**This cannot be undone.**")
    confirm = st.text_input("Type DELETE to confirm", key="delete_account_confirm")
    if st.button("Delete my account", disabled=confirm.strip() != "DELETE", icon=I.DISCARD,
                 key="delete_account"):
        svc.delete_account(user)
        for k in list(st.session_state):
            del st.session_state[k]
        if auth.mode() != "dev":
            auth.logout()
        else:
            st.session_state["flash"] = "Account deleted."
            st.rerun()
