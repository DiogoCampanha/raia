"""
raia.provenance
===============

Run metadata for the audit trail.

The blackboard used to record *that* a human approved something — approver and
timestamp — but nothing about what the system was looking at when it produced
the draft. For an architecture whose central argument is that the audit trail
is structural, "why did it say that?" has to be answerable from the trail
itself, months later, by someone who was not in the room.

Every artifact therefore carries the model, the sampling temperature, the
corpus version, the identity of every excerpt in the prompt, a hash of the
exact prompt, which attempt was approved, whether the human edited the draft,
and the result of every automated check.
"""

import datetime as _dt
import hashlib
from typing import Any, Dict, List, Optional, Sequence

from . import config

SCHEMA_VERSION = "raia-artifact/1"


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def prompt_hash(system: str, user: str) -> str:
    h = hashlib.sha256()
    h.update((system or "").encode("utf-8"))
    h.update(b"\x00")
    h.update((user or "").encode("utf-8"))
    return h.hexdigest()[:16]


def build(
    *,
    agent_key: str,
    agent_name: str,
    layer: str,
    excerpt_ids: Sequence[str],
    pinned_ids: Sequence[str],
    prompt_digest: str,
    attempt: int,
    engine: Optional[str] = None,
    restored: bool = False,
    retries: int = 0,
    finish_reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Assemble the provenance record for one generated draft."""
    return {
        "schema": SCHEMA_VERSION,
        "agent": {"key": agent_key, "name": agent_name, "layer": layer},
        "generated_at": _now(),
        "model": {
            "provider": config.LLM_PROVIDER,
            "name": config.LLM_MODEL,
            "temperature": config.LLM_TEMPERATURE,
            "max_tokens": config.LLM_MAX_TOKENS,
            "finish_reason": finish_reason,
            "retries": retries,
        },
        "corpus": {
            "version": config.corpus_version(),
            "top_k": config.RAG_TOP_K,
            "excerpts": list(excerpt_ids),
            "pinned": list(pinned_ids),
        },
        "rationale_engine": engine,
        "prompt_sha256_16": prompt_digest,
        "attempt": attempt,
        "restored_from_disk": restored,
    }


def finalize(
    record: Dict[str, Any],
    *,
    approver: str,
    edited: bool,
    validation: Dict[str, Any],
    rejection_history: Sequence[Dict[str, str]] = (),
) -> Dict[str, Any]:
    """Complete the record at the moment of human approval."""
    out = dict(record or {})
    out["approval"] = {
        "approved_by": approver,
        "approved_at": _now(),
        "human_edited_draft": edited,
        "rejections_before_approval": list(rejection_history),
    }
    out["validation"] = validation
    return out


def header_comment(key: str, record: Dict[str, Any]) -> str:
    """The HTML comment stamped at the top of every artifact file.

    Kept human-readable on purpose: the Markdown file is the artifact a person
    reads, and its provenance should not require opening the JSON sidecar.
    """
    approval = record.get("approval", {})
    model = record.get("model", {})
    corpus = record.get("corpus", {})
    validation = record.get("validation", {})
    lines: List[str] = [
        f"RAIA artifact: {key}",
        f"approved by: {approval.get('approved_by', 'human')}",
        f"approved at: {approval.get('approved_at', _now())}",
        f"human edited draft: {'yes' if approval.get('human_edited_draft') else 'no'}",
        f"attempt approved: {record.get('attempt', 1)}",
        f"model: {model.get('provider', '?')}/{model.get('name', '?')} "
        f"@ temperature {model.get('temperature', '?')}",
        f"corpus version: {corpus.get('version', '?')} "
        f"(top_k {corpus.get('top_k', '?')}, {len(corpus.get('excerpts', []))} excerpts, "
        f"{len(corpus.get('pinned', []))} pinned)",
        f"rationale engine: {record.get('rationale_engine') or 'none'}",
        f"prompt sha256/16: {record.get('prompt_sha256_16', '?')}",
        f"automated checks: {validation.get('headline', 'not run')}",
    ]
    body = "\n".join(f"     {l}" for l in lines)
    return f"<!--\n{body}\n-->\n\n"
