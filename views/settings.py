"""Settings: profile, legal documents, personal data, session and account deletion."""

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

st.subheader("Your data", anchor=False)
with st.container(border=True):
    st.markdown("Download everything RAIA holds about you: account, memberships, invitations "
                "and assessment answers. Project content is downloaded from each project.")
    st.download_button("Download my data (JSON)", data=lambda: svc.my_data_export(user),
                       file_name="raia-my-data.json", mime="application/json",
                       icon=I.DOWNLOAD, key="my_data")

if auth.mode() != "dev":
    st.subheader("Session", anchor=False)
    if st.button("Sign out", key="logout", icon=I.LOGOUT):
        for k in list(st.session_state):
            del st.session_state[k]
        auth.logout()

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
