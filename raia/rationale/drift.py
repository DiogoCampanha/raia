"""
raia.rationale.drift
====================

Deterministic fairness analysis for the Drift Monitor.

This agent already computed its metrics in code — the pattern the rest of the
system was rebuilt around. What it lacked was everything surrounding the
numbers: the thresholds it was judging them against came from the model's
reading of upstream prose, group sizes were never reported, no trend was
computed, and alert severity was a matter of tone.

Here the thresholds are *parsed* out of the approved upstream artifacts, the
breach, the trend and the severity are computed, and every group below a
minimum sample size is labelled as unable to support a conclusion. A parity
gap measured on twelve observations must not render identically to one
measured on a hundred thousand.
"""

import io
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .. import config
from ..fields import chosen, options, text_of
from .types import ChecklistItem, Finding, Pin, RationaleResult, md_table

SECTION_NIST_MEASURE = "MEASURE (analysis and tracking)"
SECTION_NIST_MANAGE = "MANAGE (response and recovery)"
SECTION_NIST_MONITORING = "Post-Deployment Monitoring Guidance (Measure/Manage in Practice)"

INCIDENT_OPTIONS = options(
    ("none", "No incident — routine monitoring"),
    ("complaint", "A complaint or contestation was received"),
    ("regression", "A metric regression was noticed by the team"),
    ("outage", "An outage or data-pipeline failure occurred in the window"),
)

REQUIRED_COLUMNS = {"window", "group", "selection_rate"}

#: Metric phrases that may carry a threshold in an approved upstream artifact.
_THRESHOLD_RE = re.compile(
    r"(?P<metric>demographic parity difference|parity difference|statistical parity|"
    r"selection[- ]rate (?:gap|difference)|accuracy gap|accuracy difference)"
    r"(?P<middle>[^.\n]{0,90}?)"
    r"(?P<op><=|≤|<|of at most|at most|no more than|not exceed(?:ing)?|below|under)\s*"
    r"(?P<value>\d*\.?\d+)\s*(?P<pct>%)?",
    re.I,
)


def parse_thresholds(*texts: str) -> Dict[str, Dict[str, Any]]:
    """Extract fairness thresholds from approved upstream artifacts.

    The strictest value found for each metric wins, and the phrase it came from
    is recorded so a human can check the reading. When nothing is found, the
    caller falls back to a configured default that is always labelled as one.
    """
    found: Dict[str, Dict[str, Any]] = {}
    for text in texts:
        for m in _THRESHOLD_RE.finditer(text or ""):
            metric = m.group("metric").lower()
            key = "accuracy_gap" if "accuracy" in metric else "parity_difference"
            value = float(m.group("value"))
            if m.group("pct") or value > 1:
                value = value / 100.0
            quote = re.sub(r"\s+", " ", m.group(0)).strip()
            if key not in found or value < found[key]["value"]:
                found[key] = {"value": value, "source": "approved upstream artifact", "quote": quote}
    return found


def analyse(csv_text: str, thresholds: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Compute per-window fairness metrics, breaches, trend and sample adequacy.

    Expected columns: ``window``, ``group``, ``selection_rate``; optionally
    ``accuracy`` and ``n`` (observations behind the row).
    """
    try:
        df = pd.read_csv(io.StringIO((csv_text or "").strip()))
    except Exception as exc:
        raise ValueError(f"Could not parse the telemetry: {exc}") from exc

    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Telemetry is missing required column(s): {', '.join(sorted(missing))}. "
            "Expected header: window,group,selection_rate[,accuracy][,n]"
        )

    has_acc = "accuracy" in df.columns
    has_n = "n" in df.columns
    parity_t = thresholds.get("parity_difference", {}).get("value")
    acc_t = thresholds.get("accuracy_gap", {}).get("value")

    windows: List[Dict[str, Any]] = []
    for window, g in df.groupby("window", sort=True):
        sr = pd.to_numeric(g.set_index("group")["selection_rate"], errors="coerce").dropna()
        if sr.empty:
            continue
        dp = float(sr.max() - sr.min())
        row: Dict[str, Any] = {
            "window": str(window),
            "dp_difference": round(dp, 4),
            "highest": {"group": str(sr.idxmax()), "rate": round(float(sr.max()), 4)},
            "lowest": {"group": str(sr.idxmin()), "rate": round(float(sr.min()), 4)},
            "groups": int(sr.size),
        }
        if has_acc:
            acc = pd.to_numeric(g.set_index("group")["accuracy"], errors="coerce").dropna()
            row["accuracy_gap"] = round(float(acc.max() - acc.min()), 4) if not acc.empty else None
        if has_n:
            counts = pd.to_numeric(g.set_index("group")["n"], errors="coerce").fillna(0)
            row["total_n"] = int(counts.sum())
            row["min_group_n"] = int(counts.min())
            row["small_groups"] = [
                str(k) for k, v in counts.items() if v < config.MIN_GROUP_SAMPLES
            ]
            total = float(counts.sum()) or 1.0
            row["shares"] = {str(k): round(float(v) / total, 4) for k, v in counts.items()}
        row["parity_breach"] = bool(parity_t is not None and dp > parity_t)
        if has_acc and acc_t is not None and row.get("accuracy_gap") is not None:
            row["accuracy_breach"] = bool(row["accuracy_gap"] > acc_t)
        windows.append(row)

    trend: Dict[str, Any] = {}
    if len(windows) >= 2:
        first, last = windows[0]["dp_difference"], windows[-1]["dp_difference"]
        series = [w["dp_difference"] for w in windows]
        trend = {
            "first_window": windows[0]["window"],
            "last_window": windows[-1]["window"],
            "first_value": first,
            "last_value": last,
            "delta": round(last - first, 4),
            "direction": "widening" if last > first else ("narrowing" if last < first else "flat"),
            "monotonic": all(b >= a for a, b in zip(series, series[1:]))
            or all(b <= a for a, b in zip(series, series[1:])),
        }

    representativeness: List[str] = []
    if has_n and len(windows) >= 2 and windows[0].get("shares") and windows[-1].get("shares"):
        first_shares, last_shares = windows[0]["shares"], windows[-1]["shares"]
        for grp, first_share in first_shares.items():
            last_share = last_shares.get(grp)
            if last_share is None:
                representativeness.append(f"{grp} disappears from the data by {windows[-1]['window']}")
            elif first_share > 0 and abs(last_share - first_share) / first_share >= 0.3:
                representativeness.append(
                    f"{grp} moves from {first_share} to {last_share} of the population"
                )

    return {
        "windows": windows,
        "trend": trend,
        "representativeness": representativeness,
        "has_accuracy": has_acc,
        "has_counts": has_n,
        "rows": int(len(df)),
    }


def _severity(window: Dict[str, Any], trend: Dict[str, Any], threshold: Optional[float]) -> Optional[str]:
    if threshold is None:
        return None
    dp = window["dp_difference"]
    if dp > threshold:
        widening = trend.get("direction") == "widening" and trend.get("monotonic")
        return "high" if widening else "medium"
    if dp >= 0.8 * threshold:
        return "low"
    return None


def summary_table(analysis: Dict[str, Any], threshold: Optional[float]) -> str:
    headers = ["Window", "Parity difference", "Highest", "Lowest"]
    if analysis["has_accuracy"]:
        headers.append("Accuracy gap")
    if analysis["has_counts"]:
        headers += ["Observations", "Smallest group"]
    headers += ["Breach", "Severity"]

    rows: List[List[str]] = []
    for w in analysis["windows"]:
        row = [
            w["window"],
            f"{w['dp_difference']:.4f}",
            f"{w['highest']['group']} ({w['highest']['rate']:.4f})",
            f"{w['lowest']['group']} ({w['lowest']['rate']:.4f})",
        ]
        if analysis["has_accuracy"]:
            gap = w.get("accuracy_gap")
            row.append(f"{gap:.4f}" if gap is not None else "—")
        if analysis["has_counts"]:
            row += [str(w.get("total_n", "—")), str(w.get("min_group_n", "—"))]
        row.append("yes" if w.get("parity_breach") else ("—" if threshold is not None else "no threshold"))
        row.append(_severity(w, analysis["trend"], threshold) or "—")
        rows.append(row)
    return md_table(headers, rows)


def allowed_numbers(analysis: Dict[str, Any], thresholds: Dict[str, Dict[str, Any]]) -> List[str]:
    """Every figure the narrative is allowed to contain."""
    out: List[str] = []

    def push(v: Any) -> None:
        if v is None:
            return
        out.append(str(v))
        if isinstance(v, float):
            out.extend([f"{v:.4f}", f"{v:.3f}", f"{v:.2f}", f"{v:.1f}",
                        f"{v * 100:.1f}", f"{v * 100:.0f}"])

    for w in analysis["windows"]:
        push(w["dp_difference"])
        push(w["highest"]["rate"])
        push(w["lowest"]["rate"])
        push(w.get("accuracy_gap"))
        push(w.get("total_n"))
        push(w.get("min_group_n"))
        for share in (w.get("shares") or {}).values():
            push(share)
    for key in ("first_value", "last_value", "delta"):
        push(analysis["trend"].get(key))
    for t in thresholds.values():
        push(t.get("value"))
    push(config.MIN_GROUP_SAMPLES)
    return sorted({o for o in out})


def run(inputs: Dict[str, Any], upstream: Dict[str, Any]) -> RationaleResult:
    r = RationaleResult(engine="drift_analysis")

    csv_text = text_of(inputs, "telemetry_csv")
    notes = text_of(inputs, "context_notes")
    incident = chosen(inputs, "incident", "none")

    risk = (upstream.get("risk_classification") or {}).get("data") or {}
    review_text = (upstream.get("requirements_review") or {}).get("text") or ""
    stories_text = (upstream.get("refined_stories") or {}).get("text") or ""

    thresholds = parse_thresholds(stories_text, review_text)
    if "parity_difference" not in thresholds:
        thresholds["parity_difference"] = {
            "value": config.DEFAULT_PARITY_THRESHOLD,
            "source": "system default — no threshold found in the approved artifacts",
            "quote": "",
        }
    parity_t = thresholds["parity_difference"]["value"]

    try:
        analysis = analyse(csv_text, thresholds)
    except ValueError as exc:
        r.notes.append(str(exc))
        r.findings.append(Finding("telemetry.invalid", "Telemetry could not be analysed", str(exc)))
        r.checklist = [ChecklistItem("telemetry", "Explain what is wrong with the telemetry and what is needed")]
        r.pins = [Pin("nist_ai_rmf", SECTION_NIST_MEASURE, "measurement requirements")]
        r.verdict = {"analysed": False}
        r.data["error"] = str(exc)
        return r

    if not analysis["windows"]:
        r.notes.append("The telemetry parsed but contained no usable rows.")
        r.verdict = {"analysed": False}
        return r

    r.tables["Fairness metrics computed by code (ground truth — never restate a different number)"] = (
        summary_table(analysis, parity_t)
    )

    t = thresholds["parity_difference"]
    r.findings.append(
        Finding(
            "threshold.parity",
            f"Parity threshold in force: {t['value']}",
            t["quote"] or t["source"],
        )
    )
    if "accuracy_gap" in thresholds:
        ta = thresholds["accuracy_gap"]
        r.findings.append(
            Finding("threshold.accuracy", f"Accuracy-gap threshold: {ta['value']}", ta["quote"] or ta["source"])
        )

    breaches = [w for w in analysis["windows"] if w.get("parity_breach")]
    approaching = [
        w for w in analysis["windows"]
        if not w.get("parity_breach") and w["dp_difference"] >= 0.8 * parity_t
    ]
    if breaches:
        r.findings.append(
            Finding("drift.breach", f"{len(breaches)} window(s) breach the parity threshold",
                    ", ".join(w["window"] for w in breaches))
        )
    if approaching:
        r.findings.append(
            Finding("drift.approaching", f"{len(approaching)} window(s) within 80% of the threshold",
                    ", ".join(w["window"] for w in approaching))
        )
    if analysis["trend"]:
        tr = analysis["trend"]
        r.findings.append(
            Finding("drift.trend", f"Gap is {tr['direction']} across windows",
                    f"{tr['first_value']} at {tr['first_window']} → {tr['last_value']} at "
                    f"{tr['last_window']} (delta {tr['delta']}"
                    + (", monotonic)" if tr["monotonic"] else ")"))
        )

    # -- Sample adequacy ------------------------------------------------------

    if not analysis["has_counts"]:
        r.notes.append(
            "The telemetry carries no `n` column, so no figure below can be judged for statistical "
            "adequacy. Say so explicitly: a parity difference without group sizes cannot support a "
            "conclusion, only a question. Add an `n` column to the export."
        )
    else:
        small = sorted({g for w in analysis["windows"] for g in (w.get("small_groups") or [])})
        if small:
            r.findings.append(
                Finding("samples.small",
                        f"{len(small)} group(s) fall below {config.MIN_GROUP_SAMPLES} observations",
                        ", ".join(small) + " — report their figures as indicative only")
            )
    if analysis["representativeness"]:
        r.findings.append(
            Finding("representativeness.shift", "The population mix changed across windows",
                    "; ".join(analysis["representativeness"]))
        )

    # -- Open issues -----------------------------------------------------------

    if thresholds["parity_difference"]["source"].startswith("system default"):
        r.raise_issue(
            "No fairness threshold was found in the approved artifacts, so a system default was "
            "applied. The threshold this product is held to is a human decision and should be "
            "written into an ethical requirement.",
            type="missing_information", decision_owner="product", blocking=False,
        )
    if breaches and not (risk.get("eu_is_high_risk") or risk.get("br_is_high_risk")):
        r.raise_issue(
            "A threshold is breached on a system not classified high-risk. Confirm the "
            "classification still holds, or record why the breach is acceptable.",
            type="missing_information", decision_owner="legal_compliance", blocking=False,
        )
    if incident != "none":
        r.raise_issue(
            f"An operational event was declared ({incident}). Whether it explains the metric "
            "movement, or is a separate failure, needs a human judgement.",
            type="missing_information", decision_owner="operations", blocking=False,
        )
    if notes:
        r.notes.append(
            "The on-call team supplied operational context; weigh it when interpreting the "
            "movement, but do not let it override a breach."
        )

    r.pins = [
        Pin("nist_ai_rmf", SECTION_NIST_MEASURE, "measurement and tracking"),
        Pin("nist_ai_rmf", SECTION_NIST_MANAGE, "response and recovery"),
        Pin("nist_ai_rmf", SECTION_NIST_MONITORING, "post-deployment monitoring"),
    ]

    r.checklist = [
        ChecklistItem("alerts", "Raise one alert per computed breach, with its severity"),
        ChecklistItem("interpretation", "Interpret the movement across windows, including the trend"),
        ChecklistItem("adequacy", "State where sample sizes do not support a conclusion"),
        ChecklistItem("actions", "Recommend responses grounded in the retrieved management practices"),
        ChecklistItem("open_issues", "Carry forward every open issue raised here, plus any you add"),
    ]

    r.verdict = {
        "analysed": True,
        "windows": len(analysis["windows"]),
        "breaches": [w["window"] for w in breaches],
        "trend": analysis["trend"].get("direction", "unknown"),
        "parity_threshold": parity_t,
    }
    r.query_terms = [
        "fairness drift monitoring", "demographic parity", "post-deployment monitoring",
        "incident response", analysis["trend"].get("direction", ""),
    ]
    r.data.update(
        {
            "thresholds": thresholds,
            "analysis": analysis,
            "incident": incident,
            "allowed_numbers": allowed_numbers(analysis, thresholds),
        }
    )
    return r
