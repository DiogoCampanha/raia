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
from typing import Any, Dict, List, Set

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

_STORY_ID = re.compile(r"^\s*(?:[-*]\s*)?(S\d+|US-?\d+|STORY-?\d+)[.):\-]?\s+(.*)$", re.I)
_AS_A = re.compile(r"^\s*(?:[-*]\s*)?(?:\d+[.)]\s*)?(as an?\b.*)$", re.I)


def parse_stories(text: str) -> List[Dict[str, str]]:
    """Split a backlog blob into identified stories.

    Accepts explicit ids (``S1``, ``US-12``), plain ``As a …`` lines, or one
    story per paragraph, and always returns a stable id for every story so the
    register can be checked for completeness.
    """
    stories: List[Dict[str, str]] = []
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text or "") if b.strip()]
    lines: List[str] = []
    for b in blocks:
        lines.extend([l for l in b.splitlines() if l.strip()] or [b])

    for line in lines:
        m = _STORY_ID.match(line)
        if m:
            stories.append({"id": m.group(1).upper().replace("US-", "S").replace("STORY-", "S"),
                            "text": m.group(2).strip()})
            continue
        m2 = _AS_A.match(line)
        if m2:
            stories.append({"id": f"S{len(stories) + 1}", "text": m2.group(1).strip()})
            continue
        stories.append({"id": f"S{len(stories) + 1}", "text": line.strip()})
    return stories


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

    stories = parse_stories(text_of(inputs, "user_stories"))
    caps = [c for c in selected(inputs, "touched_capabilities") if c != "none"]
    sprint_goal = text_of(inputs, "sprint_goal")
    dod = text_of(inputs, "definition_of_done")

    risk = (upstream.get("risk_classification") or {}).get("data") or {}
    review = (upstream.get("requirements_review") or {}).get("data") or {}
    evr_ids: List[str] = review.get("evr_ids") or []

    tokens = _context_tokens(risk, caps)

    selected_cards: List[Dict[str, Any]] = []
    for card in CARDS:
        why: List[str] = []
        if card["always"]:
            why.append("applies to any AI product")
        why.extend(t for t in card["triggers"] if t in tokens)
        if why:
            selected_cards.append({**card, "why": why})

    r.findings.append(
        Finding("stories.parsed", f"{len(stories)} story/stories in the register",
                ", ".join(s["id"] for s in stories))
    )
    r.findings.append(
        Finding("cards.selected", f"{len(selected_cards)} of 21 ECCOLA cards are in scope",
                ", ".join(c["id"] for c in selected_cards))
    )

    r.tables["ECCOLA cards selected for this sprint (use these ids; do not invent others)"] = md_table(
        ["Card", "Title", "Module", "Selected because"],
        [[c["id"], c["title"], c["module"], ", ".join(c["why"])] for c in selected_cards],
    )
    r.tables["Story register (every id must appear in your output exactly once)"] = md_table(
        ["Story", "Text"], [[s["id"], s["text"][:100]] for s in stories]
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
            "No capability was declared for this sprint, so only the always-relevant cards were "
            "selected. If the stories do touch scoring, automation or personal data, go back and "
            "declare it — card selection is driven by that answer."
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
        ChecklistItem("open_issues", "Carry forward every open issue raised here, plus any you add"),
    ]

    r.verdict = {
        "story_count": len(stories),
        "story_ids": [s["id"] for s in stories],
        "card_ids": [c["id"] for c in selected_cards],
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
            "stories": stories,
            "cards": [{"id": c["id"], "title": c["title"], "why": c["why"]} for c in selected_cards],
            "capabilities": caps,
            "evr_ids": evr_ids,
            "sprint_goal": sprint_goal,
        }
    )
    return r
