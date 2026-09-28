# Agent card — User Story Refiner · Generate from requirements mode

> Generated from the code by `python -m raia.contract.agent_cards`. Follows `docs/templates/agent-card.md`. Do not edit by hand.

## 1. Purpose

Turns approved ethical requirements into RAI stories for the backlog, each with verifiable acceptance criteria and linked to the requirement it implements.

A mode of the User Story Refiner, not an agent of its own: it shares that agent's place in the architecture and runs through the same gate, with its own record.

## 2. Place in the lifecycle

| | |
|---|---|
| Layer | Dev |
| SDLC phase | Iterative development (sprints) |
| When to run | Once the ethical requirements are approved, and again when new requirements have no story. |
| Requires approved | Requirements Reviewer |
| Reads | Risk Classifier, Requirements Reviewer, backlog |
| Produces | `04a_rai_backlog.md` — rai backlog record |

## 3. Normative grounding

| Source | Authority |
|---|---|
| Microsoft Responsible AI Standard v2 | standard |
| ECCOLA Method (21 cards) | advisory |

## 4. Inputs

| Group | Question | Kind | Required |
|---|---|---|---|
| Which requirements | How many requirements | select | no |
| Which requirements | Or name the requirements (optional) | text | no |
| How your team works | Your definition of done (optional) | textarea | no |

## 5. What the decision procedure settles in code

- Picks the requirements this run covers: those with no story yet, the five with the highest priority by default (legal obligations first), or the ones you name.
- Checks that every requirement in scope comes back covered by a story or with a reason it needs none, and that every story links a requirement.
- Gives each approved story its backlog id (RAI-n) and adds it to the backlog.

Checklist the record must declare:

- `coverage` — Cover every requirement in scope with a story, or give a one-line reason it needs none
- `stories` — Write each story as a user story a team can schedule in one sprint
- `criteria` — Give each story verifiable ethical acceptance criteria
- `traceability` — Trace each story and criterion to the requirement ids it implements
- `cards` — Use only ECCOLA cards the story's touches select
- `open_issues` — Carry forward every open issue raised here, plus any you add

Excerpts pinned for the canonical scenario:

- Microsoft Responsible AI Standard v2 — Practical Requirement Style (What RAIA Borrows) (how to make a criterion verifiable)
- ECCOLA Method (21 cards) — How ECCOLA Is Used in Sprints (how cards are applied in a sprint)

## 6. What a person decides

- Whether each generated story is work your team can schedule in one sprint.
- Whether a requirement really needs no story, when the agent says so.
- When each story goes into a sprint: the board suggests, you decide.
- Every open issue the record raises, and whether to approve, edit or reject the record.

## 7. The record it produces

Schema `raia-record/1.3` — `docs/schema/story_generate.schema.json`. Identifier prefix `SG`. Shared core as in `docs/output-contract.md`; the extension:

| Field | Content |
|---|---|
| `stories` | The generated RAI stories. Every requirement in scope is covered by at least one story, or listed in not_story. |
| `stories[].story_id` | G1, G2, … in order. Code gives the backlog id (RAI-n) at approval. |
| `stories[].title` | The story in a few words. |
| `stories[].description` | The story as a team schedules it: "As a <role>, I want <capability>, so that <benefit>." |
| `stories[].evr_ids` | The requirement id(s) in scope that this story implements (at least one). |
| `stories[].touches` | What the story touches; it selects the cards allowed. |
| `stories[].eccola_cards` | ECCOLA card ids its touches select that make it relevant. |
| `stories[].criteria` | Verifiable ethical acceptance criteria, labelled AC-<story id>-<n> (e.g. AC-G1-1). |
| `stories[].criteria[].id` | AC-<story id>-<n>, e.g. AC-S1-1. |
| `stories[].criteria[].ms_goal` | The Microsoft RAI Standard v2 goal it serves. |
| `stories[].criteria[].stakeholder_group` | The affected stakeholder group. |
| `stories[].criteria[].condition` | Measurable condition with its threshold, written as an acceptance criterion. |
| `stories[].criteria[].evidence_artifact` | The artifact that demonstrates compliance. |
| `stories[].criteria[].owner_role` | — |
| `stories[].criteria[].evr_ids` | Approved EVR ids this criterion implements. |
| `not_story` | Requirements in scope that need no story, each with its reason. |
| `not_story[].evr_id` | A requirement id in scope, exactly. |
| `not_story[].reason` | One line: why no story implements it (e.g. a policy decision). |

Rendered sections: Summary → Generated Stories → Requirements Without a Story → Findings → Action Plan → Open Issues → Not Grounded in Retrieved Excerpts → Declared Coverage → Verdict Reconciliation.

Verdict keys the agent declares: `requirement_count`.

## 8. Checks

- The record conforms to the schema (one repair attempt, then a fallback record)
- Every citation resolves to an excerpt retrieved for this run
- Every checklist item is declared covered, not applicable or not grounded
- Every finding has an action or an open issue
- The rule engine's issues are carried forward; the verdict is reconciled
- Every requirement in scope is covered by a story or justified, and no other id appears
- Every story links at least one requirement
- At most three stories per requirement
- Cards are those the story's touches select
- Criteria are labelled AC-<story>-<n>

## 9. Limitations

- The normative corpus is a set of curated summaries prepared for the project; a citation resolves to a section of a summary, not to official wording.
- Stories are generated for approved requirements only; a risk the requirements do not cover does not become a story here (the Auditor reports it as a backlog gap).
- One run covers a short list of requirements; the rest wait for the next run.
- Acceptance criteria are checked for form, not for whether the threshold is right.
