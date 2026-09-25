# The RAIA Output Contract (`raia-record/1.1`)

Every RAIA agent answers in the same standard record. Two projects that go
through the same stage answer the same questions, on the same scales, with the
same identifiers — and a reviewer who has read one stage can read any stage of
any project.

This document is the standard. The code that enforces it lives in
`raia/contract/`; the published JSON Schemas live in `docs/schema/`; the tests
in `tests/test_contract.py` fail when the two drift apart.

## 1. Why a contract, and why this one

Before the contract, every agent had fixed headings but free prose inside them.
Nothing said what a recommendation must contain, so one run wrote an owner and
a deadline and the next wrote a paragraph; one called a harm "serious" and the
next "notable". Structure had to be recovered from prose with regular
expressions. The records of two projects could not be compared, and the
reviewer at the approval gate had to learn a new layout at every stage.

Three design rules follow:

1. **The model fills a schema; code writes the document.** The model returns
   one JSON object that must validate against its agent's schema. Code renders
   the Markdown a person reads. The JSON is the record; the Markdown is a view.
2. **What must not vary between runs is computed, not generated.** Identifiers,
   risk level, priority, blocking flags, carried-forward issues and the overall
   status floor are computed by code from the model's placements and from the
   rule engine's facts.
3. **Every vocabulary is closed and comes from the project's normative
   sources** — the seven Responsible AI principles, NIST AI RMF 1.0, IEEE
   7000-2021, Microsoft Responsible AI Standard v2, ECCOLA, the EU AI Act and
   PL 2338/2023. No other standard is used. Where a source names a concept but
   not a scale (NIST asks for likelihood and magnitude without fixing levels),
   the levels are RAIA's operationalisation, anchored to the sources' own
   wording.

## 2. The division of labour

| The model decides | Code decides | A person decides |
|---|---|---|
| Which findings exist and what they say | Final identifiers (`RC-F1`, `RC-A1`, `RC-I1`) | Whether to approve, edit or reject |
| Placement of each finding on the magnitude and likelihood scales, with a rationale | Risk level (matrix) and priority (matrix + floors), blocking flag and its basis | How each open issue is arbitrated |
| Actions: response, owner, lifecycle stage, cadence, verification, evidence artifact | An action's priority (from the findings it answers) | Whether a risk is accepted |
| The agent-specific content (justifications, requirements, criteria, audit verdicts, alerts) | Carrying every rule-engine issue forward, typed; opening issues for disagreements and accepted risks | |
| Whether it agrees with the rule engine | Restoring an upgraded audit verdict or a restated severity, and reporting it | |
| Coverage declarations | The overall status floor; rendering; all checks | |

## 3. The shared core

Every record, for every agent, has these fields.

| Field | Content | Grounding |
|---|---|---|
| `headline` | The bottom line in one sentence: the verdict and what it means for the team (required of the model; older records fall back to the summary's first sentence) | Human oversight: the reviewer reads it first |
| `summary` | At most three sentences that add to the headline | Human oversight |
| `overall_status` | `on_track` · `needs_attention` · `blocked` (code raises, never lowers) | Human oversight |
| `declared_verdict`, `agrees_with_rule_engine`, `disagreement_rationale` | The agent's verdict per key, and whether it agrees with the rule engine | RAIA reconciliation channel; conflicts reach a human |
| `findings[]` | `title`, `statement`, `principle`, `nist_category`, `magnitude`, `likelihood`, `placement_rationale`, `stakeholders`, `citations`, `links`; computed: `risk_level`, `priority`, `blocking`, `priority_basis` | Seven principles; NIST AI RMF categories; NIST AI RMF MAP 5 (likelihood and magnitude) |
| `actions[]` | `action`, `finding_ids`, `response`, `owner_role`, `lifecycle_stage`, `review_cadence`, `verification_method`, `evidence_artifact`, `citations`, `links`; computed: `priority` | NIST AI RMF MANAGE 1 (responses) and lifecycle; Microsoft RAI Standard v2 requirement pattern (owner, review cadence, evidence artifact); IEEE 7000 (verification) |
| `open_issues[]` | `type`, `description`, `options`, `decision_owner`, `blocking`, `links`; computed: `origin` (`engine`, `agent`, `code`) | Authority precedence and same-level conflicts; NIST AI RMF GOVERN 2 (roles) |
| `not_grounded[]` | Claims that matter but that the retrieved excerpts do not support | Grounded recommendations |
| `coverage[]` | `key`, `status` (`covered` · `not-applicable` · `not-grounded`), `justification` | Declared completeness |
| `extension` | The agent-specific part (section 4) | The agent's normative source |
| computed `meta`, `computed_verdict`, `contract_notes` | Schema version, record type, agent, layer, SDLC phase, the frameworks grounding the agent; the rule engine's verdict; corrections code applied | Provenance |

## 4. The agent extensions

Each agent's extension is shaped by what its normative source produces.

### Risk Classifier — EU AI Act, PL 2338/2023

| Field | Content |
|---|---|
| `prohibited_screen` | Result of the EU AI Act Art. 5 and PL 2338/2023 excessive-risk screens |
| `eu_tier_justification`, `br_tier_justification` | Why each computed tier holds, naming the area or article |
| `obligations[]` | One note per obligation code in the computed table, exactly: what it means for this product, cited |
| `human_oversight_assessment` | The declared autonomy and oversight tested against the human-oversight obligations |
| `affected_persons_rights` | How explanation, contestation and human review are built into the product |
| `impact_assessments` | The fundamental-rights and algorithmic impact assessments the instruments require |

### Requirements Reviewer — IEEE 7000 (Value-Based Engineering), Microsoft RAI Standard v2 (A1)

| Field | Content |
|---|---|
| `context_of_use` | The operational environment (IEEE 7000 concept of operations) |
| `stakeholders[]` | `name`, `kind` (`direct` · `indirect`), `values` |
| `value_register[]` | Core values ranked (1 = highest) with the design's `threats` to and `opportunities` for each (risk-based design) |
| `gap_analysis[]` | One entry per computed EVR id: why the gap matters here, cited |
| `evrs[]` | One ethical value requirement per assigned id: `value`, `stakeholders`, `statement`, `fit_criterion`, `verification_method`, `traces_to` — traceable, verifiable, contextual, prioritised |
| `impact_assessment` | `intended_uses`, `harms_and_benefits[]` per stakeholder, `mitigations` (Microsoft RAI Standard v2 goal A1) |

### User Story Refiner — ECCOLA, Microsoft RAI Standard v2 (verifiable requirements)

| Field | Content |
|---|---|
| `stories[]` | Exactly one entry per story id |
| `stories[].eccola_cards`, `card_discussion` | Cards in scope for that story only, and their questions answered for it in two or three sentences |
| `stories[].criteria[]` | New criteria only, `AC-<story>-<n>`: `ms_goal`, `stakeholder_group`, measurable `condition` with threshold, `evidence_artifact`, `owner_role`, `evr_ids` |
| `stories[].conflicts[]` | An existing criterion of the story (`<story>-E<n>`) that conflicts with an approved requirement or a card in scope: `conflicts_with`, `problem`, `suggested_rewrite`. Code opens one `value_tradeoff` issue per conflict for the product owner |
| `stories[].no_impact_reason` | For stories with no ethical impact, one line |
| `sprint_ethics_log[]` | Up to five decisions, one sentence each with its reason (ECCOLA's documentation step) |

Stories are entered one by one — id, title, description, existing acceptance
criteria and the capabilities the story touches — so ECCOLA cards are selected
per story and existing criteria have ids a conflict can point at. Existing
criteria stay the team's: RAIA never rewrites them, it flags them.

### Auditor — Microsoft RAI Standard v2 (accountability), NIST AI RMF GOVERN

| Field | Content |
|---|---|
| `items[]` | One per computed item: `verdict` (`satisfied` · `partially_satisfied` · `at_risk` · `not_verified`), `evidence`, `evidence_needed`, `downgrade_reason`; computed: `computed_verdict` |
| `accountability_log[]` | `decision`, `decided_by`, `artifact`, `reference` |
| `upcoming_checkpoints[]` | `checkpoint`, `triggered_by`, `item_ids`, `lifecycle_stage` |

A verdict may be downgraded, never upgraded: an item with no evidence reported
as satisfied is restored to `not_verified` by code, and the attempt fails a check.

### Drift Monitor — NIST AI RMF MEASURE and MANAGE

| Field | Content |
|---|---|
| `alerts[]` | One per computed breach window, with exactly the computed `severity` and what it means for affected people |
| `trend_interpretation`, `representativeness`, `sample_adequacy[]` | MEASURE 2 and 3: movement, population representativeness, where samples do not support a conclusion |
| `response_plan` | `escalation_path`, `deactivation_criteria` (MANAGE 2), `affected_community_feedback` (MANAGE 4), `recovery_and_communication` |

## 5. Vocabularies and anchors

<!-- VOCABULARY:START -->
**Magnitude** (NIST AI RMF MAP 5; anchored to the harm criteria of the EU AI Act and PL 2338/2023)

| Value | Definition |
|---|---|
| `negligible` | No effect on people's rights, opportunities, safety or wellbeing; an inconvenience that is noticed and corrected in normal operation. |
| `limited` | A reversible effect on a small number of people who can notice it and obtain a correction without help; no legal or similarly significant effect. |
| `significant` | An effect on people's access to opportunities, services or fair treatment, or on their privacy — reversible, but only with effort, or affecting many people or a group protected against discrimination. |
| `severe` | A legal or similarly significant effect on persons, harm to fundamental rights, health or safety, or harm that is hard to reverse, falls on vulnerable groups, or operates at scale — the criteria the legal texts use to call a system high-risk. |

**Likelihood** (NIST AI RMF MAP 5)

| Value | Definition |
|---|---|
| `rare` | Requires an unusual combination of conditions not expected in the documented context of use. |
| `possible` | Could occur in the documented context of use, but nothing in the inputs or evidence suggests it is currently happening. |
| `likely` | Expected to occur in the documented context of use unless a control is in place, and no such control is evidenced. |
| `observed` | Already shown by measured or documented evidence (telemetry, an audit result, an incident). |

**Risk response** (NIST AI RMF MANAGE 1)

| Value | Definition |
|---|---|
| `mitigate` | Reduce the likelihood or magnitude with a control the team builds or operates. |
| `transfer` | Move the risk to a party better placed to bear it (a provider, a deployer, an insurer), with that transfer documented. |
| `avoid` | Remove the feature, use or data that creates the risk. |
| `accept` | Keep the risk as it is. Only a person can accept a risk: an accept response always opens an issue for human arbitration. |

**Principles** (the seven principles the project adopts): `accountability` Accountability, `fairness` Diversity, non-discrimination and fairness, `human_oversight` Human agency and oversight, `privacy` Privacy and data governance, `robustness` Technical robustness and safety, `transparency` Transparency, `wellbeing` Social and environmental well-being

**NIST AI RMF categories**: `GOVERN 1` Policies, processes and legal requirements are in place and managed; `GOVERN 2` Accountability structures, roles and responsibilities are documented; `GOVERN 3` Diverse perspectives inform decision-making; `GOVERN 4` A culture that communicates risks and impacts; `GOVERN 5` Engagement with AI actors and external stakeholders (feedback, appeal, redress); `GOVERN 6` Third-party risks are addressed; `MAP 1` Context, intended purpose and potential impacts are documented; `MAP 2` The AI system is categorised; `MAP 3` Capabilities, targeted usage, benefits and costs are understood; `MAP 4` Risks and benefits are mapped for all components; `MAP 5` Impacts are characterised by likelihood and magnitude; `MEASURE 1` Methods and metrics are identified, applied and documented; `MEASURE 2` Trustworthy characteristics, including fairness and representativeness, are evaluated; `MEASURE 3` Identified risks are tracked over time, including in production; `MEASURE 4` Feedback about measurement efficacy is gathered; `MANAGE 1` Risks are prioritised and responded to; `MANAGE 2` Benefits are maximised and negative impacts minimised, with deactivation criteria; `MANAGE 3` Third-party risks are managed and monitored; `MANAGE 4` Treatments, response, recovery and communication plans are documented and monitored

**Lifecycle stages** (NIST AI RMF): `plan_and_design`, `collect_and_process_data`, `build_and_use_model`, `verify_and_validate`, `deploy_and_use`, `operate_and_monitor`

**Owner roles** (NIST AI RMF GOVERN 2; the audiences of the RAIA layers): `product` Product management, `engineering` Engineering, `data_science` Data science / ML, `legal_compliance` Legal and compliance, `operations` Operations / MLOps, `leadership` Leadership

**Review cadence** (Microsoft RAI Standard v2): `once`, `every_sprint`, `every_release`, `continuous`

**Verification methods** (IEEE 7000): `test`, `audit`, `measurement`, `inspection`

**Microsoft RAI Standard v2 goals**: `A1` Impact assessment; `A2` Oversight of significant adverse impacts; `A3` Fit for purpose; `A4` Data governance and management; `A5` Human oversight and control; `T1` System intelligibility for decision-making; `T2` Communication to stakeholders; `T3` Disclosure of AI interaction; `F1` Quality of service; `F2` Allocation of resources and opportunities; `F3` Minimization of stereotyping, demeaning, and erasing outputs; `RS1` Reliability and safety guidance; `RS2` Failures and remediations; `RS3` Ongoing monitoring, feedback, and evaluation; `PS1` Privacy; `PS2` Security; `I1` Inclusiveness

**ECCOLA cards**: `#0` Stakeholder Analysis; `#1` Types of Transparency; `#2` Regulation; `#3` Traceability; `#4` Communication; `#5` Explainability; `#6` Privacy and Data; `#7` Data Quality; `#8` Access to Data; `#9` Human Agency; `#10` Human Oversight; `#11` System Reliability; `#12` System Security; `#13` System Safety; `#14` Accessibility; `#15` Stakeholder Participation; `#16` Non-Discrimination / Fairness; `#17` Societal and Environmental Impact; `#18` Auditability; `#19` Ability to Redress; `#20` Accountability

**Open-issue types**: `normative_conflict` Conflict between norms of the same authority level; `engine_disagreement` The agent disagrees with the rule engine; `value_tradeoff` Values trade off against each other; `not_grounded` Important claim not grounded in the retrieved excerpts; `missing_information` Information only a person can supply; `risk_acceptance` A risk is proposed for acceptance; `prohibited_practice` A prohibited or excessive-risk practice was declared
<!-- VOCABULARY:END -->

## 6. Risk level and priority

NIST AI RMF asks that impacts be characterised by likelihood and magnitude
(MAP 5) and that risks be prioritised on them (MANAGE 1). RAIA applies this
table:

<!-- MATRIX:START -->
| magnitude \ likelihood | rare | possible | likely | observed |
|---|---|---|---|---|
| negligible | low | low | low | medium |
| limited | low | low | medium | medium |
| significant | medium | medium | high | high |
| severe | high | high | critical | critical |
<!-- MATRIX:END -->

Then floors, in this order, each recorded in `priority_basis`:

| Floor | Priority | Source |
|---|---|---|
| A prohibited or excessive-risk practice was declared | `critical`, blocking | EU AI Act Art. 5; PL 2338/2023 excessive risk |
| The finding cites a legal instrument, or links a legal obligation code | at least `high` | Authority precedence legal > standard > advisory |
| A requirement closes a legal obligation gap | at least `high` | Same |
| An item is unverified on a high-risk system | at least `high` (otherwise `medium`) | Microsoft RAI Standard v2 accountability; NIST AI RMF GOVERN |
| A drift severity computed from telemetry | that severity | NIST AI RMF MEASURE 3 |

An action takes the highest priority of the findings it answers. The overall
status is at least `needs_attention` when any issue is open or any finding is
high, and `blocked` when anything is blocking.

## 7. Identifiers

| Kind | Form | Assigned by |
|---|---|---|
| Finding, action, issue in a record | `<agent prefix>-F<n>`, `-A<n>`, `-I<n>` with prefixes `RC`, `RR`, `SR`, `AU`, `DM` | code |
| Ethical value requirement | `EVR-<n>` | Requirements Reviewer rule engine |
| Story | as given, or `S<n>` | User Story Refiner rule engine |
| Acceptance criterion | `AC-<story>-<n>` | the agent, checked by code |
| ECCOLA card | `#0`–`#20` | ECCOLA |
| Obligation | `eu.*`, `br.*` codes | Risk Classifier rule engine |
| Issue in the project register | `ISSUE-<n>` | register |

## 8. The one layout: summary, actions, deep dive

RAIA is a work tool: people read a record between other work, so every record
reads top to bottom and can be put down at any point. The screen
(`raia/ui/record_view.py`) and the Markdown document (`raia/contract/render.py`)
both draw one digest (`raia/contract/digest.py`), so they cannot disagree.

**Summary**

1. **Summary** — status, headline, summary; four figures (risks identified by
   priority, actions to take and how many are urgent, decisions needed and how
   many block, one figure specific to the stage); the three main issues
   (blocking first, then by priority); the principles the findings touch.

**What to do**

2. **Action Plan** — actions grouped by computed priority: *Do now* (critical,
   high), *Plan* (medium), *Track* (low). Each names its owner, when it happens,
   what shows it is done, and the findings it answers. On screen a filter shows
   one owner's share.
3. **Open Issues** — the decisions only a person can take, with their options.

**Deep dive** (on screen, behind a dropdown; one tab per section)

4. **Findings** — each finding with who is affected, why this priority and, when
   a floor raised it, why.
5. **The agent's own sections** (section 4).
6. **Not Grounded in Retrieved Excerpts**, **Declared Coverage**, **Verdict
   Reconciliation** — the traceability appendix.

Every deep-dive section opens with a one-line **conclusion**. Conclusions are
computed from the record (counts, tiers, the most pressing finding) or are the
first sentence of the field they summarise, which is why the contract asks the
model to lead every free-text field with its conclusion.

The document ends with the machine block (`schema`, `verdict.*`, `coverage.*`).
The User Story Refiner also offers the refined stories as plain text, ready to
paste into the team's tracker.

## 9. Parsing, repair and fallback

A reply that does not validate is sent back once (`RAIA_CONTRACT_REPAIRS`):

- **Malformed or off-contract** — returned with its validation errors.
- **Cut off at the token limit** — returned with a larger budget
  (`RAIA_LLM_MAX_TOKENS_CEILING`) and an instruction to send the whole record
  compactly. The cure is a shorter record as much as a bigger budget: every
  free-text field has a `maxLength`, because a record that does not fit one
  reply is a record nobody reads at the gate either.

If it still fails, the stage shows a **fallback record**: it says whether the
reply was cut off or malformed, names the limit it hit, shows the raw reply,
carries the rule engine's issues, and fails the contract check. The provenance
records the number of retries and the budget the approved draft was written
with.

## 10. Checks

Run after every generation and again on what a person approves:

| Check | Level when it fails |
|---|---|
| The record conforms to the schema | fail |
| Code had to restore an upgraded verdict or a restated severity | fail |
| Every finding has an action or an open issue (NIST AI RMF MANAGE 1) | fail for high or critical, otherwise warning |
| Every computed identifier is accounted for, and no invented one appears | fail |
| Citations resolve to excerpts retrieved for this run | fail |
| Every checklist key declared | fail |
| Engine issues carried, verdict reconciled | fail / warning |
| Agent-specific: requirement verifiability, criterion ids, figures come from the computed set | warning / fail |

Checks inform and never block; the person at the gate decides.

## 11. Editing at the approval gate

A reviewer edits the record's fields — the headline and summary, a finding's placement on
the scales, an action's owner or response, the agent's own issues, the
extension — not the rendered prose. On approval the record is finalised again,
so priorities are recomputed and engine issues re-inserted, then re-rendered and
re-checked. An edit that does not validate cannot be approved. The provenance
records that a person edited the record.

## 12. The project action plan

The Project page's **Action plan** gathers every action from every approved
record, sorted by computed priority, with its findings, principles, NIST AI RMF
categories, owner, lifecycle stage, cadence, verification method and evidence
artifact. It is exported as `action_plan.csv` and `action_plan.json` and is
included in the project download.

## 13. Versioning

`raia-record/<major>.<minor>`. Adding an optional field is a minor change
(1.1 added `headline` and the Story Refiner's `conflicts`, and shortened the
free-text caps);
removing or renaming a field, or changing a vocabulary or the matrix, is a major
change. Records keep the version they were written with. After any change run
`python -m raia.contract.export_schema` and commit `docs/schema/`.

A field is added only if code consumes it (rendering, a check, a downstream
engine or the action plan) and it is grounded in one of the project's
normative sources.

## 14. Measuring consistency

`tests/consistency_check.py --agent <key> --runs <n>` runs one agent several
times on the same answers and reports how much the records agree: conformance,
declared verdicts, status, principles and NIST categories of findings, computed
priorities, action owners and issue types. With the mock model every figure is
1.0 by construction; with a real provider it measures the standard's effect.

## 15. Limitations

- The magnitude and likelihood levels, the matrix and the floors are RAIA's
  operationalisation. The sources ask for these judgements; they do not fix
  these scales.
- A closed vocabulary makes placements comparable; it does not make them
  correct. Two runs can agree and both be wrong, which is why the gate shows
  the placement rationale and the priority basis.
- The consistency figures are only meaningful with a real model.
