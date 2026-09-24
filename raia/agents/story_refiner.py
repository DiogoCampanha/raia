"""
User Story Refiner agent (Dev layer — Iterative development / sprints).

RAIA agent specification:
  Inputs   : the sprint's user stories — each with its description, existing
             acceptance criteria and the capabilities it touches — and the
             approved risk classification and ethical requirements
  Outputs  : refined stories with verifiable ethical acceptance criteria
  Grounding: ECCOLA cards; Microsoft RAI Standard v2 verifiable requirements

ECCOLA's own method is that relevant cards are selected per sprint. That
selection is computed here, story by story, from the approved risk tier, the
declared data categories and the capabilities each story touches, so every
card in scope carries the reason — and the stories — it is in scope for.
Existing acceptance criteria stay the team's: the agent adds new ethical
criteria and flags an existing one only when it conflicts, and code turns
each conflict into a decision for a person. The story register is a counted invariant:
every story that goes in comes back out, refined or explicitly justified as
having no ethical impact — absence of action has to be auditable too.
"""

from typing import Any, Dict, List

from ..contract import checks as contract_checks
from ..fields import InputField
from ..rationale import story_map
from ..rationale.types import RationaleResult
from .base import AgentSpec, BaseAgent

G_STORIES = "1 · The stories"
G_SPRINT = "2 · The sprint"


class UserStoryRefinerAgent(BaseAgent):
    spec = AgentSpec(
        key="story_refiner",
        name="User Story Refiner",
        layer="Dev",
        sdlc_phase="Iterative development (sprints)",
        description=(
            "Selects the ethical themes that actually apply to each story and adds "
            "verifiable acceptance criteria, flagging existing criteria that conflict."
        ),
        intro=(
            "Add each story on its own, with its acceptance criteria and what it touches. Which "
            "ethical themes apply is computed per story from those answers and the approved "
            "classification. Every story comes back either with new ethical criteria or with a "
            "one-line reason it needs none; existing criteria that conflict are flagged for you "
            "to decide."
        ),
        grounding_sources=["eccola", "ms_rai_v2"],
        upstream_keys=["risk_classification", "requirements_review"],
        required_upstream=["requirements_review"],
        output_key="refined_stories",
        engine=story_map.run,
        verdict_keys=["story_count"],
        input_fields=[
            InputField(
                key="user_stories", label="User stories", kind="stories", group=G_STORIES,
                required=True, options=story_map.CAPABILITY_OPTIONS,
                renderer=story_map.render_stories, missing=story_map.stories_missing,
                parse=story_map.parse_backlog,
                help="One card per story. Its answer to \"What does it touch?\" selects the ethical "
                     "themes for that story.",
            ),
            InputField(
                key="sprint_goal", label="Sprint goal", kind="text", group=G_SPRINT,
                help="One line. Used to focus retrieval and to judge whether a criterion is "
                     "realistic inside this sprint.",
            ),
            InputField(
                key="definition_of_done", label="Your definition of done", kind="textarea",
                group=G_SPRINT, height=100,
                help="If you have one, criteria will be written in its terms so they fit the "
                     "team's existing process rather than sitting beside it.",
            ),
        ],
        task_prompt=(
            "Refine this sprint's stories with the ECCOLA method and the Microsoft RAI Standard v2 "
            "verifiable-requirement pattern. The story ids, each story's existing acceptance "
            "criteria and the cards in scope for each story are given to you: do not invent ids, "
            "and do not leave a story out.\n\n"
            "In the extension, `stories` has exactly one entry per story id. For a story that "
            "needs ethical criteria: `eccola_cards` lists only cards in scope for THAT story that "
            "make it relevant; `card_discussion` answers those cards' questions for this story in "
            "two or three sentences; `criteria` are NEW criteria only — never restate an existing "
            "one — following the verifiable-requirement pattern: the Standard's goal, the affected "
            "stakeholder group, a measurable `condition` with its threshold, the "
            "`evidence_artifact` that demonstrates it and an owner, each labelled "
            "`AC-<story id>-<n>` (for example `AC-S1-1`) and traced to an approved EVR id where one "
            "covers it. In `conflicts`, flag an existing criterion (by its id, e.g. `S1-E2`) only "
            "when it conflicts with an approved requirement or a card in scope — say why in one "
            "sentence and suggest a rewrite; the team decides. A story with no ethical impact has "
            "no criteria and a one-line `no_impact_reason`. `sprint_ethics_log` lists up to five "
            "decisions taken and why, one sentence each.\n\n"
            "Findings are the ethical risks this sprint introduces, linked to story and card ids. "
            "Actions are what the team does about them in this sprint or later."
        ),
    )

    def extra_checks(self, report, draft, rationale, record) -> None:
        verdict = rationale.verdict or {}
        story_ids = verdict.get("story_ids") or []
        card_ids = verdict.get("card_ids") or []
        story_cards: Dict[str, List[str]] = verdict.get("story_cards") or {}
        existing: Dict[str, List[str]] = verdict.get("existing_criteria") or {}
        evr_ids = verdict.get("evr_ids") or []
        stories = (record.get("extension") or {}).get("stories") or []
        report.add(contract_checks.check_registered_ids(
            "Story register", "stories", story_ids, [s.get("story_id") for s in stories]))
        if story_cards:
            # Cards are selected per story: a card is in scope for the story whose capabilities chose it.
            allowed = [f"{sid}:{c}" for sid, cards in story_cards.items() for c in cards]
            used = [f"{s.get('story_id')}:{c}" for s in stories for c in s.get("eccola_cards") or []]
        else:
            allowed, used = card_ids, [c for s in stories for c in s.get("eccola_cards") or []]
        report.add(contract_checks.check_registered_ids(
            "Card selection", "cards", allowed, used, require_all=False))
        report.add(contract_checks.check_registered_ids(
            "Requirement references", "references", evr_ids,
            [e for s in stories for c in s.get("criteria") or [] for e in c.get("evr_ids") or []],
            require_all=False))
        report.add(contract_checks.check_registered_ids(
            "Conflicting criteria", "conflicts",
            [f"{sid}:{cid}" for sid, ids in existing.items() for cid in ids],
            [f"{s.get('story_id')}:{c.get('criterion_id')}" for s in stories for c in s.get("conflicts") or []],
            require_all=False))
        report.add(contract_checks.check_criteria_ids(record))

    def structured_from(self, record: Dict[str, Any], rationale: RationaleResult) -> Dict[str, Any]:
        """Publish the acceptance-criterion register the Auditor will audit."""
        data = super().structured_from(record, rationale)
        data["criteria"] = [
            {"id": c.get("id"), "story": s.get("story_id"), "text": c.get("condition", ""),
             "ms_goal": c.get("ms_goal"), "evidence_artifact": c.get("evidence_artifact", "")}
            for s in (record.get("extension") or {}).get("stories") or []
            for c in s.get("criteria") or []
        ]
        return data
