"""
Auditor agent (Dev layer -- Development / validation).

RAIA agent specification:
  Inputs   : sprint outcomes, planned epics, ethical requirements
  Outputs  : progress audit; accountability documentation
  Grounding: MS RAI v2 accountability; NIST *Govern*

Ethics-washing safeguard (a RAIA design commitment): "requiring audit reports to be
grounded in versioned evidence from the shared repository mitigates this
risk" -- hence the explicit evidence-linking instructions below.
"""

from .base import AgentSpec, BaseAgent, InputField


class AuditorAgent(BaseAgent):
    spec = AgentSpec(
        key="auditor",
        name="Auditor",
        layer="Dev",
        sdlc_phase="Development and validation",
        description=(
            "Audits sprint progress against the approved ethical requirements "
            "and produces accountability documentation grounded in versioned evidence."
        ),
        grounding_sources=["ms_rai_v2", "nist_ai_rmf"],
        upstream_keys=["risk_classification", "requirements_review", "refined_stories"],
        required_upstream=["requirements_review"],  # stage gate (pipeline order)
        output_key="audit_report",
        input_fields=[
            InputField(
                key="sprint_outcomes",
                label="Sprint outcomes",
                help="What was delivered this sprint? Include test results relevant to ethical acceptance criteria.",
            ),
            InputField(
                key="planned_epics",
                label="Planned epics / next steps",
                help="What is planned next? (used to flag upcoming ethical checkpoints)",
            ),
        ],
        task_prompt=(
            "Audit the sprint outcomes against the approved ethical value "
            "requirements and refined stories from the shared repository. "
            "IMPORTANT anti-ethics-washing rule: every 'satisfied' verdict must "
            "point to concrete evidence in the sprint outcomes or upstream "
            "artifacts; if no evidence exists, the verdict is 'NOT VERIFIED', "
            "never 'satisfied'. Structure as:\n"
            "## Progress Audit\n"
            "(per ethical requirement: status = Satisfied / Partially satisfied / "
            "Not verified / At risk, with the evidence quoted and the norm cited)\n"
            "## Accountability Documentation\n"
            "(who decided what, per the upstream artifacts' approval headers; "
            "MS RAI v2 accountability goals and NIST GOVERN practices cited)\n"
            "## Upcoming Ethical Checkpoints\n"
            "(for the planned epics)\n"
            "## Open Issues\n"
            "(unresolved gaps requiring human arbitration)"
        ),
    )
