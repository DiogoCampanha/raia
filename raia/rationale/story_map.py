"""
raia.rationale.story_map
========================

Deterministic ECCOLA card selection for the User Story Refiner.

ECCOLA's own method is that a team picks the cards relevant to the product and
the sprint — relevance changes sprint to sprint. That selection was being left
to the model with no record of why a card applied. Here it is computed from
context the system already holds: the approved risk tier, the declared data
categories, the purpose areas, and the capabilities the sprint's stories touch.
Each selected card carries the trigger that selected it, so "why this card?"
is answerable from the artifact.

The engine also fixes the story register. Every story that goes in must come
back out — refined, or explicitly marked as having no ethical impact with a
reason. Absence of action has to be auditable too, and that is now a counted
invariant rather than a line in a prompt.
"""

import re
from typing import Any, Dict, List, Sequence, Set

from ..fields import options, selected, text_of
from .types import ChecklistItem, Finding, Pin, RationaleResult, md_table

# ---------------------------------------------------------------------------
# Option vocabulary (form ↔ engine contract)
# ---------------------------------------------------------------------------

CAPABILITY_OPTIONS = options(
    ("scoring", "Scores, ranks or filters people"),
    ("automation", "Automates or strongly steers a decision about a person"),
    ("data_collection", "Collects or enriches personal data"),
    ("personalization", "Personalizes what a person sees"),
    ("generation", "Generates content shown to people"),
    ("explanation", "Explains an outcome to a user or an affected person"),
    ("analytics", "Reports aggregate metrics internally"),
    ("integration", "Integrates an external data source or model"),
    ("access_control", "Controls who can see or reach data"),
    ("none", "None of these"),
)

MODULE_SECTIONS = {
    "Analyze": "Analyze (context setting)",
    "Transparency": "Transparency",
    "Data": "Data (privacy and governance)",
    "Agency": "Agency and Oversight",
    "Safety": "Safety and Security",
    "Fairness": "Fairness",
    "Wellbeing": "Wellbeing and Society",
}

#: The 21 ECCOLA cards with the conditions that make each one relevant here.
#: ``always`` cards apply to any AI product; the rest are selected by trigger
#: tokens drawn from the upstream classification and the sprint's capabilities.
CARDS: List[Dict[str, Any]] = [
    {"id": "#0", "title": "Stakeholder Analysis", "module": "Analyze", "always": True, "triggers": []},
    {"id": "#1", "title": "Types of Transparency", "module": "Analyze", "always": True, "triggers": []},
    {"id": "#2", "title": "Regulation", "module": "Analyze", "always": False,
     "triggers": ["high_risk", "limited_risk"]},
    {"id": "#3", "title": "Traceability", "module": "Transparency", "always": False,
     "triggers": ["high_risk", "cap.automation", "cap.scoring"]},
    {"id": "#4", "title": "Communication", "module": "Transparency", "always": False,
     "triggers": ["cap.generation", "cap.personalization", "limited_risk"]},
    {"id": "#5", "title": "Explainability", "module": "Transparency", "always": False,
     "triggers": ["high_risk", "significant_effects", "cap.scoring", "cap.explanation"]},
    {"id": "#6", "title": "Privacy and Data", "module": "Data", "always": False,
     "triggers": ["personal_data", "cap.data_collection"]},
    {"id": "#7", "title": "Data Quality", "module": "Data", "always": False,
     "triggers": ["high_risk", "cap.scoring", "cap.integration"]},
    {"id": "#8", "title": "Access to Data", "module": "Data", "always": False,
     "triggers": ["personal_data", "cap.access_control", "cap.data_collection"]},
    {"id": "#9", "title": "Human Agency", "module": "Agency", "always": False,
     "triggers": ["cap.personalization", "cap.generation", "significant_effects"]},
    {"id": "#10", "title": "Human Oversight", "module": "Agency", "always": False,
     "triggers": ["high_risk", "cap.automation", "significant_effects"]},
    {"id": "#11", "title": "System Reliability", "module": "Safety", "always": False,
     "triggers": ["high_risk", "production"]},
    {"id": "#12", "title": "System Security", "module": "Safety", "always": False,
     "triggers": ["personal_data", "cap.integration", "production"]},
    {"id": "#13", "title": "System Safety", "module": "Safety", "always": False,
     "triggers": ["high_risk", "safety_component"]},
    {"id": "#14", "title": "Accessibility", "module": "Fairness", "always": False,
     "triggers": ["cap.explanation", "cap.personalization", "disability_data"]},
    {"id": "#15", "title": "Stakeholder Participation", "module": "Fairness", "always": False,
     "triggers": ["high_risk"]},
    {"id": "#16", "title": "Non-Discrimination / Fairness", "module": "Fairness", "always": False,
     "triggers": ["protected_data", "cap.scoring", "cap.automation", "high_risk"]},
    {"id": "#17", "title": "Societal and Environmental Impact", "module": "Wellbeing", "always": False,
     "triggers": ["cap.generation", "cap.personalization", "high_risk"]},
    {"id": "#18", "title": "Auditability", "module": "Wellbeing", "always": False,
     "triggers": ["high_risk", "cap.automation"]},
    {"id": "#19", "title": "Ability to Redress", "module": "Wellbeing", "always": False,
     "triggers": ["significant_effects", "high_risk"]},
    {"id": "#20", "title": "Accountability", "module": "Wellbeing", "always": True, "triggers": []},
]

SECTION_MS_STYLE = "Practical Requirement Style (What RAIA Borrows)"
SECTION_ECCOLA_SPRINTS = "How ECCOLA Is Used in Sprints"

_STORY_ID = re.compile(r"^\s*(?:[-*]\s*)?(S\d+|US-?\d+|STORY-?\d+|(?!AC-?\d)[A-Z][A-Z0-9]{1,9}-\d+)[.):\-]?\s+(.*)$", re.I)
_AS_A = re.compile(r"^\s*(?:[-*]\s*)?(?:\d+[.)]\s*)?(as an?\b.*)$", re.I)
_AC_HEADER = re.compile(r"^\s*(?:acceptance\s+criteria|a\.?c\.?)(?![\w-])\s*[:\-]?\s*(.*)$", re.I)
_AC_LINE = re.compile(r"^\s*(?:[-*\u2022]|\d+[.)]|AC-?\d+\s*[:.)\-]|given\b)", re.I)
_BULLET = re.compile(r"^\s*(?:[-*\u2022]\s*|\d+[.)]\s*|AC-?\d+\s*[:.)\-]\s*)", re.I)
_TITLE = re.compile(r"^\s*title\s*:\s*(.*)$", re.I)
_VALID_ID = re.compile(r"^[A-Z][A-Z0-9]{0,9}-?\d+$")


def _legacy_id(raw: str) -> str:
    """``US-12`` and ``STORY-12`` are read as ``S12``; any other id is kept, upper-cased."""
    m = re.match(r"^(?:US|STORY)-?(\d+)$", raw, re.I)
    return f"S{m.group(1)}" if m else raw.upper()


def parse_backlog(text: str) -> List[Dict[str, Any]]:
    """Split pasted backlog text into stories, each with its own acceptance criteria.

    A story starts at an explicit id (``S1``, ``US-12``, ``PROJ-42``), at an
    ``As a …`` line once the current story already has one, or after a blank
    line. Lines under an "Acceptance criteria" heading, and bullet or
    ``Given …`` lines after the description, are the story's criteria — not
    stories of their own.
    """
    stories: List[Dict[str, Any]] = []
    cur: Dict[str, Any] = {}
    in_ac = False

    def close() -> None:
        nonlocal cur, in_ac
        if cur and (cur.get("description") or cur.get("title") or cur.get("criteria")):
            stories.append({"id": cur.get("id", ""), "title": cur.get("title", ""),
                            "description": " ".join(cur.get("description") or []).strip(),
                            "acceptance_criteria": "\n".join(cur.get("criteria") or []),
                            "capabilities": []})
        cur, in_ac = {}, False

    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            if cur.get("description") and not in_ac:
                close()
            continue
        m_id = _STORY_ID.match(line)
        if m_id:
            close()
            cur = {"id": _legacy_id(m_id.group(1)), "description": [], "criteria": []}
            rest = m_id.group(2).strip()
            if rest and not _AS_A.match(rest) and len(rest) <= 90 and not rest.endswith("."):
                cur["title"] = rest
            elif rest:
                cur["description"].append(rest)
            continue
        m_title = _TITLE.match(line)
        if m_title:
            close()
            cur = {"title": m_title.group(1).strip(), "description": [], "criteria": []}
            continue
        m_ac = _AC_HEADER.match(line)
        if m_ac and (cur.get("description") or cur.get("title")):
            in_ac = True
            cur.setdefault("criteria", [])
            if m_ac.group(1).strip():
                cur["criteria"].append(_BULLET.sub("", m_ac.group(1)).strip())
            continue
        if _AS_A.match(line):
            if cur.get("description") or in_ac:
                close()
            cur = cur or {"description": [], "criteria": []}
            cur.setdefault("description", []).append(_AS_A.match(line).group(1).strip())
            continue
        if not cur:
            cur = {"description": [line], "criteria": []}
            continue
        if in_ac or (cur.get("description") and _AC_LINE.match(line)):
            in_ac = True
            cur.setdefault("criteria", []).append(_BULLET.sub("", line).strip())
            continue
        cur.setdefault("description", []).append(line)
    close()
    return stories


def parse_stories(text: str) -> List[Dict[str, str]]:
    """Legacy reader: a backlog blob → ``[{"id", "text"}]`` (see :func:`normalize_stories`)."""
    return [{"id": s["id"], "text": s["text"]} for s in normalize_stories(text)]


def _criteria_lines(value: Any) -> List[str]:
    if isinstance(value, (list, tuple)):
        lines = [str(v) for v in value]
    else:
        lines = str(value or "").splitlines()
    out = []
    for line in lines:
        t = _BULLET.sub("", line).strip()
        if t:
            out.append(t)
    return out


def normalize_stories(value: Any, fallback_caps: Sequence[str] = ()) -> List[Dict[str, Any]]:
    """Stories as the engine reads them, whatever shape the form stored.

    Accepts the structured list the form writes (one entry per story: id,
    title, description, acceptance criteria, what it touches) or, for answers
    saved before stories were entered one by one, a pasted blob. Every story
    gets a stable id — the one the team uses when it is well-formed and
    unique, ``S<n>`` otherwise — and every existing acceptance criterion gets
    ``<story id>-E<n>`` so a conflict can point at it.
    """
    raw = parse_backlog(value) if isinstance(value, str) else [s for s in value or [] if isinstance(s, dict)]
    out: List[Dict[str, Any]] = []
    used: Set[str] = set()
    pending: List[Dict[str, Any]] = []
    for s in raw:
        title = str(s.get("title") or "").strip()
        description = str(s.get("description") or s.get("text") or "").strip()
        criteria = _criteria_lines(s.get("acceptance_criteria") or s.get("criteria_text") or "")
        if not (title or description or criteria):
            continue
        sid = re.sub(r"\s+", "", str(s.get("id") or "")).upper()
        sid = _legacy_id(sid) if sid else ""
        if not _VALID_ID.match(sid) or sid in used:
            sid = ""
        caps = [c for c in (s.get("capabilities") or []) if c]
        if not caps:
            caps = list(fallback_caps)
        entry = {"id": sid, "title": title, "description": description,
                 "text": (f"{title}. " if title and description else title) + description,
                 "criteria_raw": criteria, "capabilities": [c for c in caps if c != "none"],
                 "declared_capabilities": bool(s.get("capabilities"))}
        if sid:
            used.add(sid)
        pending.append(entry)
    n = 0
    for entry in pending:
        if not entry["id"]:
            n += 1
            while f"S{n}" in used:
                n += 1
            entry["id"] = f"S{n}"
            used.add(entry["id"])
        entry["criteria"] = [{"id": f"{entry['id']}-E{i}", "text": t}
                             for i, t in enumerate(entry.pop("criteria_raw"), 1)]
        out.append(entry)
    return out


def render_stories(value: Any) -> str:
    """The stories as the model reads them: one block per story, with its criteria."""
    stories = normalize_stories(value)
    if not stories:
        return "(not provided)"
    labels = {o.value: o.label for o in CAPABILITY_OPTIONS}
    blocks = []
    for s in stories:
        lines = [f"{s['id']}" + (f" — {s['title']}" if s["title"] else "")]
        if s["description"]:
            lines.append(s["description"])
        if s["criteria"]:
            lines.append("Existing acceptance criteria:")
            lines += [f"- {c['id']}: {c['text']}" for c in s["criteria"]]
        else:
            lines.append("Existing acceptance criteria: none")
        lines.append("Touches: " + (", ".join(labels.get(c, c) for c in s["capabilities"]) or "none of the listed capabilities"))
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def stories_missing(value: Any) -> List[str]:
    """Per-story answers that decide the outcome and are still empty."""
    out = []
    raw = value if isinstance(value, list) else []
    for i, s in enumerate(normalize_stories(raw), 1):
        if not s["description"] and not s["title"]:
            out.append(f"{s['id']}: the story")
        if not s["declared_capabilities"]:
            out.append(f"{s['id']}: what it touches")
    return out


def _context_tokens(risk: Dict[str, Any], caps: List[str]) -> Set[str]:
    tokens: Set[str] = {f"cap.{c}" for c in caps if c != "none"}
    if risk.get("eu_is_high_risk") or risk.get("br_is_high_risk"):
        tokens.add("high_risk")
    if str(risk.get("eu_tier", "")).startswith("limited"):
        tokens.add("limited_risk")
    if risk.get("significant_effects") == "yes":
        tokens.add("significant_effects")
    if risk.get("deployment_stage") in ("pilot", "production"):
        tokens.add("production")
    if risk.get("annex_i_product"):
        tokens.add("safety_component")
    data = set(risk.get("data_categories") or [])
    if data - {"none"}:
        tokens.add("personal_data")
    if {"protected_attributes", "proxies", "biometric"} & data:
        tokens.add("protected_data")
    if "health" in data:
        tokens.add("disability_data")
    return tokens


def run(inputs: Dict[str, Any], upstream: Dict[str, Any]) -> RationaleResult:
    r = RationaleResult(engine="story_card_map")

    # Stories are entered one by one, each with what it touches. Answers saved
    # before that carried one capability list for the whole sprint: it still
    # applies to every story that declares none of its own.
    sprint_caps = [c for c in selected(inputs, "touched_capabilities") if c != "none"]
    stories = normalize_stories(inputs.get("user_stories"), sprint_caps)
    caps = list(dict.fromkeys(c for s in stories for c in s["capabilities"]))
    sprint_goal = text_of(inputs, "sprint_goal")
    dod = text_of(inputs, "definition_of_done")

    risk = (upstream.get("risk_classification") or {}).get("data") or {}
    review = (upstream.get("requirements_review") or {}).get("data") or {}
    evr_ids: List[str] = review.get("evr_ids") or []

    tokens = _context_tokens(risk, caps)

    def cards_for(story_caps: Sequence[str]) -> List[Dict[str, Any]]:
        story_tokens = _context_tokens(risk, story_caps)
        chosen_cards = []
        for card in CARDS:
            why: List[str] = []
            if card["always"]:
                why.append("applies to any AI product")
            why.extend(t for t in card["triggers"] if t in story_tokens)
            if why:
                chosen_cards.append({**card, "why": why})
        return chosen_cards

    # Each story gets the cards its own capabilities select; the sprint's set is
    # their union, and a capability reason names the stories it came from.
    per_story: Dict[str, List[str]] = {}
    reasons: Dict[str, Dict[str, List[str]]] = {}
    for st in stories:
        chosen_cards = cards_for(st["capabilities"])
        st["cards"] = [c["id"] for c in chosen_cards]
        per_story[st["id"]] = st["cards"]
        for c in chosen_cards:
            bucket = reasons.setdefault(c["id"], {})
            for why in c["why"]:
                bucket.setdefault(why, [])
                if why.startswith("cap.") and st["id"] not in bucket[why]:
                    bucket[why].append(st["id"])
    selected_cards: List[Dict[str, Any]] = [
        {**card, "why": [f"{w} ({', '.join(ids)})" if ids else w for w, ids in reasons[card["id"]].items()]}
        for card in CARDS if card["id"] in reasons
    ]
    if not stories:
        selected_cards = cards_for(caps)

    existing_total = sum(len(st["criteria"]) for st in stories)
    r.findings.append(
        Finding("stories.parsed", f"{len(stories)} story/stories in the register",
                ", ".join(st["id"] for st in stories))
    )
    r.findings.append(
        Finding("cards.selected", f"{len(selected_cards)} of 21 ECCOLA cards are in scope",
                ", ".join(c["id"] for c in selected_cards))
    )
    r.findings.append(
        Finding("criteria.existing", f"{existing_total} existing acceptance criteria across the stories",
                ", ".join(c["id"] for st in stories for c in st["criteria"]) or "none")
    )

    r.tables["ECCOLA cards selected for this sprint (use these ids; do not invent others)"] = md_table(
        ["Card", "Title", "Module", "Selected because"],
        [[c["id"], c["title"], c["module"], ", ".join(c["why"])] for c in selected_cards],
    )
    r.tables["Story register (every id must appear in your output exactly once)"] = md_table(
        ["Story", "Title", "Existing criteria", "Cards in scope for this story"],
        [[st["id"], st["title"] or st["description"][:80], ", ".join(c["id"] for c in st["criteria"]) or "none",
          ", ".join(st["cards"])] for st in stories]
    )

    if evr_ids:
        r.tables["Approved ethical value requirements available for traceability"] = md_table(
            ["EVR id", "Source"], [[e, "approved requirements review"] for e in evr_ids]
        )
    else:
        r.notes.append(
            "The approved requirements review carries no machine-readable requirement register, "
            "so acceptance criteria cannot be traced to an identifier. Trace them to the norm instead."
        )

    if not caps:
        r.notes.append(
            "No story declares a capability, so only the always-relevant cards were selected. If "
            "the stories do touch scoring, automation or personal data, go back and declare it — "
            "card selection is driven by that answer."
        )
    if existing_total:
        r.notes.append(
            "Existing acceptance criteria are the team's. Do not repeat them; flag one only when it "
            "conflicts with an approved requirement or a card in scope, and suggest a rewrite."
        )
    if dod:
        r.notes.append("A definition of done was provided; acceptance criteria must be expressed in its terms.")

    # -- Open issues ---------------------------------------------------------

    if "high_risk" in tokens and not evr_ids:
        r.raise_issue(
            "High-risk system with no approved requirement register to trace criteria to. "
            "Criteria added here will not be auditable upstream until that is fixed.",
            type="missing_information", decision_owner="product", blocking=False,
        )
    if "cap.automation" in tokens and risk.get("human_oversight") in ("none_designed", "monitoring_only"):
        r.raise_issue(
            "This sprint automates a decision while no case-level human intervention is designed. "
            "Either a story adds one, or the gap is recorded and accepted by a human.",
            type="risk_acceptance", decision_owner="product", blocking=False,
        )

    r.pins = [Pin("eccola", SECTION_ECCOLA_SPRINTS, "how cards are applied in a sprint")]
    for module in sorted({c["module"] for c in selected_cards}):
        section = MODULE_SECTIONS.get(module)
        if section:
            r.pins.append(Pin("eccola", section, f"{module} cards in scope"))
    r.pins.append(Pin("ms_rai_v2", SECTION_MS_STYLE, "how to make a criterion verifiable"))

    r.checklist = [
        ChecklistItem("stories", "Account for every story id in the register, refined or not"),
        ChecklistItem("criteria", "Give each refined story verifiable acceptance criteria"),
        ChecklistItem("cards", "Cite the selected card id(s) that justify each criterion"),
        ChecklistItem("traceability", "Trace each criterion to an approved requirement id where one exists"),
        ChecklistItem("no_impact", "Justify, one line each, every story you leave unrefined"),
        ChecklistItem("conflicts", "Flag every existing acceptance criterion that conflicts with an approved requirement or a card in scope"),
        ChecklistItem("open_issues", "Carry forward every open issue raised here, plus any you add"),
    ]

    r.verdict = {
        "story_count": len(stories),
        "story_ids": [st["id"] for st in stories],
        "card_ids": [c["id"] for c in selected_cards],
        "story_cards": per_story,
        "existing_criteria": {st["id"]: [c["id"] for c in st["criteria"]] for st in stories if st["criteria"]},
        "evr_ids": evr_ids,
    }
    r.query_terms = (
        [c["title"] for c in selected_cards]
        + caps
        + ([sprint_goal] if sprint_goal else [])
        + ["verifiable acceptance criteria"]
    )
    r.data.update(
        {
            "stories": [{k: v for k, v in st.items() if k != "declared_capabilities"} for st in stories],
            "cards": [{"id": c["id"], "title": c["title"], "why": c["why"]} for c in selected_cards],
            "capabilities": caps,
            "evr_ids": evr_ids,
            "sprint_goal": sprint_goal,
        }
    )
    return r
