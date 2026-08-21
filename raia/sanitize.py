"""
raia.sanitize
=============

Input sanitization for free-text project artifacts, one of RAIA's
governance and reliability mechanisms: prompt injection through free-text
inputs is a recognized threat, so human-provided text is sanitized before it reaches an agent
prompt, and suspicious patterns are *surfaced at the human review gate*
rather than silently removed.

Design choices (aligned with RAIA's principle that problems must be
*detectable at review time*):

* Control characters are stripped and inputs are length-capped —
  unconditionally safe transformations.
* Suspicious patterns (instruction overrides, role reassignment, fake
  role tags, spoofed citation tags) are **flagged, not deleted**: the
  reviewer sees a deterministic warning attached to the draft and decides.
  Deleting them silently would itself violate auditability.
* Detection is deterministic (regex, no LLM), so it works identically in
  mock mode and is unit-testable offline.
"""

import re
from dataclasses import dataclass, field
from typing import List

# Hard cap on a single free-text input (chars). Generous for real briefs,
# small enough to bound prompt size and blunt flooding attacks.
MAX_INPUT_CHARS = 20_000

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
        re.compile(r"\byou are (now|no longer)\b|\bact as (an?|the)\b.{0,40}\b(system|admin|developer)\b", re.I),
        "role-reassignment attempt",
    ),
    (
        re.compile(r"\b(reveal|print|show|repeat|output)\b.{0,30}\b(system|hidden|secret)\b.{0,20}\b(prompt|instruction)", re.I),
        "system-prompt extraction attempt",
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
]


@dataclass
class SanitizationResult:
    """Cleaned text plus the list of findings to surface at the H gate."""

    text: str
    findings: List[str] = field(default_factory=list)


def sanitize_free_text(text: str) -> SanitizationResult:
    """Sanitize one human-provided free-text input.

    Strips control characters, caps length, and flags (without removing)
    patterns commonly used for prompt injection. Findings are meant to be
    shown to the human reviewer alongside the draft.
    """
    clean = _CONTROL_CHARS.sub("", text or "")
    findings: List[str] = []

    if len(clean) > MAX_INPUT_CHARS:
        clean = clean[:MAX_INPUT_CHARS]
        findings.append(f"input truncated to {MAX_INPUT_CHARS} characters")

    for pattern, label in _SUSPICIOUS:
        if pattern.search(clean) and label not in findings:
            findings.append(label)

    # The one transformation beyond flagging: literal <user_input> delimiters
    # are neutralized (angle brackets swapped for guillemets) so input can
    # never break out of its data envelope in the prompt. The content stays
    # visible to the reviewer; only the markup is defused.
    clean = re.sub(
        r"<(\s*/?\s*user_input\s*)>", r"‹\1›", clean, flags=re.I
    )

    return SanitizationResult(text=clean, findings=findings)


def sanitization_notice(findings: List[str]) -> str:
    """Deterministic warning block prepended to a draft when inputs look
    suspicious — visible at the human review gate and, if the human still
    approves, preserved in the Git-versioned artifact (audit evidence)."""
    bullets = "\n".join(f"> - {f}" for f in findings)
    return (
        "> ⚠️ **Input sanitization notice** — patterns often used for\n"
        "> prompt injection were detected in the human-provided inputs. Review\n"
        "> the draft below with extra care before approving:\n"
        f"{bullets}\n\n"
    )
