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

import re
from typing import Any, Dict, List

from .. import validators
from ..fields import InputField
from ..rationale import story_map
from ..rationale.types import RationaleResult
from .base import AgentSpec, BaseAgent

G_BACKLOG = "1 · The sprint's backlog"
G_SCOPE = "2 · What these stories touch"

AC_ID = re.compile(r"\bAC-(S\d+)-(\d+)\b")


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
        required_sections=[
            "Refined Stories",
            "Stories Without Ethical Impact",
            "Open Issues",
        ],
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
            "Add verifiable ethical acceptance criteria to the sprint's stories, using the "
            "card selection and the story register the engine computed. The selected cards and "
            "the story ids are given to you: do not invent card ids, do not invent story ids, "
            "and do not leave a story out of your answer.\n\n"
            "Under **Refined Stories**, for each story that needs criteria: restate the story "
            "with its id, name the selected card id(s) that make it relevant and cite the "
            "excerpt that grounds them, then list the acceptance criteria. Label every "
            "criterion with an id of the form `AC-<story id>-<n>` — for example `AC-S1-1` — so "
            "it can be audited later. Each criterion must be measurable or testable: a "
            "threshold, a check, an artifact that must exist. Where an approved requirement id "
            "(EVR-n) covers it, name that id.\n\n"
            "Under **Stories Without Ethical Impact**, list every remaining story id with one "
            "line saying why no criterion was added. This section is not optional: a story that "
            "appears in neither section is a gap in the audit trail.\n\n"
            "Under **Open Issues**, carry forward every issue the engine raised, plus any "
            "criterion that conflicts with the sprint's constraints."
        ),
    )

    def extra_checks(
        self, report: validators.ValidationReport, draft: str, rationale: RationaleResult
    ) -> None:
        story_ids = rationale.verdict.get("story_ids") or []
        card_ids = rationale.verdict.get("card_ids") or []
        evr_ids = rationale.verdict.get("evr_ids") or []

        report.add(
            validators.check_traceability(draft, story_ids, "Story register", code="stories")
        )
        if evr_ids:
            report.add(
                validators.check_unknown_ids(
                    draft, r"\bEVR-\d+\b", evr_ids, "Requirement references"
                )
            )
        report.add(
            validators.check_unknown_ids(
                draft, r"(?<![\w])#\d{1,2}(?![\w])", card_ids, "Ethical theme references"
            )
        )
        orphan = sorted({f"AC-{s}-{n}" for s, n in AC_ID.findall(draft) if s not in set(story_ids)})
        if orphan:
            report.add(
                validators.ValidationItem(
                    "criteria.orphan", validators.FAIL, "Acceptance criterion ids",
                    "Criteria are attached to story ids that are not in the register.", orphan,
                )
            )

    def structured_from(self, draft: str, rationale: RationaleResult) -> Dict[str, Any]:
        """Extract the acceptance-criterion register the Auditor will audit."""
        data = super().structured_from(draft, rationale)
        criteria: List[Dict[str, str]] = []
        for line in (draft or "").splitlines():
            for story, n in AC_ID.findall(line):
                cid = f"AC-{story}-{n}"
                if any(c["id"] == cid for c in criteria):
                    continue
                criteria.append({"id": cid, "story": story, "text": line.strip(" -*\t")})
        data["criteria"] = criteria
        return data
