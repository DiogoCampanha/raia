"""
Requirements Reviewer agent (Product layer -- Requirements definition).

Paper Table 2:
  Inputs   : software requirements, risk classification
  Outputs  : gap analysis; proposed ethical value requirements
  Grounding: IEEE 7000 VBE; Microsoft Impact Assessments
"""

from .base import AgentSpec, BaseAgent, InputField


class RequirementsReviewerAgent(BaseAgent):
    spec = AgentSpec(
        key="requirements_reviewer",
        name="Requirements Reviewer",
        layer="Product",
        sdlc_phase="Requirements definition",
        description=(
            "Reviews the software requirements against the risk classification "
            "and derives ethical value requirements following IEEE 7000's VBE."
        ),
        grounding_sources=["ieee_7000", "ms_rai_v2"],
        upstream_keys=["product_brief", "risk_classification"],
        required_upstream=["risk_classification"],  # stage gate (Figure 1)
        output_key="requirements_review",
        input_fields=[
            InputField(
                key="requirements",
                label="Software requirements",
                help="Paste the current functional and non-functional requirements (one per line or numbered).",
            ),
        ],
        task_prompt=(
            "Review the software requirements in light of the approved risk "
            "classification. Apply IEEE 7000's Value-Based Engineering: identify "
            "stakeholder values at stake, derive ethical value requirements "
            "(EVRs), and use the Microsoft RAI Standard v2 style of verifiable, "
            "specific requirements. Structure your output as:\n"
            "## Gap Analysis\n"
            "(which RAI concerns the current requirements do NOT cover, each gap "
            "cited to its grounding excerpt)\n"
            "## Proposed Ethical Value Requirements\n"
            "(numbered EVR-1, EVR-2, ...; each measurable/verifiable, traceable to "
            "a value and a norm excerpt — e.g. 'selection outcomes shall be "
            "auditable per protected attribute')\n"
            "## Impact Assessment Notes\n"
            "(what a Microsoft-style Impact Assessment would flag for this system)\n"
            "## Open Issues\n"
            "(value conflicts, e.g. fairness vs. accuracy, for human arbitration)"
        ),
    )
