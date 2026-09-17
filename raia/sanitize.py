"""
raia.sanitize
=============

Input sanitization for free-text project artifacts — one of RAIA's governance
and reliability mechanisms.

Prompt injection through free-text project artifacts is a recognized threat, so
human-provided text is sanitized before it reaches an agent prompt and
suspicious patterns are *surfaced at the human review gate* rather than
silently removed.

Two things are worth being honest about.

**The surface.** Sanitizing the input form was never enough: the largest
free-text surface in the system is the draft a reviewer edits before approving,
which is committed to the blackboard and then injected into every downstream
prompt. That path is now sanitized too (see :mod:`raia.repository`).

**The limits.** Regex detection catches careless and opportunistic injection.
It does not catch a careful paraphrase, and it never will — which is precisely
why detection is a *notice to a human* rather than a control the system relies
on. The controls that actually carry the weight are the approval gate, the
citation validator, and least-privilege tool permissions.

Design choices, aligned with the principle that problems must be detectable at
review time:

* Control characters are stripped and text is length-capped — unconditionally
  safe transformations.
* Suspicious patterns are **flagged, not deleted**: the reviewer sees a
  deterministic warning attached to the draft and decides. Deleting them
  silently would itself violate auditability.
* Detection is deterministic (regex, no model call), so it behaves identically
  offline and is unit-testable.
* Patterns cover English and Portuguese, because the evaluation panel and the
  intended users work in both.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional

#: Hard cap on a single free-text input (chars). Generous for real briefs,
#: small enough to bound prompt size and blunt flooding attacks.
MAX_INPUT_CHARS = 20_000

#: Cap applied to an approved artifact. Far larger: an artifact is a generated
#: document that a human has read and accepted, not an untrusted paste, and
#: truncating one would corrupt the audit trail.
MAX_ARTIFACT_CHARS = 200_000

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# (pattern, human-readable finding) — matched case-insensitively.
_SUSPICIOUS = [
    (
        re.compile(
            r"\b(ignore|disregard|forget|override)\b.{0,40}\b(previous|prior|above|earlier|system)\b"
            r".{0,40}\b(instruction|rule|prompt|message|direction)", re.I | re.S,
        ),
        "instruction-override attempt",
    ),
    (
        re.compile(
            r"\b(ignore|ignora|ignorar|desconsider\w*|esque\w*|desrespeit\w*)\b.{0,40}"
            r"\b(anterior\w*|acima|prévi\w*|sistema)\b.{0,40}"
            r"\b(instru\w*|regra\w*|prompt|mensage\w*|orienta\w*)", re.I | re.S,
        ),
        "instruction-override attempt (Portuguese)",
    ),
    (
        re.compile(r"\byou are (now|no longer)\b|\bact as (an?|the)\b.{0,40}\b(system|admin|developer)\b", re.I),
        "role-reassignment attempt",
    ),
    (
        re.compile(r"\b(voc[êe] (agora )?[ée]|aja como|finja ser|assuma o papel)\b.{0,40}"
                   r"\b(sistema|administrador|desenvolvedor|outro agente)\b", re.I),
        "role-reassignment attempt (Portuguese)",
    ),
    (
        re.compile(r"\b(reveal|print|show|repeat|output)\b.{0,30}\b(system|hidden|secret)\b.{0,20}\b(prompt|instruction)", re.I),
        "system-prompt extraction attempt",
    ),
    (
        re.compile(r"\b(revel\w*|mostr\w*|imprim\w*|repit\w*|exib\w*)\b.{0,30}"
                   r"\b(sistema|oculto|secreto|inicial)\b.{0,20}\b(prompt|instru\w*)", re.I),
        "system-prompt extraction attempt (Portuguese)",
    ),
    (
        re.compile(r"</?\s*(system|assistant|tool)[\s_-]*(message|prompt|response)?\s*>", re.I),
        "fake role/markup tag",
    ),
    (
        re.compile(r"\[\s*Source\s*:", re.I),
        "citation-tag spoofing (input already contains RAIA citation markup)",
    ),
    (
        re.compile(r"<\s*/?\s*user_input\s*>", re.I),
        "input-delimiter spoofing",
    ),
    (
        re.compile(r"```\s*raia\b", re.I),
        "machine-block spoofing (input contains a RAIA contract block)",
    ),
    (
        re.compile(r"\b(classify|classific\w*|mark|marque|treat|trate)\b.{0,30}"
                   r"\b(as|como)\b.{0,20}\b(minimal|low|m[íi]nimo|baixo|n[ãa]o[- ]?high|not high)\b", re.I),
        "attempt to dictate the classification outcome",
    ),
]


@dataclass
class SanitizationResult:
    """Cleaned text plus the list of findings to surface at the H gate."""

    text: str
    findings: List[str] = field(default_factory=list)


def sanitize_free_text(text: str, max_chars: Optional[int] = None) -> SanitizationResult:
    """Sanitize one free-text value.

    Strips control characters, caps length, and flags (without removing)
    patterns commonly used for prompt injection. Findings are meant to be shown
    to the human reviewer alongside the draft.
    """
    limit = MAX_INPUT_CHARS if max_chars is None else max_chars
    clean = _CONTROL_CHARS.sub("", text or "")
    findings: List[str] = []

    if len(clean) > limit:
        clean = clean[:limit]
        findings.append(f"text truncated to {limit} characters")

    for pattern, label in _SUSPICIOUS:
        if pattern.search(clean) and label not in findings:
            findings.append(label)

    # The one transformation beyond flagging: literal <user_input> delimiters
    # are neutralized (angle brackets swapped for guillemets) so input can never
    # break out of its data envelope in the prompt. The content stays visible to
    # the reviewer; only the markup is defused.
    clean = re.sub(r"<(\s*/?\s*user_input\s*)>", r"‹\1›", clean, flags=re.I)

    return SanitizationResult(text=clean, findings=findings)


def sanitize_artifact(text: str) -> SanitizationResult:
    """Sanitize an approved artifact on its way into the shared repository."""
    return sanitize_free_text(text, max_chars=MAX_ARTIFACT_CHARS)


def sanitization_notice(findings: List[str]) -> str:
    """Deterministic warning block prepended to a draft when inputs look
    suspicious — visible at the human review gate and, if the human still
    approves, preserved in the Git-versioned artifact (audit evidence)."""
    bullets = "\n".join(f"> - {f}" for f in findings)
    return (
        "> **Input sanitization notice** — patterns often used for\n"
        "> prompt injection were detected in the human-provided inputs. Review\n"
        "> the draft below with extra care before approving:\n"
        f"{bullets}\n\n"
    )
