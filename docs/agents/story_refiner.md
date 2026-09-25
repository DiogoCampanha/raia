# Agent card — User Story Refiner

> Generated from the code by `python -m raia.contract.agent_cards`. Follows `docs/templates/agent-card.md`. Do not edit by hand.

## 1. Purpose

Selects the ethical themes that actually apply to each story and adds verifiable acceptance criteria, flagging existing criteria that conflict.

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
| The stories | User stories | stories | yes |
| The sprint | Sprint goal | text | no |
| The sprint | Your definition of done | textarea | no |

## 5. What the decision procedure settles in code

- Selects the ECCOLA themes relevant to each story from the approved risk tier, requirements and what that story touches, and records why each one applies.
- Traces every new acceptance criterion back to an approved requirement.
- Turns every existing criterion the agent flags as conflicting into a decision.
- Shows each story's new version with its changes marked, ready to copy back to your tracker; the risks and actions behind the changes come second.

Checklist the record must declare:

- `stories` — Account for every story id in the register, refined or not
- `criteria` — Give each refined story verifiable acceptance criteria
- `cards` — Cite the selected card id(s) that justify each criterion
- `traceability` — Trace each criterion to an approved requirement id where one exists
- `no_impact` — Justify, one line each, every story you leave unrefined
- `conflicts` — Flag every existing acceptance criterion that conflicts with an approved requirement or a card in scope
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
- Whether a conflicting existing criterion is rewritten or kept, and why — the copy of the story follows your choice.
- Which stories carry no ethical impact and can move on unchanged.
- Every open issue the record raises, and whether to approve, edit or reject the record.

## 7. The record it produces

Schema `raia-record/1.2` — `docs/schema/story_refiner.schema.json`. Identifier prefix `SR`. Shared core as in `docs/output-contract.md`; the extension:

| Field | Content |
|---|---|
| `stories` | Exactly one entry per story id in the register. |
| `stories[].story_id` | A story id from the register, exactly. |
| `stories[].eccola_cards` | ECCOLA card ids in scope for THIS story that make it relevant. |
| `stories[].card_discussion` | The cards' questions, answered for this story in two or three sentences. |
| `stories[].criteria` | New verifiable ethical acceptance criteria (Microsoft RAI Standard v2 requirement pattern). Do not repeat the story's existing criteria. |
| `stories[].criteria[].id` | AC-<story id>-<n>, e.g. AC-S1-1. |
| `stories[].criteria[].ms_goal` | The Microsoft RAI Standard v2 goal it serves. |
| `stories[].criteria[].stakeholder_group` | The affected stakeholder group. |
| `stories[].criteria[].condition` | Measurable condition with its threshold, written as an acceptance criterion. |
| `stories[].criteria[].evidence_artifact` | The artifact that demonstrates compliance. |
| `stories[].criteria[].owner_role` | — |
| `stories[].criteria[].evr_ids` | Approved EVR ids this criterion implements. |
| `stories[].conflicts` | Existing acceptance criteria of this story that conflict with an approved requirement or a selected card. Only real conflicts; leave empty otherwise. |
| `stories[].conflicts[].criterion_id` | The id of one of the story's EXISTING acceptance criteria (e.g. S1-E2), exactly. |
| `stories[].conflicts[].conflicts_with` | What it conflicts with: approved EVR ids, selected ECCOLA card ids or principle keys. |
| `stories[].conflicts[].problem` | One sentence: why the existing criterion conflicts. |
| `stories[].conflicts[].suggested_rewrite` | The criterion rewritten so the conflict is gone. |
| `stories[].no_impact_reason` | Only for a story with no ethical impact: one line. |
| `sprint_ethics_log` | Up to five decisions taken this sprint, one sentence each with its reason (ECCOLA documentation step). |

Rendered sections: Summary → Refined Stories → Stories Without Ethical Impact → Findings → Action Plan → Open Issues → Sprint Ethics Log → Not Grounded in Retrieved Excerpts → Declared Coverage → Verdict Reconciliation.

Verdict keys the agent declares: `story_count`.

## 8. Checks

- The record conforms to the schema (one repair attempt, then a fallback record)
- Every citation resolves to an excerpt retrieved for this run
- Every checklist item is declared covered, not applicable or not grounded
- Every finding has an action or an open issue
- The rule engine's issues are carried forward; the verdict is reconciled
- Every story id has an entry
- Only cards in scope for each story and approved EVR ids are used
- Criteria are labelled AC-<story>-<n>
- A conflict names an existing criterion of its own story, and opens a decision (by code)

## 9. Limitations

- The normative corpus is a set of curated summaries prepared for the project; a citation resolves to a section of a summary, not to official wording.
- Card selection follows each story's declared capabilities and the upstream answers; a capability not declared does not select its cards.
- A conflict is flagged by the agent and settled by a person. The copy of a story offers the suggested rewrite, and the person can keep the original instead; the record keeps the criterion as entered and the decision open until someone takes it.
- Acceptance criteria are checked for form, not for whether the threshold is right.
