"""
Risk Classifier agent (Product layer — Conception / value definition).

RAIA agent specification:
  Inputs   : what the product is, what the AI produces, where and by whom it
             is used, how the AI works, and the structured facts that
             actually decide a classification
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

from ..contract import checks as contract_checks
from ..fields import InputField, ShowIf, YES_NO, YES_NO_UNSURE
from ..rationale import risk_screen
from .base import AgentSpec, BaseAgent

G_PRODUCT = "1 · The product"
G_TECH = "2 · How the AI works"
G_FOOTPRINT = "3 · Legal footprint"
G_PURPOSE = "4 · Purpose and practices"
G_DECISIONS = "5 · How decisions are made"
G_DATA = "6 · Data"
G_STATUS = "7 · Status and exemptions"


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
        input_fields=[
            # The product, in the team's words. Each question asks for one thing
            # and shows an answer of the expected shape: the model reasons over
            # these, and together they become the product brief every later
            # stage reads.
            InputField(
                key="product_brief", label="What is the product?", group=G_PRODUCT, required=True,
                height=110,
                help="Name it, say what problem it solves and for whom, and which part of it uses AI. "
                     "Two or three sentences are enough.",
                placeholder="e.g. TalentMatch is a web tool that HR teams use to screen job "
                            "applications. It reads each CV and ranks the applicants for an opening, "
                            "so recruiters review the strongest candidates first.",
            ),
            InputField(
                key="ai_output", label="What does the AI produce or decide?", group=G_PRODUCT,
                required=True, height=110,
                help="Be concrete: a score, a ranking, a yes/no, generated text or images, an action it "
                     "takes. Then say what happens next with that output, and to whom.",
                placeholder="e.g. A 0–100 fit score per applicant and a shortlist of the top 20. "
                            "Recruiters see only the shortlist; applicants below it receive an "
                            "automatic rejection email.",
            ),
            InputField(
                key="intended_use", label="Where, how and by whom will it be used?", group=G_PRODUCT,
                required=True, height=110,
                help="The setting, who operates it day to day, how often, and roughly how many "
                     "people it affects (per month, say).",
                placeholder="e.g. Used by in-house recruiters at mid-size companies in Brazil and "
                            "Portugal, for every open vacancy: about 5,000 applications a month.",
            ),
            InputField(
                key="target_users", label="Who uses it, and who is affected by its outputs?",
                group=G_PRODUCT, required=True, height=110,
                help="Name the people who operate it and the people its outputs are about — "
                     "including people who never use the system themselves.",
                placeholder="e.g. Operators: recruiters and HR managers. Affected: every applicant, "
                            "including those rejected automatically, who never see the tool.",
            ),
            InputField(
                key="out_of_scope", label="What should it not be used for?", group=G_PRODUCT,
                height=90,
                help="Uses you exclude or would treat as misuse. Obligations attach to the intended "
                     "purpose, so this bounds what the classification covers.",
                placeholder="e.g. Not for promotions, performance reviews or dismissals.",
            ),

            InputField(
                key="ai_techniques", label="What kind of AI does it use?", kind="multiselect",
                group=G_TECH, required=True, options=risk_screen.TECHNIQUE_OPTIONS,
                help="Select every technique in the product. Both regimes define an AI system by "
                     "its ability to infer outputs; rules written only by people may fall outside "
                     "that definition.",
            ),
            InputField(
                key="ai_pipeline", label="Where in the product does the AI act?", kind="multiselect",
                group=G_TECH, required=True, options=risk_screen.PIPELINE_OPTIONS,
                help="Select every step where an AI output is produced or used. These are checked "
                     "against your transparency and autonomy answers.",
            ),
            InputField(
                key="model_source", label="Where does the model come from?", kind="select",
                group=G_TECH, required=True, options=risk_screen.MODEL_SOURCE_OPTIONS,
                help="If several models are involved, choose the one that produces the output "
                     "described above.",
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
            "Explain and justify the classification the rule engine computed, in language the "
            "product team can act on, under the EU AI Act and PL 2338/2023. Do not re-derive the "
            "tier or the obligation list: they are given to you. Your work is the reasoning, the "
            "context, the edge cases, and anything the structured answers left ambiguous. Treat "
            "the product answers — what the AI produces, where and by whom it is used, what it "
            "is not for, and how the AI works — as the facts of the case; where the prose "
            "contradicts a structured answer, say so in an open issue rather than choosing one.\n\n"
            "In the extension: `prohibited_screen` states the result of the EU AI Act Art. 5 and "
            "PL 2338/2023 excessive-risk screens. `eu_tier_justification` and "
            "`br_tier_justification` name the specific area or article that produces each tier "
            "and say plainly what it means for this team; if you believe a computed tier is "
            "wrong, set `agrees_with_rule_engine` to false and argue it. `obligations` holds one "
            "entry per obligation code in the computed table, exactly, explaining what satisfying "
            "it looks like for this product, cited; never add a code — if one seems missing, "
            "raise an open issue. `human_oversight_assessment` tests the declared autonomy and "
            "oversight against the human-oversight obligations; `affected_persons_rights` says "
            "how explanation, contestation and human review are built into the product; "
            "`impact_assessments` names the fundamental-rights and algorithmic impact "
            "assessments the instruments require here.\n\n"
            "Findings are the risks the classification exposes for this product (for example an "
            "obligation the current design does not meet), each linked to the obligation codes it "
            "concerns. Actions are the next steps for the declared lifecycle stage."
        ),
    )

    def extra_checks(self, report, draft, rationale, record) -> None:
        computed = [o.get("code") for o in (rationale.data or {}).get("obligations") or []]
        noted = [o.get("code") for o in (record.get("extension") or {}).get("obligations") or []]
        report.add(contract_checks.check_registered_ids(
            "Obligation register", "obligations", computed, noted))
