"""
raia.rationale.types
====================

Shared vocabulary for the deterministic rationale engines.

Each RAIA agent now runs a rule engine *before* any prompt is assembled. The
engine reads the structured intake and the upstream artifacts, and produces a
:class:`RationaleResult`: a candidate verdict, the findings that support it,
the checklist the agent must declare coverage against, the norm excerpts that
must be in the prompt regardless of similarity score, and any conflicts that
are escalated to the human.

Division of labour (the architecture's reasoning contract):

* **code decides what is enumerable** — prohibition lists, area lists,
  obligation tables, coverage matrices, traceability, thresholds;
* **the model justifies, handles open-textured judgement, and writes prose**;
* **disagreement between the two is never averaged** — it becomes an Open
  Issue for human arbitration.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Status codes an agent may declare for a checklist item.
COVERED = "covered"
NOT_APPLICABLE = "not-applicable"
NOT_GROUNDED = "not-grounded"
VALID_STATUSES = (COVERED, NOT_APPLICABLE, NOT_GROUNDED)


@dataclass(frozen=True)
class Finding:
    """One fact the engine established deterministically from the inputs."""

    code: str
    label: str
    detail: str = ""

    def as_line(self) -> str:
        tail = f" — {self.detail}" if self.detail else ""
        return f"`{self.code}` · {self.label}{tail}"


@dataclass(frozen=True)
class ChecklistItem:
    """An element the agent's output MUST account for, one way or another.

    This is the "declared completeness" contract that replaces the vaguer goal
    of being as thorough as possible: the agent states, per key, whether it
    covered the item, why it does not apply, or that the retrieved excerpts do
    not ground it. A validator then checks that every key was declared.
    """

    key: str
    label: str
    why: str = ""


@dataclass(frozen=True)
class Pin:
    """A norm excerpt that must be in the prompt whatever the similarity score.

    Pins exist because the corpus is small enough that top-k retrieval can
    silently drop the decisive passage — classifying a recruitment system
    without ever seeing the high-risk area list, and looking confident doing
    it. Pinned sections are fetched by exact metadata match and merged ahead
    of the similarity results.
    """

    source: str
    section: str
    reason: str = ""


@dataclass
class RationaleResult:
    """What an engine hands to the agent before the model is called."""

    engine: str
    verdict: Dict[str, Any] = field(default_factory=dict)
    findings: List[Finding] = field(default_factory=list)
    checklist: List[ChecklistItem] = field(default_factory=list)
    pins: List[Pin] = field(default_factory=list)
    open_issues: List[str] = field(default_factory=list)
    #: Typed metadata for each open issue, index-aligned with ``open_issues``
    #: when raised through :meth:`raise_issue`: type, deciding role, blocking.
    issue_meta: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    tables: Dict[str, str] = field(default_factory=dict)
    data: Dict[str, Any] = field(default_factory=dict)
    query_terms: List[str] = field(default_factory=list)

    def raise_issue(self, text: str, type: str = "missing_information",
                    decision_owner: str = "product", blocking: bool = False) -> None:
        """Escalate something only a person can settle, with its type and owner.

        The text is what the reviewer reads; the type, the deciding role and the
        blocking flag are what make two projects' registers comparable.
        """
        self.open_issues.append(text)
        self.issue_meta.append(
            {"text": text, "type": type, "decision_owner": decision_owner, "blocking": blocking}
        )

    def typed_issues(self) -> List[Dict[str, Any]]:
        """Every engine issue with its metadata (untyped ones get safe defaults)."""
        meta = {m["text"]: m for m in self.issue_meta}
        return [
            dict(meta.get(t) or {"text": t, "type": "missing_information",
                                 "decision_owner": "product", "blocking": False})
            for t in self.open_issues
        ]

    # -- rendering ---------------------------------------------------------

    def summary_md(self) -> str:
        """The deterministic block injected into the prompt and shown at the gate.

        The model is told to treat this as ground truth: it may argue with a
        verdict, but it may not quietly restate it.
        """
        parts: List[str] = ["### Computed by code (ground truth — do not alter)"]

        if self.verdict:
            parts.append("**Verdict**\n")
            for k, v in self.verdict.items():
                parts.append(f"- `{k}`: **{_fmt(v)}**")

        if self.findings:
            parts.append("\n**Established findings**\n")
            parts.extend(f"- {f.as_line()}" for f in self.findings)

        for title, table in self.tables.items():
            parts.append(f"\n**{title}**\n\n{table}")

        if self.notes:
            parts.append("\n**Notes**\n")
            parts.extend(f"- {n}" for n in self.notes)

        if self.open_issues:
            parts.append("\n**Open issues raised by the rule engine (carry these forward)**\n")
            parts.extend(f"- {i}" for i in self.open_issues)

        if self.checklist:
            parts.append("\n**Required coverage** (declare each key in the machine block)\n")
            parts.extend(
                f"- `{c.key}` — {c.label}" + (f" ({c.why})" if c.why else "")
                for c in self.checklist
            )

        return "\n".join(parts)

    def checklist_keys(self) -> List[str]:
        return [c.key for c in self.checklist]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine": self.engine,
            "verdict": self.verdict,
            "findings": [
                {"code": f.code, "label": f.label, "detail": f.detail} for f in self.findings
            ],
            "checklist": [{"key": c.key, "label": c.label} for c in self.checklist],
            "pins": [{"source": p.source, "section": p.section} for p in self.pins],
            "open_issues": list(self.open_issues),
            "issue_meta": self.typed_issues(),
            "notes": list(self.notes),
            "data": self.data,
        }


def _fmt(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value) if value else "none"
    return str(value)


def empty_rationale(engine: str) -> RationaleResult:
    return RationaleResult(engine=engine)


def md_table(headers: List[str], rows: List[List[str]]) -> str:
    """Small Markdown table helper used by every engine."""
    if not rows:
        return "_(none)_"
    head = "| " + " | ".join(headers) + " |"
    sep = "|" + "---|" * len(headers)
    body = ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join([head, sep, *body])


def optional(value: Optional[str], fallback: str = "—") -> str:
    return value if value else fallback
