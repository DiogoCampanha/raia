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

from typing import Any, Dict

from .. import validators
from ..fields import InputField
from ..rationale import drift
from ..rationale.types import RationaleResult
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
        required_sections=[
            "Drift Alerts",
            "Fairness & Representativeness Analysis",
            "Recommended Actions",
            "Open Issues",
        ],
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
            "Interpret the fairness metrics computed from the telemetry. The numbers, the "
            "threshold, the breaches, the trend and the sample-adequacy flags are all given to "
            "you and are ground truth: never restate a different figure, never estimate one, "
            "and never introduce a number that is not in the computed table. Your job is "
            "meaning, not measurement.\n\n"
            "Under **Drift Alerts**, raise one alert per computed breach — the window, the "
            "severity the engine assigned, what it means for affected people — citing the "
            "management practice that grounds the response.\n\n"
            "Under **Fairness & Representativeness Analysis**, read the movement across "
            "windows: the direction of the trend, whether the population mix shifted, and "
            "whether the operational context plausibly explains it. Where a group's sample is "
            "too small to conclude from, say so plainly rather than hedging.\n\n"
            "Under **Recommended Actions**, give responses grounded in the retrieved practices: "
            "what to investigate, what to retrain, which decisions to review by hand, what "
            "would justify a rollback.\n\n"
            "Under **Open Issues**, carry forward every issue the engine raised, plus anything "
            "the telemetry cannot settle."
        ),
    )

    def extra_checks(
        self, report: validators.ValidationReport, draft: str, rationale: RationaleResult
    ) -> None:
        allowed = (rationale.data or {}).get("allowed_numbers") or []
        if allowed:
            report.add(validators.check_numbers(draft, allowed, "Reported figures"))
