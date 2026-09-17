#!/usr/bin/env python3
"""
app.py — RAIA Streamlit application entry point.

Run with:
    streamlit run app.py

This file only decides *who* is here and *which pages exist*; each page lives
in ``views/`` and every building block in :mod:`raia.ui`. The page map (routes,
menu, and which pages need sign-in) is documented in :mod:`raia.ui.routes`.

Navigation is a top menu. Pages reached only from inside a project — the
project itself and each of its stages — are registered but hidden from the
menu, and take their context from the URL.
"""

import streamlit as st

# --- Configuration bridge (MUST run before importing raia.config) ----------
from raia.deploy import apply_secrets  # noqa: E402

apply_secrets()

from raia import auth                                  # noqa: E402
from raia.deploy import runtime_status                 # noqa: E402
from raia.ui import legal, routes, theme               # noqa: E402
from raia.ui.state import ensure_normative_index, get_service  # noqa: E402
from raia.ui.theme import I                            # noqa: E402


def _page(name: str, title: str, icon: str, url_path: str, **kw) -> "st.Page":
    return routes.register(
        name, st.Page(routes.FILES[name], title=title, icon=icon, url_path=url_path, **kw)
    )


def main() -> None:
    st.set_page_config(page_title="RAIA", page_icon=theme.ICON, layout="wide")
    theme.apply()
    st.logo(theme.LOGO, size="large")

    privacy = _page(routes.PRIVACY, "Privacy & terms", I.PRIVACY, "privacy")

    status = runtime_status()
    problem = auth.configuration_problem()
    identity = auth.current_identity() if (status.ready and not problem) else None

    if identity is None:
        st.session_state["_boot"] = {"status": status, "problem": problem}
        login = _page(routes.LOGIN, "Sign in", ":material/login:", "login", default=True)
        st.navigation([login, privacy], position="top").run()
        return

    user = get_service().sign_in(identity.email, identity.name)
    st.session_state["_user"] = user

    if legal.needs_acceptance(user.consented_at):
        consent = st.Page("views/consent.py", title="Welcome", icon=I.SHIELD,
                          url_path="welcome", default=True)
        st.navigation([consent, privacy], position="top").run()
        return

    with st.spinner("Preparing the normative knowledge base (first start only)"):
        ensure_normative_index()

    if status.explicit_mock:
        st.warning("**Mock mode is on.** Agent outputs are canned placeholders; no model is "
                   "being called. Maintainers: remove `RAIA_LLM_PROVIDER` from the app's "
                   "secrets to run for real.", icon=I.MOCK)

    home = _page(routes.HOME, "Home", I.HOME, "home", default=True)
    project = _page(routes.PROJECT, "Project", I.PROJECT, "project", visibility="hidden")
    stage = _page(routes.STAGE, "Stage", I.AGENTS, "stage", visibility="hidden")
    agents = _page(routes.AGENTS, "Agents", I.AGENTS, "agents")
    assessment = _page(routes.ASSESSMENT, "Assessment", I.ASSESSMENT, "assessment")
    settings = _page(routes.SETTINGS, "Settings", I.SETTINGS, "settings")
    account = [settings, privacy]
    if user.is_admin:
        account.insert(1, _page(routes.RESEARCH, "Research data", I.RESEARCH, "research"))

    st.navigation(
        {"": [home, project, stage, agents, assessment], "Account": account},
        position="top",
    ).run()


if __name__ == "__main__":
    main()
