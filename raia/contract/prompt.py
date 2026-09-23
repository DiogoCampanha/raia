"""
raia.contract.prompt
====================

The output contract as the model is shown it: the JSON Schema of its record,
the anchored scales, the identifiers it must use, and the division of labour
(what it decides, what code decides).

The last line is a machine-readable hint block. It repeats, as JSON, what the
prose above already says; the offline test double reads it to build a
conforming record without parsing prose.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from ..rationale.types import RationaleResult
from . import rubric
from . import vocab as V
from .assemble import drift_severities
from .schema import model_facing_schema

HINTS_MARKER = "RAIA-RECORD-HINTS:"


def _anchors(title: str, anchors: Dict[str, str]) -> str:
    return f"**{title}**\n" + "\n".join(f"- `{k}` — {v}" for k, v in anchors.items())


def hints(agent_key: str, verdict_keys: List[str], rationale: RationaleResult,
          citations: List[str]) -> Dict[str, Any]:
    data = rationale.data or {}
    verdict = rationale.verdict or {}
    ids: Dict[str, Any] = {}
    if agent_key == "risk_classifier":
        ids["obligation_codes"] = [o.get("code") for o in data.get("obligations") or []]
    if agent_key == "requirements_reviewer":
        ids["evr_ids"] = list(verdict.get("evr_ids") or [])
    if agent_key == "story_refiner":
        ids["story_ids"] = list(verdict.get("story_ids") or [])
        ids["card_ids"] = list(verdict.get("card_ids") or [])
        ids["evr_ids"] = list(verdict.get("evr_ids") or [])
    if agent_key == "auditor":
        ids["audit_items"] = {str(i.get("id")): i.get("computed_verdict")
                              for i in data.get("audited_items") or []}
        ids["not_verified"] = list(verdict.get("not_verified") or [])
    if agent_key == "drift_monitor":
        ids["breach_severities"] = drift_severities(rationale)
    return {
        "agent_key": agent_key,
        "verdict_keys": list(verdict_keys),
        "computed_verdict": {k: verdict.get(k) for k in verdict_keys},
        "checklist_keys": rationale.checklist_keys(),
        "citations": citations[:4],
        "ids": ids,
    }


def contract_text(agent_key: str, verdict_keys: List[str], rationale: RationaleResult,
                  citations: List[str]) -> str:
    schema = json.dumps(model_facing_schema(agent_key), ensure_ascii=False, separators=(",", ":"))
    h = hints(agent_key, verdict_keys, rationale, citations)
    id_lines = "\n".join(f"- `{k}`: {json.dumps(v, ensure_ascii=False)}" for k, v in h["ids"].items()) or "- (none)"
    return f"""## Output contract (non-negotiable)

Reply with ONE JSON object inside a ```json fence, and nothing else. It is validated against
this JSON Schema ({V.SCHEMA_VERSION}); a reply that does not validate is returned to you:

```json
{schema}
```

### What you decide, and what code decides

- You identify **findings** and place each one on two anchored scales: impact **magnitude** and
  **likelihood** (NIST AI RMF MAP 5), with a `placement_rationale`. You do **not** assign risk
  level, priority or blocking: code computes them from the matrix below and raises them where a
  legal obligation, a prohibited practice or a computed severity requires it.
- For every finding, propose at least one **action** with a risk response (NIST AI RMF MANAGE 1),
  an accountable `owner_role`, the `lifecycle_stage`, a `review_cadence`, how completion is
  verified (test, audit, measurement or inspection) and the `evidence_artifact` that will show it.
  Choosing `accept` always opens an issue: only a person can accept a risk.
- Use local ids (`F1`, `A1`, `I1`) and reference findings by them. Code assigns the final ids.
- The rule engine's open issues are carried forward by code with their type and owner. Do not
  repeat them in `open_issues`; add only issues you raise.
- `declared_verdict` must contain exactly these keys: {", ".join(verdict_keys) or "(none)"}. Set
  `agrees_with_rule_engine` honestly; if false, argue it in `disagreement_rationale`.
- `coverage` must contain exactly one entry per checklist key: {", ".join(h["checklist_keys"]) or "(none)"}.
- Every `citations` entry is a tag copied exactly from the retrieved excerpts.
- Write for the people who will act on it: specific to this product, short enough to review.
- Stay inside every `maxLength` in the schema: at most three sentences per free-text field, one
  or two per obligation note. The whole record must fit in a single reply — a reply cut off at
  the token limit cannot be read at all. Where several obligations are met by the same work, say
  so once and refer back to it rather than repeating it.

### Identifiers from the computed block you must use exactly

{id_lines}

### Anchored scales

{_anchors("Magnitude", V.MAGNITUDE_ANCHORS)}

{_anchors("Likelihood", V.LIKELIHOOD_ANCHORS)}

{_anchors("Risk response", V.RESPONSE_ANCHORS)}

**Risk level matrix (applied by code)**

{rubric.matrix_md()}

{HINTS_MARKER} {json.dumps(h, ensure_ascii=False, default=str)}
"""
