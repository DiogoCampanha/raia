"""
Write one agent card per agent to ``docs/agents/``, from the code.

    python -m raia.contract.agent_cards

Every card follows ``docs/templates/agent-card.md``: purpose, place in the
lifecycle, normative grounding, inputs, what the decision procedure settles,
what a person decides, the record it produces, the identifiers it must account
for, its checks and its limitations. Everything a spec, a schema or a rule
engine already declares is read from them, so a card cannot drift from the
implementation; ``tests/test_contract.py`` fails when a card is out of date.
"""

from pathlib import Path
from typing import Dict, List

from .. import config
from ..examples import EXAMPLES
from ..repository import ARTIFACT_FILES
from . import vocab as V
from .assemble import PREFIX, RECORD_TYPES
from .render import AGENT_SECTIONS, COMMON_HEAD, COMMON_TAIL
from .schema import EXTENSIONS

OUT = Path(__file__).resolve().parents[2] / "docs" / "agents"

#: The prose no spec holds: what the agent cannot do. Stated so nobody finds it first.
LIMITATIONS: Dict[str, List[str]] = {
    "risk_classifier": [
        "The screens match declared answers against enumerated lists; a purpose the person does not "
        "declare is not screened.",
        "Whether the narrow-task exemption holds is open-textured and always left to a person.",
    ],
    "requirements_reviewer": [
        "The coverage matrix is lexical: it produces candidate gaps for review and is not evidence "
        "that a requirement is absent or adequate.",
        "Value elicitation is recorded from the declared stakeholders; it does not replace eliciting "
        "values from those stakeholders.",
    ],
    "story_refiner": [
        "Card selection follows the declared capabilities and upstream answers; a capability not "
        "declared does not select its cards.",
        "Acceptance criteria are checked for form, not for whether the threshold is right.",
    ],
    "auditor": [
        "Evidence matching is lexical and conservative: an item lands in NOT VERIFIED when in doubt, "
        "and a match is only a reason to assess, not proof.",
    ],
    "drift_monitor": [
        "Metrics are computed from the telemetry supplied; the Ops layer is a demonstrable prototype.",
        "Severity follows a fixed threshold rule; whether a breach warrants action is a human decision.",
    ],
}

CHECKS: Dict[str, List[str]] = {
    "risk_classifier": ["Every computed obligation code has a note, and no other code appears"],
    "requirements_reviewer": ["Every assigned EVR id has a requirement and a gap note, and no other id appears",
                              "Every requirement carries a testable element"],
    "story_refiner": ["Every story id has an entry", "Only selected ECCOLA cards and approved EVR ids are used",
                      "Criteria are labelled AC-<story>-<n>"],
    "auditor": ["Every computed item has a verdict", "An unevidenced item is never upgraded (restored by code)"],
    "drift_monitor": ["One alert per computed breach, with the computed severity (restored by code)",
                      "Every figure in the prose is in the computed set"],
}

COMMON_CHECKS = [
    "The record conforms to the schema (one repair attempt, then a fallback record)",
    "Every citation resolves to an excerpt retrieved for this run",
    "Every checklist item is declared covered, not applicable or not grounded",
    "Every finding has an action or an open issue",
    "The rule engine's issues are carried forward; the verdict is reconciled",
]


def _fields(model, prefix: str = "") -> List[str]:
    """Field rows for a model, nested models flattened as ``parent[].child``."""
    from typing import get_args

    from pydantic import BaseModel

    rows = []
    for name, f in model.model_fields.items():
        if (f.json_schema_extra or {}).get("computed"):
            continue
        path = f"{prefix}{name}"
        rows.append(f"| `{path}` | {(f.description or '—').replace('|', '/')} |")
        inner = [a for a in (get_args(f.annotation) or (f.annotation,))
                 if isinstance(a, type) and issubclass(a, BaseModel)]
        if inner:
            many = "[]" if get_args(f.annotation) else ""
            rows += _fields(inner[0], f"{path}{many}.")
    return rows


def card(key: str) -> str:
    from ..agents import AGENTS
    from ..ui.agent_docs import DOCS

    agent = AGENTS[key]
    spec = agent.spec
    docs = DOCS.get(key, {})
    try:
        rationale = spec.engine(EXAMPLES.get(key, {}), {}) if spec.engine else None
    except Exception:  # noqa: BLE001 - engines that need upstream data
        rationale = None
    producers = {a.spec.output_key: a.spec.name for a in AGENTS.values()}

    lines = [
        f"# Agent card — {spec.name}",
        "",
        "> Generated from the code by `python -m raia.contract.agent_cards`. Follows "
        "`docs/templates/agent-card.md`. Do not edit by hand.",
        "",
        "## 1. Purpose",
        "",
        spec.description.strip(),
        "",
        "## 2. Place in the lifecycle",
        "",
        "| | |", "|---|---|",
        f"| Layer | {spec.layer} |",
        f"| SDLC phase | {spec.sdlc_phase} |",
        f"| When to run | {docs.get('when', '—')} |",
        f"| Requires approved | {', '.join(producers.get(u, u) for u in spec.required_upstream) or 'nothing — first stage'} |",
        f"| Reads | {', '.join(producers.get(u, u) for u in spec.upstream_keys) or 'nothing'} |",
        f"| Produces | `{ARTIFACT_FILES.get(spec.output_key, spec.output_key)}` — {RECORD_TYPES[key].lower()} |",
        "",
        "## 3. Normative grounding",
        "",
        "| Source | Authority |", "|---|---|",
        *[f"| {config.SOURCE_NAMES.get(s, s)} | {config.AUTHORITY_LEVELS.get(s, '')} |" for s in spec.grounding_sources],
        "",
        "## 4. Inputs",
        "",
        "| Group | Question | Kind | Required |", "|---|---|---|---|",
        *[f"| {f.group.split('·', 1)[-1].strip()} | {f.label} | {f.kind} | {'yes' if f.required else 'no'} |"
          for f in spec.input_fields],
        "",
        "## 5. What the decision procedure settles in code",
        "",
        *[f"- {d}" for d in docs.get("decides", [])],
        "",
    ]
    if rationale is not None:
        lines += [
            "Checklist the record must declare:",
            "",
            *[f"- `{c.key}` — {c.label}" for c in rationale.checklist],
            "",
            "Excerpts pinned for the canonical scenario:",
            "",
            *[f"- {config.SOURCE_NAMES.get(p.source, p.source)} — {p.section} ({p.reason})" for p in rationale.pins],
            "",
        ]
    lines += [
        "## 6. What a person decides",
        "",
        *[f"- {d}" for d in docs.get("you", [])],
        "- Every open issue the record raises, and whether to approve, edit or reject the record.",
        "",
        "## 7. The record it produces",
        "",
        f"Schema `{V.SCHEMA_VERSION}` — `docs/schema/{key}.schema.json`. Identifier prefix `{PREFIX[key]}`. "
        "Shared core as in `docs/output-contract.md`; the extension:",
        "",
        "| Field | Content |", "|---|---|",
        *_fields(EXTENSIONS[key]),
        "",
        "Rendered sections: " + " → ".join(COMMON_HEAD + AGENT_SECTIONS[key] + COMMON_TAIL) + ".",
        "",
        f"Verdict keys the agent declares: {', '.join(f'`{k}`' for k in spec.verdict_keys) or '—'}.",
        "",
        "## 8. Checks",
        "",
        *[f"- {c}" for c in COMMON_CHECKS + CHECKS.get(key, [])],
        "",
        "## 9. Limitations",
        "",
        "- The normative corpus is a set of curated summaries prepared for the project; a citation "
        "resolves to a section of a summary, not to official wording.",
        *[f"- {l}" for l in LIMITATIONS.get(key, [])],
        "",
    ]
    return "\n".join(lines)


def generated() -> Dict[str, str]:
    from ..agents import AGENTS

    return {f"{key}.md": card(key) for key in AGENTS}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in generated().items():
        (OUT / name).write_text(text, encoding="utf-8")
        print(f"wrote docs/agents/{name}")


if __name__ == "__main__":
    main()
