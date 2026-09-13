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
        required_sections=[
            "Gap Analysis",
            "Proposed Ethical Value Requirements",
            "Impact Assessment Notes",
            "Open Issues",
        ],
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
            "Write the ethical value requirements for the gaps the engine computed. The gap "
            "list and the requirement identifiers are given to you — use exactly those ids, "
            "do not renumber, do not invent additional ones, and do not drop one.\n\n"
            "Under **Gap Analysis**, explain each computed GAP row: what is missing, why it "
            "matters for this product specifically, and which excerpt grounds the concern. "
            "Where a row was marked covered by a control or an existing requirement, do not "
            "restate it.\n\n"
            "Under **Proposed Ethical Value Requirements**, write one requirement per assigned "
            "id. Each must name the value it protects and the stakeholder it protects, be bound "
            "to this system's context, and above all be *verifiable* — a test, an audit, a "
            "measurement or an inspection must be able to settle whether it is met. Prefer "
            "\"selection outcomes shall be auditable per protected attribute\" to \"the system "
            "shall be fair\".\n\n"
            "Under **Impact Assessment Notes**, say what a structured impact assessment would "
            "flag for this system that the requirements do not yet cover.\n\n"
            "Under **Open Issues**, carry forward every issue the engine raised, and add any "
            "value conflict you found. Surface trade-offs; never resolve one yourself."
        ),
    )

    def extra_checks(
        self, report: validators.ValidationReport, draft: str, rationale: RationaleResult
    ) -> None:
        evr_ids = rationale.verdict.get("evr_ids") or []
        report.add(
            validators.check_traceability(
                draft, evr_ids, "Requirement register", code="evr_register"
            )
        )
        report.add(validators.check_requirement_quality(draft, evr_ids))
