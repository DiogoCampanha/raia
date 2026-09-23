"""Guide: how to use RAIA and its agents, step by step, for testers.

The content lives in :mod:`raia.ui.guide`, which also generates
``docs/TESTERS.md``; this page only lays it out.
"""

import streamlit as st

from raia.ui import guide, routes
from raia.ui.components import page_header
from raia.ui.theme import I, STATUS

page_header(guide.TITLE, guide.SUBTITLE, eyebrow="Guide")

with st.container(border=True):
    st.markdown(guide.INTRO)

# ---- Finding your way ------------------------------------------------------------

st.subheader("Finding your way", anchor=False)
st.caption("The menu at the top of the screen.")
cols = st.columns(len(guide.MENU), gap="small")
for col, (head, body) in zip(cols, guide.MENU):
    with col, st.container(border=True, height="stretch"):
        st.markdown(f"**{head}**")
        st.caption(body)

# ---- Step by step ----------------------------------------------------------------

st.subheader("Step by step", anchor=False)
for n, step in enumerate(guide.STEPS, 1):
    with st.container(border=True):
        st.markdown(f"#### {n} · {step.title}")
        st.markdown(step.body)
        if step.link:
            route, label = step.link
            routes.link(route, label, icon=I.OPEN)
        if step.title == "Continue through the stages":
            st.markdown(
                "| Agent | What it asks you | Needs approved first | Produces |\n|---|---|---|---|\n"
                + "\n".join(f"| {a} | {b} | {c} | {d} |" for a, b, c, d in guide.agent_rows())
            )
            st.caption("Every stage shows one of these statuses:")
            by_label = {label: (color, icon) for label, color, icon in STATUS.values()}
            for label, meaning in guide.STATUSES:
                color, icon = by_label.get(label, ("gray", None))
                c1, c2 = st.columns([1.3, 4], vertical_alignment="center")
                with c1:
                    st.badge(label, icon=icon, color=color)
                c2.caption(meaning)

# ---- What to look for --------------------------------------------------------------

st.subheader("What to look for", anchor=False)
st.caption("These are what the study is asking you about.")
for row in range(0, len(guide.LOOK_FOR), 2):
    cols = st.columns(2, gap="medium")
    for col, (head, body) in zip(cols, guide.LOOK_FOR[row:row + 2]):
        with col, st.container(border=True, height="stretch"):
            st.markdown(f"**{head}**")
            st.caption(body)

left, right = st.columns(2, gap="large")
with left:
    st.subheader("Worth trying to break", anchor=False)
    st.markdown("\n".join(f"- {item}" for item in guide.TRY_TO_BREAK))
with right:
    st.subheader("What feedback helps most", anchor=False)
    st.markdown("\n".join(f"- {item}" for item in guide.FEEDBACK))
    routes.link(routes.ASSESSMENT, "Open the assessment", icon=I.ASSESSMENT)

# ---- Troubleshooting -----------------------------------------------------------------

st.subheader("If something goes wrong", anchor=False)
for head, body in guide.TROUBLE:
    with st.expander(head.replace("**", "")):
        st.markdown(body)
