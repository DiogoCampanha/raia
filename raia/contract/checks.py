"""
raia.contract.checks
====================

Deterministic checks on a finalised RAIA record.

They sit beside the text-level validators in :mod:`raia.validators` (which
still run on the rendered Markdown — citations, sections, coverage, numbers)
and check what only a structured record can show: that it conforms to its
schema, that every finding received a response, that every identifier the rule
engine assigned is accounted for, and that code had to correct nothing the
model asserted. Like every validator, they inform the reviewer and never block.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Sequence

from ..validators import FAIL, PASS, WARN, ValidationItem


def check_schema(record: Dict[str, Any], repairs: int = 0) -> ValidationItem:
    errors = record.get("schema_errors") or []
    if errors:
        tail = (f" after {repairs} retry attempt(s)" if repairs else
                " and no retry was possible")
        if record.get("truncated"):
            detail = (
                "The model's reply was cut off at the token limit" + tail + ", so it could not be "
                "read as a RAIA record. No analysis from this attempt can be relied on — reject to "
                "regenerate. If it recurs, raise RAIA_LLM_MAX_TOKENS or split what the stage covers."
            )
        else:
            detail = (
                "The model's reply did not validate against the RAIA record schema" + tail + ". No "
                "analysis from this attempt can be relied on — reject to regenerate."
            )
        return ValidationItem("contract.schema_invalid", FAIL, "Output contract", detail, list(errors))
    tail = f" after {repairs} repair attempt(s)" if repairs else ""
    return ValidationItem("contract.schema_valid", PASS, "Output contract",
                          f"The record conforms to {record.get('meta', {}).get('schema_version', 'the schema')}{tail}.")


def check_corrections(record: Dict[str, Any]) -> List[ValidationItem]:
    notes = record.get("contract_notes") or []
    upgrades = [n for n in notes if n.startswith("UPGRADE:")]
    severities = [n for n in notes if n.startswith("SEVERITY:")]
    shortened = [n for n in notes if n.startswith("SHORTENED:")]
    strengths = [n for n in notes if n.startswith("STRENGTH:")]
    other = [n for n in notes if n not in upgrades and n not in severities and n not in shortened
             and n not in strengths]
    out: List[ValidationItem] = []
    if upgrades:
        out.append(ValidationItem(
            "verdicts.upgraded", FAIL, "Evidence discipline",
            "The model reported item(s) with no evidence as satisfied. Code restored them to not "
            "verified; the attempt itself overreached.", upgrades))
    if severities:
        out.append(ValidationItem(
            "severity.altered", FAIL, "Computed severity",
            "The model restated a severity the engine computed. Code restored the computed value.",
            severities))
    if strengths:
        out.append(ValidationItem(
            "strengths.unsupported", WARN, "Evidence discipline",
            "The model stated strength(s) that no satisfied item and no approval on record supports. "
            "Code removed them: a strength needs evidence as much as a verdict does.",
            [n.split(":", 1)[1].strip() for n in strengths]))
    if shortened:
        out.append(ValidationItem(
            "contract.shortened", WARN, "Length limits",
            f"The model wrote past {len(shortened)} length limit(s). Code shortened those values at a "
            "sentence or word end instead of discarding the reply; check that nothing important was cut.",
            [n.split(":", 1)[1].strip() for n in shortened]))
    if other:
        out.append(ValidationItem("contract.corrected", WARN, "Corrections applied by code",
                                  f"{len(other)} correction(s) were applied to the record.", other))
    if not out:
        out.append(ValidationItem("contract.uncorrected", PASS, "Corrections applied by code",
                                  "Code did not need to correct anything the model asserted."))
    return out


def check_responses(record: Dict[str, Any]) -> ValidationItem:
    """NIST AI RMF MANAGE 1: every identified risk is responded to."""
    findings = record.get("findings") or []
    if not findings:
        if record.get("schema_errors"):
            return ValidationItem("findings.none", WARN, "Risk responses", "No findings to respond to.")
        return ValidationItem("findings.none", WARN, "Risk responses",
                              "The record contains no findings. Check that this stage really found nothing.")
    answered = {fid for a in record.get("actions") or [] for fid in a.get("finding_ids") or []}
    answered |= {l for i in record.get("open_issues") or [] for l in i.get("links") or []}
    missing = [f"{f['id']} ({f.get('priority')}): {f.get('title', '')}" for f in findings if f["id"] not in answered]
    if missing:
        severe = any("(high)" in m or "(critical)" in m for m in missing)
        return ValidationItem(
            "findings.unanswered", FAIL if severe else WARN, "Risk responses",
            f"{len(missing)} finding(s) have no action and no open issue. Every identified risk needs "
            "a response: mitigate, transfer, avoid, or a recorded acceptance.", missing)
    unlinked = [a["id"] for a in record.get("actions") or [] if not a.get("finding_ids")]
    if unlinked:
        return ValidationItem("actions.unlinked", WARN, "Risk responses",
                              "Action(s) that respond to no finding: priority defaults to medium.", unlinked)
    return ValidationItem("findings.answered", PASS, "Risk responses",
                          f"All {len(findings)} finding(s) have a response.")


def check_registered_ids(label: str, code: str, expected: Sequence[str], present: Iterable[str],
                         strict_unknown: bool = True, require_all: bool = True) -> ValidationItem:
    expected_set, present_list = list(dict.fromkeys(expected)), [p for p in present if p]
    missing = [e for e in expected_set if e not in present_list] if require_all else []
    unknown = sorted({p for p in present_list if p not in expected_set}) if strict_unknown else []
    if missing or unknown:
        return ValidationItem(
            f"{code}.mismatch", FAIL, label,
            f"{len(missing)} computed id(s) missing, {len(unknown)} id(s) not in the computed register.",
            [f"missing: {m}" for m in missing] + [f"unknown: {u}" for u in unknown])
    return ValidationItem(f"{code}.match", PASS, label,
                          f"All {len(expected_set)} computed identifiers are accounted for, and no others.")


AC_RE = re.compile(r"^AC-(S\d+|[A-Za-z]+-?\d+)-\d+$")


def check_criteria_ids(record: Dict[str, Any]) -> ValidationItem:
    bad = []
    for s in (record.get("extension") or {}).get("stories") or []:
        for c in s.get("criteria") or []:
            cid = str(c.get("id", ""))
            if not cid.startswith(f"AC-{s.get('story_id')}-") or not cid.rsplit("-", 1)[-1].isdigit():
                bad.append(f"{cid} under {s.get('story_id')}")
    if bad:
        return ValidationItem("criteria.ids", WARN, "Criterion identifiers",
                              "Criteria must be labelled AC-<story id>-<n> under their own story.", bad)
    return ValidationItem("criteria.ids", PASS, "Criterion identifiers", "Every criterion id follows the convention.")


_SKIP_KEYS = {"citations", "id", "item_id", "story_id", "evr_id", "window", "severity", "links",
              "finding_ids", "evr_ids", "code", "meta", "computed_verdict", "contract_notes",
              "schema_errors", "declared_verdict", "coverage", "priority_basis", "risk_level"}


def narrative_text(record: Dict[str, Any]) -> str:
    """All model-written prose in a record, without identifiers or citations."""
    out: List[str] = []

    def walk(node: Any, key: str = "") -> None:
        if key in _SKIP_KEYS:
            return
        if isinstance(node, str):
            out.append(node)
        elif isinstance(node, dict):
            for k, v in node.items():
                walk(v, k)
        elif isinstance(node, list):
            for v in node:
                walk(v, key)

    walk(record)
    return "\n".join(out)
