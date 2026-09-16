"""
raia.auth
=========

Who is using RAIA.

Hosted deployments sign people in with **Google** through Streamlit's native
OpenID Connect support (``st.login``). RAIA never sees or stores a password:
it receives an identity the provider has verified — an email address and a
display name — and everything else (projects, roles, approvals) hangs off that.

A ``dev`` mode exists for laptops and the test-suite: one fixed local identity,
no network. It is refused on any deployment backed by PostgreSQL unless it is
selected explicitly, so a misconfigured hosted app fails closed instead of
opening every project to whoever finds the URL.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from . import config, db


@dataclass(frozen=True)
class Identity:
    email: str
    name: str


def _auth_secrets() -> Any:
    try:
        import streamlit as st

        return st.secrets.get("auth")
    except Exception:  # noqa: BLE001 - no secrets file is normal locally
        return None


def oidc_configured() -> bool:
    section = _auth_secrets()
    if not section:
        return False
    try:
        has_flat = bool(section.get("client_id")) and bool(section.get("server_metadata_url"))
        has_named = any(isinstance(v, dict) or hasattr(v, "get") for v in section.values())
        return bool(section.get("redirect_uri")) and bool(section.get("cookie_secret")) and (
            has_flat or has_named
        )
    except Exception:  # noqa: BLE001
        return False


def mode() -> str:
    if config.AUTH_MODE in ("google", "dev"):
        return config.AUTH_MODE
    return "google" if oidc_configured() else "dev"


def configuration_problem() -> Optional[str]:
    """A reason the app must not serve anyone, or ``None``."""
    m = mode()
    if m == "dev" and db.is_postgres_url(config.DATABASE_URL) and config.AUTH_MODE != "dev":
        return (
            "This deployment stores projects in a shared database but has no sign-in "
            "configured. Add the [auth] block for Google sign-in to the app's secrets."
        )
    if m == "google" and not oidc_configured():
        return (
            "Google sign-in was selected (RAIA_AUTH = \"google\") but the [auth] block in the "
            "app's secrets is incomplete: it needs redirect_uri, cookie_secret, client_id, "
            "client_secret and server_metadata_url."
        )
    return None


def current_identity() -> Optional[Identity]:
    """The signed-in person, or ``None`` when nobody is signed in."""
    if mode() == "dev":
        return Identity(config.DEV_USER_EMAIL, config.DEV_USER_NAME)
    import streamlit as st

    user = st.user
    if not getattr(user, "is_logged_in", False):
        return None
    email = user.get("email")
    if not email:
        return None
    # Google marks addresses it has verified. An unverified address must not
    # be able to claim an invitation sent to that address.
    if user.get("email_verified") is False:
        return None
    return Identity(str(email), str(user.get("name") or ""))


def login() -> None:
    import streamlit as st

    section = _auth_secrets() or {}
    named = [k for k, v in dict(section).items() if hasattr(v, "get")]
    if named:
        st.login(named[0])
    else:
        st.login()


def logout() -> None:
    if mode() == "dev":
        return
    import streamlit as st

    st.logout()
