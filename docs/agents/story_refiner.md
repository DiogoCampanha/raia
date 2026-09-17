# Agent card — User Story Refiner

> Generated from the code by `python -m raia.contract.agent_cards`. Follows `docs/templates/agent-card.md`. Do not edit by hand.

## 1. Purpose

Selects the ethical themes that actually apply to this sprint and adds verifiable acceptance criteria to the backlog stories.

## 2. Place in the lifecycle

| | |
|---|---|
| Layer | Dev |
| SDLC phase | Iterative development (sprints) |
| When to run | During sprint planning, for the stories about to enter a sprint. |
| Requires approved | Requirements Reviewer |
| Reads | Risk Classifier, Requirements Reviewer |
| Produces | `04_refined_stories.md` — refined stories record |

## 3. Normative grounding

| Source | Authority |
|---|---|
| ECCOLA Method (21 cards) | advisory |
| Microsoft Responsible AI Standard v2 | standard |

## 4. Inputs

| Group | Question | Kind | Required |
|---|---|---|---|
| The sprint's backlog | Backlog user stories | textarea | yes |
| The sprint's backlog | Sprint goal | text | no |
| What these stories touch | What do these stories touch? | multiselect | yes |
| What these stories touch | Your definition of done | textarea | no |

## 5. What the decision procedure settles in code

- Selects the ECCOLA themes relevant to this sprint from the approved risk tier, requirements and what the stories touch, and records why each one applies.
- Traces every acceptance criterion back to an approved requirement.

Checklist the record must declare:

- `stories` — Account for every story id in the register, refined or not
- `criteria` — Give each refined story verifiable acceptance criteria
- `cards` — Cite the selected card id(s) that justify each criterion
- `traceability` — Trace each criterion to an approved requirement id where one exists
- `no_impact` — Justify, one line each, every story you leave unrefined
- `open_issues` — Carry forward every open issue raised here, plus any you add

Excerpts pinned for the canonical scenario:

- ECCOLA Method (21 cards) — How ECCOLA Is Used in Sprints (how cards are applied in a sprint)
- ECCOLA Method (21 cards) — Agency and Oversight (Agency cards in scope)
- ECCOLA Method (21 cards) — Analyze (context setting) (Analyze cards in scope)
- ECCOLA Method (21 cards) — Data (privacy and governance) (Data cards in scope)
- ECCOLA Method (21 cards) — Fairness (Fairness cards in scope)
- ECCOLA Method (21 cards) — Transparency (Transparency cards in scope)
- ECCOLA Method (21 cards) — Wellbeing and Society (Wellbeing cards in scope)
- Microsoft Responsible AI Standard v2 — Practical Requirement Style (What RAIA Borrows) (how to make a criterion verifiable)

## 6. What a person decides

- Whether each acceptance criterion is testable in your context.
- Which stories carry no ethical impact and can move on unchanged.
- Every open issue the record raises, and whether to approve, edit or reject the record.

## 7. The record it produces

Schema `raia-record/1.0` — `docs/schema/story_refiner.schema.json`. Identifier prefix `SR`. Shared core as in `docs/output-contract.md`; the extension:

| Field | Content |
|---|---|
| `stories` | Exactly one entry per story id in the register. |
| `stories[].story_id` | A story id from the register, exactly. |
| `stories[].eccola_cards` | Selected ECCOLA card ids that make the story relevant. |
| `stories[].card_discussion` | The card questions, answered for this story. |
| `stories[].criteria` | Verifiable acceptance criteria (Microsoft RAI Standard v2 requirement pattern). |
| `stories[].criteria[].id` | AC-<story id>-<n>, e.g. AC-S1-1. |
| `stories[].criteria[].ms_goal` | The Microsoft RAI Standard v2 goal it serves. |
| `stories[].criteria[].stakeholder_group` | The affected stakeholder group. |
| `stories[].criteria[].condition` | Measurable condition with its threshold. |
| `stories[].criteria[].evidence_artifact` | The artifact that demonstrates compliance. |
| `stories[].criteria[].owner_role` | — |
| `stories[].criteria[].evr_ids` | Approved EVR ids this criterion implements. |
| `stories[].no_impact_reason` | Only for a story with no ethical impact. |
| `sprint_ethics_log` | Decisions and rationales taken this sprint (ECCOLA documentation step). |

Rendered sections: Summary → Findings → Refined Stories → Stories Without Ethical Impact → Sprint Ethics Log → Action Plan → Open Issues → Not Grounded in Retrieved Excerpts → Declared Coverage.

Verdict keys the agent declares: `story_count`.

## 8. Checks

- The record conforms to the schema (one repair attempt, then a fallback record)
- Every citation resolves to an excerpt retrieved for this run
- Every checklist item is declared covered, not applicable or not grounded
- Every finding has an action or an open issue
- The rule engine's issues are carried forward; the verdict is reconciled
- Every story id has an entry
- Only selected ECCOLA cards and approved EVR ids are used
- Criteria are labelled AC-<story>-<n>

## 9. Limitations

- The normative corpus is a set of curated summaries prepared for the project; a citation resolves to a section of a summary, not to official wording.
- Card selection follows the declared capabilities and upstream answers; a capability not declared does not select its cards.
- Acceptance criteria are checked for form, not for whether the threshold is right.
