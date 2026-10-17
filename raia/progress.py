"""
raia.progress
=============

Where an agent run is, for whoever is watching.

An agent turn has a few long steps (the decision procedure, retrieval, the model
pass, the checks). The stage page shows a working screen while it runs; this
module lets the run say which step it is on without knowing anything about the
page. A listener is set for the duration of one run; with none set, reporting a
step does nothing, so the pipeline and the tests are unaffected.
"""

from __future__ import annotations

import contextlib
import contextvars
from typing import Callable, Iterator, Optional

_LISTENER: contextvars.ContextVar[Optional[Callable[[str], None]]] = contextvars.ContextVar(
    "raia_progress", default=None)


def step(label: str) -> None:
    """Report that the run has reached ``label``. Never raises."""
    fn = _LISTENER.get()
    if fn is None:
        return
    try:
        fn(label)
    except Exception:  # noqa: BLE001 - a display problem must never break a run
        pass


@contextlib.contextmanager
def listening(fn: Callable[[str], None]) -> Iterator[None]:
    token = _LISTENER.set(fn)
    try:
        yield
    finally:
        _LISTENER.reset(token)
