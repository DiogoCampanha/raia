"""
User Story Refiner agent (Dev layer -- Iterative development / sprints).

Paper Table 2:
  Inputs   : backlog user stories, ethical requirements
  Outputs  : refined stories with ethical acceptance criteria
  Grounding: ECCOLA themes; MS RAI v2 verifiable requirements
"""

from .base import AgentSpec, BaseAgent, InputField


class UserStoryRefinerAgent(BaseAgent):
    spec = AgentSpec(
        key="story_refiner",
        name="User Story Refiner",
        layer="Dev",
        sdlc_phase="Iterative development (sprints)",
        description=(
            "Evolves ECCOLA's card logic into dynamic, context-aware guidance: "
            "adds verifiable ethical acceptance criteria to backlog stories."
        ),
        grounding_sources=["eccola", "ms_rai_v2"],
        upstream_keys=["risk_classification", "requirements_review"],
        required_upstream=["requirements_review"],  # stage gate (Figure 1)
        output_key="refined_stories",
        input_fields=[
            InputField(
                key="user_stories",
                label="Backlog user stories",
                help="Paste the sprint's user stories (one per line, e.g. 'As a recruiter, I want ...').",
            ),
        ],
        task_prompt=(
            "Refine each backlog user story with ethical acceptance criteria. "
            "Use the ECCOLA themes to decide WHICH concerns apply to each story "
            "given this project's context, and the Microsoft RAI Standard v2 "
            "style to make each criterion VERIFIABLE (measurable thresholds, "
            "testable conditions — e.g. 'demographic parity difference across "
            "gender and race groups <= 0.1 on validation data'). Structure as:\n"
            "## Refined Stories\n"
            "(for each story: the original text, the applicable ECCOLA theme(s) "
            "with citations, and the added acceptance criteria, each traceable to "
            "an upstream ethical value requirement (EVR-n) where one exists)\n"
            "## Stories Without Ethical Impact\n"
            "(stories where no criteria were added, with a one-line justification "
            "— absence of action must also be auditable)\n"
            "## Open Issues\n"
            "(criteria that conflict with sprint constraints, for human arbitration)"
        ),
    )
