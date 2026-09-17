"""Public landing page: what RAIA is, and sign-in."""

import streamlit as st

from raia import auth
from raia.ui import routes
from raia.ui.components import page_header
from raia.ui.theme import I

boot = st.session_state.get("_boot", {})
status = boot.get("status")
problem = boot.get("problem")

page_header(
    "Responsible AI, applied across the software life cycle",
    "RAIA is a Responsible AI Assistant: five specialized agents, grounded in legal texts and "
    "consolidated frameworks, with a human approval gate after every stage.",
    eyebrow="RAIA · Responsible AI Assistant",
)

if status is not None and not status.ready:
    st.error("This deployment is not fully configured yet, so the agents cannot run. Nothing "
             "is wrong on your side: please let the study coordinator know you saw this screen.",
             icon=I.ERROR)
    if status.problem:
        st.caption(status.problem)
    with st.expander("Maintainer setup"):
        st.markdown(
            "Open the app's **Settings → Secrets** on the hosting platform and add the model "
            f"credential, for example `{status.key_env_var or 'ANTHROPIC_API_KEY'} = \"sk-...\"`. "
            "The app restarts on its own."
        )
elif problem:
    st.error("Sign-in is not configured, so the app will not open. " + problem, icon=I.ERROR)
else:
    if st.button("Sign in with Google", type="primary", icon=":material/login:", key="login"):
        auth.login()
    st.caption("RAIA receives your name and email address from Google, never your password.")

st.space("medium")
cols = st.columns(3, gap="large")
points = [
    (":material/gavel:", "Grounded", "Verdicts are computed by rules from the EU AI Act, "
     "PL 2338/2023 and four Responsible AI frameworks, and every citation is checked."),
    (":material/how_to_reg:", "Human-approved", "Nothing is saved until a person reviews the "
     "evidence and approves. No agent ever triggers another one."),
    (":material/history:", "Auditable", "Every approval is a versioned, tamper-evident record "
     "attributed to the person who made it."),
]
for col, (icon, head, body) in zip(cols, points):
    with col, st.container(border=True):
        st.markdown(f"{icon} **{head}**")
        st.caption(body)

st.space("small")
routes.link(routes.PRIVACY, "Privacy Policy and User Agreement", icon=I.PRIVACY)
