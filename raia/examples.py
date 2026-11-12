"""
raia.examples
=============

The project's walkthrough scenarios, one per example case.

Each case is kept in one place, and filled into the *structured* fields as well
as the prose ones, because the structured answers are what the decision
procedures read. An example that only filled in the text boxes would
demonstrate the old behaviour — a model inferring everything from prose — which
is exactly what the walkthrough is meant to show has changed.

Three cases, chosen so that each takes a path through the rules the others never touch:

* **Resume screening** (``resume_screening``, the default) — deliberately a hard
  one: an employment system is high-risk under both regimes, it is fully
  automated with no oversight designed, and it processes proxies for protected
  attributes. Every stage has something real to say, and the classification is
  blocked in its current form.
* **Customer-support assistant** (``support_assistant``) — a retailer deploys a
  third-party language model to answer customers and propose refunds that a
  person confirms. Limited risk (transparency duties) in the EU, outside the
  listed high-risk areas in Brazil: it takes the deployer, third-party-model and
  transparency paths the first case never touches, with nothing blocking.

* **B2B marketplace** (``b2b_marketplace``) — an ordering app in which models
  recommend products to small shops and choose the promotions each shop sees.
  Outside every listed high-risk area, live in production, sold in Brazil and
  other markets but not in the EU, fully automated with nobody reviewing an
  individual offer. It is the case most commercial products resemble: the legal
  tier says "minimal" and "not listed", nothing blocks, and the work that
  remains comes from the principles (who gets which discount, and whether a shop
  can know or ask why) rather than from a list of obligations.

``EXAMPLES`` is the default case's answers per agent, for callers that only
need one scenario.
"""

from typing import Any, Dict

RESUME_SCREENING: Dict[str, Dict[str, Any]] = {
    "risk_classifier": {
        "product_brief": (
            "TalentFlow is a resume-screening platform. A machine-learning model ranks and "
            "filters job applications, producing a shortlist for recruiters. The AI component "
            "scores each resume against the job description and against historical hiring data."
        ),
        "ai_output": (
            "A fit score for every application and a ranked shortlist per vacancy. Applications "
            "below the cut-off are rejected automatically and never reach a recruiter."
        ),
        "intended_use": (
            "Used by corporate HR departments in Brazil and the EU to screen high-volume "
            "vacancies. Recruiters see the ranked shortlist and decide whom to interview. "
            "Candidates below the cut-off are not shown to a recruiter at all."
        ),
        "target_users": (
            "Users: recruiters and HR managers. Affected people: all job applicants, including "
            "members of protected groups; candidates filtered out never interact with the "
            "system directly and are not told a model was involved."
        ),
        "out_of_scope": (
            "Not for internal promotions, performance reviews or dismissals."
        ),
        "ai_techniques": ["machine_learning"],
        "ai_pipeline": ["input_processing", "scoring", "decision"],
        "model_source": "in_house",
        "role": "provider",
        "markets": ["eu", "br"],
        "public_sector": "no",
        "gpai_provider": "no",
        "purpose_areas": ["employment"],
        "annex_i_product": "no",
        "prohibited_practices": ["none"],
        "transparency_triggers": ["none"],
        "decision_autonomy": "fully_automated",
        "significant_effects": "yes",
        "human_oversight": "none_designed",
        "data_categories": ["protected_attributes", "proxies"],
        "deployment_stage": "development",
        "profiling": "yes",
        "art63_claim": "no",
    },
    "requirements_reviewer": {
        "requirements": (
            "R1. The system shall rank applications by predicted job fit.\n"
            "R2. The system shall process at least 10,000 resumes per hour.\n"
            "R3. Recruiters shall be able to export the shortlist to CSV.\n"
            "R4. The system shall integrate with the corporate SSO.\n"
            "R5. Model retraining shall occur monthly on new hiring data."
        ),
        "requirement_format": "numbered",
        "existing_controls": ["logging"],
        "constraints": (
            "The first release is committed to a customer for the end of the quarter. "
            "The data team has no capacity for a new labelling effort this cycle."
        ),
        "values_at_stake": ["fairness", "transparency"],
        "stakeholders": ["users", "subjects"],
    },
    "story_refiner": {
        "user_stories": [
            {"id": "S1", "title": "Ranked shortlist",
             "description": "As a recruiter, I want to see the top-20 ranked candidates for a vacancy so "
                            "that I can build an interview shortlist quickly.",
             "acceptance_criteria": "Shows the 20 highest-scoring candidates, ordered by score\n"
                                    "The list loads in under 2 seconds for a vacancy with 5,000 applications",
             "capabilities": ["scoring", "automation"]},
            {"id": "S2", "title": "Minimum-qualification filter",
             "description": "As a recruiter, I want to filter candidates by minimum qualification criteria "
                            "so that unqualified applications are excluded automatically.",
             "acceptance_criteria": "Applications that miss any minimum criterion are rejected automatically, "
                                    "with no human review\nThe filter criteria are configurable per vacancy",
             "capabilities": ["automation", "scoring"]},
            {"id": "S3", "title": "Screening throughput dashboard",
             "description": "As an HR manager, I want a dashboard of screening throughput so that I can "
                            "report hiring KPIs.",
             "acceptance_criteria": "Shows applications screened per week and per vacancy",
             "capabilities": ["analytics"]},
        ],
        "sprint_goal": "Ship ranking v2 and the qualification filter",
        "definition_of_done": (
            "Merged behind a feature flag, unit and integration tests green, evaluation report "
            "attached to the ticket, documentation updated."
        ),
    },
    "story_generate": {
        "scope": "short",
        "definition_of_done": (
            "Merged behind a feature flag, unit and integration tests green, evaluation report "
            "attached to the ticket, documentation updated."
        ),
    },
    "auditor": {
        "sprint_id": "Sprint 7",
        "sprint_outcomes": (
            "Delivered the ranking API v2 (S1) with a disaggregated evaluation report — "
            "demographic parity difference measured at 0.08 across gender and 0.12 across race "
            "groups on validation data. The qualification filter (S2) shipped without "
            "disaggregated testing. Audit-log storage for ranking decisions was enabled."
        ),
        "evidence_types": ["test_results", "disaggregated", "audit_log"],
        "planned_epics": (
            "Next: explanation UI for recruiters (why a candidate was ranked); "
            "candidate-facing contestation form; retraining pipeline automation."
        ),
    },
}


SUPPORT_ASSISTANT: Dict[str, Dict[str, Any]] = {
    "risk_classifier": {
        "product_brief": (
            "HelpDesk Assist is the customer-support assistant of an online retailer. A third-party "
            "large language model, used through its vendor's API, answers customers' questions about "
            "orders, deliveries and returns in a chat window, and drafts replies that support agents "
            "can send."
        ),
        "ai_output": (
            "Chat answers to customers, draft replies for support agents, and a refund proposal for a "
            "late or damaged order. A support agent confirms or changes every refund before it is "
            "paid; nothing is refunded automatically."
        ),
        "intended_use": (
            "Used on the retailer's website and app in Brazil and the EU, in Portuguese and English, "
            "for questions about the customer's own orders. Hands the conversation to a person when "
            "the customer asks or when the assistant is unsure."
        ),
        "target_users": (
            "Users: customers of the store and the support team. Affected people: customers whose "
            "questions and refund requests the assistant handles, including people with low digital "
            "literacy or who write in a second language."
        ),
        "out_of_scope": (
            "Not for credit, payment disputes, account closures or any decision about a customer's "
            "eligibility for a service."
        ),
        "ai_techniques": ["generative"],
        "ai_pipeline": ["interaction", "generation"],
        "model_source": "third_party",
        "role": "deployer",
        "markets": ["eu", "br"],
        "public_sector": "no",
        "gpai_provider": "no",
        "purpose_areas": ["none"],
        "annex_i_product": "no",
        "prohibited_practices": ["none"],
        "transparency_triggers": ["chat_interaction", "synthetic_content"],
        "decision_autonomy": "human_override",
        "significant_effects": "no",
        "human_oversight": "override_possible",
        "data_categories": ["communications", "financial"],
        "deployment_stage": "pilot",
        "profiling": "no",
        "art63_claim": "no",
    },
    "requirements_reviewer": {
        "requirements": (
            "R1. The assistant shall answer at least 80% of order-status questions without a hand-off.\n"
            "R2. The assistant shall hand the conversation to a person when the customer asks.\n"
            "R3. Every conversation shall be stored for 90 days for quality review.\n"
            "R4. The assistant shall support Portuguese and English.\n"
            "R5. The assistant shall propose a refund for a late order, for a support agent to confirm."
        ),
        "requirement_format": "numbered",
        "existing_controls": ["logging", "instructions"],
        "constraints": (
            "The model is a vendor's; there is no budget to fine-tune it this year. The pilot runs "
            "for one quarter in two markets before any wider launch."
        ),
        "values_at_stake": ["transparency", "privacy"],
        "stakeholders": ["users", "subjects", "vulnerable"],
    },
    "story_refiner": {
        "user_stories": [
            {"id": "HD-1", "title": "Say it is an AI",
             "description": "As a customer, I want to know I am talking to an AI assistant so that I can "
                            "decide whether to ask for a person.",
             "acceptance_criteria": "The chat opens with a greeting from the assistant\n"
                                    "The greeting is shown in the customer's language",
             "capabilities": ["generation"]},
            {"id": "HD-2", "title": "Hand off to a person",
             "description": "As a customer, I want to reach a person when the assistant cannot help so that "
                            "my problem is solved.",
             "acceptance_criteria": "A \"Talk to a person\" option is available in the chat\n"
                                    "The support agent sees the conversation so far",
             "capabilities": ["automation", "integration"]},
            {"id": "HD-3", "title": "Refund proposal for a late order",
             "description": "As a support agent, I want the assistant to propose a refund for a late order "
                            "so that I can resolve the case quickly.",
             "acceptance_criteria": "Refunds below R$ 50 are approved automatically without agent review\n"
                                    "The proposal shows the order, the delay and the amount",
             "capabilities": ["automation", "scoring"]},
        ],
        "sprint_goal": "Launch the pilot chat with disclosure and hand-off",
        "definition_of_done": (
            "Merged behind a feature flag, tests green in Portuguese and English, conversation logging "
            "verified, support team briefed."
        ),
    },
    "story_generate": {
        "scope": "short",
        "definition_of_done": (
            "Merged behind a feature flag, tests green in Portuguese and English, conversation logging "
            "verified, support team briefed."
        ),
    },
    "auditor": {
        "sprint_id": "Pilot sprint 2",
        "sprint_outcomes": (
            "Delivered the AI disclosure in the chat greeting (HD-1), tested in Portuguese and English "
            "with screenshots attached to the ticket. The hand-off to a person (HD-2) shipped and was "
            "tested in English only. Refund proposals (HD-3) are in code review. Conversation logging "
            "is enabled with 90-day retention."
        ),
        "evidence_types": ["test_results", "code_review", "audit_log"],
        "planned_epics": (
            "Next: hand-off tests in Portuguese; refund proposals behind a person's confirmation; a "
            "customer-facing notice on how conversations are stored."
        ),
    },
}

B2B_MARKETPLACE: Dict[str, Dict[str, Any]] = {
    "risk_classifier": {
        "product_brief": (
            "ShelfLink is an ordering app that small retailers (corner shops, bars, restaurants) use "
            "to buy stock from distributors. Machine-learning models recommend products to each shop "
            "and choose which promotions and discount levels each shop is shown."
        ),
        "ai_output": (
            "A ranked list of recommended products on each shop's home screen, and the promotions and "
            "discount level offered to that shop. Both are shown automatically; no person reviews what "
            "an individual shop is offered."
        ),
        "intended_use": (
            "Used in Brazil and other Latin American markets by shop owners and their staff whenever "
            "they place an order: about 200,000 shops a month. Commercial teams set campaign budgets "
            "and rules; the models decide which shop sees which offer."
        ),
        "target_users": (
            "Users: shop owners and staff who order through the app. Affected: the same shops, many of "
            "them sole traders, whose offers differ from their neighbours'; shops in lower-income areas, "
            "which never see an offer the model does not select for them; and the distributors and "
            "brands whose products are ranked higher or lower."
        ),
        "out_of_scope": (
            "Not for setting credit limits or payment terms, not for refusing or delaying service to a "
            "shop, and not for assessing sales staff."
        ),
        "ai_techniques": ["machine_learning"],
        "ai_pipeline": ["scoring", "decision"],
        "model_source": "in_house",
        "role": "both",
        "markets": ["br", "other"],
        "public_sector": "no",
        "gpai_provider": "no",
        "purpose_areas": ["none"],
        "annex_i_product": "no",
        "prohibited_practices": ["none"],
        "transparency_triggers": ["none"],
        "decision_autonomy": "fully_automated",
        "significant_effects": "unsure",
        "human_oversight": "monitoring_only",
        "data_categories": ["location", "proxies"],
        "deployment_stage": "production",
        "profiling": "yes",
        "art63_claim": "no",
    },
    "requirements_reviewer": {
        "requirements": (
            "R1. The app shall show each shop a ranked list of recommended products on its home screen.\n"
            "R2. The promotion engine shall select, for each shop, the offers most likely to increase its order value.\n"
            "R3. Recommendations and offers shall refresh at least once a day.\n"
            "R4. Commercial teams shall be able to set a budget and eligibility rules per campaign.\n"
            "R5. Conversion and discount spend shall be reported per campaign and per region."
        ),
        "requirement_format": "numbered",
        "existing_controls": ["logging", "governance"],
        "constraints": (
            "Campaigns are agreed with brand partners a quarter ahead. The data team can run one new "
            "offline analysis per sprint."
        ),
        "values_at_stake": ["fairness", "transparency"],
        "stakeholders": ["users", "subjects", "vulnerable"],
    },
    "story_refiner": {
        "user_stories": [
            {"id": "SL-1", "title": "Recommended for your shop",
             "description": "As a shop owner, I want to see products recommended for my shop so that I can "
                            "place my order faster.",
             "acceptance_criteria": "The home screen shows 12 recommended products\n"
                                    "The list refreshes once a day",
             "capabilities": ["personalization", "scoring"]},
            {"id": "SL-2", "title": "Personalised discount",
             "description": "As a commercial manager, I want each shop to receive the discount level most "
                            "likely to grow its order so that the campaign budget is spent where it converts.",
             "acceptance_criteria": "The discount level for each shop is set by the model, with no manual review\n"
                                    "Shops are not told that offers differ from shop to shop",
             "capabilities": ["personalization", "automation", "scoring"]},
            {"id": "SL-3", "title": "Campaign results dashboard",
             "description": "As a commercial manager, I want conversion and spend per campaign so that I can "
                            "report results to brand partners.",
             "acceptance_criteria": "Shows conversion and discount spend per campaign and per region",
             "capabilities": ["analytics"]},
        ],
        "sprint_goal": "Launch personalised discounts for the quarter's campaigns",
        "definition_of_done": (
            "Merged behind a feature flag, tests green, offline evaluation attached to the ticket, "
            "campaign owners briefed."
        ),
    },
    "story_generate": {
        "scope": "short",
        "definition_of_done": (
            "Merged behind a feature flag, tests green, offline evaluation attached to the ticket, "
            "campaign owners briefed."
        ),
    },
    "auditor": {
        "sprint_id": "Sprint 14",
        "sprint_outcomes": (
            "Delivered the recommendation list (SL-1) with an offline evaluation and a report of discount "
            "levels by region and by shop size attached to the ticket: the average discount was 9% in the "
            "highest-income regions and 6% in the lowest. Personalised discounts (SL-2) shipped to 10% of "
            "shops without the planned check of discount gaps between regions. Logging of which offer "
            "each shop was shown, and why, was enabled."
        ),
        "evidence_types": ["test_results", "disaggregated", "audit_log"],
        "planned_epics": (
            "Next: a notice in the app that offers are personalised; a way for a shop to ask why it did "
            "not receive an offer; a monthly review of discount gaps between regions."
        ),
    },
}

#: The example cases: what each is called, what it shows, and its answers per agent.
#: Listed from the lightest legal tier to the heaviest, which is also the order
#: Home offers them in.
CASES: Dict[str, Dict[str, Any]] = {
    "b2b_marketplace": {
        "title": "B2B marketplace",
        "project_name": "Demo — B2B marketplace",
        "summary": "Models recommend products and choose the promotions each small shop sees in an ordering app.",
        "shows": "Outside the high-risk lists: what is left to manage when the legal tier says minimal.",
        "agents": B2B_MARKETPLACE,
    },
    "support_assistant": {
        "title": "Customer-support assistant",
        "project_name": "Demo — customer-support assistant",
        "summary": "A third-party language model answers customers and proposes refunds a person confirms.",
        "shows": "Limited risk: transparency duties, a deployer's obligations, and a clean path to sprints.",
        "agents": SUPPORT_ASSISTANT,
    },
    "resume_screening": {
        "title": "Resume screening",
        "project_name": "Demo — resume screening",
        "summary": "A model ranks job applications and rejects the lowest automatically.",
        "shows": "High risk and blocked: see what stops a product, and what unblocks it.",
        "agents": RESUME_SCREENING,
    },
}

DEFAULT_CASE = "resume_screening"

#: Saved beside a demo project's answers: which case filled them, so the form
#: offers the same case first when a person loads the example again.
EXAMPLE_KEY = "_example_case"

#: The default case's answers per agent.
EXAMPLES: Dict[str, Dict[str, Any]] = CASES[DEFAULT_CASE]["agents"]


def example_for(case: str, agent_key: str) -> Dict[str, Any]:
    """One agent's example answers in one case (empty when there are none)."""
    return dict((CASES.get(case) or CASES[DEFAULT_CASE])["agents"].get(agent_key) or {})
