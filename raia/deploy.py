"""
raia.deploy
===========

Hosted-deployment glue: **configuration comes from Streamlit secrets**, not
from a ``.env`` file.

RAIA's design keeps the system provider-agnostic by reading everything from
environment variables (see :mod:`raia.config`). That works well locally with
a ``.env`` file, but a hosted deployment (Streamlit Community Cloud) has no
filesystem the maintainer can edit: configuration is pasted into the app's
*Secrets* box instead.

This module is the bridge. It runs **before** :mod:`raia.config` is imported
and copies Streamlit secrets into the process environment, accepting the
shapes a maintainer would plausibly type::

    ANTHROPIC_API_KEY = "sk-ant-..."          # canonical

    anthropic_api_key = "sk-ant-..."          # lowercase
    CLAUDE_API_KEY    = "sk-ant-..."          # familiar alias
    LLM_API_KEY       = "sk-ant-..."          # provider-neutral

    [anthropic]                               # sectioned
    api_key = "sk-ant-..."

It also decides the provider: if only an OpenAI key is present the provider
switches to ``openai`` automatically, so a maintainer never has to set two
values to change one thing.

Finally it reports what it found (:func:`runtime_status`) so the UI can state
plainly whether the deployment is live or misconfigured. RAIA never degrades
to canned output silently: mock mode is an explicit choice
(``RAIA_LLM_PROVIDER = "mock"``), never an accident.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Iterator, Mapping, Optional, Tuple

# --------------------------------------------------------------------------
# Which environment variable each provider's credential lives in
# --------------------------------------------------------------------------

PROVIDER_KEY_ENV: Dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}

#: Names (case-insensitive, section-flattened) that mean "the Anthropic key".
_ANTHROPIC_ALIASES = {
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_APIKEY",
    "ANTHROPIC_KEY",
    "ANTHROPIC_TOKEN",
    "CLAUDE_API_KEY",
    "CLAUDE_APIKEY",
    "CLAUDE_KEY",
}

#: Names that mean "the OpenAI key".
_OPENAI_ALIASES = {
    "OPENAI_API_KEY",
    "OPENAI_APIKEY",
    "OPENAI_KEY",
    "OPENAI_TOKEN",
}

#: Provider-neutral names: assigned to whichever provider is configured.
_GENERIC_KEY_ALIASES = {
    "API_KEY",
    "APIKEY",
    "LLM_API_KEY",
    "LLM_KEY",
    "RAIA_API_KEY",
    "RAIA_LLM_API_KEY",
    "RAIA_LLM_KEY",
}

#: Tuning knobs accepted with or without the RAIA_ prefix.
_SETTING_ALIASES = {
    "LLM_PROVIDER": "RAIA_LLM_PROVIDER",
    "PROVIDER": "RAIA_LLM_PROVIDER",
    "LLM_MODEL": "RAIA_LLM_MODEL",
    "MODEL": "RAIA_LLM_MODEL",
    "LLM_TEMPERATURE": "RAIA_LLM_TEMPERATURE",
    "TEMPERATURE": "RAIA_LLM_TEMPERATURE",
    "LLM_MAX_TOKENS": "RAIA_LLM_MAX_TOKENS",
    "MAX_TOKENS": "RAIA_LLM_MAX_TOKENS",
    "RAG_TOP_K": "RAIA_RAG_TOP_K",
    "TOP_K": "RAIA_RAG_TOP_K",
}

#: Env vars RAIA itself understands, accepted verbatim.
_PASSTHROUGH_PREFIXES = ("RAIA_",)


# --------------------------------------------------------------------------
# Secret flattening
# --------------------------------------------------------------------------


def _flatten(mapping: Mapping[str, Any], prefix: str = "") -> Iterator[Tuple[str, Any]]:
    """Yield ``(FLAT_NAME, value)`` pairs, joining nested sections with ``_``.

    ``[anthropic] api_key = "x"`` therefore arrives as
    ``("ANTHROPIC_API_KEY", "x")`` -- the canonical name, for free.
    """
    for key, value in mapping.items():
        name = f"{prefix}{key}"
        if isinstance(value, Mapping):
            yield from _flatten(value, prefix=f"{name}_")
        else:
            yield name.upper().replace("-", "_"), value


def _clean(value: Any) -> str:
    """Normalize a secret value to a stripped string.

    Guards against the two mistakes people actually make when pasting a key
    into a web form: surrounding quotes and stray whitespace/newlines.
    """
    text = str(value).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    return "".join(text.split())  # kills newlines pasted mid-key


def collect(
    secrets: Optional[Mapping[str, Any]] = None,
    current_env: Optional[Mapping[str, str]] = None,
) -> Dict[str, str]:
    """Translate a secrets mapping into RAIA environment variables.

    Pure function (no side effects) so it can be unit-tested without
    Streamlit. Pass ``None`` for ``secrets`` to read ``st.secrets``; a
    missing or empty secrets file yields ``{}``. ``current_env`` is the
    already-set environment that secrets must not override.
    """
    if secrets is None:
        secrets = _streamlit_secrets()
    if current_env is None:
        current_env = os.environ
    if not secrets:
        return {}

    env: Dict[str, str] = {}
    generic_key: Optional[str] = None

    for name, raw in _flatten(secrets):
        if raw is None or raw == "":
            continue
        value = _clean(raw)

        if name in _ANTHROPIC_ALIASES:
            env["ANTHROPIC_API_KEY"] = value
        elif name in _OPENAI_ALIASES:
            env["OPENAI_API_KEY"] = value
        elif name in _GENERIC_KEY_ALIASES:
            generic_key = value
        elif name in _SETTING_ALIASES:
            env[_SETTING_ALIASES[name]] = value
        elif name.startswith(_PASSTHROUGH_PREFIXES):
            env[name] = value
        else:
            # Unknown but harmless (e.g. a key for some other integration):
            # pass it through so nothing the maintainer set is lost.
            env[name] = value

    # A provider-neutral key fills whichever provider ends up selected.
    if generic_key:
        provider = (
            env.get("RAIA_LLM_PROVIDER") or current_env.get("RAIA_LLM_PROVIDER") or ""
        ).lower()
        target = PROVIDER_KEY_ENV.get(provider, "ANTHROPIC_API_KEY")
        env.setdefault(target, generic_key)

    # If the only credential present is OpenAI's, select that provider so the
    # maintainer does not have to set two secrets to express one intention.
    if "RAIA_LLM_PROVIDER" not in env and "RAIA_LLM_PROVIDER" not in current_env:
        if env.get("OPENAI_API_KEY") and not env.get("ANTHROPIC_API_KEY"):
            env["RAIA_LLM_PROVIDER"] = "openai"

    return env


def _streamlit_secrets() -> Mapping[str, Any]:
    """Read ``st.secrets``, tolerating every "not configured" failure mode."""
    try:
        import streamlit as st

        return dict(st.secrets)
    except Exception:
        # No secrets.toml, Streamlit not installed, or running outside a
        # Streamlit process -- all normal. Local runs use .env instead.
        return {}


def apply_secrets(secrets: Optional[Mapping[str, Any]] = None) -> Dict[str, str]:
    """Copy secrets into ``os.environ``.

    MUST be called before ``raia.config`` is imported, because that module
    snapshots the environment at import time. Existing environment variables
    win, so a local ``.env`` or a shell export still overrides a secret.
    Returns the names/values that were applied.
    """
    env = collect(secrets)
    for name, value in env.items():
        os.environ.setdefault(name, value)
    return env


# --------------------------------------------------------------------------
# Status reporting (so the UI never has to guess)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RuntimeStatus:
    """What the deployment is actually able to do right now."""

    provider: str
    model: str
    key_env_var: Optional[str]
    key_present: bool
    key_looks_valid: bool
    explicit_mock: bool

    @property
    def ready(self) -> bool:
        """True when agent runs will reach a real (or deliberately mocked) model."""
        return self.explicit_mock or (self.key_present and self.key_looks_valid)

    @property
    def problem(self) -> Optional[str]:
        """A one-line diagnosis, or None when everything is configured."""
        if self.ready:
            return None
        if not self.key_present:
            return f"No API key found. Set `{self.key_env_var}` in the app's secrets."
        return (
            f"The `{self.key_env_var}` secret does not look like a valid "
            f"{self.provider} key (check for a truncated paste)."
        )


def _key_shape_ok(provider: str, key: str) -> bool:
    """Cheap sanity check on a credential's shape -- catches truncated pastes.

    Deliberately permissive: a real authentication failure is reported at
    call time with the provider's own message. This only rejects values that
    cannot possibly be keys (placeholders, a handful of characters).
    """
    if len(key) < 20:
        return False
    if key.lower() in {"changeme", "your-api-key", "your_api_key_here", "todo"}:
        return False
    if provider == "anthropic":
        return key.startswith("sk-")
    if provider == "openai":
        return key.startswith("sk-")
    return True


def runtime_status() -> RuntimeStatus:
    """Inspect the live configuration. Import ``raia.config`` lazily."""
    from . import config

    provider = config.LLM_PROVIDER
    key_var = PROVIDER_KEY_ENV.get(provider)
    key = os.environ.get(key_var, "") if key_var else ""
    return RuntimeStatus(
        provider=provider,
        model=config.LLM_MODEL,
        key_env_var=key_var,
        key_present=bool(key),
        key_looks_valid=bool(key) and _key_shape_ok(provider, key),
        explicit_mock=(provider == "mock"),
    )


def friendly_llm_error(exc: BaseException) -> str:
    """Turn a provider exception into something a tester can act on.

    Testers are ethicists and product people, not API users; a raw
    ``AuthenticationError`` traceback tells them nothing useful.
    """
    text = f"{type(exc).__name__}: {exc}"
    low = text.lower()
    if "authentication" in low or "401" in low or "invalid x-api-key" in low:
        return (
            "The deployment's API key was rejected by the provider. This is a "
            "configuration problem on our side, not something you did — please "
            "tell the study coordinator."
        )
    if "rate" in low and "limit" in low or "429" in low:
        return (
            "The provider is rate-limiting this deployment. Wait a few seconds "
            "and run the stage again."
        )
    if "credit" in low or "quota" in low or "billing" in low:
        return (
            "The deployment's API account is out of credit. Please tell the "
            "study coordinator."
        )
    if "overloaded" in low or "529" in low or "timeout" in low or "timed out" in low:
        return (
            "The model provider is temporarily overloaded. Run the stage again "
            "in a moment."
        )
    return f"The model call failed. Please report this to the coordinator.\n\n`{text}`"
