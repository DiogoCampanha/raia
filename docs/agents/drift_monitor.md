# Agent card — Drift Monitor

> Generated from the code by `python -m raia.contract.agent_cards`. Follows `docs/templates/agent-card.md`. Do not edit by hand.

## 1. Purpose

Watches production telemetry for fairness and representativeness drift, computing every metric in code and letting the model interpret only.

## 2. Place in the lifecycle

| | |
|---|---|
| Layer | Ops |
| SDLC phase | Deployment and monitoring |
| When to run | After deployment, on each monitoring period's telemetry export. |
| Requires approved | Risk Classifier |
| Reads | Risk Classifier, Requirements Reviewer, User Story Refiner |
| Produces | `06_drift_report.md` — drift monitoring record |

## 3. Normative grounding

| Source | Authority |
|---|---|
| NIST AI Risk Management Framework 1.0 | advisory |

## 4. Inputs

| Group | Question | Kind | Required |
|---|---|---|---|
| Telemetry | Production telemetry | csv | yes |
| Operational context | Did anything happen in this period? | select | yes |
| Operational context | Operational context | textarea | no |

## 5. What the decision procedure settles in code

- Computes every fairness and representativeness metric in code, with group sizes and trend, against thresholds read from the approved upstream artifacts.
- Checks that every number in the narrative is one the code computed.

Checklist the record must declare:

- `alerts` — Raise one alert per computed breach, with its severity
- `interpretation` — Interpret the movement across windows, including the trend
- `adequacy` — State where sample sizes do not support a conclusion
- `actions` — Recommend responses grounded in the retrieved management practices
- `open_issues` — Carry forward every open issue raised here, plus any you add

Excerpts pinned for the canonical scenario:

- NIST AI Risk Management Framework 1.0 — MEASURE (analysis and tracking) (measurement and tracking)
- NIST AI Risk Management Framework 1.0 — MANAGE (response and recovery) (response and recovery)
- NIST AI Risk Management Framework 1.0 — Post-Deployment Monitoring Guidance (Measure/Manage in Practice) (post-deployment monitoring)

## 6. What a person decides

- Whether a drift alert warrants action, and which action.
- Whether operational context explains a change in the numbers.
- Every open issue the record raises, and whether to approve, edit or reject the record.

## 7. The record it produces

Schema `raia-record/1.2` — `docs/schema/drift_monitor.schema.json`. Identifier prefix `DM`. Shared core as in `docs/output-contract.md`; the extension:

| Field | Content |
|---|---|
| `alerts` | One alert per computed breach window. |
| `alerts[].window` | A computed breach window label, exactly. |
| `alerts[].severity` | Exactly the severity the engine computed. |
| `alerts[].meaning_for_affected_people` | What this means for the people affected, in one or two sentences. |
| `alerts[].citations` | Citation tags copied exactly from the retrieved excerpts, e.g. "[Source: ... / authority: legal]". Never invent one. |
| `trend_interpretation` | The movement across windows, conclusion first (NIST AI RMF MEASURE 3). |
| `representativeness` | Whether the population mix shifted relative to the population affected, conclusion first (MEASURE 2). |
| `sample_adequacy` | Groups whose samples do not support a conclusion. |
| `response_plan` | Response, recovery and communication (NIST AI RMF MANAGE). |
| `response_plan.escalation_path` | Who is alerted, in what order, within what time. |
| `response_plan.deactivation_criteria` | When the system is rolled back or deactivated (MANAGE 2). |
| `response_plan.affected_community_feedback` | How input from users and affected communities is captured (MANAGE 4). |
| `response_plan.recovery_and_communication` | How the system recovers and who is told. |

Rendered sections: Summary → Action Plan → Open Issues → Findings → Drift Alerts → Fairness & Representativeness Analysis → Response Plan → Not Grounded in Retrieved Excerpts → Declared Coverage → Verdict Reconciliation.

Verdict keys the agent declares: `windows`.

## 8. Checks

- The record conforms to the schema (one repair attempt, then a fallback record)
- Every citation resolves to an excerpt retrieved for this run
- Every checklist item is declared covered, not applicable or not grounded
- Every finding has an action or an open issue
- The rule engine's issues are carried forward; the verdict is reconciled
- One alert per computed breach, with the computed severity (restored by code)
- Every figure in the prose is in the computed set

## 9. Limitations

- The normative corpus is a set of curated summaries prepared for the project; a citation resolves to a section of a summary, not to official wording.
- Metrics are computed from the telemetry supplied; the Ops layer is a demonstrable prototype.
- Severity follows a fixed threshold rule; whether a breach warrants action is a human decision.
