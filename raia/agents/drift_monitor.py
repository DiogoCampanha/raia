"""
Drift Monitor agent (Ops layer -- Deployment / monitoring).

RAIA agent specification:
  Inputs   : production telemetry, fairness metrics
  Outputs  : drift alerts focused on fairness and representativeness
  Grounding: NIST *Measure* / *Manage*

Unlike the other agents, part of this agent's analysis is DETERMINISTIC:
fairness metrics are computed with pandas from the telemetry CSV before the
LLM is asked to interpret them. Numbers come from code, not from the model
-- another hallucination-mitigation measure: the LLM interprets and
contextualizes; it never invents metric values.
"""

import io
from typing import Dict, List, Optional

import pandas as pd

from .base import AgentSpec, BaseAgent, InputField


def compute_fairness_summary(csv_text: str) -> str:
    """Compute per-window fairness metrics from telemetry CSV.

    Expected columns (header required):
        window          -- time window label (e.g. 2026-05, week-23)
        group           -- demographic group (e.g. gender=F, race=black)
        selection_rate  -- fraction of positive outcomes for the group (0..1)
        accuracy        -- (optional) model accuracy for the group

    Returns a Markdown table with, per window:
        * demographic parity difference (max - min selection rate);
        * the most/least selected groups;
        * accuracy gap when accuracy is provided.
    Raises ValueError with a friendly message when the CSV is malformed.
    """
    try:
        df = pd.read_csv(io.StringIO(csv_text.strip()))
    except Exception as exc:
        raise ValueError(f"Could not parse telemetry CSV: {exc}") from exc

    required = {"window", "group", "selection_rate"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Telemetry CSV is missing required column(s): {', '.join(sorted(missing))}. "
            "Expected header: window,group,selection_rate[,accuracy]"
        )

    rows: List[str] = []
    has_acc = "accuracy" in df.columns
    header = "| Window | DP difference | Highest group | Lowest group |"
    header += " Accuracy gap |" if has_acc else ""
    sep = "|---" * (5 if has_acc else 4) + "|"

    for window, g in df.groupby("window", sort=True):
        sr = g.set_index("group")["selection_rate"]
        dp_diff = float(sr.max() - sr.min())
        hi, lo = sr.idxmax(), sr.idxmin()
        row = (
            f"| {window} | {dp_diff:.3f} | {hi} ({sr.max():.3f}) | {lo} ({sr.min():.3f}) |"
        )
        if has_acc:
            acc = g.set_index("group")["accuracy"]
            row += f" {float(acc.max() - acc.min()):.3f} |"
        rows.append(row)

    return "\n".join([header, sep, *rows])


class DriftMonitorAgent(BaseAgent):
    spec = AgentSpec(
        key="drift_monitor",
        name="Drift Monitor",
        layer="Ops",
        sdlc_phase="Deployment and monitoring",
        description=(
            "Watches production telemetry for fairness and representativeness "
            "drift, instantiating the NIST Measure and Manage functions."
        ),
        grounding_sources=["nist_ai_rmf"],
        upstream_keys=["risk_classification", "requirements_review"],
        required_upstream=["risk_classification"],  # Ops adoptable after Product
        output_key="drift_report",
        input_fields=[
            InputField(
                key="telemetry_csv",
                label="Production telemetry (CSV)",
                help=(
                    "Columns: window,group,selection_rate[,accuracy]. "
                    "One row per time-window x demographic group."
                ),
                kind="csv",
            ),
            InputField(
                key="context_notes",
                label="Operational context (optional)",
                help="Anything the on-call team knows: data source changes, seasonality, incidents.",
            ),
        ],
        task_prompt=(
            "Analyze the fairness metrics computed below (computed by code from "
            "the raw telemetry — treat the numbers as ground truth; NEVER alter "
            "or invent metric values). Compare drift across windows against any "
            "thresholds defined in the upstream ethical requirements (e.g. "
            "demographic parity difference <= 0.1). Apply the NIST AI RMF "
            "MEASURE and MANAGE functions. Structure as:\n"
            "## Drift Alerts\n"
            "(one alert per violated or trending-toward-violation threshold, with "
            "severity and the NIST practice cited)\n"
            "## Fairness & Representativeness Analysis\n"
            "(interpretation of the computed metrics across windows)\n"
            "## Recommended Actions\n"
            "(MANAGE-grounded responses: e.g. retraining triggers, human review "
            "of affected decisions, rollback criteria)\n"
            "## Open Issues\n"
            "(ambiguities requiring human arbitration)"
        ),
    )

    def run(
        self,
        repo,
        inputs: Dict[str, str],
        feedback: Optional[List[str]] = None,
    ) -> str:
        """Compute fairness metrics deterministically, then delegate to the LLM."""
        csv_text = inputs.get("telemetry_csv", "")
        try:
            summary = compute_fairness_summary(csv_text)
            summary_block = f"### Computed fairness metrics (by code)\n\n{summary}"
        except ValueError as exc:
            summary_block = f"### Telemetry problem\n\n{exc}"

        # Inject the computed table as an extra input the LLM must rely on.
        enriched = dict(inputs)
        enriched["computed_metrics"] = summary_block
        # Temporarily surface it as an input field so BaseAgent renders it.
        return super().run(repo, {**enriched, "telemetry_csv": summary_block}, feedback)
