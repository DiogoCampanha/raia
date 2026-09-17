"""Tester assessment: optional profile, the five evaluation dimensions, stages, open questions."""

import streamlit as st

from raia.agents import AGENTS
from raia.ui import routes
from raia.ui.assessment import (CONSENT_TEXT, DIMENSIONS, INSTRUMENT_ID, NO_ANSWER, OPEN_QUESTIONS,
                                PROFILE, SCALE, SCALE_LABELS, STAGE_ITEM)
from raia.ui.components import page_header
from raia.ui.state import current_user, flash, get_service, show_flash
from raia.ui.theme import I

user = current_user()
svc = get_service()

page_header(
    "Assessment",
    "Your assessment of RAIA is the evidence this research depends on. It takes about ten "
    "minutes. You can save a draft and come back, and submit again later: the latest "
    "submission counts.",
    eyebrow="Research evaluation",
)
show_flash()

latest = svc.my_latest_rating(user)
draft = svc.my_assessment_draft(user)
source = draft or latest or {}
if latest:
    st.caption(f"You submitted on {latest['submitted_at'][:16].replace('T', ' ')} UTC.")
if draft:
    st.caption(f"Showing your draft saved on {draft['submitted_at'][:16].replace('T', ' ')} UTC.")

# Prefill from the stored draft or submission. Streamlit forgets widgets that were
# not drawn in a run (a person visiting another page), so any answer missing from
# the session is restored; answers already on screen are never overwritten.
def _prefill(key: str, value) -> None:
    if key not in st.session_state and value not in (None, ""):
        st.session_state[key] = value


for key, _, options in PROFILE:
    v = (source.get("profile") or {}).get(key)
    _prefill(f"a_profile_{key}", v if v in options + [NO_ANSWER] else None)
for key, _, _ in DIMENSIONS:
    v = (source.get("dimensions") or {}).get(key, {})
    _prefill(f"a_dim_{key}", v.get("score") if v.get("score") in SCALE else None)
    _prefill(f"a_dim_{key}_why", v.get("comment"))
for key in AGENTS:
    v = (source.get("stages") or {}).get(key, {})
    _prefill(f"a_stage_{key}", v.get("score") if v.get("score") in SCALE else None)
    _prefill(f"a_stage_{key}_comment", v.get("comment"))
for key, _ in OPEN_QUESTIONS:
    _prefill(f"a_open_{key}", (source.get("open") or {}).get(key))
_prefill("a_consent", True if source.get("consent") else None)


def _likert(label: str, key: str) -> None:
    st.radio(label, SCALE, index=None, key=key, horizontal=True,
             format_func=lambda v: f"{v} · {SCALE_LABELS[v]}")


with st.container(border=True):
    st.markdown(f"{I.SHIELD} **Consent**")
    st.checkbox(CONSENT_TEXT, key="a_consent")
    routes.link(routes.PRIVACY, "Read the Privacy Policy and User Agreement", icon=I.PRIVACY)

st.subheader("1. About you", anchor=False)
st.caption("Optional. Broad categories only, reported in aggregate. Nothing here identifies you.")
with st.container(border=True):
    cols = st.columns(2, gap="large")
    for i, (key, label, options) in enumerate(PROFILE):
        cols[i % 2].selectbox(label, options + [NO_ANSWER], index=None, key=f"a_profile_{key}",
                              placeholder="Choose one")

st.subheader("2. Evaluation of RAIA", anchor=False)
st.caption("Required. Rate how much you agree with each statement, from 1 (strongly disagree) to "
           "5 (strongly agree).")
done = 0
for i, (key, dimension, statement) in enumerate(DIMENSIONS, start=1):
    with st.container(border=True):
        st.markdown(f"**{dimension}**")
        _likert(statement, f"a_dim_{key}")
        st.text_input("Why? (optional)", key=f"a_dim_{key}_why")
        done += st.session_state.get(f"a_dim_{key}") is not None
st.progress(done / len(DIMENSIONS), text=f"{done} of {len(DIMENSIONS)} required answers")

st.subheader("3. Each stage", anchor=False)
st.caption("Optional. Rate only the stages you used.")
for key, agent in AGENTS.items():
    with st.expander(agent.spec.name):
        _likert(STAGE_ITEM, f"a_stage_{key}")
        st.text_input("Anything specific about this stage? (optional)", key=f"a_stage_{key}_comment")

st.subheader("4. Open questions", anchor=False)
with st.container(border=True):
    for key, question in OPEN_QUESTIONS:
        st.text_area(question, key=f"a_open_{key}", height=90)


def _payload() -> dict:
    ss = st.session_state
    return {
        "instrument": INSTRUMENT_ID,
        "consent": bool(ss.get("a_consent")),
        "profile": {k: ss.get(f"a_profile_{k}") for k, _, _ in PROFILE},
        "dimensions": {k: {"score": ss.get(f"a_dim_{k}"),
                           "comment": (ss.get(f"a_dim_{k}_why") or "").strip()}
                       for k, _, _ in DIMENSIONS},
        "stages": {k: {"score": ss.get(f"a_stage_{k}"),
                       "comment": (ss.get(f"a_stage_{k}_comment") or "").strip()}
                   for k in AGENTS},
        "open": {k: (ss.get(f"a_open_{k}") or "").strip() for k, _ in OPEN_QUESTIONS},
    }


st.divider()
row = st.container(horizontal=True)
if row.button("Submit assessment", type="primary", key="assess_submit", icon=I.CONFIRM):
    body = _payload()
    missing = [d for k, d, _ in DIMENSIONS if body["dimensions"][k]["score"] is None]
    if not body["consent"]:
        st.error("Please give your consent before submitting.", icon=I.ERROR)
    elif missing:
        st.error("Please rate every evaluation statement: " + ", ".join(missing) + ".", icon=I.ERROR)
    else:
        body["stages_rated"] = sum(1 for s in body["stages"].values() if s["score"] is not None)
        svc.submit_rating(user, body)
        flash("Thank you. Your assessment was recorded.")
        st.rerun()
if row.button("Save draft", key="assess_draft", icon=I.SAVE):
    svc.save_assessment_draft(user, _payload())
    flash("Draft saved. It is not included in the research data until you submit.")
    st.rerun()
