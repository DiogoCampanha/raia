"""
raia.contract.actions
=====================

The project's action plan: every action from every approved record, in one
list sorted by priority, with the finding, principle and NIST AI RMF category
it answers and the owner, lifecycle stage, review cadence, verification method
and evidence artifact the Microsoft RAI Standard v2 requirement pattern and
IEEE 7000 ask for.

It is read from the approved records only — a draft under review contributes
nothing — and it is exported as CSV and JSON so a team can load it into
whatever tracker it already uses.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict, List

from . import vocab as V

COLUMNS = [
    "id", "priority", "stage", "action", "response", "owner_role", "lifecycle_stage",
    "review_cadence", "verification_method", "evidence_artifact", "findings",
    "principles", "nist_categories", "blocking", "artifact",
]


def project_actions(repo: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for key in repo.existing_artifacts():
        record = ((repo.read_data(key) or {}).get("structured") or {}).get("record") or {}
        if not record:
            continue
        findings = {f.get("id"): f for f in record.get("findings") or []}
        stage = (record.get("meta") or {}).get("agent_name", key)
        for a in record.get("actions") or []:
            linked = [findings[f] for f in a.get("finding_ids") or [] if f in findings]
            rows.append({
                "id": a.get("id"),
                "priority": a.get("priority") or "medium",
                "stage": stage,
                "action": a.get("action", ""),
                "response": a.get("response", ""),
                "owner_role": a.get("owner_role", ""),
                "lifecycle_stage": a.get("lifecycle_stage", ""),
                "review_cadence": a.get("review_cadence", ""),
                "verification_method": a.get("verification_method", ""),
                "evidence_artifact": a.get("evidence_artifact", ""),
                "findings": "; ".join(f"{f.get('id')} {f.get('title', '')}" for f in linked),
                "principles": "; ".join(dict.fromkeys(V.PRINCIPLE_NAMES.get(f.get("principle"), f.get("principle", "")) for f in linked)),
                "nist_categories": "; ".join(dict.fromkeys(f.get("nist_category", "") for f in linked)),
                "blocking": any(f.get("blocking") for f in linked),
                "artifact": key,
            })
    rows.sort(key=lambda r: (-V.rank(V.PRIORITIES, r["priority"]), r["id"] or ""))
    return rows


def to_csv(rows: List[Dict[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return buffer.getvalue()


def to_json(rows: List[Dict[str, Any]]) -> str:
    return json.dumps({"schema": V.SCHEMA_VERSION, "actions": rows}, indent=2, ensure_ascii=False)


def summary(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    out = {p: 0 for p in reversed(V.PRIORITIES)}
    for r in rows:
        out[r["priority"]] = out.get(r["priority"], 0) + 1
    return out
