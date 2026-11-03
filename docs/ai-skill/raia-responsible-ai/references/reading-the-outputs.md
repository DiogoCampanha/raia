# Reading RAIA's outputs

RAIA runs four agents in order, each ending at a human approval gate. Every agent answers in one standard record (schema `raia-record/1.5`): the model filled it, code computed the ids, risk levels, priorities and status, and a person approved it. What you read in `project/artifacts/` is what that person approved.

## The stages at a glance

| Stage | File | Id prefix | Grounded in | Writes | Hands on |
|---|---|---|---|---|---|
| **Risk Classifier** | `02_risk_classification.md` | `RC` | EU AI Act (Regulation (EU) 2024/1689); Brazilian AI Bill PL 2338/2023 | findings | Legal obligations (codes such as `eu.art14`), the principles its risks touch, its open decisions. |
| **Requirements Reviewer** | `03_requirements_review.md` | `RR` | IEEE 7000-2021 (Value-Based Engineering); Microsoft Responsible AI Standard v2 | requirements only | Ethical value requirements (`EVR-n`); one a reviewer overrode is not handed on. |
| **User Story Refiner (generate from requirements mode)** | `04a_rai_backlog.md` | `SG` | Microsoft Responsible AI Standard v2; ECCOLA Method (21 cards) | findings, actions | RAI stories (`RAI-n`) in the backlog, each implementing at least one requirement. |
| **User Story Refiner** | `04_refined_stories.md` | `SR` | ECCOLA Method (21 cards); Microsoft Responsible AI Standard v2 | findings, actions | Ethical acceptance criteria on the backlog stories (`AC-<story>-n`). |
| **Auditor** | `05_audit_report.md` | `AU` | Microsoft Responsible AI Standard v2; NIST AI Risk Management Framework 1.0 | findings, actions | The audit verdicts that close a sprint, and the pathway forward. |

The User Story Refiner has two modes, each with its own record: **generate** (approved requirements with no story become RAI stories, `RAI-n`) and **refine** (the team's stories get ethical acceptance criteria and conflicts flagged). Sprint copies of a record are kept as `<file>.SPR-n.md`; the file without a sprint suffix is the latest.

## Every record has the same core

Read a record top to bottom and stop when you have what you need.

| Part | What it tells you | How to use it |
|---|---|---|
| Headline and summary | The verdict and what it means for the team | Quote it when you explain why something matters |
| Overall status | See the table below | Blocked → find the blocking decision before anything else |
| Findings (`<prefix>-F<n>`) | A risk: principle, NIST AI RMF category, magnitude × likelihood, computed risk level and priority, blocking flag, `priority_basis` | Priority and blocking are computed: never lower them |
| Actions (`<prefix>-A<n>`) | Response, owner role, lifecycle stage, review cadence, verification method, evidence artifact, the findings it answers | Turn them into backlog items or criteria; keep the owner and evidence |
| Open issues (`<prefix>-I<n>`, `ISSUE-n` in the register) | A decision only a person can take, with options and a decision owner | Present, never decide |
| Not grounded | Claims that matter but that RAIA's sources did not support | Do not build on them without a source |
| Coverage | Each checklist item declared covered, not applicable or not grounded | A "not grounded" item is a gap in the analysis, not in the product |
| Review | Cards the person accepted, rejected (with a reason) or overrode | A rejected card is gone from the record: do not bring it back |
| Provenance header (top of the `.md`) | Who approved, when, which model, whether the draft was edited, check results | Cite the approval date when you say how current something is |

Overall status (code can raise it, never lower it):

| Status | Meaning |
|---|---|
| **On track** (`on_track`) | Nothing found needs action before the next stage. |
| **Needs attention** (`needs_attention`) | There are high risks or open decisions. The next stage can start, but they travel with it. |
| **Blocked in its current form** (`blocked`) | N item(s) must be resolved before this product can go ahead as described. They are listed under Gaps to close, each with what unblocks it. |

## Stage by stage

### 1. Risk Classifier — `02_risk_classification.md`

**What it is.** The risk analysis, and only that. It screens the declared purpose against the prohibited practices and high-risk areas of the EU AI Act and PL 2338/2023, derives the tier in each jurisdiction and lists the legal obligations that follow from the tier and the team's role (provider or deployer).

**Read first.** The two tiers; the prohibited-practice screen; the blocking decisions (often human oversight on a high-risk system).

**What it does not contain.** Actions. What to do about each risk is written at the next stage, as requirements. Do not invent mitigations from this record alone.

**Hands on.** Obligation codes (`eu.art14`, `br.supervision`, …) and the principles its risks touch.

**`01_product_brief.md`** is the description the team gave RAIA at this stage. It is the baseline for the reconciliation step in `SKILL.md`.

### 2. Requirements Reviewer — `03_requirements_review.md`

**What it is.** The response to the approved risks, written as ethical value requirements (`EVR-n`) in the IEEE 7000 style: value, stakeholders, statement, fit criterion, verification method. Code built a coverage matrix (every obligation and each of the seven principles against the team's requirements and controls); every uncovered cell is a gap, and each gap became an EVR.

**Read first.** The EVR register with its computed priority (from the risks behind it; a legal-obligation gap is at least high); the gap analysis; the stakeholder and value register.

**What it does not contain.** New risks or separate actions: the requirements are the actions.

**Hands on.** The EVRs. One that a reviewer overrode or excluded is not handed on: do not use it.

### 3. User Story Refiner — `04a_rai_backlog.md` (generate) and `04_refined_stories.md` (refine)

**Generate mode.** For a short list of requirements with no story (legal obligations first), RAI stories, each linking at least one EVR, with ECCOLA cards and ethical acceptance criteria. Requirements in scope that need no story are justified under "not a story". On approval the stories entered the backlog as `RAI-n`, criteria as `AC-RAI-n-<k>`.

**Refine mode.** The team's own stories, one by one. For each: the ECCOLA cards its capabilities select, new ethical criteria (`AC-<story>-<n>`) with a measurable condition, Microsoft RAI Standard v2 goal, stakeholder group, evidence artifact and owner role, and conflicts with the team's existing criteria (`<story>-E<n>`) with a suggested rewrite. A story with no ethical impact carries a one-line reason.

**Read first.** The refined stories themselves; then conflicts (each one opened a decision for the product owner).

**Hands on.** Ethical acceptance criteria on backlog stories, and the story-to-requirement links the roadmap uses.

### 4. Auditor — `05_audit_report.md`

**What it is.** A project-wide audit at the close of a sprint. Each item of the sprint (ethical criteria of its stories, requirements whose stories it completes) gets a verdict: satisfied, partially satisfied, at risk or not verified. Code rated the opinion; the model may lower verdicts, never raise them. It also reports where every requirement stands, the progress across sprints and whether the backlog is enough to cover the ethical risks.

**Read first.** The opinion and its reasons; "next focus"; the backlog assessment (requirements weakly or not covered); upcoming checkpoints.

**Hands on.** Verified stories (only an approved audit verifies), stories carried over, and the pathway forward.

`07_open_issues.md` is the project-wide register of decisions (`ISSUE-n`) raised by any stage, with status. `08_backlog.md` and `09_sprints.md` are the board as RAIA keeps it.

## Following an id through the chain

```
RC-F2 (risk, Risk Classifier) ─┐
eu.art14 (obligation) ─────────┼─> gap ─> EVR-4 (requirement) ─> RAI-2 (story) ─> AC-RAI-2-1 (criterion) ─> AU item verdict
principle "human_oversight" ───┘                                  US-7 (team story, refined) ─> AC-US-7-1
```

- From a risk to its response: find the EVR whose gap lists the finding (`answers_risks`, or the gap's `risks`).
- From a requirement to the work: `roadmap.csv` (stories per requirement, state, sprint verified in).
- From a story to its evidence: its criteria (`backlog.csv`, `ethical_criteria`) and the audit item with the same id.
- From anything to a decision: the open issue whose `links` name it.

## Decisions (open issues)

Each names a decision owner and whether it blocks. When an issue lists no options of its own, these are the defaults, and a written answer is always possible.

| Type | What it means | Default options |
|---|---|---|
| `normative_conflict` | Conflict between norms of the same authority level | Apply the stricter rule · Record which rule governs here, and why |
| `engine_disagreement` | The agent disagrees with the rule engine | Keep the computed verdict · Adopt the agent's verdict and record why |
| `value_tradeoff` | Values trade off against each other | Find a design that serves both values · Give one value priority and record why |
| `not_grounded` | Important claim not grounded in the retrieved excerpts | Find a source that supports it · Drop the claim |
| `missing_information` | Information only a person can supply | Supply the information and run the stage again · Record the answer here |
| `risk_acceptance` | A risk to treat or to accept | Accept the risk and record the decision · Require a treatment |
| `prohibited_practice` | A prohibited or excessive-risk practice was declared | Remove the practice from the design · Record the legal exception that applies |
