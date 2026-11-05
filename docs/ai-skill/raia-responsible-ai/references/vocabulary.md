# Vocabulary

> Generated from the RAIA code. These are the only values RAIA uses: use them exactly.

## Priority

Priorities, lowest to highest: `low`, `medium`, `high`, `critical`. Work is read in three groups:

| Group | Priorities | Meaning |
|---|---|---|
| Do now | critical, high | Critical and high priority |
| Plan | medium | Medium priority: schedule it |
| Track | low | Low priority: keep an eye on it |

## Impact magnitude (NIST AI RMF MAP 5; anchored to the harm criteria of the EU AI Act and PL 2338/2023)

| Value | Definition |
|---|---|
| `negligible` | No effect on people's rights, opportunities, safety or wellbeing; an inconvenience that is noticed and corrected in normal operation. |
| `limited` | A reversible effect on a small number of people who can notice it and obtain a correction without help; no legal or similarly significant effect. |
| `significant` | An effect on people's access to opportunities, services or fair treatment, or on their privacy — reversible, but only with effort, or affecting many people or a group protected against discrimination. |
| `severe` | A legal or similarly significant effect on persons, harm to fundamental rights, health or safety, or harm that is hard to reverse, falls on vulnerable groups, or operates at scale — the criteria the legal texts use to call a system high-risk. |

## Likelihood (NIST AI RMF MAP 5)

| Value | Definition |
|---|---|
| `rare` | Requires an unusual combination of conditions not expected in the documented context of use. |
| `possible` | Could occur in the documented context of use, but nothing in the inputs or evidence suggests it is currently happening. |
| `likely` | Expected to occur in the documented context of use unless a control is in place, and no such control is evidenced. |
| `observed` | Already shown by measured or documented evidence (telemetry, an audit result, an incident). |

## Risk level: magnitude × likelihood

| magnitude \ likelihood | rare | possible | likely | observed |
|---|---|---|---|---|
| negligible | low | low | low | medium |
| limited | low | low | medium | medium |
| significant | medium | medium | high | high |
| severe | high | high | critical | critical |

## Priority floors

The priority starts at the risk level, then each floor that applies raises it (never lowers it). An action takes the highest priority of the findings it answers. A record is at least *needs attention* when any decision is open or any finding is high, and *blocked* when anything is blocking.

| When | Priority | Source |
|---|---|---|
| A prohibited or excessive-risk practice was declared | critical, blocking | EU AI Act Art. 5; PL 2338/2023 excessive risk |
| The finding cites a legal instrument, or links a legal obligation code | at least high | Authority precedence: legal > standard > advisory |
| A requirement closes a legal obligation gap | at least high | Same |
| A requirement answers approved risks | the highest of their priorities (at least medium for a principle declared at stake, otherwise low) | NIST AI RMF MANAGE 1 |
| An audit item is unverified on a high-risk system | at least high (otherwise medium) | Microsoft RAI Standard v2 accountability; NIST AI RMF GOVERN |

## Risk response (NIST AI RMF MANAGE 1)

| Value | Definition |
|---|---|
| `mitigate` | Reduce the likelihood or magnitude with a control the team builds or operates. |
| `transfer` | Move the risk to a party better placed to bear it (a provider, a deployer, an insurer), with that transfer documented. |
| `avoid` | Remove the feature, use or data that creates the risk. |
| `accept` | Keep the risk as it is. Only a person can accept a risk: an accept response always opens an issue for human arbitration. |

## Lifecycle stage (NIST AI RMF)

| Value | Label |
|---|---|
| `plan_and_design` | Plan and design |
| `collect_and_process_data` | Collect and process data |
| `build_and_use_model` | Build and use model |
| `verify_and_validate` | Verify and validate |
| `deploy_and_use` | Deploy and use |
| `operate_and_monitor` | Operate and monitor |

## Owner role (NIST AI RMF GOVERN 2)

| Value | Label |
|---|---|
| `product` | Product management |
| `engineering` | Engineering |
| `data_science` | Data science / ML |
| `legal_compliance` | Legal and compliance |
| `operations` | Operations / MLOps |
| `leadership` | Leadership |

## Review cadence (Microsoft RAI Standard v2)

`once` (once), `every_sprint` (every sprint), `every_release` (every release), `continuous` (continuously)

## Verification method (IEEE 7000)

`test`, `audit`, `measurement`, `inspection`. Stakeholders are `direct` or `indirect`.

## Principles

`accountability` Accountability, `fairness` Diversity, non-discrimination and fairness, `human_oversight` Human agency and oversight, `privacy` Privacy and data governance, `robustness` Technical robustness and safety, `transparency` Transparency, `wellbeing` Social and environmental well-being

## NIST AI RMF categories

| Category | Outcome |
|---|---|
| `GOVERN 1` | Policies, processes and legal requirements are in place and managed |
| `GOVERN 2` | Accountability structures, roles and responsibilities are documented |
| `GOVERN 3` | Diverse perspectives inform decision-making |
| `GOVERN 4` | A culture that communicates risks and impacts |
| `GOVERN 5` | Engagement with AI actors and external stakeholders (feedback, appeal, redress) |
| `GOVERN 6` | Third-party risks are addressed |
| `MAP 1` | Context, intended purpose and potential impacts are documented |
| `MAP 2` | The AI system is categorised |
| `MAP 3` | Capabilities, targeted usage, benefits and costs are understood |
| `MAP 4` | Risks and benefits are mapped for all components |
| `MAP 5` | Impacts are characterised by likelihood and magnitude |
| `MEASURE 1` | Methods and metrics are identified, applied and documented |
| `MEASURE 2` | Trustworthy characteristics, including fairness and representativeness, are evaluated |
| `MEASURE 3` | Identified risks are tracked over time, including in production |
| `MEASURE 4` | Feedback about measurement efficacy is gathered |
| `MANAGE 1` | Risks are prioritised and responded to |
| `MANAGE 2` | Benefits are maximised and negative impacts minimised, with deactivation criteria |
| `MANAGE 3` | Third-party risks are managed and monitored |
| `MANAGE 4` | Treatments, response, recovery and communication plans are documented and monitored |

## Microsoft RAI Standard v2 goals

`A1` Impact assessment, `A2` Oversight of significant adverse impacts, `A3` Fit for purpose, `A4` Data governance and management, `A5` Human oversight and control, `T1` System intelligibility for decision-making, `T2` Communication to stakeholders, `T3` Disclosure of AI interaction, `F1` Quality of service, `F2` Allocation of resources and opportunities, `F3` Minimization of stereotyping, demeaning, and erasing outputs, `RS1` Reliability and safety guidance, `RS2` Failures and remediations, `RS3` Ongoing monitoring, feedback, and evaluation, `PS1` Privacy, `PS2` Security, `I1` Inclusiveness

## ECCOLA cards

`#0` Stakeholder Analysis, `#1` Types of Transparency, `#2` Regulation, `#3` Traceability, `#4` Communication, `#5` Explainability, `#6` Privacy and Data, `#7` Data Quality, `#8` Access to Data, `#9` Human Agency, `#10` Human Oversight, `#11` System Reliability, `#12` System Security, `#13` System Safety, `#14` Accessibility, `#15` Stakeholder Participation, `#16` Non-Discrimination / Fairness, `#17` Societal and Environmental Impact, `#18` Auditability, `#19` Ability to Redress, `#20` Accountability

## Open-issue (decision) types

| Type | Meaning |
|---|---|
| `normative_conflict` | Conflict between norms of the same authority level |
| `engine_disagreement` | The agent disagrees with the rule engine |
| `value_tradeoff` | Values trade off against each other |
| `not_grounded` | Important claim not grounded in the retrieved excerpts |
| `missing_information` | Information only a person can supply |
| `risk_acceptance` | A risk to treat or to accept |
| `prohibited_practice` | A prohibited or excessive-risk practice was declared |

## Audit verdicts (strongest to weakest; may move down, never up)

`satisfied` Satisfied, `partially_satisfied` Partially satisfied, `at_risk` At risk, `not_verified` Not verified

## Audit opinion

Rated by rule, checked from the weakest up; never better than the evidence allows. "Satisfied share" is 60%. In a project run in sprints, the best possible rating is *Needs improvement* while a high or critical risk has no story, or a legal-obligation requirement has had no story in any sprint by the second sprint.

| Rating | When |
|---|---|
| Not rated | There was nothing to audit: no approved requirement or criterion register. |
| Not effective | No evidence was declared, nothing was satisfied, or a blocking decision is open. |
| Needs improvement | Under 60% of items satisfied, an item at risk, or a critical finding. |
| Effective with observations | 60% or more satisfied, with high findings or unverified items remaining. |
| Effective | Every item satisfied and no high or critical finding. |

## Backlog

Story status: `backlog` Backlog, `in_sprint` In sprint, `done` Done, `verified` Verified, `needs_review` Needs review, `obsolete` Obsolete. A tick means delivered (`done`); only an approved RAIA audit sets `verified`.

Story origin: `rai` RAI, `product` Product.

Sprint state: `planning` Planning, `active` Active, `review` Ended, awaiting audit, `closed` Closed.

Requirement state on the roadmap: `no_story` No story, `planned` Planned, `in_sprint` In sprint, `delivered` Delivered, not verified, `verified` Verified, `at_risk` At risk.

## Identifiers

| Kind | Form | Assigned by |
|---|---|---|
| Finding, action, issue in a record | `<prefix>-F<n>`, `-A<n>`, `-I<n>` (prefixes `RC`, `RR`, `SR`, `SG`, `AU`) | code |
| Ethical value requirement | `EVR-<n>` | Requirements Reviewer |
| Story in the backlog | `RAI-<n>` (from requirements), `US-<n>` (product) | backlog register |
| Story in a record | as given, or `S<n>`; `G<n>` in generate mode | User Story Refiner |
| Existing acceptance criterion | `<story>-E<n>` | backlog register |
| Ethical acceptance criterion | `AC-<story>-<n>` | the agent, checked by code |
| Sprint | `SPR-<n>` | sprints register |
| Decision in the project register | `ISSUE-<n>` | register |
| ECCOLA card | `#0`–`#20` | ECCOLA |
| Legal obligation | `eu.*`, `br.*` codes | Risk Classifier |
