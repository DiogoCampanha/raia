"""
Risk Classifier agent (Product layer -- Conception / value definition).

Paper Table 2:
  Inputs   : product brief, intended use, target users
  Outputs  : risk classification with applicable legal obligations
             and recommendations
  Grounding: EU AI Act risk tiers; Brazilian bill PL 2338/2023
"""

from .base import AgentSpec, BaseAgent, InputField


class RiskClassifierAgent(BaseAgent):
    spec = AgentSpec(
        key="risk_classifier",
        name="Risk Classifier",
        layer="Product",
        sdlc_phase="Conception and value definition",
        description=(
            "Classifies the AI system into a legal risk tier and lists the "
            "obligations that follow from that classification."
        ),
        grounding_sources=["eu_ai_act", "pl_2338_2023"],
        upstream_keys=[],          # first agent: nothing upstream yet
        required_upstream=[],      # only needs the human-provided brief
        output_key="risk_classification",
        input_fields=[
            InputField(
                key="product_brief",
                label="Product brief",
                help="What is the product? What problem does it solve? What does the AI component do?",
            ),
            InputField(
                key="intended_use",
                label="Intended use",
                help="How and in which context will the system be used? Who operates it?",
            ),
            InputField(
                key="target_users",
                label="Target users and affected people",
                help="Who uses the system, and who is affected by its outputs (including non-users)?",
            ),
        ],
        task_prompt=(
            "Classify this AI system under BOTH the EU AI Act risk tiers "
            "(unacceptable / high-risk / limited-transparency / minimal) and the "
            "Brazilian bill PL 2338/2023 (excessive risk / high risk / other). "
            "Structure your output as:\n"
            "## Risk Classification\n"
            "(tier per jurisdiction, with the specific Annex/Article that applies)\n"
            "## Applicable Legal Obligations\n"
            "(each obligation cited to the grounding excerpt)\n"
            "## Recommendations for the Team\n"
            "(concrete next steps, e.g. impact assessment, human oversight design)\n"
            "## Open Issues\n"
            "(ambiguities in classification or conflicts requiring human arbitration)"
        ),
    )
