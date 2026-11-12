"""Guide: how to use RAIA and its agents, step by step, for testers.

The content lives in :mod:`raia.ui.guide`, which also generates
``docs/TESTERS.md``; this page only lays it out: a table of contents that stays
in view, and each step with a screenshot of the screen it describes.
"""

import html

import streamlit as st

from raia.ui import guide, routes
from raia.ui.components import page_header
from raia.ui.theme import I, STATUS


def txt(text: str) -> str:
    """Escape text for an HTML text node (apostrophes stay as they are)."""
    return html.escape(text, quote=False)

page_header(guide.TITLE, guide.SUBTITLE, eyebrow="Guide")

with st.container(border=True, key="card-notice-intro"):
    st.markdown(guide.INTRO)

SECTIONS = [("path", guide.EVALUATION_PATH_TITLE), ("scope", guide.SCOPE_TITLE), ("menu", "Finding your way")] + [(f"step-{n}", f"{n}. {s.title}") for n, s in enumerate(guide.STEPS, 1)] + [
    ("words", "Words RAIA uses"), ("look-for", "What to look for"), ("break", "Worth trying to break"),
    ("trouble", "If something goes wrong")]

toc, body = st.columns([1, 3.2], gap="large")
with toc, st.container(key="guide-toc"):
    st.html('<nav class="raia-toc" aria-label="On this page"><p class="h">On this page</p><ol>'
            + "".join(f'<li><a href="#{a}">{txt(t)}</a></li>' for a, t in SECTIONS) + "</ol></nav>")

with body:
    # ---- The short path ----------------------------------------------------------
    st.subheader(guide.EVALUATION_PATH_TITLE, anchor="path")
    st.caption(guide.EVALUATION_PATH_LEAD)
    with st.container(border=True, key="card-notice-path"):
        st.markdown("\n".join(f"{n}. **{head}.** {text}"
                              for n, (head, text) in enumerate(guide.EVALUATION_PATH, 1)))
        st.caption(guide.ADVICE)
        links = st.container(horizontal=True, key="guide-path-links")
        with links:
            routes.link(routes.HOME, "Go to Home", icon=I.OPEN)
            routes.link(routes.ASSESSMENT, "Open the assessment", icon=I.ASSESSMENT)

    # ---- What RAIA is, and is not ------------------------------------------------
    st.subheader(guide.SCOPE_TITLE, anchor="scope")
    with st.container(border=True):
        st.markdown("\n".join(f"- **{head}** {text}" for head, text in guide.SCOPE))

    # ---- Finding your way --------------------------------------------------------
    st.subheader("Finding your way", anchor="menu")
    st.caption("The menu at the top of the screen.")
    with st.container(border=True):
        st.html('<dl class="guide-menu">' + "".join(
            f"<dt>{txt(head)}</dt><dd>{txt(body_.replace('*', ''))}</dd>" for head, body_ in guide.MENU) + "</dl>")

    # ---- Step by step ------------------------------------------------------------
    st.subheader("Step by step", anchor=False)
    for n, step in enumerate(guide.STEPS, 1):
        with st.container(border=True, key=f"card-step-{n}"):
            st.html(f'<h4 class="guide-step-h" id="step-{n}"><span class="num">{n}</span>{txt(step.title)}</h4>')
            st.markdown(step.body)
            shot = guide.image_path(step)
            if shot:
                st.image(str(shot), width="stretch")
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

    # ---- Words RAIA uses -----------------------------------------------------------
    st.subheader("Words RAIA uses", anchor="words")
    st.caption("Every identifier is a prefix that says what the thing is, then a number. Each stage's page "
               "has the words for that stage under \"Words used here\".")
    with st.container(border=True):
        st.html('<dl class="guide-menu">' + "".join(
            f"<dt>{txt(term)}</dt><dd>{txt(meaning)}</dd>" for term, meaning, _ in guide.GLOSSARY) + "</dl>")

    # ---- What to look for ----------------------------------------------------------
    st.subheader("What to look for", anchor="look-for")
    st.caption("These are what the study is asking you about.")
    for row in range(0, len(guide.LOOK_FOR), 2):
        cols = st.columns(2, gap="medium")
        for col, (head, text) in zip(cols, guide.LOOK_FOR[row:row + 2]):
            with col, st.container(border=True, height="stretch"):
                st.markdown(f"**{head}**")
                st.caption(text)

    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("Worth trying to break", anchor="break")
        st.markdown("\n".join(f"- {item}" for item in guide.TRY_TO_BREAK))
    with right:
        st.subheader("What feedback helps most", anchor=False)
        st.markdown("\n".join(f"- {item}" for item in guide.FEEDBACK))
        routes.link(routes.ASSESSMENT, "Open the assessment", icon=I.ASSESSMENT)

    # ---- Troubleshooting -------------------------------------------------------------
    st.subheader("If something goes wrong", anchor="trouble")
    for head, text in guide.TROUBLE:
        with st.expander(head.replace("**", "")):
            st.markdown(text)
