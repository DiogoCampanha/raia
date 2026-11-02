"""Public landing page: what RAIA is, and sign-in."""

import streamlit as st

from raia import auth
from raia.agents import AGENTS
from raia.ui import routes
from raia.ui.components import esc, icon_html, pipeline_html
from raia.ui.theme import I

boot = st.session_state.get("_boot", {})
status = boot.get("status")
problem = boot.get("problem")

POINTS = [
    ("gavel", "Grounded", "Verdicts are computed by rules from the EU AI Act, PL 2338/2023 and four "
     "Responsible AI frameworks, and every citation is checked."),
    ("how_to_reg", "Human-approved", "Nothing is saved until a person reviews the evidence and approves. "
     "No agent ever triggers another one."),
    ("history", "Auditable", "Every approval is a versioned, tamper-evident record attributed to the "
     "person who made it."),
]

with st.container(key="login-split"):
    brand, side = st.columns([1.2, 1], gap="large", vertical_alignment="center")

with brand:
    st.html(
        '<section class="brand-panel">'
        '<h1 class="raia-title brand-h">Responsible AI, applied across the software life cycle</h1>'
        '<p class="brand-lead">RAIA is a Responsible AI Assistant: four specialized agents, grounded in '
        "legal texts and consolidated frameworks, with a human approval gate after every stage.</p>"
        + pipeline_html([(k, a.spec.name) for k, a in AGENTS.items()])
        + "</section>"
    )

with side, st.container(border=True, key="card-signin"):
    st.html('<h2 class="raia-serif signin-h">Sign in</h2>'
            '<p class="signin-sub">Use your Google account to open your projects.</p>')
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
        if st.button("Sign in with Google", type="primary", icon=":material/login:", key="login",
                     width="stretch"):
            auth.login()
        st.caption("RAIA receives your name and email address from Google, never your password.")
    st.html('<ul class="signin-points">' + "".join(
        f'<li>{icon_html(icon)}<div><b>{esc(head)}</b><span>{esc(body)}</span></div></li>'
        for icon, head, body in POINTS) + "</ul>")
