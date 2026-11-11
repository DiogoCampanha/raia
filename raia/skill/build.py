"""
Write the RAIA AI Skill's instructions and references, from the code.

    python -m raia.skill.build

The skill has two parts. The **fixed part** (``SKILL.md`` and its references)
is the same for every project and every download of a version: it is written
here, from the prose in ``raia/skill/text/`` with each ``{{block}}`` filled
from the vocabularies, rules and registers the software itself uses
(``references/vocabulary.md`` is generated whole). The **project part** is one
project's outputs and is written at download time (:mod:`raia.export`,
:mod:`raia.skill.context`).

This module writes the static copy in ``docs/ai-skill/``: the fixed part, the
install notes of each format and the single-file format, without a project.
``tests/test_skill.py`` fails when that copy is out of date, and when the fixed
part changes without a new :data:`SKILL_VERSION`.
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
        "skill_version": SKILL_VERSION,
        **_screening_blocks(),
    }


def _screening_blocks() -> Dict[str, str]:
    """The Risk Classifier's screen as tables, for an assistant working without a RAIA record.

    Everything here is read from the rule engine: the questions and their
    options from the agent's form, the lists from the engine's vocabularies,
    and the obligations by running the engine on answers that trigger each of
    them, so a row cannot say something the engine does not do.
    """
    from ..agents import AGENTS
    from ..rationale import risk_screen as RS

    asked = [f for f in AGENTS["risk_classifier"].spec.input_fields if f.kind in ("select", "multiselect", "boolean")]
    questions = _table(["Question", "Answers (one, or any that apply)"],
                       [[f.label, " · ".join(o.label for o in f.options)] for f in asked])

    def where(meta) -> str:
        return " and ".join(n for n, on in (("EU AI Act", meta["eu"]), ("PL 2338/2023", meta["br"])) if on)

    prohibited = _table(["Practice", "Under", "Status"],
                        [[m["label"], where(m), "restricted: narrow legal exceptions only" if m["conditional"]
                          else "prohibited"] for m in RS.PROHIBITED_PRACTICES.values()])
    areas = _table(["Area", "EU AI Act, Annex III", "PL 2338/2023, art. 17"],
                   [[m["label"], m["annex_iii"] or "not listed", m["pl_art17"] or "not listed"]
                    for m in RS.PURPOSE_AREAS.values()])
    transparency = "\n".join(f"- {o.label}" for o in RS.TRANSPARENCY_OPTIONS if o.value != "none")
    everything = RS.run({
        "role": "both", "markets": ["eu", "br"], "purpose_areas": ["essential_services"], "public_sector": "yes",
        "gpai_provider": "yes", "transparency_triggers": ["chat_interaction"], "prohibited_practices": ["none"],
        "art63_claim": "yes", "profiling": "no", "ai_techniques": ["machine_learning"], "ai_pipeline": ["scoring"],
        "model_source": "in_house", "decision_autonomy": "human_override", "human_oversight": "human_decides",
        "significant_effects": "no", "data_categories": ["none"], "deployment_stage": "development",
    })
    obligations = _table(["Code", "Where", "Obligation", "Applies when"],
                         [[f"`{o['code']}`", "EU AI Act" if o["jurisdiction"] == "EU" else "PL 2338/2023",
                           o["title"], o["why"]] for o in everything.data["obligations"]])
    return {
        "screening_questions": questions, "prohibited_table": prohibited, "areas_table": areas,
        "transparency_table": transparency, "obligations_table": obligations,
        "tier_unacceptable": RS.TIER_UNACCEPTABLE, "tier_restricted": RS.TIER_RESTRICTED, "tier_high": RS.TIER_HIGH,
        "tier_limited": RS.TIER_LIMITED, "tier_minimal": RS.TIER_MINIMAL,
        "br_excessive": RS.BR_EXCESSIVE, "br_high": RS.BR_HIGH, "br_not_listed": RS.BR_NOT_LISTED,
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


#: The version of the fixed part. The fixed part is frozen: it is byte-identical
#: for every project and every download of a version, and nobody edits it after
#: download. Changing anything in it (the prose in ``text/``, or a vocabulary or
#: rule the tables are generated from) means a new version here and a new
#: :data:`FIXED_FINGERPRINT`; ``tests/test_skill.py`` fails until both are set.
SKILL_VERSION = "2.0.0"
FIXED_FINGERPRINT = "00399ba6d511f513"

#: The folder (or part of a single file) that holds one project's outputs.
PROJECT_DIR = "raia-project"

#: The formats the skill is offered in: key -> (label, file extension, what it is).
FORMATS = {
    "cursor": ("Cursor", "zip", "a skill folder under .cursor/skills/ and the project folder beside it"),
    "chatgpt": ("ChatGPT", "zip", "a skill to upload, and the project files to attach"),
    "claude": ("Claude", "zip", "a skill to upload, and the project files to attach"),
    "generic": ("One Markdown file (any assistant)", "md", "instructions and project context in one file"),
}

_FRONTMATTER = re.compile(r"^---\n.*?\n---\n", re.S)
#: Where the project part starts in the single-file format. Everything before it
#: is the fixed part; everything from it on is replaced when the project changes.
GENERIC_PROJECT_MARKER = "<!-- raia-skill: project part. Replace everything from this line down when the project changes. -->"

_REFERENCE_ORDER = ("reading-the-outputs.md", "vocabulary.md", "rai-guidelines.md", "screening.md",
                    "playbooks.md", "templates.md")


def fixed_files() -> Dict[str, str]:
    """The fixed part: ``SKILL.md`` and its references, by path inside the skill folder.

    No argument, on purpose: nothing about a project, a person or a date can
    reach these files.
    """
    values = blocks()
    out: Dict[str, str] = {"SKILL.md": fill((TEXT / "SKILL.md").read_text(encoding="utf-8"), values)}
    for src in sorted((TEXT / "references").glob("*.md")):
        out[f"references/{src.name}"] = fill(src.read_text(encoding="utf-8"), values)
    out["references/vocabulary.md"] = vocabulary()
    return out


def fingerprint(files: Optional[Dict[str, str]] = None) -> str:
    """A digest of the fixed part: it changes if and only if a byte of it does."""
    import hashlib

    files = fixed_files() if files is None else files
    h = hashlib.sha256()
    for name in sorted(files):
        h.update(name.encode("utf-8") + b"\0" + files[name].encode("utf-8") + b"\0")
    return h.hexdigest()[:16]


def fixed_zip() -> bytes:
    """The fixed part as a zip to upload as a skill: the same bytes every time."""
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in sorted(fixed_files().items()):
            info = zipfile.ZipInfo(f"{SKILL_DIR}/{name}", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, text)
    return buffer.getvalue()


def agents_md() -> str:
    return fill((TEXT / "AGENTS.md").read_text(encoding="utf-8"), blocks())


def install_readme(fmt: str) -> str:
    """``README_FIRST.md`` for one format: how to install it. The same for every project."""
    values = dict(blocks())
    values["use_section"] = fill((TEXT / "install" / "use.md").read_text(encoding="utf-8"), values).rstrip()
    return fill((TEXT / "install" / f"{fmt}.md").read_text(encoding="utf-8"), values)


def project_readme(project: str, created: str) -> str:
    """The note that opens the project part: whose it is, and when it was taken."""
    values = dict(blocks(), project=project or "your project", created=created or "(the date of your download)")
    return fill((TEXT / "install" / "project_readme.md").read_text(encoding="utf-8"), values)


def generic_fixed() -> str:
    """The fixed part as one Markdown document (the single-file format, before the project part)."""
    files = fixed_files()
    parts = [install_readme("generic").rstrip(), "", "---", "",
             f"<!-- raia-skill: fixed part, version {SKILL_VERSION}. Do not edit. -->", "",
             _FRONTMATTER.sub("", files["SKILL.md"]).strip(), ""]
    for name in _REFERENCE_ORDER:
        parts += ["---", "", f"<!-- references/{name} -->", "", files[f"references/{name}"].strip(), ""]
    return "\n".join(parts) + "\n---\n\n"


def generic_markdown(project_part: Optional[str] = None) -> str:
    """The single-file format: the fixed part, then one project's context (or a note that there is none)."""
    body = (project_part or "").strip() or (
        "No project part was included. Screen the product yourself (`references/screening.md`) and say that "
        "the result is self-assessed.")
    return generic_fixed() + GENERIC_PROJECT_MARKER + "\n\n# Project part\n\n" + body + "\n"


def generated() -> Dict[str, str]:
    """The static copy kept in docs/ai-skill/, by path relative to it: the skill without a project."""
    files = {f"{SKILL_DIR}/{name}": text for name, text in fixed_files().items()}
    files["AGENTS.md"] = agents_md()
    for fmt in FORMATS:
        if fmt != "generic":
            files[f"install/README_FIRST.{fmt}.md"] = install_readme(fmt)
    files["raia-skill.md"] = generic_markdown()
    files[f"{PROJECT_DIR}/README.md"] = (
        "# Project part\n\nIn a download from RAIA (**Download AI Skill** on a project's Documents tab) this "
        "folder holds `PROJECT_CONTEXT.md` and the project's approved outputs. This copy in the repository "
        "shows the skill without a project.\n")
    return files


def main() -> None:
    wanted = generated()
    for name, text in wanted.items():
        path = OUT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"wrote docs/ai-skill/{name}")
    for path in sorted(OUT.rglob("*")):
        if path.is_file() and path.relative_to(OUT).as_posix() not in wanted:
            path.unlink()
            print(f"removed docs/ai-skill/{path.relative_to(OUT).as_posix()}")
    print(f"fixed part: version {SKILL_VERSION}, fingerprint {fingerprint()}")


if __name__ == "__main__":
    main()
