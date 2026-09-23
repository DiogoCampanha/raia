"""
raia.rationale.risk_screen
==========================

Deterministic legal risk screen for the Risk Classifier.

What is enumerable is decided here, in code: the prohibited-practice lists,
the high-risk purpose-area lists for both jurisdictions, the role-dependent
obligation tables, the transparency triggers, and whether the declared
techniques put the product within the legal definition of an AI system. What is open-textured —
whether a narrow-task exemption actually holds, whether a harm is
"significant" — is left to the model, which must justify it and may disagree
with the screen. Disagreement is escalated, never averaged.

The option vocabularies live in this module and are imported by the agent
spec, so the coupling between a form field and the rule that reads it is
explicit and greppable.
"""

from typing import Any, Dict, List

from ..fields import chosen, is_yes, options, selected, text_of
from .types import ChecklistItem, Finding, Pin, RationaleResult, md_table

# ---------------------------------------------------------------------------
# Option vocabularies (form ↔ engine contract)
# ---------------------------------------------------------------------------

ROLE_OPTIONS = options(
    ("provider", "Provider — we build it, or place it on the market under our name"),
    ("deployer", "Deployer — we operate a system built by someone else"),
    ("both", "Both — we build it and we operate it ourselves"),
)

MARKET_OPTIONS = options(
    ("eu", "European Union / EEA"),
    ("br", "Brazil"),
    ("other", "Other jurisdictions only"),
)

#: Prohibited / excessive-risk practices, unioned across both jurisdictions.
#: ``eu`` and ``br`` say which regime each practice bites under; ``conditional``
#: marks practices that are restricted rather than flatly banned.
PROHIBITED_PRACTICES: Dict[str, Dict[str, Any]] = {
    "subliminal": {
        "label": "Subliminal, manipulative or deceptive techniques that materially distort behaviour",
        "eu": True, "br": True, "conditional": False,
    },
    "vulnerability": {
        "label": "Exploits vulnerabilities of age, disability, or social/economic situation",
        "eu": True, "br": True, "conditional": False,
    },
    "social_scoring": {
        "label": "Social scoring leading to unjustified or disproportionate detrimental treatment",
        "eu": True, "br": True, "conditional": False,
    },
    "crime_prediction": {
        "label": "Predicts criminal offence or recidivism risk from profiling or personality traits",
        "eu": True, "br": True, "conditional": False,
    },
    "face_scraping": {
        "label": "Untargeted scraping of facial images to build a recognition database",
        "eu": True, "br": False, "conditional": False,
    },
    "emotion_work_edu": {
        "label": "Infers emotions in the workplace or in educational institutions",
        "eu": True, "br": False, "conditional": False,
    },
    "biometric_categorisation": {
        "label": "Biometric categorisation inferring sensitive attributes",
        "eu": True, "br": False, "conditional": False,
    },
    "csam": {
        "label": "Enables production or dissemination of child sexual abuse material",
        "eu": False, "br": True, "conditional": False,
    },
    "autonomous_weapons": {
        "label": "Autonomous weapons without meaningful human control",
        "eu": False, "br": True, "conditional": False,
    },
    "realtime_rbi": {
        "label": "Real-time remote biometric identification in public spaces for law enforcement",
        "eu": True, "br": True, "conditional": True,
    },
}

PROHIBITED_OPTIONS = options(
    *[(k, v["label"]) for k, v in PROHIBITED_PRACTICES.items()],
    ("none", "None of these"),
)

#: High-risk purpose areas, unioned across both jurisdictions. One question on
#: the form, two matchers reading it.
PURPOSE_AREAS: Dict[str, Dict[str, Any]] = {
    "biometrics": {
        "label": "Biometric identification, categorisation or emotion recognition",
        "annex_iii": "1 — Biometrics", "pl_art17": "8 — Biometric identification and emotion recognition",
    },
    "critical_infra": {
        "label": "Safety component of critical infrastructure (traffic, water, energy, digital)",
        "annex_iii": "2 — Critical infrastructure", "pl_art17": "1 — Critical infrastructure",
    },
    "education": {
        "label": "Education and vocational training — admission, assessment, proctoring",
        "annex_iii": "3 — Education and vocational training", "pl_art17": "2 — Education and vocational training",
    },
    "employment": {
        "label": "Employment — recruitment, screening, evaluation, promotion, termination, task allocation, worker monitoring",
        "annex_iii": "4 — Employment, workers management and access to self-employment",
        "pl_art17": "3 — Recruitment, screening and evaluation of candidates and workers",
    },
    "essential_services": {
        "label": "Access to essential services — credit scoring, insurance pricing, public benefits, emergency triage",
        "annex_iii": "5 — Access to essential private and public services",
        "pl_art17": "4 — Access to essential public and private services and benefits",
    },
    "law_enforcement": {
        "label": "Law enforcement or public security",
        "annex_iii": "6 — Law enforcement", "pl_art17": "9 — Criminal investigation and public security",
    },
    "migration": {
        "label": "Migration, asylum or border control",
        "annex_iii": "7 — Migration, asylum and border control", "pl_art17": "10 — Migration and border control",
    },
    "justice": {
        "label": "Administration of justice or democratic processes",
        "annex_iii": "8 — Administration of justice and democratic processes",
        "pl_art17": "5 — Administration of justice",
    },
    "health": {
        "label": "Health applications, including diagnosis support",
        "annex_iii": "", "pl_art17": "7 — Health applications and diagnosis support",
    },
    "autonomous_vehicles": {
        "label": "Autonomous vehicles operating in public spaces",
        "annex_iii": "", "pl_art17": "6 — Autonomous vehicles in public spaces",
    },
    "content_curation": {
        "label": "Large-scale content curation or recommendation affecting information integrity",
        "annex_iii": "", "pl_art17": "11 — Large-scale content curation and recommendation",
    },
}

PURPOSE_OPTIONS = options(
    *[(k, v["label"]) for k, v in PURPOSE_AREAS.items()],
    ("none", "None of these — the purpose is outside every listed area"),
)

TRANSPARENCY_OPTIONS = options(
    ("chat_interaction", "People interact with the system directly (chatbot, assistant, voice agent)"),
    ("synthetic_content", "The system generates or manipulates image, audio, video or text content"),
    ("deepfake", "The system produces content resembling real people, places or events"),
    ("emotion_recognition", "The system performs emotion recognition on people"),
    ("biometric_categorisation", "The system performs biometric categorisation"),
    ("none", "None of these"),
)

AUTONOMY_OPTIONS = options(
    ("fully_automated", "Fully automated — the system's output is the decision"),
    ("human_confirms", "A person confirms the output, but in practice almost always accepts it"),
    ("human_override", "A recommendation a person reviews and may override"),
    ("informational", "Purely informational — no decision about a person follows from it"),
)

OVERSIGHT_OPTIONS = options(
    ("none_designed", "No oversight mechanism designed yet"),
    ("monitoring_only", "People can monitor outputs but cannot intervene in a specific case"),
    ("override_possible", "A person can override an individual output"),
    ("human_decides", "A person makes the decision; the system only informs it"),
)

DATA_OPTIONS = options(
    ("biometric", "Biometric data"),
    ("health", "Health data"),
    ("protected_attributes", "Protected attributes (race, gender, age, disability, religion, origin)"),
    ("proxies", "Strong proxies for protected attributes (postcode, school, name, photo)"),
    ("children", "Data about children or adolescents"),
    ("location", "Location or movement data"),
    ("financial", "Financial or credit data"),
    ("communications", "Private communications content"),
    ("none", "None of these"),
)

#: How the AI works. Both instruments define an AI system by its capacity to
#: *infer* how to generate outputs; rules written solely by people do not
#: infer. ``INFERRING`` lists the techniques that do.
TECHNIQUE_OPTIONS = options(
    ("rules", "Rules or thresholds written by people — nothing is learned from data"),
    ("machine_learning", "Machine learning trained on data (including deep learning) — "
                         "classifies, scores, ranks, predicts or recommends"),
    ("generative", "Generative AI — produces text, images, audio, video or code (for example an LLM)"),
    ("knowledge_based", "Logic- or knowledge-based inference — reasons over encoded knowledge "
                        "(expert system, knowledge graph)"),
)
INFERRING = {"machine_learning", "generative", "knowledge_based"}

#: Where in the product the AI acts. Read against the transparency and
#: autonomy answers, so an inconsistency between them is surfaced.
PIPELINE_OPTIONS = options(
    ("input_processing", "Reads or prepares inputs — extraction, transcription, enrichment"),
    ("scoring", "Scores, ranks, classifies or predicts"),
    ("generation", "Generates content that people see or receive"),
    ("interaction", "Talks with people directly (chat, voice, assistant)"),
    ("decision", "Makes or carries out a decision with no person in between"),
    ("monitoring", "Monitors people, processes or systems"),
)

MODEL_SOURCE_OPTIONS = options(
    ("in_house", "Built and trained by us"),
    ("adapted", "A third-party model we fine-tune or otherwise adapt"),
    ("third_party", "A third-party model or AI service used as-is (for example through an API)"),
    ("none", "No trained model — the logic is rules only"),
)

STAGE_OPTIONS = options(
    ("idea", "Idea / discovery"),
    ("development", "In development"),
    ("pilot", "Piloting with real users"),
    ("production", "Live in production"),
)

# ---------------------------------------------------------------------------
# Obligation tables — assembled, never generated
# ---------------------------------------------------------------------------

# (code, jurisdiction, applies_to, title, corpus section that grounds it)
EU_PROVIDER_HIGH_RISK = [
    ("eu.art9", "Risk management system across the whole lifecycle"),
    ("eu.art10", "Data and data governance, including examination for biases"),
    ("eu.art11", "Technical documentation before market placement"),
    ("eu.art12", "Automatic record-keeping and logging for traceability"),
    ("eu.art13", "Transparency and instructions for use provided to deployers"),
    ("eu.art14", "Human oversight designed into the system"),
    ("eu.art15", "Accuracy, robustness and cybersecurity"),
]

EU_DEPLOYER_HIGH_RISK = [
    ("eu.art26", "Use per instructions, competent human oversight, input-data relevance, log keeping"),
]

BR_HIGH_RISK = [
    ("br.aia", "Algorithmic Impact Assessment, documented, shared with the authority and kept current"),
    ("br.logging", "Documentation and automatic logging enabling auditability and traceability"),
    ("br.testing", "Reliability, robustness and accuracy testing appropriate to intended use"),
    ("br.data_governance", "Data governance to mitigate discriminatory bias, with representativeness analysis"),
    ("br.explainability", "Technical explainability sufficient for human review of decisions"),
    ("br.supervision", "Effective human supervision enabling understanding and intervention"),
]

BR_ALL_TIERS = [
    ("br.governance", "Governance structures and internal processes for transparency, data governance and security"),
    ("br.rights", "Operationalize affected persons' rights: prior information, explanation, contestation, human review, non-discrimination"),
]

SECTION_EU_SCOPE = "Scope and Approach"
SECTION_BR_SCOPE = "Purpose and Approach"
SECTION_EU_ART5 = "Article 5 — Prohibited AI Practices (Unacceptable Risk)"
SECTION_EU_ANNEX = "Article 6 and Annex III — High-Risk AI Systems"
SECTION_EU_OBLIG = "Obligations for High-Risk Systems (Articles 8–15)"
SECTION_EU_DEPLOYER = "Deployer Obligations (Art. 26) and Fundamental Rights Impact Assessment (Art. 27)"
SECTION_EU_ART50 = "Article 50 — Transparency Obligations (Limited Risk)"
SECTION_EU_GPAI = "General-Purpose AI Models (Arts. 51–55)"
SECTION_BR_EXCESSIVE = "Excessive Risk (Prohibited) Systems"
SECTION_BR_HIGH = "High-Risk Systems (Art. 17 area list)"
SECTION_BR_GOV = "Governance Obligations"
SECTION_BR_RIGHTS = "Rights of Affected Persons"

TIER_UNACCEPTABLE = "unacceptable — prohibited practice"
TIER_RESTRICTED = "prohibited unless a narrow legal exception applies"
TIER_HIGH = "high-risk"
TIER_HIGH_EXEMPT = "high-risk unless the narrow-task exemption is documented and holds"
TIER_LIMITED = "limited risk — transparency duties"
TIER_MINIMAL = "minimal risk"

BR_EXCESSIVE = "excessive risk — prohibited"
BR_HIGH = "high risk"
BR_NOT_LISTED = "not in the listed high-risk areas"


def _clean(codes: List[str]) -> List[str]:
    return [c for c in codes if c and c != "none"]


def run(inputs: Dict[str, Any]) -> RationaleResult:
    """Screen the structured intake and produce a candidate classification."""
    r = RationaleResult(engine="risk_screen")

    role = chosen(inputs, "role", "provider")
    markets = _clean(selected(inputs, "markets"))
    practices = _clean(selected(inputs, "prohibited_practices"))
    areas = _clean(selected(inputs, "purpose_areas"))
    triggers = _clean(selected(inputs, "transparency_triggers"))
    data_cats = _clean(selected(inputs, "data_categories"))
    autonomy = chosen(inputs, "decision_autonomy", "human_override")
    oversight = chosen(inputs, "human_oversight", "none_designed")
    stage = chosen(inputs, "deployment_stage", "idea")
    annex_i = is_yes(inputs, "annex_i_product")
    gpai = is_yes(inputs, "gpai_provider")
    public_sector = is_yes(inputs, "public_sector")
    art63 = is_yes(inputs, "art63_claim")
    significant = chosen(inputs, "significant_effects", "unsure")

    techniques = _clean(selected(inputs, "ai_techniques"))
    pipeline = _clean(selected(inputs, "ai_pipeline"))
    model_source = chosen(inputs, "model_source", "")

    eu_in_scope = "eu" in markets
    br_in_scope = "br" in markets

    # -- 0. How the AI works ----------------------------------------------------
    #
    # Two things are settled here, both conservatively. First, whether the
    # declared techniques infer at all: a product built only on rules written
    # by people may fall outside both instruments' definition of an AI system.
    # The engine never concludes that — it screens the product as if it were
    # in scope and asks a person. Second, whether the technique and pipeline
    # answers imply a transparency duty the transparency question missed: a
    # generative system that was not declared as generating content still
    # carries the marking duty. The duty is applied and the disagreement is
    # escalated, so the reviewer sees both answers.

    rules_only = bool(techniques) and not any(t in INFERRING for t in techniques)
    derived_triggers: List[str] = []
    if ("generative" in techniques or "generation" in pipeline) and "synthetic_content" not in triggers:
        derived_triggers.append("synthetic_content")
    if "interaction" in pipeline and "chat_interaction" not in triggers:
        derived_triggers.append("chat_interaction")
    triggers = triggers + derived_triggers
    trigger_labels = {o.value: o.label for o in TRANSPARENCY_OPTIONS}

    if rules_only:
        r.findings.append(
            Finding(
                code="scope.ai_definition",
                label="Only rules written by people were declared",
                detail="may fall outside the AI-system definition (EU Art. 3(1); PL 2338/2023 Art. 4); "
                       "screened as in scope until a person decides",
            )
        )
    for t in derived_triggers:
        r.findings.append(
            Finding(
                code=f"transparency.{t}",
                label=trigger_labels[t],
                detail="implied by how the AI works, though not selected among the transparency answers",
            )
        )

    # -- 1. Prohibited-practice screen -------------------------------------

    eu_banned = [p for p in practices if PROHIBITED_PRACTICES.get(p, {}).get("eu")]
    br_banned = [p for p in practices if PROHIBITED_PRACTICES.get(p, {}).get("br")]
    conditional = [p for p in practices if PROHIBITED_PRACTICES.get(p, {}).get("conditional")]
    hard_eu = [p for p in eu_banned if p not in conditional]
    hard_br = [p for p in br_banned if p not in conditional]

    for p in practices:
        meta = PROHIBITED_PRACTICES.get(p)
        if not meta:
            continue
        regimes = [j for j, on in (("EU", meta["eu"]), ("BR", meta["br"])) if on]
        r.findings.append(
            Finding(
                code=f"prohibited.{p}",
                label=meta["label"],
                detail=("restricted, narrow exceptions only" if meta["conditional"] else "prohibited")
                + f" ({', '.join(regimes)})",
            )
        )

    # -- 2. High-risk area match -------------------------------------------

    eu_areas = [a for a in areas if PURPOSE_AREAS.get(a, {}).get("annex_iii")]
    br_areas = [a for a in areas if PURPOSE_AREAS.get(a, {}).get("pl_art17")]

    for a in areas:
        meta = PURPOSE_AREAS.get(a)
        if not meta:
            continue
        bits = []
        if meta["annex_iii"]:
            bits.append(f"EU Annex III {meta['annex_iii']}")
        if meta["pl_art17"]:
            bits.append(f"BR Art. 17 item {meta['pl_art17']}")
        r.findings.append(
            Finding(code=f"area.{a}", label=meta["label"], detail="; ".join(bits) or "not a listed area")
        )

    if annex_i:
        r.findings.append(
            Finding(
                code="area.annex_i",
                label="Safety component of a product already covered by EU product-safety legislation",
                detail="high-risk route independent of the Annex III list",
            )
        )

    # -- 3. Tier assignment -------------------------------------------------

    if hard_eu:
        tier_eu = TIER_UNACCEPTABLE
    elif conditional and not (eu_areas or annex_i):
        tier_eu = TIER_RESTRICTED
    elif annex_i or eu_areas:
        tier_eu = TIER_HIGH_EXEMPT if art63 else TIER_HIGH
    elif [t for t in triggers if t]:
        tier_eu = TIER_LIMITED
    else:
        tier_eu = TIER_MINIMAL

    if hard_br:
        tier_br = BR_EXCESSIVE
    elif conditional and not br_areas:
        tier_br = TIER_RESTRICTED
    elif br_areas:
        tier_br = BR_HIGH
    else:
        tier_br = BR_NOT_LISTED

    eu_is_high = tier_eu in (TIER_HIGH, TIER_HIGH_EXEMPT)
    br_is_high = tier_br == BR_HIGH

    r.verdict = {
        "eu_tier": tier_eu,
        "br_tier": tier_br,
        "eu_in_scope": eu_in_scope,
        "br_in_scope": br_in_scope,
        "role": role,
        "art_6_3_exemption_claimed": art63,
        "gpai_obligations": gpai,
    }

    # -- 4. Obligation assembly (table-driven) ------------------------------

    obligations: List[Dict[str, str]] = []

    def add(code: str, jur: str, title: str, section: str, why: str) -> None:
        obligations.append(
            {"code": code, "jurisdiction": jur, "title": title, "section": section, "why": why}
        )

    if eu_is_high:
        if role in ("provider", "both"):
            for code, title in EU_PROVIDER_HIGH_RISK:
                add(code, "EU", title, SECTION_EU_OBLIG, "high-risk + provider role")
        if role in ("deployer", "both"):
            for code, title in EU_DEPLOYER_HIGH_RISK:
                add(code, "EU", title, SECTION_EU_DEPLOYER, "high-risk + deployer role")
            if public_sector or "essential_services" in areas:
                add(
                    "eu.art27",
                    "EU",
                    "Fundamental rights impact assessment before first use",
                    SECTION_EU_DEPLOYER,
                    "deployer is a public body or provides essential services",
                )
        if art63:
            add(
                "eu.art6_3_doc",
                "EU",
                "Document and keep reviewable the assessment that the narrow-task exemption applies",
                SECTION_EU_ANNEX,
                "narrow-task exemption claimed",
            )

    if triggers:
        add("eu.art50", "EU", "Transparency duties: disclose AI interaction, mark synthetic content, "
            "disclose deep fakes, inform people exposed to emotion recognition or biometric categorisation",
            SECTION_EU_ART50, "transparency trigger present")

    if gpai:
        add("eu.gpai", "EU", "General-purpose model duties: technical documentation, information to "
            "downstream providers, copyright policy, training-content summary",
            SECTION_EU_GPAI, "provider of a general-purpose model")

    if br_is_high:
        for code, title in BR_HIGH_RISK:
            add(code, "BR", title, SECTION_BR_HIGH, "listed high-risk area")
        if public_sector:
            add("br.publicity", "BR", "Additional publicity requirements for public-sector deployment",
                SECTION_BR_GOV, "public-sector deployment")
    if br_in_scope or br_areas:
        for code, title in BR_ALL_TIERS:
            section = SECTION_BR_RIGHTS if code == "br.rights" else SECTION_BR_GOV
            add(code, "BR", title, section, "applies to all AI agents")

    r.data["obligations"] = obligations
    r.tables["Obligations assembled from the tier and role (do not add or drop entries)"] = md_table(
        ["Code", "Jurisdiction", "Obligation", "Triggered by"],
        [[o["code"], o["jurisdiction"], o["title"], o["why"]] for o in obligations],
    )

    # -- 5. Open issues ------------------------------------------------------

    if hard_eu or hard_br:
        r.raise_issue(
            "A prohibited practice was declared. Development cannot proceed on this design; "
            "escalate to legal before any further stage.",
            type="prohibited_practice", decision_owner="legal_compliance", blocking=True,
        )
    if conditional:
        r.raise_issue(
            "A restricted practice was declared (narrow legal exceptions only). Confirm the "
            "specific legal basis and authorisation before proceeding.",
            type="prohibited_practice", decision_owner="legal_compliance", blocking=True,
        )
    if art63:
        r.raise_issue(
            "The narrow-task exemption is claimed. It must be documented before market placement "
            "and remains reviewable by authorities — the rule engine cannot confirm it.",
            type="missing_information", decision_owner="legal_compliance", blocking=False,
        )
    if significant == "unsure":
        r.raise_issue(
            "Whether outputs produce legal or similarly significant effects on people is undetermined. "
            "This drives affected-persons' rights and must be settled by a human.",
            type="missing_information", decision_owner="legal_compliance", blocking=False,
        )
    if autonomy in ("fully_automated", "human_confirms") and oversight in ("none_designed", "monitoring_only"):
        r.raise_issue(
            "Automation level and the designed oversight are inconsistent: decisions are effectively "
            "automated while no case-level human intervention exists. Human arbitration required.",
            type="risk_acceptance", decision_owner="product", blocking=False,
        )
    if eu_is_high != br_is_high and eu_in_scope and br_in_scope:
        r.raise_issue(
            "The two jurisdictions classify this system differently. Record which regime governs "
            "the product decision, or apply the stricter one.",
            type="normative_conflict", decision_owner="legal_compliance", blocking=False,
        )
    if rules_only:
        r.raise_issue(
            "Only rules written by people were declared as the system's logic. A system that does "
            "not infer its outputs may fall outside the legal definition of an AI system in both "
            "regimes. The screen treats the product as in scope; a person must decide whether it is.",
            type="missing_information", decision_owner="legal_compliance", blocking=False,
        )
    if derived_triggers:
        r.raise_issue(
            "How the AI works implies transparency duties that were not selected ("
            + "; ".join(trigger_labels[t] for t in derived_triggers)
            + "). The screen applies them; confirm, or correct the answers and re-run.",
            type="missing_information", decision_owner="product", blocking=False,
        )
    if model_source == "none" and any(t in INFERRING for t in techniques):
        r.raise_issue(
            "The answers disagree: no trained model was declared, yet the techniques include "
            "learning or inference. Correct whichever answer is wrong.",
            type="missing_information", decision_owner="product", blocking=False,
        )
    if gpai and model_source == "third_party":
        r.raise_issue(
            "The answers disagree: you declared that you provide a general-purpose AI model, and "
            "also that the model is a third party's, used as-is. The general-purpose model duties "
            "fall on the model's provider; confirm which you are.",
            type="missing_information", decision_owner="legal_compliance", blocking=False,
        )
    if "decision" in pipeline and autonomy in ("human_override", "informational"):
        r.raise_issue(
            "The answers disagree: the AI is declared to make or carry out decisions with no person "
            "in between, but the autonomy answer says a person reviews its output or no decision "
            "follows. Human arbitration required.",
            type="risk_acceptance", decision_owner="product", blocking=False,
        )
    if not markets:
        r.notes.append("No target market was selected; both regimes were screened as informational.")

    # -- 6. Notes the model must respect ------------------------------------

    if data_cats:
        r.notes.append(
            "Sensitive data categories declared: "
            + ", ".join(data_cats)
            + ". These drive the data-governance and non-discrimination obligations downstream."
        )
    if "proxies" in data_cats and "protected_attributes" not in data_cats:
        r.notes.append(
            "Proxies for protected attributes are processed without the attributes themselves — "
            "bias testing cannot rely on the absence of protected attributes in the feature set."
        )
    if model_source in ("adapted", "third_party"):
        r.notes.append(
            "A third party's model is part of the system: its documentation and instructions for "
            "use are evidence the later stages will ask for."
        )
    r.notes.append(f"Declared lifecycle stage: {stage}.")
    if not eu_in_scope:
        r.notes.append("The EU classification is informational — the EU was not selected as a target market.")
    if not br_in_scope:
        r.notes.append("The Brazilian classification is informational — Brazil was not selected as a target market.")

    # -- 7. Pins -------------------------------------------------------------

    r.pins = [
        Pin("eu_ai_act", SECTION_EU_ART5, "prohibited-practice screen"),
        Pin("eu_ai_act", SECTION_EU_ANNEX, "high-risk area determination"),
        Pin("pl_2338_2023", SECTION_BR_EXCESSIVE, "excessive-risk screen"),
        Pin("pl_2338_2023", SECTION_BR_HIGH, "high-risk area determination"),
    ]
    if eu_is_high:
        r.pins += [
            Pin("eu_ai_act", SECTION_EU_OBLIG, "provider obligations"),
            Pin("eu_ai_act", SECTION_EU_DEPLOYER, "deployer obligations"),
        ]
    if br_is_high or br_in_scope:
        r.pins += [
            Pin("pl_2338_2023", SECTION_BR_GOV, "governance obligations"),
            Pin("pl_2338_2023", SECTION_BR_RIGHTS, "rights of affected persons"),
        ]
    if triggers:
        r.pins.append(Pin("eu_ai_act", SECTION_EU_ART50, "transparency duties"))
    if rules_only:
        r.pins += [
            Pin("eu_ai_act", SECTION_EU_SCOPE, "AI-system definition"),
            Pin("pl_2338_2023", SECTION_BR_SCOPE, "AI-system definition"),
        ]
    if gpai:
        r.pins.append(Pin("eu_ai_act", SECTION_EU_GPAI, "general-purpose model duties"))

    # -- 8. Checklist --------------------------------------------------------

    r.checklist = [
        ChecklistItem("prohibited_screen", "State the result of the prohibited-practice screen for both regimes"),
        ChecklistItem("tier_eu", "Justify the EU tier, naming the specific area or article"),
        ChecklistItem("tier_br", "Justify the Brazilian tier, naming the specific area"),
        ChecklistItem("obligations", "Explain every assembled obligation in the team's own context"),
        ChecklistItem("oversight", "Assess whether the declared oversight design meets the obligations"),
        ChecklistItem("data_governance", "Address the declared data categories and bias exposure"),
        ChecklistItem("next_steps", "Give concrete next steps for this lifecycle stage"),
        ChecklistItem("open_issues", "Carry forward every open issue raised here, plus any you add"),
    ]
    if rules_only:
        r.checklist.insert(0, ChecklistItem(
            "ai_scope", "Say whether the product meets the AI-system definition, given the declared techniques"))

    # -- 9. Retrieval facets -------------------------------------------------

    r.query_terms = (
        [PURPOSE_AREAS[a]["label"] for a in areas if a in PURPOSE_AREAS]
        + [PROHIBITED_PRACTICES[p]["label"] for p in practices if p in PROHIBITED_PRACTICES]
        + [tier_eu, tier_br, f"role {role}"]
        + data_cats
        + (["definition of an AI system, inference, rules defined by natural persons"] if rules_only else [])
        + [trigger_labels[t] for t in derived_triggers]
    )

    r.data.update(
        {
            "role": role,
            "markets": markets,
            "purpose_areas": areas,
            "prohibited_practices": practices,
            "transparency_triggers": triggers,
            "data_categories": data_cats,
            "decision_autonomy": autonomy,
            "human_oversight": oversight,
            "deployment_stage": stage,
            "significant_effects": significant,
            "public_sector": public_sector,
            "annex_i_product": annex_i,
            "gpai_provider": gpai,
            "art_6_3_claimed": art63,
            "art_6_3_reason": text_of(inputs, "art63_reason"),
            "ai_techniques": techniques,
            "ai_pipeline": pipeline,
            "model_source": model_source,
            "ai_definition_uncertain": rules_only,
            "derived_transparency_triggers": derived_triggers,
            "eu_is_high_risk": eu_is_high,
            "br_is_high_risk": br_is_high,
        }
    )
    return r
