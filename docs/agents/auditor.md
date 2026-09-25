# Agent card — Auditor

> Generated from the code by `python -m raia.contract.agent_cards`. Follows `docs/templates/agent-card.md`. Do not edit by hand.

## 1. Purpose

Audits sprint progress against the approved ethical requirements and reports it as an audit: an opinion, strengths, risks, opportunities and the way forward, grounded in versioned evidence.

## 2. Place in the lifecycle

| | |
|---|---|
| Layer | Dev |
| SDLC phase | Development and validation |
| When to run | At the end of a sprint or before a release decision. |
| Requires approved | Requirements Reviewer |
| Reads | Risk Classifier, Requirements Reviewer, User Story Refiner |
| Produces | `05_audit_report.md` — audit record |

## 3. Normative grounding

| Source | Authority |
|---|---|
| Microsoft Responsible AI Standard v2 | standard |
| NIST AI Risk Management Framework 1.0 | advisory |

## 4. Inputs

| Group | Question | Kind | Required |
|---|---|---|---|
| What happened this sprint | Sprint | text | no |
| What happened this sprint | Sprint outcomes | textarea | yes |
| Evidence produced | What evidence did this sprint actually produce? | multiselect | yes |
| What comes next | Planned epics / next steps | textarea | no |

## 5. What the decision procedure settles in code

- Reads the register of approved requirements and acceptance criteria and matches each one to the evidence the sprint produced.
- Refuses to mark anything verified without evidence: an item with no evidence is not verified, whatever the narrative says.
- Rates the audit — not effective, needs improvement, effective with observations or effective — from the final verdicts, priorities and open decisions, never above what the declared evidence allows; removes any strength the evidence does not support.

Checklist the record must declare:

- `verdicts` — Give a verdict and its evidence for every item in the computed table
- `not_verified` — Explain what evidence each NOT VERIFIED item would need
- `accountability` — Record who decided what, from the upstream approval headers
- `upcoming` — Flag the ethical checkpoints the planned work will hit
- `strengths` — State the strengths the evidence supports, and nothing it does not
- `pathway` — Recommend the way forward, in order
- `open_issues` — Carry forward every open issue raised here, plus any you add

Excerpts pinned for the canonical scenario:

- Microsoft Responsible AI Standard v2 — Accountability Goals (accountability documentation)
- NIST AI Risk Management Framework 1.0 — GOVERN (cross-cutting) (governance practices)
- NIST AI Risk Management Framework 1.0 — MEASURE (analysis and tracking) (what counts as measurement evidence)

## 6. What a person decides

- Whether the evidence is sufficient for an accountability record.
- The decisions the pathway forward opens with, and who carries each recommendation.
- What becomes an ethical checkpoint for the next iteration.
- Every open issue the record raises, and whether to approve, edit or reject the record.

## 7. The record it produces

Schema `raia-record/1.2` — `docs/schema/auditor.schema.json`. Identifier prefix `AU`. Shared core as in `docs/output-contract.md`; the extension:

| Field | Content |
|---|---|
| `items` | One entry per computed audit item. |
| `items[].item_id` | A computed audit item id, exactly. |
| `items[].verdict` | — |
| `items[].evidence` | Quoted from the sprint outcomes or an upstream artifact; empty if none. |
| `items[].evidence_needed` | What would verify it, when not satisfied. |
| `items[].downgrade_reason` | — |
| `items[].citations` | Citation tags copied exactly from the retrieved excerpts, e.g. "[Source: ... / authority: legal]". Never invent one. |
| `accountability_log` | Who decided what, from the upstream approval headers (NIST AI RMF GOVERN 2). |
| `accountability_log[].decision` | — |
| `accountability_log[].decided_by` | — |
| `accountability_log[].artifact` | The approved artifact that records it. |
| `accountability_log[].reference` | Commit, date or approval header it was read from. |
| `upcoming_checkpoints` | Ethical checkpoints the planned work will hit. |
| `upcoming_checkpoints[].checkpoint` | — |
| `upcoming_checkpoints[].triggered_by` | The planned epic or event that reaches it. |
| `upcoming_checkpoints[].item_ids` | — |
| `upcoming_checkpoints[].lifecycle_stage` | — |
| `strengths` | Up to three strengths, each resting on verified evidence or an approval on record. |
| `strengths[].statement` | One sentence: what is working, specific to this product. |
| `strengths[].refs` | What shows it: ids of items whose verdict is satisfied or partially_satisfied, or the key of an approved upstream artifact (e.g. requirements_review) whose approval record shows it. A strength resting on anything else is removed by code. |
| `strengths[].evidence` | The evidence, quoted or named in one line. |
| `opportunities` | Up to three opportunities for improvement. |
| `opportunities[].statement` | One sentence: an improvement beyond closing the gaps — something that would make the next audits cheaper or the controls stronger. |
| `opportunities[].refs` | Item ids or principle keys it concerns. |
| `opportunities[].benefit` | What it would change, in one line. |
| `pathway_summary` | One sentence: the way forward, in the order the team should take it. |

Rendered sections: Audit Opinion → Strengths → Risks → Opportunities → Pathway Forward → Open Issues → Verdict Register → Accountability Documentation → Not Grounded in Retrieved Excerpts → Declared Coverage → Verdict Reconciliation.

Verdict keys the agent declares: `items_audited`, `opinion_ceiling`.

## 8. Checks

- The record conforms to the schema (one repair attempt, then a fallback record)
- Every citation resolves to an excerpt retrieved for this run
- Every checklist item is declared covered, not applicable or not grounded
- Every finding has an action or an open issue
- The rule engine's issues are carried forward; the verdict is reconciled
- Every computed item has a verdict
- An unevidenced item is never upgraded (restored by code)
- A strength rests on a satisfied item or an approval on record (anything else removed by code)
- The opinion is rated by code and never rises above the best the declared evidence allows

## 9. Limitations

- The normative corpus is a set of curated summaries prepared for the project; a citation resolves to a section of a summary, not to official wording.
- Evidence matching is lexical and conservative: an item lands in NOT VERIFIED when in doubt, and a match is only a reason to assess, not proof.
- The opinion follows a fixed RAIA rule over counts (share satisfied, items at risk, finding priorities, blocking decisions); it rates the evidence the sprint produced, not the quality of the controls themselves.
