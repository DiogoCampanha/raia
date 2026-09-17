"""
Requirements Reviewer agent (Product layer — Requirements definition).

RAIA agent specification:
  Inputs   : software requirements, existing controls, values at stake,
             and the approved risk classification
  Outputs  : gap analysis; proposed ethical value requirements
  Grounding: IEEE 7000 value-based engineering; Microsoft impact assessments

The gap list is *computed*, not chosen by the model: the obligations produced
upstream and the seven adopted Responsible AI principles form a matrix against
the team's stated requirements and existing controls, and the empty cells are
the gaps. Requirement identifiers are assigned by the engine so that downstream
agents can be checked against a register that actually exists.
"""

from typing import Any, Dict

from .. import validators
from ..contract import checks as contract_checks
from ..fields import InputField
from ..rationale import coverage
from ..rationale.types import RationaleResult
from .base import AgentSpec, BaseAgent

G_REQS = "1 · Current requirements"
G_CONTEXT = "2 · What already exists"
G_VALUES = "3 · Values and stakeholders"


class RequirementsReviewerAgent(BaseAgent):
    spec = AgentSpec(
        key="requirements_reviewer",
        name="Requirements Reviewer",
        layer="Product",
        sdlc_phase="Requirements definition",
        description=(
            "Reviews the software requirements against the risk classification "
            "and derives verifiable ethical value requirements."
        ),
        intro=(
            "The gaps are computed from the approved obligations and the seven Responsible "
            "AI principles — the agent writes a requirement for each one, it does not decide "
            "which gaps exist. Telling it which controls you already have is what stops it "
            "from proposing work you have already done."
        ),
        grounding_sources=["ieee_7000", "ms_rai_v2"],
        upstream_keys=["product_brief", "risk_classification"],
        required_upstream=["risk_classification"],
        output_key="requirements_review",
        engine=coverage.run,
        verdict_keys=["gap_count"],
        input_fields=[
            InputField(
                key="requirements", label="Software requirements", group=G_REQS, required=True,
                height=220,
                help="Paste the current functional and non-functional requirements, one per line.",
            ),
            InputField(
                key="requirement_format", label="How are they written?", kind="select",
                group=G_REQS, options=coverage.FORMAT_OPTIONS, default="numbered",
                help="Used to split them into identified items so gaps can be tied to a requirement.",
            ),
            InputField(
                key="existing_controls", label="Which of these are already in place?",
                kind="multiselect", group=G_CONTEXT, required=True, options=coverage.CONTROL_OPTIONS,
                help="Each control discharges specific obligations. Anything not covered here or by a "
                     "requirement becomes a computed gap.",
            ),
            InputField(
                key="constraints", label="Delivery constraints", kind="textarea", group=G_CONTEXT,
                height=100,
                help="Deadlines, platform limits, team capacity. Requirements that cannot be met "
                     "within them are recorded as open issues rather than quietly dropped.",
            ),
            InputField(
                key="values_at_stake", label="Which principles does your team believe are at stake?",
                kind="multiselect", group=G_VALUES, options=coverage.PRINCIPLE_OPTIONS,
                help="A principle flagged here is reported as a gap unless the requirements clearly "
                     "address it — your judgement overrides the lexical check.",
            ),
            InputField(
                key="stakeholders", label="Whose values were elicited?",
                kind="multiselect", group=G_VALUES, required=True,
                options=coverage.STAKEHOLDER_OPTIONS,
                help="Value elicitation that omits the people a decision is made about is incomplete, "
                     "and the engine will say so.",
            ),
        ],
        task_prompt=(
            "Turn the gaps the engine computed into ethical value requirements, following IEEE "
            "7000 Value-Based Engineering and the Microsoft RAI Standard v2 impact assessment "
            "(goal A1). The gap list and the requirement identifiers are given to you: use exactly "
            "those ids, do not renumber, do not invent additional ones, and do not drop one.\n\n"
            "In the extension: `context_of_use` characterises the operational environment. "
            "`stakeholders` lists direct and indirect stakeholders — including people who never "
            "use the system but are affected by it — and the values at stake for each. "
            "`value_register` ranks the core values (1 = highest) and, for each, the threats the "
            "design poses to it and the opportunities to advance it. `gap_analysis` explains "
            "every computed gap: what is missing, why it matters for this product, and which "
            "excerpt grounds the concern. `evrs` holds one ethical value requirement per assigned "
            "id, and each must be traceable (the value and stakeholders it protects), contextual "
            "(bound to this system), prioritised (its value is in the register) and above all "
            "verifiable: a `fit_criterion` a test, audit, measurement or inspection can settle. "
            "Prefer \"selection outcomes shall be auditable per protected attribute\" to \"the "
            "system shall be fair\". `impact_assessment` records intended uses, potential harms "
            "and benefits per stakeholder, and mitigations.\n\n"
            "Findings are the value threats that carry real risk, linked to EVR ids. Actions adopt "
            "and verify the requirements. Where values trade off, raise a `value_tradeoff` issue; "
            "never resolve one yourself."
        ),
    )

    def extra_checks(self, report, draft, rationale, record) -> None:
        evr_ids = rationale.verdict.get("evr_ids") or []
        ext = record.get("extension") or {}
        report.add(contract_checks.check_registered_ids(
            "Requirement register", "evr_register", evr_ids, [e.get("id") for e in ext.get("evrs") or []]))
        report.add(contract_checks.check_registered_ids(
            "Gap analysis", "gap_analysis", evr_ids, [g.get("evr_id") for g in ext.get("gap_analysis") or []]))
        report.add(validators.check_requirement_quality(draft, evr_ids))

    def structured_from(self, record: Dict[str, Any], rationale: RationaleResult) -> Dict[str, Any]:
        """Publish the approved requirements, so the Auditor audits their wording."""
        data = super().structured_from(record, rationale)
        data["evrs"] = [
            {"id": e.get("id"), "value": e.get("value"), "statement": e.get("statement", ""),
             "fit_criterion": e.get("fit_criterion", ""), "verification_method": e.get("verification_method")}
            for e in (record.get("extension") or {}).get("evrs") or []
        ]
        return data
