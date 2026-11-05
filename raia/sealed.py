"""
raia.sealed
===========

Symmetric encryption for what RAIA keeps but nobody should read casually:
the exact prompts and raw replies of each run.

The key comes from ``RAIA_TRANSCRIPT_KEY``. Without it nothing is sealed and
callers must not store the plain text: a run then keeps only its prompt hash
and token counts. Several comma-separated keys may be given; the first seals,
all of them open, so a key can be rotated without losing older transcripts.
"""

from __future__ import annotations

import base64
import hashlib
from typing import List, Optional

from . import config


def _fernet_key(passphrase: str) -> bytes:
    return base64.urlsafe_b64encode(hashlib.sha256(passphrase.encode("utf-8")).digest())


def _cipher():
    keys: List[str] = [k.strip() for k in (config.TRANSCRIPT_KEY or "").split(",") if k.strip()]
    if not keys:
        return None
    from cryptography.fernet import Fernet, MultiFernet

    return MultiFernet([Fernet(_fernet_key(k)) for k in keys])


def available() -> bool:
    """True when this deployment can seal (and therefore store) transcripts."""
    return _cipher() is not None


def seal(text: str) -> Optional[str]:
    """Encrypt ``text``; ``None`` when no key is configured."""
    c = _cipher()
    return c.encrypt(text.encode("utf-8")).decode("ascii") if c is not None else None


def unseal(token: str) -> Optional[str]:
    """Decrypt a sealed value; ``None`` when no configured key opens it."""
    c = _cipher()
    if c is None or not token:
        return None
    try:
        return c.decrypt(token.encode("ascii")).decode("utf-8")
    except Exception:  # noqa: BLE001 - a key that was rotated out
        return None
