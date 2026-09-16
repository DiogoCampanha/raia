"""
Auditor agent (Dev layer — Development / validation).

RAIA agent specification:
  Inputs   : sprint outcomes, planned epics, declared evidence types, and the
             approved ethical requirements and acceptance criteria
  Outputs  : progress audit; accountability documentation
  Grounding: Microsoft RAI Standard v2 accountability; NIST GOVERN

The anti-ethics-washing rule is enforced rather than requested. The register of
approved requirements and criteria is read from the upstream artifacts, each is
matched against the reported sprint outcomes, and anything with no evidence is
assigned NOT VERIFIED *by code* before the model is asked anything. The model
may downgrade a verdict — it reads the narrative the matcher only
pattern-matched — but a validator prevents it from upgrading one.
"""

from typing import Any, Dict

from .. import validators
from ..fields import InputField
from ..rationale import traceability
from ..rationale.types import RationaleResult
from .base import AgentSpec, BaseAgent

G_SPRINT = "1 · What happened this sprint"
G_EVIDENCE = "2 · Evidence produced"
G_NEXT = "3 · What comes next"


class AuditorAgent(BaseAgent):
    spec = AgentSpec(
        key="auditor",
        name="Auditor",
        layer="Dev",
        sdlc_phase="Development and validation",
        description=(
            "Audits sprint progress against the approved ethical requirements and "
            "produces accountability documentation grounded in versioned evidence."
        ),
        intro=(
            "Verdicts are pre-assigned by code: anything with no trace in the sprint outcomes "
            "is NOT VERIFIED before the agent reads a word. The agent can downgrade a verdict; "
            "it cannot upgrade one. If nothing is marked satisfied, that is the audit working."
        ),
        grounding_sources=["ms_rai_v2", "nist_ai_rmf"],
        upstream_keys=["risk_classification", "requirements_review", "refined_stories"],
        required_upstream=["requirements_review"],
        output_key="audit_report",
        engine=traceability.run,
        verdict_keys=["items_audited"],
        required_sections=[
            "Progress Audit",
            "Accountability Documentation",
            "Upcoming Ethical Checkpoints",
            "Open Issues",
        ],
        input_fields=[
            InputField(
                key="sprint_id", label="Sprint", kind="text", group=G_SPRINT,
                placeholder="Sprint 7",
                help="Recorded in the audit trail so a verdict can be tied to a point in time.",
            ),
            InputField(
                key="sprint_outcomes", label="Sprint outcomes", group=G_SPRINT, required=True,
                height=220,
                help="What was delivered, and what was tested. Name requirement or story ids "
                     "(EVR-2, AC-S1-1) where you can — an item with no trace here is "
                     "automatically unverified.",
            ),
            InputField(
                key="evidence_types", label="What evidence did this sprint actually produce?",
                kind="multiselect", group=G_EVIDENCE, required=True,
                options=traceability.EVIDENCE_OPTIONS,
                help="If nothing is selected, every item is unverified regardless of what the "
                     "narrative says. That is the intended behaviour.",
            ),
            InputField(
                key="planned_epics", label="Planned epics / next steps", group=G_NEXT, height=120,
                help="Used to flag the ethical checkpoints the upcoming work will hit.",
            ),
        ],
        task_prompt=(
            "Audit this sprint against the register the engine computed. The verdict table is "
            "given to you and it is binding in one direction: you may downgrade a verdict when "
            "the narrative shows the match was superficial, and you must never upgrade one. An "
            "item marked NOT VERIFIED stays unverified in your report, whatever the sprint "
            "notes claim.\n\n"
            "Under **Progress Audit**, work through every item in the table. For each: its id, "
            "your verdict (Satisfied / Partially satisfied / Not verified / At risk), the "
            "evidence quoted from the sprint outcomes or an upstream artifact, and the norm "
            "excerpt cited. Where you downgrade a computed verdict, say why.\n\n"
            "Under **Accountability Documentation**, record who decided what, taken from the "
            "approval headers of the upstream artifacts, and what a reviewer would need to "
            "reconstruct those decisions.\n\n"
            "Under **Upcoming Ethical Checkpoints**, map the planned work to the checkpoints it "
            "will hit, so they are scheduled rather than discovered.\n\n"
            "Under **Open Issues**, carry forward every issue the engine raised, plus any "
            "unverified item that needs an owner and a date."
        ),
    )

    def extra_checks(
        self, report: validators.ValidationReport, draft: str, rationale: RationaleResult
    ) -> None:
        not_verified = rationale.verdict.get("not_verified") or []
        assessable = rationale.verdict.get("assessable") or []
        report.add(validators.check_forbidden_verdicts(draft, not_verified))
        report.add(
            validators.check_traceability(
                draft, list(not_verified) + list(assessable), "Audit coverage", code="audit"
            )
        )
