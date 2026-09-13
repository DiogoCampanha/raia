"""
Risk Classifier agent (Product layer — Conception / value definition).

RAIA agent specification:
  Inputs   : product brief, intended use, target users, and the structured
             facts that actually decide a classification
  Outputs  : risk classification with applicable legal obligations
             and recommendations
  Grounding: EU AI Act risk tiers; Brazilian bill PL 2338/2023

The classification itself is computed by the rule engine in
``raia.rationale.risk_screen``: prohibition lists, high-risk area lists and
obligation tables are enumerable, so they belong in code. The model explains
the result in the team's own context, handles the questions a rule table would
get confidently wrong — whether a narrow-task exemption really holds, whether a
harm is significant — and must declare whether it agrees with the screen.
"""

from typing import Any, Dict

from ..fields import InputField, ShowIf, YES_NO, YES_NO_UNSURE
from ..rationale import risk_screen
from .base import AgentSpec, BaseAgent

G_PRODUCT = "1 · The product"
G_FOOTPRINT = "2 · Legal footprint"
G_PURPOSE = "3 · Purpose and practices"
G_DECISIONS = "4 · How decisions are made"
G_DATA = "5 · Data"
G_STATUS = "6 · Status and exemptions"


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
        intro=(
            "The questions below are the ones that decide a classification. They are "
            "asked explicitly rather than inferred from prose, so you can see exactly "
            "what the verdict rests on — and correct it if an answer is wrong."
        ),
        grounding_sources=["eu_ai_act", "pl_2338_2023"],
        upstream_keys=[],
        required_upstream=[],
        output_key="risk_classification",
        engine=lambda inputs, upstream: risk_screen.run(inputs),
        verdict_keys=["eu_tier", "br_tier"],
        required_sections=[
            "Risk Classification",
            "Applicable Legal Obligations",
            "Recommendations for the Team",
            "Open Issues",
        ],
        input_fields=[
            InputField(
                key="product_brief", label="Product brief", group=G_PRODUCT, required=True,
                help="What is the product? What problem does it solve? What does the AI component do?",
            ),
            InputField(
                key="intended_use", label="Intended use", group=G_PRODUCT, required=True,
                help="How and in which context will the system be used? Who operates it?",
            ),
            InputField(
                key="target_users", label="Target users and affected people", group=G_PRODUCT, required=True,
                help="Who uses the system, and who is affected by its outputs (including non-users)?",
            ),

            InputField(
                key="role", label="Your role", kind="select", group=G_FOOTPRINT, required=True,
                options=risk_screen.ROLE_OPTIONS,
                help="Obligations differ sharply between building a system and operating one.",
            ),
            InputField(
                key="markets", label="Where will it be placed on the market or used?",
                kind="multiselect", group=G_FOOTPRINT, required=True,
                options=risk_screen.MARKET_OPTIONS,
                help="Both regimes are screened either way; this decides which result is binding.",
            ),
            InputField(
                key="public_sector", label="Is it deployed by a public body, or to provide a public service?",
                kind="boolean", group=G_FOOTPRINT, options=YES_NO, default="no",
                help="Triggers the impact-assessment duty for deployers and extra publicity in Brazil.",
            ),
            InputField(
                key="gpai_provider", label="Are you the provider of a general-purpose AI model?",
                kind="boolean", group=G_FOOTPRINT, options=YES_NO, default="no",
                help="Answer no if you are only using someone else's foundation model in a product.",
            ),

            InputField(
                key="purpose_areas", label="Which of these describes what the system is used for?",
                kind="multiselect", group=G_PURPOSE, required=True,
                options=risk_screen.PURPOSE_OPTIONS,
                help="Select every area that applies. These lists are what determine high-risk status.",
            ),
            InputField(
                key="annex_i_product",
                label="Is the AI a safety component of a product already regulated for safety?",
                kind="boolean", group=G_PURPOSE, options=YES_NO, default="no",
                help="For example medical devices, machinery, lifts, vehicles. This is a separate high-risk route.",
            ),
            InputField(
                key="prohibited_practices", label="Does the system do any of these?",
                kind="multiselect", group=G_PURPOSE, required=True,
                options=risk_screen.PROHIBITED_OPTIONS,
                help="Answer honestly — a match here stops the pipeline rather than producing a report.",
            ),
            InputField(
                key="transparency_triggers", label="Does any of these apply?",
                kind="multiselect", group=G_PURPOSE, required=True,
                options=risk_screen.TRANSPARENCY_OPTIONS,
                help="These trigger disclosure duties even when the system is not high-risk.",
            ),

            InputField(
                key="decision_autonomy", label="How much does the system decide on its own?",
                kind="select", group=G_DECISIONS, required=True,
                options=risk_screen.AUTONOMY_OPTIONS,
                help="Answer for what happens in practice, not what the design diagram says.",
            ),
            InputField(
                key="significant_effects",
                label="Does an output produce legal effects, or otherwise significantly affect a person?",
                kind="select", group=G_DECISIONS, required=True, options=YES_NO_UNSURE,
                help="This drives the rights of affected people: explanation, contestation, human review.",
            ),
            InputField(
                key="human_oversight", label="What oversight exists today?",
                kind="select", group=G_DECISIONS, required=True,
                options=risk_screen.OVERSIGHT_OPTIONS,
                help="What exists now, not what is planned. Planned work belongs in the recommendations.",
            ),

            InputField(
                key="data_categories", label="Which of these does the system process?",
                kind="multiselect", group=G_DATA, required=True, options=risk_screen.DATA_OPTIONS,
                help="Include data used for training as well as data used at inference time.",
            ),

            InputField(
                key="deployment_stage", label="Where is the system in its lifecycle?",
                kind="select", group=G_STATUS, required=True, options=risk_screen.STAGE_OPTIONS,
                help="Recommendations are scaled to what is still changeable at this stage.",
            ),
            InputField(
                key="art63_claim",
                label="Do you intend to claim the narrow-task exemption from high-risk status?",
                kind="boolean", group=G_STATUS, options=YES_NO, default="no",
                help="Available where a system only performs a narrow procedural task or improves "
                     "the result of a completed human activity. It must be documented and stays reviewable.",
            ),
            InputField(
                key="art63_reason", label="On what basis?", kind="textarea", group=G_STATUS, height=100,
                show_if=ShowIf("art63_claim", ("yes",)),
                help="The rule engine cannot confirm this; it is recorded as an open issue for a human.",
            ),
        ],
        task_prompt=(
            "Explain and justify the classification the rule engine computed, in language "
            "the product team can act on. Do not re-derive the tier or the obligation list — "
            "they are given to you. Your work is the reasoning, the context, the edge cases, "
            "and anything the structured answers left ambiguous.\n\n"
            "Under **Risk Classification**, state the tier for each jurisdiction with the "
            "specific area or article that produces it, and say plainly what it means for this "
            "team. If you believe the computed tier is wrong, say so here, argue it, and record "
            "it as an open issue — do not quietly classify it differently.\n\n"
            "Under **Applicable Legal Obligations**, take every obligation in the computed table "
            "and explain what satisfying it looks like for *this* product, citing the excerpt "
            "that grounds it. Do not add obligations that are not in the table; if you believe "
            "one is missing, raise it as an open issue instead.\n\n"
            "Under **Recommendations for the Team**, give concrete next steps appropriate to the "
            "declared lifecycle stage — an impact assessment, an oversight design, bias testing — "
            "each tied to an obligation.\n\n"
            "Under **Open Issues**, carry forward every issue the rule engine raised, plus any "
            "ambiguity you found that a human must settle."
        ),
    )
