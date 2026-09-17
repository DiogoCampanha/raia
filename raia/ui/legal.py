"""
raia.ui.legal
=============

The Privacy Policy and User Agreement. The text lives in
``docs/legal/PRIVACY_AND_TERMS.md`` so that the same document can be published
outside the app (Google's OAuth consent screen asks for a public policy URL);
the app renders that file and nothing else.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from raia import config

DOCUMENT = Path(__file__).resolve().parents[2] / "docs" / "legal" / "PRIVACY_AND_TERMS.md"


def text() -> str:
    contact = config.CONTACT_EMAIL or "the study coordinator who invited you to RAIA"
    return DOCUMENT.read_text(encoding="utf-8").replace("{contact}", contact)


def needs_acceptance(consented_at: Optional[str]) -> bool:
    """Whether a person must (re)accept the current version before continuing."""
    return not consented_at or consented_at < config.LEGAL_EFFECTIVE
