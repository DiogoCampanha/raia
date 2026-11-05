"""
raia.logs
=========

Structured logging for RAIA: one JSON object per line on standard error, which
is what hosted platforms collect.

Two kinds of record go through here. Operational events — a failed model call,
an unexpected error behind a reference id shown to the person — are logged
only. Security-relevant actions with account-wide or administrative reach — a
research export, a deletion, a refused access — are also written to the
``audit_log`` table by :meth:`raia.projects.ProjectService.audit`, so they
survive a platform that rotates its logs.

Log lines never carry project content, prompts, names or emails: people appear
as user ids, projects as project ids.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from typing import Any

_CONFIGURED = False

# Silent until set up: a library import (the test-suite, a script) prints nothing.
logging.getLogger("raia").addHandler(logging.NullHandler())
logging.getLogger("raia").propagate = False


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {
            "at": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in getattr(record, "fields", {}).items():
            out[key] = value
        if record.exc_info:
            out["error"] = self.formatException(record.exc_info)
        return json.dumps(out, ensure_ascii=False, default=str)


def setup() -> None:
    """Send the ``raia`` loggers to standard error as JSON (idempotent)."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("raia")
    root.addHandler(handler)
    root.setLevel(os.getenv("RAIA_LOG_LEVEL", "INFO").upper())
    root.propagate = False
    _CONFIGURED = True


def get(name: str) -> logging.Logger:
    return logging.getLogger(f"raia.{name}")


def event(logger: logging.Logger, msg: str, level: int = logging.INFO, **fields: Any) -> None:
    """Log ``msg`` with structured fields."""
    logger.log(level, msg, extra={"fields": fields})


def error_reference(logger: logging.Logger, exc: BaseException, **fields: Any) -> str:
    """Log an unexpected error with a short reference a person can quote."""
    ref = uuid.uuid4().hex[:8]
    logger.error("unexpected error", exc_info=exc, extra={"fields": {"ref": ref, **fields}})
    return ref
