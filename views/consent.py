"""Accept the Privacy Policy and User Agreement (first visit, or after it changes)."""

import streamlit as st

from raia import auth
from raia.ui import legal, routes
from raia.ui.components import page_header
from raia.ui.state import current_user, get_service
from raia.ui.theme import I

user = current_user()
page_header(
    "Before you start",
    "Please read how RAIA handles your information and the terms of use." if not user.consented_at
    else "The Privacy Policy and User Agreement changed since you last accepted it.",
)
with st.container(border=True, height=420):
    st.markdown(legal.text())
agree = st.checkbox("I have read the Privacy Policy and User Agreement and I accept them.",
                    key="consent_agree")
row = st.container(horizontal=True)
if row.button("Continue", type="primary", disabled=not agree, key="consent_continue", icon=I.OPEN):
    get_service().record_consent(user)
    st.rerun()
if auth.mode() != "dev" and row.button("Sign out", key="consent_signout", icon=I.LOGOUT):
    auth.logout()
st.caption("You can read this document at any time, without signing in.")
routes.link(routes.PRIVACY, "Open the public page", icon=I.PRIVACY)
