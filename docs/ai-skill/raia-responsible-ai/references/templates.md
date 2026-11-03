# Templates

Use these formats so what you produce can go straight into the backlog, and back into RAIA.

## Triage table (P1)

| Item | Class | EVRs | ECCOLA cards | Priority | Group | Next step |
|---|---|---|---|---|---|---|
| US-12 Ranked shortlist | Product, ethical impact | EVR-3, EVR-7 | #5, #10, #16 | high | Do now | Refine (P2): add fairness and oversight criteria |
| US-15 Export to PDF | No ethical impact | — | — | — | — | None: formats an existing report, no new data or decision |
| RAI-4 Candidate notice | RAI story | EVR-2 | #1, #4 | high | Held | Waits for ISSUE-3 (legal and compliance) |

Then: **EVRs with no story** (id, priority, statement) and **Decisions for a person** (below).

## Refined story (P2)

```
US-12 · Ranked shortlist
As a recruiter, I want a ranked shortlist of applicants, so that I can review the strongest first.

Touches: scoring, automation          ECCOLA: #0, #1, #5, #10, #16, #20
Implements: EVR-3, EVR-7

Existing criteria (the team's, unchanged)
  US-12-E1  The shortlist shows the top 20 applicants.
  US-12-E2  Applicants below the cut-off are rejected automatically.   ⚠ CONFLICT (see below)

Ethical criteria (new)
  AC-US-12-1  [F2 · applicants · evidence: fairness test report · owner: data_science · EVR-3]
              Shortlisting rate is reported per gender and age group on the release test set,
              and the gap between groups stays within the threshold set in EVR-3.
  AC-US-12-2  [A5 · applicants · evidence: UI screenshot + audit log · owner: engineering · EVR-7]
              A recruiter can open any rejected application and override the decision; every
              override is logged with who, when and why.

Conflict
  US-12-E2 conflicts with EVR-7 (case-level human oversight): automatic rejection leaves no
  person able to intervene. Suggested rewrite: "Applicants below the cut-off are listed for a
  recruiter's review before any rejection is sent." Decision: product (keep or rewrite).
```

## RAI story (P3)

```
RAI-new-1 · Tell candidates a model was involved
Implements: EVR-2 (Transparency)
As a candidate, I want to be told that an AI system screens applications and how to ask for a
human review, so that I can contest an outcome that affects me.
ECCOLA: #1, #4, #19
AC-RAI-new-1-1  [T2 · candidates · evidence: notice text + screenshot · owner: product]
                The application form and the outcome email state that an AI system is used,
                what it does and how to request a human review.
```

## Ethical acceptance criterion

`AC-<story>-<n>  [<MS goal> · <stakeholder group> · evidence: <artifact> · owner: <role> · <EVR ids>]  <measurable condition with threshold>`

## Decision for a person

| Decision | Why it is needed | Options | Owner | Blocking | Links |
|---|---|---|---|---|---|
| Keep or rewrite US-12-E2 | Conflicts with EVR-7 | Rewrite as suggested · Keep and record why | product | no | US-12, EVR-7 |

Use the open-issue types in `vocabulary.md`. If the decision already exists in RAIA's register (`ISSUE-n`), cite it instead of opening a new one.

## Self-audit note (P5)

```
Self-audit · SPR-3 · <date>                Rating: Needs improvement (RAIA rule)
Not a RAIA audit: verified status changes only with an approved audit in RAIA.

Items
| Item | Verdict | Evidence | Evidence still needed |
|---|---|---|---|
| AC-RAI-2-1 | satisfied | fairness test report v1.4 | — |
| AC-US-12-2 | not verified | — | audit log extract showing overrides |

Where the requirements stand: 3 verified · 4 in sprint · 6 planned · 7 no story
Backlog enough? No: EVR-9 (legal, eu.art14) has no story.
Strengths (max 3, each resting on a satisfied item) · Risks · Next focus (one sentence)
```

## Jira

Summary: `[<story id>] <title>`. Labels: `raia`, `raia-<story id>`, `raia-<sprint id>` when scheduled, `raia-ethics` for RAI stories. The description carries the story, its requirement links and its criteria, each with its id. A CSV for Jira's importer looks like this (one `Labels` column per label; `Story Points` only when stories are estimated):

```csv
Summary,Issue Type,Description,Labels,Labels,Labels,Labels
[RAI-4] Tell candidates a model was involved,Story,"As a candidate, I want to be told an AI system screens applications, so that I can ask for a human review.

Ethical acceptance criteria (verified by the RAIA audit):
- AC-RAI-4-1: The outcome email states that an AI system is used and how to request a human review.

Implements: EVR-2

From RAIA, story RAI-4.",raia,raia-RAI-4,raia-SPR-3,raia-ethics
```

Importing: in Jira, use the CSV import for work items, map Summary, Issue Type, Description, Labels and (if present) Story Points, and import.
