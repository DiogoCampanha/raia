"""
Write the RAIA AI Skill's instructions and references, from the code.

    python -m raia.skill.build

Writes the static copy in ``docs/ai-skill/`` (everything but the project
folder, which only exists in a project's download). The prose is in
``raia/skill/text/``; each ``{{block}}`` in it is filled here from the
vocabularies, rules and registers the software itself uses, and
``references/vocabulary.md`` is generated whole. ``tests/test_skill.py`` fails
when the static copy is out of date.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .. import config
from ..contract import vocab as V

TEXT = Path(__file__).resolve().parent / "text"
OUT = Path(__file__).resolve().parents[2] / "docs" / "ai-skill"

#: The skill's folder name, which is also its ``name`` in SKILL.md.
SKILL_DIR = "raia-responsible-ai"

#: The most SKILL.md may weigh: small enough to paste into an assistant's
#: custom-instructions field, which is how teams without skill support use it.
SKILL_MAX_CHARS = 8000

_BLOCK = re.compile(r"\{\{([a-z_]+)\}\}")

#: Readable names for the risk-context triggers of the ECCOLA card selection.
_CONTEXT_TRIGGERS = {
    "high_risk": "high-risk tier",
    "limited_risk": "limited-risk tier (transparency duties)",
    "significant_effects": "significant effects on people",
    "personal_data": "personal data",
    "protected_data": "protected attributes or their proxies",
    "disability_data": "disability data",
    "production": "live in production",
    "safety_component": "safety component",
}

#: The priority floors, in the order code applies them (see docs/output-contract.md).
FLOORS = [
    ("A prohibited or excessive-risk practice was declared", "critical, blocking",
     "EU AI Act Art. 5; PL 2338/2023 excessive risk"),
    ("The finding cites a legal instrument, or links a legal obligation code", "at least high",
     "Authority precedence: legal > standard > advisory"),
    ("A requirement closes a legal obligation gap", "at least high", "Same"),
    ("A requirement answers approved risks", "the highest of their priorities (at least medium for a principle "
     "declared at stake, otherwise low)", "NIST AI RMF MANAGE 1"),
    ("An audit item is unverified on a high-risk system", "at least high (otherwise medium)",
     "Microsoft RAI Standard v2 accountability; NIST AI RMF GOVERN"),
]

#: The identifiers RAIA assigns (see docs/output-contract.md).
IDENTIFIERS = [
    ("Finding, action, issue in a record", "`<prefix>-F<n>`, `-A<n>`, `-I<n>` (prefixes "
     + ", ".join("`{}`".format(p) for p in ("RC", "RR", "SR", "SG", "AU")) + ")", "code"),
    ("Ethical value requirement", "`EVR-<n>`", "Requirements Reviewer"),
    ("Story in the backlog", "`RAI-<n>` (from requirements), `US-<n>` (product)", "backlog register"),
    ("Story in a record", "as given, or `S<n>`; `G<n>` in generate mode", "User Story Refiner"),
    ("Existing acceptance criterion", "`<story>-E<n>`", "backlog register"),
    ("Ethical acceptance criterion", "`AC-<story>-<n>`", "the agent, checked by code"),
    ("Sprint", "`SPR-<n>`", "sprints register"),
    ("Decision in the project register", "`ISSUE-<n>`", "register"),
    ("ECCOLA card", "`#0`–`#20`", "ECCOLA"),
    ("Legal obligation", "`eu.*`, `br.*` codes", "Risk Classifier"),
]


def _table(head: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    def cell(x: object) -> str:
        return str(x).replace("|", "/").replace("\n", " ")
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head),
                      *["| " + " | ".join(cell(c) for c in r) + " |" for r in rows]])


#: The order stages run in a project: the generate mode comes before refining.
STAGE_ORDER = ("risk_classifier", "requirements_reviewer", "story_generate", "story_refiner", "auditor")


def stages() -> List[tuple]:
    """(key, agent) for every runnable stage, in the order a project runs them."""
    from ..agents import RUNNABLE

    known = [k for k in STAGE_ORDER if k in RUNNABLE]
    return [(k, RUNNABLE[k]) for k in known + [k for k in RUNNABLE if k not in known]]


def _labels(options) -> Dict[str, str]:
    return {o.value: o.label for o in options}


# ---------------------------------------------------------------------------
# Generated blocks
# ---------------------------------------------------------------------------


def _stage_table() -> str:
    from ..contract.agent_cards import HANDOFF
    from ..contract.assemble import PREFIX
    from ..repository import ARTIFACT_FILES

    rows = []
    for key, agent in stages():
        spec = agent.spec
        name = spec.name + (f" ({spec.mode_label.lower()} mode)" if spec.parent else "")
        writes = ", ".join(w for w, ok in (("findings", V.writes_findings(key)),
                                           ("actions", V.writes_actions(key))) if ok) or "requirements only"
        rows.append([f"**{name}**", f"`{ARTIFACT_FILES.get(spec.output_key, spec.output_key)}`", f"`{PREFIX[key]}`",
                     "; ".join(config.SOURCE_NAMES.get(s, s) for s in spec.grounding_sources),
                     writes, HANDOFF.get(key, ("", "—"))[1]])
    return _table(["Stage", "File", "Id prefix", "Grounded in", "Writes", "Hands on"], rows)


def _status_table() -> str:
    rows = [[f"**{V.STATUS_LABELS[s]}** (`{s}`)", V.STATUS_HELP[s].replace("{n}", "N")]
            for s in V.OVERALL_STATUSES]
    return "Overall status (code can raise it, never lower it):\n\n" + _table(["Status", "Meaning"], rows)


def _issue_types_table() -> str:
    rows = [[f"`{t}`", V.ISSUE_TYPE_LABELS[t], " · ".join(V.DEFAULT_ISSUE_OPTIONS.get(t, ()))]
            for t in V.ISSUE_TYPES]
    return ("## Decisions (open issues)\n\nEach names a decision owner and whether it blocks. When an issue "
            "lists no options of its own, these are the defaults, and a written answer is always possible.\n\n"
            + _table(["Type", "What it means", "Default options"], rows))


def _sources_table() -> str:
    rows = [[config.SOURCE_NAMES[k], config.AUTHORITY_LEVELS.get(k, "")] for k in config.SOURCE_NAMES]
    return _table(["Source", "Authority"], rows)


def _principles_table() -> str:
    from ..rationale.principles import PRINCIPLES

    return _table(["Principle", "Probe: what the work must answer"],
                  [[f"**{p.name}** (`{p.key}`)", p.probe] for p in PRINCIPLES])


def _capabilities() -> Dict[str, str]:
    from ..rationale.story_map import CAPABILITY_OPTIONS

    return {k: v for k, v in _labels(CAPABILITY_OPTIONS).items() if k != "none"}


def _eccola_table() -> str:
    from ..rationale.story_map import CARDS

    caps = _capabilities()

    def when(card) -> str:
        if card.get("always"):
            return "every AI product"
        out = []
        for t in card.get("triggers") or []:
            if t.startswith("cap."):
                out.append(f"touches `{t[4:]}`" if t[4:] in caps else t)
            else:
                out.append(_CONTEXT_TRIGGERS.get(t, t.replace("_", " ")))
        return "; ".join(out)

    return _table(["Card", "Theme", "Selected when"],
                  [[f"`{c['id']}` {c['title']}", c["module"], when(c)] for c in CARDS])


def _capabilities_table() -> str:
    return _table(["Touches", "Meaning"], [[f"`{k}`", v] for k, v in _capabilities().items()])


def _ms_goals_table() -> str:
    return ("## Microsoft Responsible AI Standard v2 goals\n\nEvery ethical acceptance criterion names one.\n\n"
            + _table(["Goal", "Name"], [[f"`{k}`", v] for k, v in V.MS_GOALS.items()]))


def _escalation_triggers() -> str:
    from ..rationale import risk_screen as RS

    def bullets(items: List[str]) -> str:
        return "\n".join(f"- {x}" for x in items)

    areas = []
    for a in RS.PURPOSE_AREAS.values():
        refs = "; ".join(x for x in (f"EU AI Act Annex III, point {a['annex_iii']}" if a.get("annex_iii") else "",
                                      f"PL 2338/2023 art. 17, item {a['pl_art17']}" if a.get("pl_art17") else "") if x)
        areas.append(f"{a['label']} ({refs})")
    prohibited = [p["label"] + (" (restricted, not flatly banned)" if p.get("conditional") else "")
                  for p in RS.PROHIBITED_PRACTICES.values()]
    data = [v for k, v in _labels(RS.DATA_OPTIONS).items() if k != "none"]
    transparency = [v for k, v in _labels(RS.TRANSPARENCY_OPTIONS).items() if k != "none"]
    autonomy = " → ".join(reversed(list(_labels(RS.AUTONOMY_OPTIONS).values())))
    markets = ", ".join(v for k, v in _labels(RS.MARKET_OPTIONS).items())
    return "\n\n".join([
        "**A purpose in a high-risk area** that RAIA was not told about:\n\n" + bullets(areas),
        "**Any practice on the prohibited or excessive-risk lists** — stop the work and escalate to legal "
        "and compliance at once:\n\n" + bullets(prohibited),
        "**A new category of data:**\n\n" + bullets(data),
        "**A new way people meet the AI** (transparency duties):\n\n" + bullets(transparency),
        "**More automation or less oversight than RAIA was told.** Autonomy, from least to most: " + autonomy
        + ". Any move towards the right, or removing a person's ability to intervene in an individual case.",
        f"**A new market** ({markets}), a change of role (building the system vs. operating someone else's), "
        "a change of model source (in-house, adapted third-party, third-party as-is), or the product going "
        "from development to real users.",
    ])


def _jira_example() -> str:
    from .. import jira

    story = {"id": "RAI-4", "origin": "rai", "title": "Tell candidates a model was involved",
             "description": "As a candidate, I want to be told an AI system screens applications, so that I "
                            "can ask for a human review.",
             "criteria": [{"id": "AC-RAI-4-1", "kind": "ethical", "evr_ids": ["EVR-2"],
                           "text": "The outcome email states that an AI system is used and how to request a "
                                   "human review."}],
             "evr_ids": ["EVR-2"], "sprint": "SPR-3"}
    return "```csv\n" + jira.to_csv([story]).strip() + "\n```"


def blocks() -> Dict[str, str]:
    return {
        "schema_version": V.SCHEMA_VERSION,
        "stage_table": _stage_table(),
        "status_table": _status_table(),
        "issue_types_table": _issue_types_table(),
        "sources_table": _sources_table(),
        "principles_table": _principles_table(),
        "eccola_table": _eccola_table(),
        "capabilities_table": _capabilities_table(),
        "ms_goals_table": _ms_goals_table(),
        "escalation_triggers": _escalation_triggers(),
        "jira_example": _jira_example(),
    }


def fill(text: str, values: Dict[str, str]) -> str:
    """Replace every ``{{block}}``; a block with no value is an error, not a gap in the skill."""
    missing = sorted({m for m in _BLOCK.findall(text) if m not in values})
    if missing:
        raise KeyError("skill text has unfilled blocks: " + ", ".join(missing))
    return _BLOCK.sub(lambda m: values[m.group(1)], text)


# ---------------------------------------------------------------------------
# vocabulary.md, generated whole
# ---------------------------------------------------------------------------


def vocabulary() -> str:
    from .. import backlog as B
    from .. import roadmap as R
    from ..contract import rubric

    def anchors(scale, defs) -> str:
        return _table(["Value", "Definition"], [[f"`{k}`", defs[k]] for k in scale])

    parts = [
        "# Vocabulary",
        "",
        "> Generated from the RAIA code. These are the only values RAIA uses: use them exactly.",
        "",
        "## Priority",
        "",
        "Priorities, lowest to highest: " + ", ".join(f"`{p}`" for p in V.PRIORITIES) + ". Work is read in three groups:",
        "",
        _table(["Group", "Priorities", "Meaning"],
               [[label, ", ".join(prios), note] for _, label, prios, note in V.ACTION_GROUPS]),
        "",
        "## Impact magnitude (NIST AI RMF MAP 5; anchored to the harm criteria of the EU AI Act and PL 2338/2023)",
        "",
        anchors(V.MAGNITUDE, V.MAGNITUDE_ANCHORS),
        "",
        "## Likelihood (NIST AI RMF MAP 5)",
        "",
        anchors(V.LIKELIHOOD, V.LIKELIHOOD_ANCHORS),
        "",
        "## Risk level: magnitude × likelihood",
        "",
        rubric.matrix_md(),
        "",
        "## Priority floors",
        "",
        "The priority starts at the risk level, then each floor that applies raises it (never lowers it). "
        "An action takes the highest priority of the findings it answers. A record is at least *needs "
        "attention* when any decision is open or any finding is high, and *blocked* when anything is blocking.",
        "",
        _table(["When", "Priority", "Source"], FLOORS),
        "",
        "## Risk response (NIST AI RMF MANAGE 1)",
        "",
        anchors(V.RESPONSES, V.RESPONSE_ANCHORS),
        "",
        "## Lifecycle stage (NIST AI RMF)",
        "",
        _table(["Value", "Label"], [[f"`{k}`", V.LIFECYCLE_LABELS[k]] for k in V.LIFECYCLE_STAGES]),
        "",
        "## Owner role (NIST AI RMF GOVERN 2)",
        "",
        _table(["Value", "Label"], [[f"`{k}`", V.OWNER_LABELS[k]] for k in V.OWNER_ROLES]),
        "",
        "## Review cadence (Microsoft RAI Standard v2)",
        "",
        ", ".join(f"`{k}` ({V.CADENCE_LABELS[k]})" for k in V.REVIEW_CADENCES),
        "",
        "## Verification method (IEEE 7000)",
        "",
        ", ".join(f"`{k}`" for k in V.VERIFICATION_METHODS) + ". Stakeholders are "
        + " or ".join(f"`{k}`" for k in V.STAKEHOLDER_KINDS) + ".",
        "",
        "## Principles",
        "",
        ", ".join(f"`{k}` {V.PRINCIPLE_NAMES[k]}" for k in V.PRINCIPLE_KEYS),
        "",
        "## NIST AI RMF categories",
        "",
        _table(["Category", "Outcome"], [[f"`{k}`", v] for k, v in V.NIST_CATEGORIES.items()]),
        "",
        "## Microsoft RAI Standard v2 goals",
        "",
        ", ".join(f"`{k}` {v}" for k, v in V.MS_GOALS.items()),
        "",
        "## ECCOLA cards",
        "",
        ", ".join(f"`{k}` {v}" for k, v in V.ECCOLA_CARDS.items()),
        "",
        "## Open-issue (decision) types",
        "",
        _table(["Type", "Meaning"], [[f"`{k}`", V.ISSUE_TYPE_LABELS[k]] for k in V.ISSUE_TYPES]),
        "",
        "## Audit verdicts (strongest to weakest; may move down, never up)",
        "",
        ", ".join(f"`{k}` {V.AUDIT_VERDICT_LABELS[k]}" for k in V.AUDIT_VERDICTS),
        "",
        "## Audit opinion",
        "",
        f"Rated by rule, checked from the weakest up; never better than the evidence allows. "
        f"\"Satisfied share\" is {int(V.AUDIT_SATISFIED_SHARE * 100)}%. In a project run in sprints, the best "
        "possible rating is *Needs improvement* while a high or critical risk has no story, or a legal-obligation "
        "requirement has had no story in any sprint by the second sprint.",
        "",
        _table(["Rating", "When"], [[V.AUDIT_OPINION_LABELS[k], V.AUDIT_OPINION_RULES[k]] for k in V.AUDIT_OPINIONS]),
        "",
        "## Backlog",
        "",
        "Story status: " + ", ".join(f"`{k}` {v}" for k, v in B.STATUS_LABELS.items())
        + ". A tick means delivered (`done`); only an approved RAIA audit sets `verified`.",
        "",
        "Story origin: " + ", ".join(f"`{k}` {v}" for k, v in B.ORIGIN_LABELS.items()) + ".",
        "",
        "Sprint state: " + ", ".join(f"`{k}` {v}" for k, v in B.SPRINT_STATE_LABELS.items()) + ".",
        "",
        "Requirement state on the roadmap: " + ", ".join(f"`{k}` {v}" for k, v in R.REQ_STATE_LABELS.items()) + ".",
        "",
        "## Identifiers",
        "",
        _table(["Kind", "Form", "Assigned by"], IDENTIFIERS),
        "",
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# The files
# ---------------------------------------------------------------------------


def static_files(project: Optional[str] = None, created: Optional[str] = None) -> Dict[str, str]:
    """Every file of the skill except the project folder, by path inside the package."""
    values = dict(blocks(), project=project or "your project", created=created or "(the date of your download)")
    out: Dict[str, str] = {}
    for src in sorted(TEXT.rglob("*.md")):
        rel = src.relative_to(TEXT).as_posix()
        dest = rel if rel in ("AGENTS.md", "README_FIRST.md") else f"{SKILL_DIR}/{rel}"
        out[dest] = fill(src.read_text(encoding="utf-8"), values)
    out[f"{SKILL_DIR}/references/vocabulary.md"] = vocabulary()
    return out


def generated() -> Dict[str, str]:
    """The static copy kept in docs/ai-skill/, by path relative to it."""
    files = static_files()
    files[f"{SKILL_DIR}/project/README.md"] = (
        "# Project folder\n\nIn a download from RAIA (**Download AI Skill** on a project's Documents tab) this "
        "folder holds `PROJECT_CONTEXT.md` and the project's approved outputs. This copy in the repository "
        "shows the skill without a project.\n")
    return files


def main() -> None:
    for name, text in generated().items():
        path = OUT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"wrote docs/ai-skill/{name}")


if __name__ == "__main__":
    main()
