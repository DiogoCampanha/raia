"""
raia.contract.vocab
===================

The closed vocabularies every RAIA record is written in.

A standard output is only as consistent as the words it allows. Free text is
where two runs of the same project drift apart: one calls a harm "serious",
the next "notable"; one assigns an action to "the team", the next to "legal".
Each list here is closed, and each one comes from the normative sources the
RAIA project is built on — nothing is borrowed from anywhere else:

* the seven Responsible AI principles the project adopts;
* NIST AI RMF 1.0 — the four functions and their categories, impact
  characterised by likelihood and magnitude, risk responses, the lifecycle
  stages and the roles accountability is documented against;
* IEEE 7000-2021 — direct and indirect stakeholders, and the four ways an
  ethical value requirement can be verified;
* Microsoft Responsible AI Standard v2 — its goals, and the requirement that
  each one names an owner and a review cadence;
* ECCOLA — its 21 cards;
* EU AI Act and PL 2338/2023 — risk tiers, and the criteria for how severe
  harm to people is (scale, vulnerability, discriminatory impact,
  irreversibility, significant effects on persons).

Where a source names a concept but not a scale (NIST asks for likelihood and
magnitude without fixing levels), the levels below are RAIA's
operationalisation, and each level is anchored to the source's own wording so
two reviewers can place the same harm on the same step.
"""

from typing import Dict, List, Tuple

from ..rationale.principles import PRINCIPLES

SCHEMA_VERSION = "raia-record/1.1"

# -- The seven principles -----------------------------------------------------

PRINCIPLE_KEYS: Tuple[str, ...] = tuple(p.key for p in PRINCIPLES)
PRINCIPLE_NAMES: Dict[str, str] = {p.key: p.name for p in PRINCIPLES}

# -- NIST AI RMF: functions and categories -----------------------------------

NIST_FUNCTIONS: Tuple[str, ...] = ("GOVERN", "MAP", "MEASURE", "MANAGE")

NIST_CATEGORIES: Dict[str, str] = {
    "GOVERN 1": "Policies, processes and legal requirements are in place and managed",
    "GOVERN 2": "Accountability structures, roles and responsibilities are documented",
    "GOVERN 3": "Diverse perspectives inform decision-making",
    "GOVERN 4": "A culture that communicates risks and impacts",
    "GOVERN 5": "Engagement with AI actors and external stakeholders (feedback, appeal, redress)",
    "GOVERN 6": "Third-party risks are addressed",
    "MAP 1": "Context, intended purpose and potential impacts are documented",
    "MAP 2": "The AI system is categorised",
    "MAP 3": "Capabilities, targeted usage, benefits and costs are understood",
    "MAP 4": "Risks and benefits are mapped for all components",
    "MAP 5": "Impacts are characterised by likelihood and magnitude",
    "MEASURE 1": "Methods and metrics are identified, applied and documented",
    "MEASURE 2": "Trustworthy characteristics, including fairness and representativeness, are evaluated",
    "MEASURE 3": "Identified risks are tracked over time, including in production",
    "MEASURE 4": "Feedback about measurement efficacy is gathered",
    "MANAGE 1": "Risks are prioritised and responded to",
    "MANAGE 2": "Benefits are maximised and negative impacts minimised, with deactivation criteria",
    "MANAGE 3": "Third-party risks are managed and monitored",
    "MANAGE 4": "Treatments, response, recovery and communication plans are documented and monitored",
}

# -- NIST AI RMF MAP 5: impact magnitude and likelihood -----------------------
# Levels are ordered from least to most. Each anchor uses the harm criteria the
# legal texts themselves apply to AI systems, so "severe" means the same thing
# on every project.

MAGNITUDE: Tuple[str, ...] = ("negligible", "limited", "significant", "severe")
MAGNITUDE_ANCHORS: Dict[str, str] = {
    "negligible": "No effect on people's rights, opportunities, safety or wellbeing; an "
                  "inconvenience that is noticed and corrected in normal operation.",
    "limited": "A reversible effect on a small number of people who can notice it and obtain "
               "a correction without help; no legal or similarly significant effect.",
    "significant": "An effect on people's access to opportunities, services or fair treatment, "
                   "or on their privacy — reversible, but only with effort, or affecting many "
                   "people or a group protected against discrimination.",
    "severe": "A legal or similarly significant effect on persons, harm to fundamental rights, "
              "health or safety, or harm that is hard to reverse, falls on vulnerable groups, or "
              "operates at scale — the criteria the legal texts use to call a system high-risk.",
}

LIKELIHOOD: Tuple[str, ...] = ("rare", "possible", "likely", "observed")
LIKELIHOOD_ANCHORS: Dict[str, str] = {
    "rare": "Requires an unusual combination of conditions not expected in the documented "
            "context of use.",
    "possible": "Could occur in the documented context of use, but nothing in the inputs or "
                "evidence suggests it is currently happening.",
    "likely": "Expected to occur in the documented context of use unless a control is in place, "
              "and no such control is evidenced.",
    "observed": "Already shown by measured or documented evidence (telemetry, an audit result, "
                "an incident).",
}

# -- NIST AI RMF MANAGE 1: risk responses -------------------------------------

RESPONSES: Tuple[str, ...] = ("mitigate", "transfer", "avoid", "accept")
RESPONSE_ANCHORS: Dict[str, str] = {
    "mitigate": "Reduce the likelihood or magnitude with a control the team builds or operates.",
    "transfer": "Move the risk to a party better placed to bear it (a provider, a deployer, an "
                "insurer), with that transfer documented.",
    "avoid": "Remove the feature, use or data that creates the risk.",
    "accept": "Keep the risk as it is. Only a person can accept a risk: an accept response "
              "always opens an issue for human arbitration.",
}

# -- NIST AI RMF lifecycle stages ---------------------------------------------

LIFECYCLE_STAGES: Tuple[str, ...] = (
    "plan_and_design", "collect_and_process_data", "build_and_use_model",
    "verify_and_validate", "deploy_and_use", "operate_and_monitor",
)
LIFECYCLE_LABELS: Dict[str, str] = {
    "plan_and_design": "Plan and design",
    "collect_and_process_data": "Collect and process data",
    "build_and_use_model": "Build and use model",
    "verify_and_validate": "Verify and validate",
    "deploy_and_use": "Deploy and use",
    "operate_and_monitor": "Operate and monitor",
}

# -- Owner roles (NIST GOVERN 2) and review cadence (Microsoft RAI Standard v2) --
# The roles are the audiences of the RAIA layers: product leadership and legal
# at conception, development teams in sprints, operations after deployment.

OWNER_ROLES: Tuple[str, ...] = (
    "product", "engineering", "data_science", "legal_compliance", "operations", "leadership",
)
OWNER_LABELS: Dict[str, str] = {
    "product": "Product management",
    "engineering": "Engineering",
    "data_science": "Data science / ML",
    "legal_compliance": "Legal and compliance",
    "operations": "Operations / MLOps",
    "leadership": "Leadership",
}

REVIEW_CADENCES: Tuple[str, ...] = ("once", "every_sprint", "every_release", "continuous")
CADENCE_LABELS: Dict[str, str] = {
    "once": "once", "every_sprint": "every sprint", "every_release": "every release",
    "continuous": "continuously",
}

# -- IEEE 7000: verification of an ethical value requirement ------------------

VERIFICATION_METHODS: Tuple[str, ...] = ("test", "audit", "measurement", "inspection")

STAKEHOLDER_KINDS: Tuple[str, ...] = ("direct", "indirect")

# -- Microsoft RAI Standard v2 goals ------------------------------------------

MS_GOALS: Dict[str, str] = {
    "A1": "Impact assessment",
    "A2": "Oversight of significant adverse impacts",
    "A3": "Fit for purpose",
    "A4": "Data governance and management",
    "A5": "Human oversight and control",
    "T1": "System intelligibility for decision-making",
    "T2": "Communication to stakeholders",
    "T3": "Disclosure of AI interaction",
    "F1": "Quality of service",
    "F2": "Allocation of resources and opportunities",
    "F3": "Minimization of stereotyping, demeaning, and erasing outputs",
    "RS1": "Reliability and safety guidance",
    "RS2": "Failures and remediations",
    "RS3": "Ongoing monitoring, feedback, and evaluation",
    "PS1": "Privacy",
    "PS2": "Security",
    "I1": "Inclusiveness",
}

# -- ECCOLA cards -------------------------------------------------------------

ECCOLA_CARDS: Dict[str, str] = {
    "#0": "Stakeholder Analysis", "#1": "Types of Transparency", "#2": "Regulation",
    "#3": "Traceability", "#4": "Communication", "#5": "Explainability",
    "#6": "Privacy and Data", "#7": "Data Quality", "#8": "Access to Data",
    "#9": "Human Agency", "#10": "Human Oversight", "#11": "System Reliability",
    "#12": "System Security", "#13": "System Safety", "#14": "Accessibility",
    "#15": "Stakeholder Participation", "#16": "Non-Discrimination / Fairness",
    "#17": "Societal and Environmental Impact", "#18": "Auditability",
    "#19": "Ability to Redress", "#20": "Accountability",
}

# -- Auditor verdicts (evidence discipline) -----------------------------------
# Ordered from strongest to weakest claim. The model may move an item down this
# list from what code computed, never up.

AUDIT_VERDICTS: Tuple[str, ...] = ("satisfied", "partially_satisfied", "at_risk", "not_verified")
AUDIT_VERDICT_LABELS: Dict[str, str] = {
    "satisfied": "Satisfied", "partially_satisfied": "Partially satisfied",
    "at_risk": "At risk", "not_verified": "Not verified",
}

# -- Open issues ----------------------------------------------------------------

ISSUE_TYPES: Tuple[str, ...] = (
    "normative_conflict", "engine_disagreement", "value_tradeoff",
    "not_grounded", "missing_information", "risk_acceptance", "prohibited_practice",
)
ISSUE_TYPE_LABELS: Dict[str, str] = {
    "normative_conflict": "Conflict between norms of the same authority level",
    "engine_disagreement": "The agent disagrees with the rule engine",
    "value_tradeoff": "Values trade off against each other",
    "not_grounded": "Important claim not grounded in the retrieved excerpts",
    "missing_information": "Information only a person can supply",
    "risk_acceptance": "A risk is proposed for acceptance",
    "prohibited_practice": "A prohibited or excessive-risk practice was declared",
}

# -- Priority and overall status ----------------------------------------------

PRIORITIES: Tuple[str, ...] = ("low", "medium", "high", "critical")
PRIORITY_LABELS: Dict[str, str] = {"low": "Low", "medium": "Medium", "high": "High", "critical": "Critical"}
OVERALL_STATUSES: Tuple[str, ...] = ("on_track", "needs_attention", "blocked")
STATUS_LABELS: Dict[str, str] = {"on_track": "On track", "needs_attention": "Needs attention",
                                 "blocked": "Blocked"}

#: How the action plan is read at a glance: what to do now, what to plan, what
#: to keep an eye on. Grouping follows the computed priority only.
ACTION_GROUPS: Tuple[Tuple[str, str, Tuple[str, ...], str], ...] = (
    ("now", "Do now", ("critical", "high"), "Critical and high priority"),
    ("plan", "Plan", ("medium",), "Medium priority: schedule it"),
    ("track", "Track", ("low",), "Low priority: keep an eye on it"),
)

AUTHORITY_LEVELS: Tuple[str, ...] = ("legal", "standard", "advisory")


def rank(scale: Tuple[str, ...], value: str) -> int:
    """Position of a value on an ordered scale (-1 when absent)."""
    try:
        return scale.index(value)
    except ValueError:
        return -1


def nist_function_of(category: str) -> str:
    return (category or "").split(" ")[0].upper()


def glossary() -> List[Tuple[str, str, str]]:
    """(vocabulary, value, definition) rows, for documentation and the prompt."""
    rows: List[Tuple[str, str, str]] = []
    rows += [("magnitude", k, v) for k, v in MAGNITUDE_ANCHORS.items()]
    rows += [("likelihood", k, v) for k, v in LIKELIHOOD_ANCHORS.items()]
    rows += [("response", k, v) for k, v in RESPONSE_ANCHORS.items()]
    return rows
