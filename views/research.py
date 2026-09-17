"""Research data export (study coordinators only)."""

import streamlit as st

from raia.ui.assessment import INSTRUMENT_ID
from raia.ui.components import page_header
from raia.ui.state import current_user, get_service
from raia.ui.theme import I

user = current_user()
page_header("Research data", "A pseudonymized export of every project's evaluation events and "
            "every submitted assessment.", eyebrow="Study coordination")
if not user.is_admin:
    st.error("Only study coordinators can see this page.", icon=I.LOCK)
    st.stop()
st.markdown(
    "Participants are codes, projects are numbered, and no names or email addresses are "
    f"included. Assessments carry the instrument id (current: `{INSTRUMENT_ID}`); drafts are "
    "excluded. Free-text answers are exported as written: read them before publishing."
)
if st.button("Prepare export", type="primary", icon=I.RESEARCH):
    st.session_state["_research_zip"] = get_service().research_export(user)
data = st.session_state.get("_research_zip")
if data:
    st.download_button("Download research data (zip)", data=data, icon=I.DOWNLOAD,
                       file_name="raia-research-data.zip", mime="application/zip")
