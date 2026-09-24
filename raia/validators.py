"""
raia.validators
===============

Deterministic checks that run *after* the model and *before* the human gate.

The RAIA architecture's reliability claims used to be carried entirely by
instructions in a prompt: the model was asked to cite, asked to respect
precedence, asked to declare what it could not ground. Nothing verified that
it did, so an unsupported obligation could reach a Git commit unchallenged.

Everything in this module is a rule, not a model call. Each validator returns
an item that is shown at the approval gate and persisted with the artifact, so
"hallucinated obligations are detectable at review time" describes a mechanism
rather than a hope.

Validators never block. They inform the human, who remains the checkpoint —
a failed check on an otherwise sound draft is a reason to look closely, not a
reason for the software to overrule a person.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .rationale.types import VALID_STATUSES

FAIL = "fail"
WARN = "warn"
PASS = "pass"

_LEVEL_ICON = {PASS: "**Pass** ·", WARN: "**Warning** ·", FAIL: "**Fail** ·"}
_LEVEL_RANK = {PASS: 0, WARN: 1, FAIL: 2}

CITATION_RE = re.compile(r"\[\s*Source\s*:\s*(?P<body>[^\]]+?)\s*\]", re.I)
MACHINE_BLOCK_RE = re.compile(r"```raia\s*\n(?P<body>.*?)```", re.S | re.I)
HEADING_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$", re.M)
NUMBER_RE = re.compile(r"(?<![\w.])(\d+(?:[.,]\d+)?)(?![\w])")


@dataclass
class ValidationItem:
    code: str
    level: str
    title: str
    detail: str = ""
    items: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "level": self.level,
            "title": self.title,
            "detail": self.detail,
            "items": list(self.items),
        }


@dataclass
class ValidationReport:
    items: List[ValidationItem] = field(default_factory=list)

    def add(self, item: ValidationItem) -> None:
        self.items.append(item)

    @property
    def failures(self) -> List[ValidationItem]:
        return [i for i in self.items if i.level == FAIL]

    @property
    def warnings(self) -> List[ValidationItem]:
        return [i for i in self.items if i.level == WARN]

    @property
    def ok(self) -> bool:
        return not self.failures

    @property
    def level(self) -> str:
        return max((i.level for i in self.items), key=lambda l: _LEVEL_RANK[l], default=PASS)

    def headline(self) -> str:
        f, w = len(self.failures), len(self.warnings)
        if f:
            return f"{f} check(s) failed, {w} warning(s)"
        if w:
            return f"All checks passed with {w} warning(s)"
        return "All checks passed"

    def summary_md(self) -> str:
        lines = [f"**Automated checks — {self.headline()}**", ""]
        for i in self.items:
            lines.append(f"{_LEVEL_ICON[i.level]} **{i.title}** — {i.detail}" if i.detail
                         else f"{_LEVEL_ICON[i.level]} **{i.title}**")
            lines.extend(f"    - {x}" for x in i.items[:12])
            if len(i.items) > 12:
                lines.append(f"    - …and {len(i.items) - 12} more")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level,
            "headline": self.headline(),
            "items": [i.to_dict() for i in self.items],
        }


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _norm(text: str) -> str:
    """Normalize a citation body for comparison.

    Dash variants and whitespace differ between what a model emits and what the
    retriever produced; neither difference should be treated as a bad citation.
    """
    text = unicodedata.normalize("NFKC", text or "")
    # A citation rendered inside a Markdown table has its pipe escaped.
    text = text.replace("\\|", "|")
    text = text.replace("—", "-").replace("–", "-").replace("−", "-")
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower().rstrip(".")


def parse_machine_block(draft: str) -> Dict[str, str]:
    """Read the ```raia key: value block the output contract requires."""
    m = MACHINE_BLOCK_RE.search(draft or "")
    if not m:
        return {}
    out: Dict[str, str] = {}
    for line in m.group("body").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip()
    return out


def strip_machine_block(draft: str) -> str:
    return MACHINE_BLOCK_RE.sub("", draft or "").strip()


def sections_in(draft: str) -> List[str]:
    return [m.group("title").strip() for m in HEADING_RE.finditer(draft or "")]


def citations_in(draft: str) -> List[str]:
    return [m.group("body").strip() for m in CITATION_RE.finditer(draft or "")]


# ---------------------------------------------------------------------------
# Individual validators
# ---------------------------------------------------------------------------


def check_citations(draft: str, allowed: Sequence[str]) -> ValidationItem:
    """Every citation tag must resolve to an excerpt that was actually retrieved.

    ``allowed`` is the list of ``NormChunk.citation()`` strings that were in the
    prompt. A tag that matches none of them is either an excerpt the agent never
    saw or an invented section — in both cases a fabricated ground.
    """
    found = citations_in(draft)
    if not found:
        return ValidationItem(
            "citations.absent", FAIL, "Citations",
            "The draft contains no citation tags at all, so no claim in it is grounded.",
        )

    index = {_norm(a.strip("[]").replace("Source:", "", 1)): a for a in allowed}
    unresolved: List[str] = []
    for tag in found:
        if _norm(tag) not in index:
            unresolved.append(f"[Source: {tag}]")

    total = len(found)
    if unresolved:
        return ValidationItem(
            "citations.unresolved", FAIL, "Citations",
            f"{len(unresolved)} of {total} citation tag(s) do not match any excerpt that was "
            "retrieved for this run. Treat the claims they support as ungrounded.",
            sorted(set(unresolved)),
        )
    return ValidationItem(
        "citations.resolved", PASS, "Citations",
        f"All {total} citation tag(s) resolve to excerpts retrieved for this run.",
    )


def check_sections(draft: str, required: Sequence[str]) -> ValidationItem:
    """The output contract's required headings must be present."""
    if not required:
        return ValidationItem("sections.none", PASS, "Output structure", "No structure required.")
    present = {_norm(s) for s in sections_in(draft)}
    missing = [s for s in required if _norm(s) not in present]
    if missing:
        return ValidationItem(
            "sections.missing", FAIL, "Output structure",
            f"{len(missing)} required section(s) are missing from the draft.",
            missing,
        )
    return ValidationItem(
        "sections.present", PASS, "Output structure",
        f"All {len(required)} required sections are present.",
    )


def check_coverage(draft: str, checklist_keys: Sequence[str]) -> ValidationItem:
    """Declared completeness: every checklist key must carry a valid status.

    This replaces "be as thorough as possible" with something measurable. An
    agent may legitimately decline an item — ``not-applicable`` with a reason,
    or ``not-grounded`` when the retrieved excerpts do not support it — but it
    may not silently skip it.
    """
    if not checklist_keys:
        return ValidationItem("coverage.none", PASS, "Declared coverage", "No checklist for this agent.")

    block = parse_machine_block(draft)
    missing, invalid = [], []
    for key in checklist_keys:
        raw = block.get(f"coverage.{key}")
        if raw is None:
            missing.append(key)
            continue
        status = raw.split("—")[0].split(" - ")[0].strip().lower()
        if status not in VALID_STATUSES:
            invalid.append(f"{key}: {raw}")

    if missing or invalid:
        detail = []
        if missing:
            detail.append(f"{len(missing)} checklist key(s) not declared")
        if invalid:
            detail.append(f"{len(invalid)} declared with an invalid status")
        return ValidationItem(
            "coverage.incomplete", FAIL, "Declared coverage",
            "; ".join(detail) + f". Valid statuses: {', '.join(VALID_STATUSES)}.",
            [f"missing: {k}" for k in missing] + [f"invalid: {k}" for k in invalid],
        )

    ungrounded = [
        k for k in checklist_keys
        if block.get(f"coverage.{k}", "").lower().startswith(("not-grounded", "not-applicable"))
    ]
    if ungrounded:
        return ValidationItem(
            "coverage.declined", WARN, "Declared coverage",
            f"{len(ungrounded)} of {len(checklist_keys)} items were declared not covered, with reasons. "
            "Check that each reason is acceptable.",
            [f"{k}: {block.get(f'coverage.{k}', '')}" for k in ungrounded],
        )
    return ValidationItem(
        "coverage.complete", PASS, "Declared coverage",
        f"All {len(checklist_keys)} checklist items declared covered.",
    )


def check_truncation(draft: str, finish_reason: Optional[str] = None) -> ValidationItem:
    """Detect a response that stopped at the token limit rather than finishing."""
    reason = (finish_reason or "").lower()
    if reason in ("max_tokens", "length"):
        return ValidationItem(
            "output.truncated", FAIL, "Completeness of the response",
            "The model stopped at the token limit; the draft is cut off. Raise the token limit "
            "or reduce the input, and regenerate.",
        )
    body = strip_machine_block(draft or "").rstrip()
    if body and not re.search(r"[.!?:)\]`|]$", body) and len(body.splitlines()[-1]) > 60:
        return ValidationItem(
            "output.maybe_truncated", WARN, "Completeness of the response",
            "The draft ends mid-sentence. It may have been cut off.",
        )
    return ValidationItem("output.complete", PASS, "Completeness of the response",
                          "The response terminated normally.")


def check_reconciliation(draft: str, verdict: Dict[str, Any], keys: Sequence[str]) -> ValidationItem:
    """Compare the model's stated verdict with the rule engine's.

    Agreement is not required — the engine cannot settle open-textured
    questions. What is required is that a disagreement be *declared*, so it
    reaches a human instead of being quietly resolved in prose.
    """
    if not keys:
        return ValidationItem("verdict.none", PASS, "Verdict reconciliation", "No verdict to reconcile.")

    block = parse_machine_block(draft)
    declared = block.get("verdict.agrees_with_screen", "").strip().lower()
    if declared not in ("yes", "no"):
        return ValidationItem(
            "verdict.undeclared", FAIL, "Verdict reconciliation",
            "The draft does not declare whether it agrees with the rule engine's verdict "
            "(`verdict.agrees_with_screen: yes|no`).",
        )

    mismatches: List[str] = []
    for key in keys:
        stated = block.get(f"verdict.{key}", "").strip()
        computed = str(verdict.get(key, "")).strip()
        if stated and _norm(stated) != _norm(computed):
            mismatches.append(f"{key}: engine said “{computed}”, draft says “{stated}”")

    if declared == "no" or mismatches:
        return ValidationItem(
            "verdict.disagreement", WARN, "Verdict reconciliation",
            "The agent disagrees with the rule engine. This is allowed, and must be arbitrated by "
            "you — check that the disagreement is argued and recorded as an open issue.",
            mismatches or ["the agent declared a disagreement without naming a differing key"],
        )
    return ValidationItem(
        "verdict.agrees", PASS, "Verdict reconciliation",
        "The agent's verdict matches the rule engine's on every checked key.",
    )


def check_numbers(draft: str, allowed: Iterable[str], label: str = "Reported figures") -> ValidationItem:
    """Every number in the narrative must come from the computed set.

    Applies where metrics are computed by code and the model only interprets
    them. Years, counts of items, and section numbers are excluded so the check
    stays about *metric values*.
    """
    allowed_set = {_norm(str(a)) for a in allowed}
    body = strip_machine_block(draft or "")
    body = re.sub(r"\[\s*Source\s*:[^\]]+\]", "", body)
    invented: List[str] = []
    for m in NUMBER_RE.finditer(body):
        raw = m.group(1)
        norm = _norm(raw.replace(",", "."))
        if norm in allowed_set or _norm(raw) in allowed_set:
            continue
        # Ignore integers that are plainly not metric values.
        if re.fullmatch(r"\d{1,4}", raw) and "." not in raw:
            continue
        invented.append(raw)

    if invented:
        return ValidationItem(
            "numbers.invented", FAIL, label,
            "The draft contains numeric values that are not in the set computed by code. "
            "Metric values must never be produced by the model.",
            sorted(set(invented)),
        )
    return ValidationItem("numbers.match", PASS, label,
                          "Every figure in the draft comes from the computed set.")


def check_traceability(draft: str, required_ids: Sequence[str], label: str,
                       code: str = "traceability") -> ValidationItem:
    """Every upstream identifier (EVR-1, S2, …) must appear in the draft."""
    if not required_ids:
        return ValidationItem(f"{code}.none", PASS, label, "Nothing upstream to trace.")
    body = draft or ""
    missing = [i for i in required_ids if not re.search(rf"(?<![\w-]){re.escape(i)}(?![\w-])", body)]
    if missing:
        return ValidationItem(
            f"{code}.missing", FAIL, label,
            f"{len(missing)} of {len(required_ids)} upstream item(s) are not accounted for in the draft.",
            missing,
        )
    return ValidationItem(f"{code}.complete", PASS, label,
                          f"All {len(required_ids)} upstream items are accounted for.")


def check_unknown_ids(draft: str, pattern: str, known: Sequence[str], label: str) -> ValidationItem:
    """Identifiers cited by the draft must exist upstream (no invented EVR ids)."""
    used = set(re.findall(pattern, draft or ""))
    unknown = sorted(u for u in used if u not in set(known))
    if unknown:
        return ValidationItem(
            "references.unknown", FAIL, label,
            "The draft references identifiers that do not exist in the approved upstream artifacts.",
            unknown,
        )
    return ValidationItem("references.known", PASS, label,
                          "Every referenced identifier exists upstream.")


def check_open_issues(draft: str, engine_issues: Sequence[str]) -> ValidationItem:
    """Conflicts raised by the rule engine must survive into the draft."""
    if not engine_issues:
        return ValidationItem("open_issues.none", PASS, "Open issues",
                              "The rule engine raised no conflicts.")
    section = _section_body(draft, "Open Issues")
    if not section.strip():
        return ValidationItem(
            "open_issues.dropped", FAIL, "Open issues",
            f"The rule engine raised {len(engine_issues)} conflict(s) and the draft has no populated "
            "Open Issues section. Conflicts must never be resolved silently.",
            list(engine_issues),
        )
    bullets = [l for l in section.splitlines() if l.strip().startswith(("-", "*", "1."))]
    if len(bullets) < len(engine_issues):
        return ValidationItem(
            "open_issues.partial", WARN, "Open issues",
            f"The rule engine raised {len(engine_issues)} conflict(s) but the draft lists {len(bullets)}. "
            "Check that none was dropped.",
            list(engine_issues),
        )
    return ValidationItem("open_issues.carried", PASS, "Open issues",
                          f"All {len(engine_issues)} engine-raised conflict(s) are carried forward.")


#: Tokens that suggest something could actually be checked. "shall" and "must"
#: are deliberately absent: they are the modal verb of every requirement ever
#: written, including the unverifiable ones, so counting them would make this
#: validator agree with everything.
_MEASURABLE = (
    "≤", "<=", ">=", "≥", "%", "threshold", "measur", "verif", "test", "audit",
    "log", "rate", "ratio", "within", "at least", "no more than", "no fewer",
    "documented", "reviewed", "signed off", "per protected", "per group",
    "evidence", "record", "report",
)


def is_verifiable(text: str) -> bool:
    """True when a requirement carries something a test, audit or measurement can settle.

    Lexical and deliberately simple: a number, or one of the measurable markers.
    Strip any identifier first — ``EVR-1`` or ``R7`` is not a threshold.
    """
    low = (text or "").lower()
    return bool(re.search(r"\d", text or "")) or any(t in low for t in _MEASURABLE)


def resolve_citations(tags: Sequence[str], allowed: Sequence[str]) -> Tuple[List[str], List[str]]:
    """Split citation tags into those that match a retrieved excerpt and those that do not.

    Resolved tags are returned in the retriever's own spelling, so what is
    stored is exactly what was retrieved.
    """
    index = {_norm(x.strip("[]").replace("Source:", "", 1)): x for x in allowed}
    resolved: List[str] = []
    unresolved: List[str] = []
    for tag in tags or []:
        m = CITATION_RE.search(str(tag))
        body = m.group("body").strip() if m else str(tag).strip("[] ").replace("Source:", "", 1)
        hit = index.get(_norm(body))
        if hit and hit not in resolved:
            resolved.append(hit)
        elif not hit:
            unresolved.append(str(tag))
    return resolved, unresolved


def check_requirement_quality(draft: str, ids: Sequence[str]) -> ValidationItem:
    """Every assigned requirement must be phrased so something can check it.

    A requirement that cannot be tested, audited, measured or inspected is the
    unactionable guidance the literature criticises, and it will quietly fail
    every downstream audit. The check is lexical and advisory: it warns, and a
    human decides.
    """
    if not ids:
        return ValidationItem("evr.none", PASS, "Requirement quality", "No requirements to check.")
    weak: List[str] = []
    for rid in ids:
        body = _near(draft, rid)
        if not body:
            continue
        # The identifier itself contains a digit; it is not evidence that the
        # requirement is measurable.
        without_id = re.sub(rf"(?<![\w-]){re.escape(rid)}(?![\w-])", "", body)
        if not is_verifiable(without_id):
            weak.append(f"{rid}: {body[:100].strip()}")
    if weak:
        return ValidationItem(
            "evr.unverifiable", WARN, "Requirement quality",
            f"{len(weak)} requirement(s) contain no measurable or testable element.",
            weak,
        )
    return ValidationItem("evr.verifiable", PASS, "Requirement quality",
                          f"All {len(ids)} requirements carry a testable element.")


def check_forbidden_verdicts(draft: str, not_verified: Sequence[str]) -> ValidationItem:
    """An item the engine found no evidence for may not be called satisfied.

    The model may downgrade a computed verdict — it has the narrative the
    engine only pattern-matched — but it may never upgrade one. This is the
    anti-ethics-washing rule, enforced.
    """
    if not not_verified:
        return ValidationItem("verdicts.none", PASS, "Evidence discipline",
                              "No item was pre-assigned NOT VERIFIED.")
    upgraded: List[str] = []
    for item_id in not_verified:
        body = _near(draft, item_id)
        if not body:
            continue
        low = body.lower()
        if re.search(r"\bsatisfied\b", low) and not re.search(
            r"\bnot\s+(?:verified|satisfied)\b|\bpartially\s+satisfied\b|\bnot\b[^.]{0,20}\bsatisfied\b", low
        ):
            upgraded.append(f"{item_id}: {body[:120].strip()}")
    if upgraded:
        return ValidationItem(
            "verdicts.upgraded", FAIL, "Evidence discipline",
            "Item(s) with no evidence in the sprint outcomes are reported as satisfied. "
            "A verdict may be downgraded by the agent, never upgraded.",
            upgraded,
        )
    return ValidationItem(
        "verdicts.respected", PASS, "Evidence discipline",
        f"All {len(not_verified)} unevidenced item(s) remain unverified.",
    )


def _near(draft: str, identifier: str) -> str:
    """The line or list item in which an identifier appears."""
    for line in (draft or "").splitlines():
        if re.search(rf"(?<![\w-]){re.escape(identifier)}(?![\w-])", line):
            return line
    return ""


def _section_body(draft: str, title: str) -> str:
    """Text under a given H2 heading, up to the next H2."""
    text = draft or ""
    target = _norm(title)
    matches = list(HEADING_RE.finditer(text))
    for i, m in enumerate(matches):
        if _norm(m.group("title")) == target:
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            return text[m.end():end]
    return ""


def extract_open_issues(draft: str) -> List[str]:
    """Pull the Open Issues bullets out of a draft, for the shared register."""
    body = _section_body(draft, "Open Issues")
    out: List[str] = []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith(("-", "*")):
            s = s.lstrip("-* ").strip()
        elif re.match(r"^\d+[.)]\s", s):
            s = re.sub(r"^\d+[.)]\s*", "", s).strip()
        else:
            continue
        if s and s.lower() not in ("none", "none.", "n/a", "(none)", "no open issues."):
            out.append(s)
    return out
