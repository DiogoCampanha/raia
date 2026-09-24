"""
raia.contract.mock
==================

A conforming record built from the contract hints, for the offline test
double in :mod:`raia.llm`. It exercises every field of the shared core and of
each agent's extension, so rendering, finalisation and the validators can be
tested end to end without a model. It is not an analysis, and says so.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from .prompt import HINTS_MARKER

MOCK_NOTE = "[MOCK MODE] No model was called; this record conforms to the contract but is not an analysis."


def read_hints(prompt: str) -> Dict[str, Any]:
    for line in reversed(prompt.splitlines()):
        if line.strip().startswith(HINTS_MARKER):
            try:
                return json.loads(line.split(HINTS_MARKER, 1)[1].strip())
            except ValueError:
                return {}
    return {}


def _finding(cite: List[str], links: List[str], principle: str = "accountability",
             category: str = "MAP 5") -> Dict[str, Any]:
    return {
        "id": "F1", "title": "Placeholder finding from mock mode", "statement": MOCK_NOTE,
        "principle": principle, "nist_category": category, "magnitude": "significant",
        "likelihood": "possible", "placement_rationale": "Mock placement.",
        "stakeholders": ["affected persons"], "citations": cite, "links": links,
    }


def build(prompt: str) -> Dict[str, Any]:
    h = read_hints(prompt)
    key = h.get("agent_key", "")
    cite = (h.get("citations") or [])[:1]
    ids = h.get("ids") or {}
    verdict = {k: (", ".join(map(str, v)) if isinstance(v, list) else str(v))
               for k, v in (h.get("computed_verdict") or {}).items()}

    links: List[str] = []
    ext: Dict[str, Any] = {}
    if key == "risk_classifier":
        links = list(ids.get("obligation_codes") or [])[:1]
        ext = {
            "prohibited_screen": MOCK_NOTE, "eu_tier_justification": MOCK_NOTE,
            "br_tier_justification": MOCK_NOTE,
            "obligations": [{"code": c, "meaning_for_this_product": MOCK_NOTE, "citations": cite}
                            for c in ids.get("obligation_codes") or []],
            "human_oversight_assessment": MOCK_NOTE, "affected_persons_rights": MOCK_NOTE,
            "impact_assessments": MOCK_NOTE,
        }
    elif key == "requirements_reviewer":
        evrs = ids.get("evr_ids") or []
        links = evrs[:1]
        ext = {
            "context_of_use": MOCK_NOTE,
            "stakeholders": [{"name": "affected persons", "kind": "indirect", "values": ["fairness"]}],
            "value_register": [{"value": "fairness", "rank": 1, "threats": MOCK_NOTE, "opportunities": MOCK_NOTE}],
            "gap_analysis": [{"evr_id": e, "explanation": MOCK_NOTE, "citations": cite} for e in evrs],
            "evrs": [{"id": e, "value": "fairness", "stakeholders": ["affected persons"],
                      "statement": "Outcomes shall be auditable per protected attribute.",
                      "fit_criterion": "An audit report per protected attribute exists for each release.",
                      "verification_method": "audit", "traces_to": [], "citations": cite} for e in evrs],
            "impact_assessment": {"intended_uses": MOCK_NOTE,
                                  "harms_and_benefits": [{"stakeholder": "affected persons", "harms": MOCK_NOTE, "benefits": MOCK_NOTE}],
                                  "mitigations": MOCK_NOTE},
        }
    elif key == "story_refiner":
        stories = ids.get("story_ids") or []
        cards = ids.get("card_ids") or []
        links = stories[:1]
        entries = []
        for i, sid in enumerate(stories):
            if i == 0:
                entries.append({"story_id": sid, "eccola_cards": cards[:1], "card_discussion": MOCK_NOTE,
                                "criteria": [{"id": f"AC-{sid}-1", "ms_goal": "F2", "stakeholder_group": "applicants",
                                              "condition": "Measured selection-rate test passes the threshold.",
                                              "evidence_artifact": "evaluation report", "owner_role": "data_science",
                                              "evr_ids": (ids.get("evr_ids") or [])[:1]}]})
            else:
                entries.append({"story_id": sid, "no_impact_reason": MOCK_NOTE})
        ext = {"stories": entries, "sprint_ethics_log": MOCK_NOTE}
    elif key == "auditor":
        items = ids.get("audit_items") or {}
        links = list(items)[:1]
        ext = {
            "items": [{"item_id": i, "verdict": "not_verified", "evidence": "", "evidence_needed": MOCK_NOTE,
                       "citations": cite} for i in items],
            "accountability_log": [{"decision": MOCK_NOTE, "decided_by": "reviewer", "artifact": "risk_classification"}],
            "upcoming_checkpoints": [{"checkpoint": MOCK_NOTE, "triggered_by": "planned epics",
                                      "item_ids": list(items)[:1], "lifecycle_stage": "verify_and_validate"}],
        }
    elif key == "drift_monitor":
        sev = ids.get("breach_severities") or {}
        links = list(sev)[:1]
        ext = {
            "alerts": [{"window": w, "severity": s, "meaning_for_affected_people": MOCK_NOTE, "citations": cite}
                       for w, s in sev.items()],
            "trend_interpretation": MOCK_NOTE, "representativeness": MOCK_NOTE, "sample_adequacy": [],
            "response_plan": {"escalation_path": MOCK_NOTE, "deactivation_criteria": MOCK_NOTE,
                              "affected_community_feedback": MOCK_NOTE, "recovery_and_communication": MOCK_NOTE},
        }

    return {
        "summary": MOCK_NOTE,
        "overall_status": "needs_attention",
        "declared_verdict": verdict,
        "agrees_with_rule_engine": True,
        "disagreement_rationale": "",
        "findings": [_finding(cite, links)],
        "actions": [{
            "id": "A1", "finding_ids": ["F1"], "action": "Placeholder action from mock mode.",
            "response": "mitigate", "owner_role": "product", "lifecycle_stage": "plan_and_design",
            "review_cadence": "every_release", "verification_method": "inspection",
            "evidence_artifact": "placeholder artifact", "citations": cite, "links": [],
        }],
        "open_issues": [],
        "not_grounded": [],
        "coverage": [{"key": k, "status": "covered", "justification": "Placeholder declaration from mock mode."}
                     for k in h.get("checklist_keys") or []],
        "extension": ext,
    }


def recommend(h: Dict[str, Any]) -> Dict[str, Any]:
    """Candidate requirements for the Requirements Reviewer's recommendation, in mock mode."""
    cite = (h.get("citations") or [])[:1]
    refs = (h.get("gap_refs") or [])[: int(h.get("max") or 5)]
    return {"candidates": [{
        "addresses": ref,
        "value": "accountability",
        "statement": f"[MOCK MODE] The team shall record how {ref} is met for each release.",
        "fit_criterion": f"A signed-off record for {ref} exists for every release.",
        "verification_method": "audit",
        "citations": cite,
    } for ref in refs]}


def reply(prompt: str) -> str:
    h = read_hints(prompt)
    if h.get("agent_key") == "requirements_reviewer:recommend":
        return "```json\n" + json.dumps(recommend(h), ensure_ascii=False, indent=1) + "\n```"
    return "```json\n" + json.dumps(build(prompt), ensure_ascii=False, indent=1) + "\n```"
