"""
raia.rationale.principles
=========================

The seven Responsible AI principles the RAIA project adopts, as a structure
the code can enumerate.

They used to exist only in prose, which meant "did we consider fairness?" was
something a prompt asked for and nothing could check. Here each principle
carries the corpus sections that ground it and the concrete questions a
requirement must answer, so principle coverage becomes a computed matrix
rather than a hope.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple


@dataclass(frozen=True)
class Principle:
    key: str
    name: str
    probe: str                       # what a requirement must actually answer
    grounding: Tuple[Tuple[str, str], ...] = ()   # (corpus source, section)
    keywords: Tuple[str, ...] = ()   # used to detect coverage in existing requirements


PRINCIPLES: Tuple[Principle, ...] = (
    Principle(
        key="accountability",
        name="Accountability",
        probe="Who is answerable for outcomes at each stage, and what evidence records it?",
        grounding=(
            ("ms_rai_v2", "Accountability Goals"),
            ("nist_ai_rmf", "GOVERN (cross-cutting)"),
        ),
        keywords=("accountab", "owner", "responsib", "sign-off", "approval", "audit",
                  "log", "governance", "record", "trace"),
    ),
    Principle(
        key="fairness",
        name="Diversity, non-discrimination and fairness",
        probe="Could outputs disadvantage a group, which fairness measure applies, and how is it checked?",
        grounding=(
            ("ms_rai_v2", "Fairness Goals"),
            ("eccola", "Fairness"),
        ),
        keywords=("fair", "discriminat", "bias", "parity", "protected", "equit",
                  "representativ", "disaggregat", "accessib"),
    ),
    Principle(
        key="human_oversight",
        name="Human agency and oversight",
        probe="Can a person understand, intervene in, override or stop the system where impact is significant?",
        grounding=(
            ("eu_ai_act", "Obligations for High-Risk Systems (Articles 8–15)"),
            ("eccola", "Agency and Oversight"),
        ),
        keywords=("oversight", "human review", "override", "intervene", "escalat",
                  "manual", "approve", "contest", "appeal", "human-in"),
    ),
    Principle(
        key="privacy",
        name="Privacy and data governance",
        probe="What personal data is processed, on what basis, minimised how, and governed by whom?",
        grounding=(
            ("ms_rai_v2", "Privacy & Security and Inclusiveness Goals"),
            ("eccola", "Data (privacy and governance)"),
        ),
        keywords=("privacy", "personal data", "lgpd", "gdpr", "consent", "retention",
                  "minimi", "anonym", "pseudonym", "encrypt", "access control"),
    ),
    Principle(
        key="robustness",
        name="Technical robustness and safety",
        probe="How is the system tested for accuracy and resilience in its real operating conditions?",
        grounding=(
            ("ms_rai_v2", "Reliability & Safety Goals"),
            ("nist_ai_rmf", "MEASURE (analysis and tracking)"),
        ),
        keywords=("robust", "reliab", "accuracy", "availab", "failover", "degrad",
                  "adversarial", "security", "test", "monitor", "drift"),
    ),
    Principle(
        key="transparency",
        name="Transparency",
        probe="What are affected people and operators told, and can a decision be explained to them?",
        grounding=(
            ("ms_rai_v2", "Transparency Goals"),
            ("eccola", "Transparency"),
        ),
        keywords=("transparen", "explain", "disclos", "inform", "notice", "document",
                  "interpretab", "traceab"),
    ),
    Principle(
        key="wellbeing",
        name="Social and environmental well-being",
        probe="What are the broader effects on affected communities, work and the environment?",
        grounding=(
            ("eccola", "Wellbeing and Society"),
            ("nist_ai_rmf", "MAP (context and risk identification)"),
        ),
        keywords=("societ", "environment", "sustainab", "wellbeing", "well-being",
                  "energy", "carbon", "community", "redress", "remedy"),
    ),
)

BY_KEY: Dict[str, Principle] = {p.key: p for p in PRINCIPLES}


def keys() -> List[str]:
    return [p.key for p in PRINCIPLES]


def covered_by(text: str, principle: Principle) -> bool:
    """Keyword-level check that a body of requirement text touches a principle.

    Deliberately a coarse, transparent heuristic rather than a model call: its
    output is a *candidate* gap list that the model then reviews and the human
    approves. A false positive costs a sentence of justification; a false
    negative is caught because the model is shown the same requirements.
    """
    low = (text or "").lower()
    return any(re.search(r"\b" + re.escape(k), low) for k in principle.keywords)


def coverage(text: str, subset: Sequence[str] = ()) -> Dict[str, bool]:
    """Map principle key -> whether the text appears to address it."""
    chosen = [BY_KEY[k] for k in subset if k in BY_KEY] or list(PRINCIPLES)
    return {p.key: covered_by(text, p) for p in chosen}


def grounding_pins(subset: Sequence[str] = ()) -> List[Tuple[str, str]]:
    chosen = [BY_KEY[k] for k in subset if k in BY_KEY] or list(PRINCIPLES)
    seen: List[Tuple[str, str]] = []
    for p in chosen:
        for g in p.grounding:
            if g not in seen:
                seen.append(g)
    return seen
