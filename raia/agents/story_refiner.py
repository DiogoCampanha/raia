"""
User Story Refiner agent (Dev layer — Iterative development / sprints).

RAIA agent specification:
  Inputs   : backlog user stories, the capabilities they touch, and the
             approved risk classification and ethical requirements
  Outputs  : refined stories with verifiable ethical acceptance criteria
  Grounding: ECCOLA cards; Microsoft RAI Standard v2 verifiable requirements

ECCOLA's own method is that relevant cards are selected per sprint. That
selection is computed here from the approved risk tier, the declared data
categories and the capabilities this sprint touches, so every card in scope
carries the reason it is in scope. The story register is a counted invariant:
every story that goes in comes back out, refined or explicitly justified as
having no ethical impact — absence of action has to be auditable too.
"""

from typing import Any, Dict

from ..contract import checks as contract_checks
from ..fields import InputField
from ..rationale import story_map
from ..rationale.types import RationaleResult
from .base import AgentSpec, BaseAgent

G_BACKLOG = "1 · The sprint's backlog"
G_SCOPE = "2 · What these stories touch"


class UserStoryRefinerAgent(BaseAgent):
    spec = AgentSpec(
        key="story_refiner",
        name="User Story Refiner",
        layer="Dev",
        sdlc_phase="Iterative development (sprints)",
        description=(
            "Selects the ethical themes that actually apply to this sprint and adds "
            "verifiable acceptance criteria to the backlog stories."
        ),
        intro=(
            "Which ethical themes apply is computed from the approved classification and the "
            "capabilities you declare below — so the selection is traceable rather than a "
            "judgement call the agent made silently. Every story you paste comes back either "
            "refined or explicitly justified as having no ethical impact."
        ),
        grounding_sources=["eccola", "ms_rai_v2"],
        upstream_keys=["risk_classification", "requirements_review"],
        required_upstream=["requirements_review"],
        output_key="refined_stories",
        engine=story_map.run,
        verdict_keys=["story_count"],
        input_fields=[
            InputField(
                key="user_stories", label="Backlog user stories", group=G_BACKLOG, required=True,
                height=220,
                help="One story per line or per paragraph. Existing ids (S1, US-12) are preserved; "
                     "unlabelled stories are numbered for you.",
            ),
            InputField(
                key="sprint_goal", label="Sprint goal", kind="text", group=G_BACKLOG,
                help="One line. Used to focus retrieval and to judge whether a criterion is "
                     "realistic inside this sprint.",
            ),
            InputField(
                key="touched_capabilities", label="What do these stories touch?",
                kind="multiselect", group=G_SCOPE, required=True,
                options=story_map.CAPABILITY_OPTIONS,
                help="This answer selects the ethical themes. Leaving it empty means only the "
                     "always-relevant themes apply.",
            ),
            InputField(
                key="definition_of_done", label="Your definition of done", kind="textarea",
                group=G_SCOPE, height=100,
                help="If you have one, criteria will be written in its terms so they fit the "
                     "team's existing process rather than sitting beside it.",
            ),
        ],
        task_prompt=(
            "Refine this sprint's stories with the ECCOLA method and the Microsoft RAI Standard v2 "
            "verifiable-requirement pattern. The selected cards and the story ids are given to "
            "you: do not invent card ids, do not invent story ids, and do not leave a story "
            "out.\n\n"
            "In the extension, `stories` has exactly one entry per story id. For a story that "
            "needs criteria: `eccola_cards` lists only selected card ids that make it relevant; "
            "`card_discussion` answers those cards' questions for this story; `criteria` follow "
            "the verifiable-requirement pattern — the Standard's goal, the affected stakeholder "
            "group, a measurable `condition` with its threshold, the `evidence_artifact` that "
            "demonstrates it and an owner — each labelled `AC-<story id>-<n>` (for example "
            "`AC-S1-1`) and traced to an approved EVR id where one covers it. A story with no "
            "ethical impact has no criteria and a one-line `no_impact_reason`. "
            "`sprint_ethics_log` records the decisions taken and why, as ECCOLA's documentation "
            "step asks.\n\n"
            "Findings are the ethical risks this sprint introduces, linked to story and card ids. "
            "Actions are what the team does about them in this sprint or later."
        ),
    )

    def extra_checks(self, report, draft, rationale, record) -> None:
        story_ids = rationale.verdict.get("story_ids") or []
        card_ids = rationale.verdict.get("card_ids") or []
        evr_ids = rationale.verdict.get("evr_ids") or []
        stories = (record.get("extension") or {}).get("stories") or []
        report.add(contract_checks.check_registered_ids(
            "Story register", "stories", story_ids, [s.get("story_id") for s in stories]))
        report.add(contract_checks.check_registered_ids(
            "Card selection", "cards", card_ids,
            [c for s in stories for c in s.get("eccola_cards") or []], require_all=False))
        report.add(contract_checks.check_registered_ids(
            "Requirement references", "references", evr_ids,
            [e for s in stories for c in s.get("criteria") or [] for e in c.get("evr_ids") or []],
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
