"""
Drift Monitor agent (Ops layer — Deployment / monitoring).

RAIA agent specification:
  Inputs   : production telemetry, operational context, and the approved
             classification and ethical requirements
  Outputs  : drift alerts focused on fairness and representativeness
  Grounding: NIST AI RMF MEASURE / MANAGE

This agent's analysis was always deterministic, and it became the pattern for
the rest of the system. It now also computes what used to be left implicit: the
threshold it judges against is parsed out of the approved upstream artifacts
rather than inferred from prose, breaches and trends are computed, alert
severity follows a rule, and any group below a minimum sample size is labelled
as unable to support a conclusion. Every figure in the narrative is checked
against the computed set — the model interprets numbers, it never produces one.
"""

from .. import validators
from ..contract import checks as contract_checks
from ..contract.assemble import drift_severities
from ..fields import InputField
from ..rationale import drift
from .base import AgentSpec, BaseAgent

G_TELEMETRY = "1 · Telemetry"
G_CONTEXT = "2 · Operational context"


def compute_fairness_summary(csv_text: str) -> str:
    """Per-window fairness metrics as a Markdown table.

    Kept as a standalone entry point: metric computation is the part of this
    system that must be reproducible outside the UI, the graph and the model.
    """
    thresholds = {"parity_difference": {"value": None, "source": "none", "quote": ""}}
    analysis = drift.analyse(csv_text, {})
    return drift.summary_table(analysis, thresholds["parity_difference"]["value"])


class DriftMonitorAgent(BaseAgent):
    spec = AgentSpec(
        key="drift_monitor",
        name="Drift Monitor",
        layer="Ops",
        sdlc_phase="Deployment and monitoring",
        description=(
            "Watches production telemetry for fairness and representativeness drift, "
            "computing every metric in code and letting the model interpret only."
        ),
        intro=(
            "Every number below the fold is computed from your telemetry, including the "
            "threshold — which is read out of your approved ethical requirements rather than "
            "assumed. Include an `n` column: without group sizes, a parity gap is a question, "
            "not a finding."
        ),
        grounding_sources=["nist_ai_rmf"],
        upstream_keys=["risk_classification", "requirements_review", "refined_stories"],
        required_upstream=["risk_classification"],
        output_key="drift_report",
        engine=drift.run,
        verdict_keys=["windows"],
        input_fields=[
            InputField(
                key="telemetry_csv", label="Production telemetry", kind="csv", group=G_TELEMETRY,
                required=True, height=200, file_types=("csv", "txt"),
                help="Columns: window,group,selection_rate[,accuracy][,n]. One row per time "
                     "window and demographic group. Upload a file or paste the rows.",
            ),
            InputField(
                key="incident", label="Did anything happen in this period?", kind="select",
                group=G_CONTEXT, required=True, options=drift.INCIDENT_OPTIONS, default="none",
                help="An operational event changes how a metric movement should be read, and is "
                     "escalated for human judgement rather than explained away.",
            ),
            InputField(
                key="context_notes", label="Operational context", kind="textarea", group=G_CONTEXT,
                height=120,
                help="Anything the on-call team knows: data-source changes, seasonality, "
                     "releases, backfills.",
            ),
        ],
        task_prompt=(
            "Interpret the fairness metrics computed from the telemetry, following NIST AI RMF "
            "MEASURE and MANAGE. The numbers, the threshold, the breaches, the trend, the "
            "severities and the sample-adequacy flags are ground truth: never restate a different "
            "figure, never estimate one, and never write a number that is not in the computed "
            "table. Your job is meaning, not measurement.\n\n"
            "In the extension: `alerts` has one entry per computed breach window, with exactly the "
            "severity the engine computed and what it means for the people affected, cited. "
            "`trend_interpretation` reads the movement across windows; `representativeness` says "
            "whether the population mix shifted relative to the population affected; "
            "`sample_adequacy` names where a group's sample is too small to conclude from. "
            "`response_plan` gives the escalation path, the criteria that would justify rollback "
            "or deactivation, how input from users and affected communities is captured, and "
            "recovery and communication.\n\n"
            "Findings are the measured risks — a breach is `observed` — linked to the window "
            "labels. Actions are responses grounded in the retrieved management practices."
        ),
    )

    def extra_checks(self, report, draft, rationale, record) -> None:
        allowed = (rationale.data or {}).get("allowed_numbers") or []
        if allowed:
            report.add(validators.check_numbers(
                contract_checks.narrative_text(record), allowed, "Reported figures"))
        breaches = list(drift_severities(rationale))
        alerts = [a.get("window") for a in (record.get("extension") or {}).get("alerts") or []]
        report.add(contract_checks.check_registered_ids("Drift alerts", "alerts", breaches, alerts))
