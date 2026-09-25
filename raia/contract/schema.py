"""
raia.contract.schema
====================

The RAIA record: one shared core every agent fills, plus one extension per
agent shaped by the normative source that agent operationalises.

The model does not write a document. It returns one JSON object that must
validate against the schema of its agent; code then computes what must not
vary between runs (ids, risk level, priority, blocking flags, carried-forward
issues), and renders the Markdown a person reads. The JSON is the record; the
Markdown is a view of it.

Field lengths are capped. RAIA is a work tool: a record is read by people
who will act on it between other work, so every free-text field is short and
leads with its conclusion. A record that does not fit one reply is also a
record nobody reads at the approval gate, and a reply cut off at the token
limit cannot be parsed at all — so the caps are part of the contract, not a
formatting preference.

Fields marked ``computed`` are filled by code. They are removed from the schema
the model is shown, and anything the model puts in them is overwritten.

Shared core — what every stage answers, on every project:

==========================  ==================================================
Field                       Grounding
==========================  ==================================================
headline, summary,          human oversight: the reviewer reads the bottom line
overall_status              first
declared_verdict,           the reconciliation channel: agreement with the rule
agrees_with_rule_engine     engine is declared, never implied
findings[]                  NIST AI RMF MAP 5 (likelihood × magnitude), one of
                            the seven principles, a NIST AI RMF category
actions[]                   NIST AI RMF MANAGE 1 (mitigate/transfer/avoid/accept),
                            lifecycle stage; Microsoft RAI Standard v2 (owner,
                            review cadence, evidence artifact); IEEE 7000
                            (test/audit/measurement/inspection)
open_issues[]               authority precedence and same-level conflicts;
                            human arbitration
not_grounded[]              grounded recommendations: what the excerpts do not support
coverage[]                  declared completeness
==========================  ==================================================
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Literal, Optional, Type

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..rationale.types import VALID_STATUSES
from . import vocab as V

Principle = Literal[V.PRINCIPLE_KEYS]  # type: ignore[valid-type]
NistCategory = Literal[tuple(V.NIST_CATEGORIES)]  # type: ignore[valid-type]
Magnitude = Literal[V.MAGNITUDE]  # type: ignore[valid-type]
Likelihood = Literal[V.LIKELIHOOD]  # type: ignore[valid-type]
Response = Literal[V.RESPONSES]  # type: ignore[valid-type]
Lifecycle = Literal[V.LIFECYCLE_STAGES]  # type: ignore[valid-type]
Owner = Literal[V.OWNER_ROLES]  # type: ignore[valid-type]
Cadence = Literal[V.REVIEW_CADENCES]  # type: ignore[valid-type]
Verification = Literal[V.VERIFICATION_METHODS]  # type: ignore[valid-type]
IssueType = Literal[V.ISSUE_TYPES]  # type: ignore[valid-type]
Status = Literal[V.OVERALL_STATUSES]  # type: ignore[valid-type]
CoverageStatus = Literal[VALID_STATUSES]  # type: ignore[valid-type]
MsGoal = Literal[tuple(V.MS_GOALS)]  # type: ignore[valid-type]
Card = Literal[tuple(V.ECCOLA_CARDS)]  # type: ignore[valid-type]
AuditVerdict = Literal[V.AUDIT_VERDICTS]  # type: ignore[valid-type]
Severity = Literal["low", "medium", "high"]
StakeholderKind = Literal[V.STAKEHOLDER_KINDS]  # type: ignore[valid-type]


def computed(default: Any = None, **kw: Any) -> Any:
    """A field filled by code, hidden from the schema the model sees."""
    return Field(default=default, json_schema_extra={"computed": True}, **kw)


def asked(default: Any = "", **kw: Any) -> Any:
    """A field the model must fill, that older records may lack.

    It is required in the schema the model is shown, and optional when a
    stored record is read back, so records written before the field existed
    still load, render and approve.
    """
    return Field(default=default, json_schema_extra={"model_required": True}, **kw)


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


Citations = Field(default_factory=list, description=(
    "Citation tags copied exactly from the retrieved excerpts, e.g. "
    "\"[Source: ... | authority: legal]\". Never invent one."))


# ---------------------------------------------------------------------------
# Shared core
# ---------------------------------------------------------------------------


class Finding(_Model):
    id: str = Field(description="Local identifier such as F1. Code assigns the final id.")
    title: str = Field(max_length=120, description="The risk or gap in a few words (at most 12).")
    statement: str = Field(max_length=400, description="One or two sentences: what could go wrong or is missing, for whom, here.")
    principle: Principle = Field(description="The Responsible AI principle at stake.")
    nist_category: NistCategory = Field(description="The NIST AI RMF category this finding belongs to.")
    magnitude: Magnitude = Field(description="Impact magnitude, using the anchored definitions.")
    likelihood: Likelihood = Field(description="Likelihood, using the anchored definitions.")
    placement_rationale: str = Field(max_length=250, description="One sentence: why this magnitude and likelihood.")
    stakeholders: List[str] = Field(default_factory=list, description="Who is affected, direct and indirect.")
    citations: List[str] = Citations
    links: List[str] = Field(default_factory=list, description=(
        "Identifiers from the computed block this finding concerns (obligation codes, EVR ids, "
        "story ids, card ids, audit item ids, telemetry windows)."))
    risk_level: Optional[str] = computed()
    priority: Optional[str] = computed()
    blocking: Optional[bool] = computed()
    priority_basis: Optional[str] = computed()


class Action(_Model):
    id: str = Field(description="Local identifier such as A1. Code assigns the final id.")
    finding_ids: List[str] = Field(description="The finding ids (local) this action responds to.")
    action: str = Field(max_length=250, description="One sentence starting with a verb: what is done, specific and checkable.")
    response: Response = Field(description="Risk response (NIST AI RMF MANAGE 1).")
    owner_role: Owner = Field(description="The accountable role.")
    lifecycle_stage: Lifecycle = Field(description="Lifecycle stage in which it must be done.")
    review_cadence: Cadence = Field(description="How often it is reviewed.")
    verification_method: Verification = Field(description="How completion is verified.")
    evidence_artifact: str = Field(max_length=150, description="The artifact that will demonstrate completion, named concretely.")
    citations: List[str] = Citations
    links: List[str] = Field(default_factory=list)
    priority: Optional[str] = computed()


class CoverageItem(_Model):
    key: str
    status: CoverageStatus
    justification: str = Field(max_length=200, description="One short sentence.")


class OpenIssue(_Model):
    id: str = Field(default="", description="Local identifier such as I1.")
    type: IssueType
    description: str = Field(max_length=400, description="The decision a person must take, in one or two sentences.")
    options: List[str] = Field(default_factory=list, description="The choices a person could make, a few words each.")
    decision_owner: Owner = Field(description="The role that must arbitrate.")
    blocking: bool = Field(default=False, description="True if work must not proceed until decided.")
    links: List[str] = Field(default_factory=list)
    origin: Optional[str] = computed("agent")


class RecordCore(_Model):
    headline: str = asked(max_length=200, description=(
        "The bottom line in ONE sentence of at most 25 words a busy reader can act on: the verdict "
        "and what it means for the team."))
    summary: str = Field(max_length=600, description=(
        "At most three sentences that add to the headline: the main risks and what must happen next. "
        "No framework explanations."))
    overall_status: Status
    declared_verdict: Dict[str, str] = Field(default_factory=dict, description=(
        "Your value for each verdict key named in the contract."))
    agrees_with_rule_engine: bool
    disagreement_rationale: str = Field(default="", description="Required when you disagree.")
    findings: List[Finding] = Field(default_factory=list)
    actions: List[Action] = Field(default_factory=list)
    open_issues: List[OpenIssue] = Field(default_factory=list, description=(
        "Issues you raise. The rule engine's issues are carried forward by code; do not repeat them."))
    not_grounded: List[str] = Field(default_factory=list, description=(
        "Claims you believe matter that the retrieved excerpts do not support."))
    coverage: List[CoverageItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Risk Classifier — EU AI Act, PL 2338/2023
# ---------------------------------------------------------------------------


class ObligationNote(_Model):
    code: str = Field(description="An obligation code from the computed table, exactly.")
    meaning_for_this_product: str = Field(max_length=300, description="One sentence: what the team must do or show for this product.")
    citations: List[str] = Citations


class RiskClassificationExt(_Model):
    prohibited_screen: str = Field(max_length=400, description="Result of the EU AI Act Art. 5 and PL 2338 excessive-risk screen, conclusion first.")
    eu_tier_justification: str = Field(max_length=400, description="Why the EU tier holds, naming the area or article; at most two sentences.")
    br_tier_justification: str = Field(max_length=400, description="Why the Brazilian tier holds, naming the area; at most two sentences.")
    obligations: List[ObligationNote] = Field(default_factory=list, description="One note per computed obligation code.")
    human_oversight_assessment: str = Field(max_length=450, description="Whether the declared oversight design meets the oversight obligations, conclusion first.")
    affected_persons_rights: str = Field(max_length=450, description="How affected persons' rights are operationalised in the product, conclusion first.")
    impact_assessments: str = Field(max_length=400, description="Which impact assessments the instruments require (fundamental rights / algorithmic).")


# ---------------------------------------------------------------------------
# Requirements Reviewer — IEEE 7000 (Value-Based Engineering), Microsoft RAI v2 A1
# ---------------------------------------------------------------------------


class StakeholderEntry(_Model):
    name: str
    kind: StakeholderKind = Field(description="direct (uses the system) or indirect (affected without using it).")
    values: List[Principle] = Field(default_factory=list)


class ValueEntry(_Model):
    value: Principle = Field(description="The core value.")
    rank: int = Field(ge=1, description="1 = highest priority core value.")
    threats: str = Field(max_length=250, description="How the design could harm this value, in one sentence.")
    opportunities: str = Field(max_length=250, description="How the design could advance it, in one sentence.")


class GapNote(_Model):
    evr_id: str = Field(description="A computed EVR id, exactly.")
    explanation: str = Field(max_length=300, description="What is missing and why it matters for this product, in one or two sentences.")
    citations: List[str] = Citations


class EthicalValueRequirement(_Model):
    id: str = Field(description="An assigned EVR id, exactly.")
    value: Principle
    stakeholders: List[str]
    statement: str = Field(max_length=300, description="The requirement, bound to this context of use, in one sentence.")
    fit_criterion: str = Field(max_length=250, description="The measurable condition that settles whether it is met.")
    verification_method: Verification
    traces_to: List[str] = Field(default_factory=list, description="Obligation codes or principle refs it derives from.")
    citations: List[str] = Citations


class HarmBenefit(_Model):
    stakeholder: str
    harms: str = Field(max_length=250)
    benefits: str = Field(max_length=250)


class ImpactAssessment(_Model):
    intended_uses: str = Field(max_length=400, description="Intended and out-of-scope uses.")
    harms_and_benefits: List[HarmBenefit] = Field(default_factory=list, description="Potential harms and benefits per stakeholder.")
    mitigations: str = Field(max_length=400, description="The main mitigations, conclusion first.")


class RequirementsReviewExt(_Model):
    context_of_use: str = Field(max_length=450, description="The operational environment and conditions of use (IEEE 7000 concept of operations).")
    stakeholders: List[StakeholderEntry] = Field(default_factory=list, description="Direct and indirect stakeholders and the values at stake for each.")
    value_register: List[ValueEntry] = Field(default_factory=list, description="Prioritised core values with threats and opportunities (IEEE 7000 Value Register).")
    gap_analysis: List[GapNote] = Field(default_factory=list, description="One entry per computed EVR id.")
    evrs: List[EthicalValueRequirement] = Field(default_factory=list, description="One ethical value requirement per assigned id.")
    impact_assessment: ImpactAssessment = Field(description="Microsoft RAI Standard v2 goal A1 impact assessment.")


# ---------------------------------------------------------------------------
# User Story Refiner — ECCOLA, Microsoft RAI v2 verifiable requirements
# ---------------------------------------------------------------------------


class AcceptanceCriterion(_Model):
    id: str = Field(description="AC-<story id>-<n>, e.g. AC-S1-1.")
    ms_goal: MsGoal = Field(description="The Microsoft RAI Standard v2 goal it serves.")
    stakeholder_group: str = Field(description="The affected stakeholder group.")
    condition: str = Field(max_length=250, description="Measurable condition with its threshold, written as an acceptance criterion.")
    evidence_artifact: str = Field(description="The artifact that demonstrates compliance.")
    owner_role: Owner
    evr_ids: List[str] = Field(default_factory=list, description="Approved EVR ids this criterion implements.")


class CriterionConflict(_Model):
    criterion_id: str = Field(description="The id of one of the story's EXISTING acceptance criteria (e.g. S1-E2), exactly.")
    conflicts_with: List[str] = Field(default_factory=list, description=(
        "What it conflicts with: approved EVR ids, selected ECCOLA card ids or principle keys."))
    problem: str = Field(max_length=250, description="One sentence: why the existing criterion conflicts.")
    suggested_rewrite: str = Field(default="", max_length=250, description="The criterion rewritten so the conflict is gone.")


class StoryEntry(_Model):
    story_id: str = Field(description="A story id from the register, exactly.")
    eccola_cards: List[Card] = Field(default_factory=list, description="ECCOLA card ids in scope for THIS story that make it relevant.")
    card_discussion: str = Field(default="", max_length=400, description="The cards' questions, answered for this story in two or three sentences.")
    criteria: List[AcceptanceCriterion] = Field(default_factory=list, description=(
        "New verifiable ethical acceptance criteria (Microsoft RAI Standard v2 requirement pattern). "
        "Do not repeat the story's existing criteria."))
    conflicts: List[CriterionConflict] = Field(default_factory=list, description=(
        "Existing acceptance criteria of this story that conflict with an approved requirement or a "
        "selected card. Only real conflicts; leave empty otherwise."))
    no_impact_reason: str = Field(default="", max_length=200, description="Only for a story with no ethical impact: one line.")


class RefinedStoriesExt(_Model):
    stories: List[StoryEntry] = Field(default_factory=list, description="Exactly one entry per story id in the register.")
    sprint_ethics_log: List[str] = Field(default_factory=list, max_length=5, description=(
        "Up to five decisions taken this sprint, one sentence each with its reason (ECCOLA "
        "documentation step)."))

    @field_validator("sprint_ethics_log", mode="before")
    @classmethod
    def _log_as_list(cls, value: Any) -> Any:
        # Records written before the log was a list carried one paragraph.
        if isinstance(value, str):
            return [value] if value.strip() else []
        return value


# ---------------------------------------------------------------------------
# Auditor — Microsoft RAI v2 accountability, NIST AI RMF GOVERN
# ---------------------------------------------------------------------------


class AuditItem(_Model):
    item_id: str = Field(description="A computed audit item id, exactly.")
    verdict: AuditVerdict
    evidence: str = Field(max_length=350, description="Quoted from the sprint outcomes or an upstream artifact; empty if none.")
    evidence_needed: str = Field(default="", max_length=250, description="What would verify it, when not satisfied.")
    downgrade_reason: str = Field(default="", max_length=250)
    citations: List[str] = Citations
    computed_verdict: Optional[str] = computed()


class DecisionEntry(_Model):
    decision: str = Field(max_length=200)
    decided_by: str
    artifact: str = Field(description="The approved artifact that records it.")
    reference: str = Field(default="", description="Commit, date or approval header it was read from.")


class Checkpoint(_Model):
    checkpoint: str = Field(max_length=200)
    triggered_by: str = Field(description="The planned epic or event that reaches it.")
    item_ids: List[str] = Field(default_factory=list)
    lifecycle_stage: Lifecycle


class Strength(_Model):
    statement: str = Field(max_length=200, description="One sentence: what is working, specific to this product.")
    refs: List[str] = Field(default_factory=list, description=(
        "What shows it: ids of items whose verdict is satisfied or partially_satisfied, or the key of "
        "an approved upstream artifact (e.g. requirements_review) whose approval record shows it. "
        "A strength resting on anything else is removed by code."))
    evidence: str = Field(default="", max_length=200, description="The evidence, quoted or named in one line.")


class Opportunity(_Model):
    statement: str = Field(max_length=200, description=(
        "One sentence: an improvement beyond closing the gaps — something that would make the next "
        "audits cheaper or the controls stronger."))
    refs: List[str] = Field(default_factory=list, description="Item ids or principle keys it concerns.")
    benefit: str = Field(default="", max_length=200, description="What it would change, in one line.")


class AuditReportExt(_Model):
    items: List[AuditItem] = Field(default_factory=list, description="One entry per computed audit item.")
    accountability_log: List[DecisionEntry] = Field(default_factory=list, description="Who decided what, from the upstream approval headers (NIST AI RMF GOVERN 2).")
    upcoming_checkpoints: List[Checkpoint] = Field(default_factory=list, description="Ethical checkpoints the planned work will hit.")
    strengths: List[Strength] = Field(default_factory=list, max_length=3, description=(
        "Up to three strengths, each resting on verified evidence or an approval on record."))
    opportunities: List[Opportunity] = Field(default_factory=list, max_length=3, description=(
        "Up to three opportunities for improvement."))
    pathway_summary: str = Field(default="", max_length=250, description=(
        "One sentence: the way forward, in the order the team should take it."))
    opinion: Optional[Dict[str, Any]] = computed()


# ---------------------------------------------------------------------------
# Drift Monitor — NIST AI RMF MEASURE and MANAGE
# ---------------------------------------------------------------------------


class Alert(_Model):
    window: str = Field(description="A computed breach window label, exactly.")
    severity: Severity = Field(description="Exactly the severity the engine computed.")
    meaning_for_affected_people: str = Field(max_length=300, description="What this means for the people affected, in one or two sentences.")
    citations: List[str] = Citations


class ResponsePlan(_Model):
    escalation_path: str = Field(max_length=300, description="Who is alerted, in what order, within what time.")
    deactivation_criteria: str = Field(max_length=300, description="When the system is rolled back or deactivated (MANAGE 2).")
    affected_community_feedback: str = Field(max_length=300, description="How input from users and affected communities is captured (MANAGE 4).")
    recovery_and_communication: str = Field(max_length=300, description="How the system recovers and who is told.")


class DriftAlertsExt(_Model):
    alerts: List[Alert] = Field(default_factory=list, description="One alert per computed breach window.")
    trend_interpretation: str = Field(max_length=400, description="The movement across windows, conclusion first (NIST AI RMF MEASURE 3).")
    representativeness: str = Field(max_length=400, description="Whether the population mix shifted relative to the population affected, conclusion first (MEASURE 2).")
    sample_adequacy: List[str] = Field(default_factory=list, description="Groups whose samples do not support a conclusion.")
    response_plan: ResponsePlan = Field(description="Response, recovery and communication (NIST AI RMF MANAGE).")


EXTENSIONS: Dict[str, Type[_Model]] = {
    "risk_classifier": RiskClassificationExt,
    "requirements_reviewer": RequirementsReviewExt,
    "story_refiner": RefinedStoriesExt,
    "auditor": AuditReportExt,
    "drift_monitor": DriftAlertsExt,
}

_RECORDS: Dict[str, Type[RecordCore]] = {}


def record_model(agent_key: str) -> Type[RecordCore]:
    """The full record model for one agent: shared core + its extension."""
    if agent_key not in _RECORDS:
        ext = EXTENSIONS.get(agent_key)
        if ext is None:
            _RECORDS[agent_key] = RecordCore
        else:
            name = "".join(p.title() for p in agent_key.split("_")) + "Record"
            _RECORDS[agent_key] = type(name, (RecordCore,), {
                "__annotations__": {"extension": ext},
                "__module__": __name__,
            })
    return _RECORDS[agent_key]


def full_schema(agent_key: str) -> Dict[str, Any]:
    return record_model(agent_key).model_json_schema()


def model_facing_schema(agent_key: str) -> Dict[str, Any]:
    """The JSON Schema shown to the model: computed fields removed."""
    schema = copy.deepcopy(full_schema(agent_key))

    def strip(node: Any) -> None:
        if isinstance(node, dict):
            props = node.get("properties")
            if isinstance(props, dict):
                for name in [k for k, v in props.items() if isinstance(v, dict) and v.get("computed")]:
                    props.pop(name)
                    if name in node.get("required", []):
                        node["required"].remove(name)
                for name, v in props.items():
                    if isinstance(v, dict) and v.pop("model_required", False):
                        v.pop("default", None)
                        if name not in node.setdefault("required", []):
                            node["required"].append(name)
            for v in node.values():
                strip(v)
        elif isinstance(node, list):
            for v in node:
                strip(v)

    strip(schema)
    return schema
