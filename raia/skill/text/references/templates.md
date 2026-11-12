# Templates

Use these formats so what you produce can go straight into the backlog or a document, and back into RAIA. The examples use ids from a RAIA project; without a project part, trace to a principle instead.

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

Full format, for a record or a review:

`AC-<story>-<n>  [<MS goal> · <stakeholder group> · evidence: <artifact> · owner: <role> · <EVR ids>]  <measurable condition with threshold>`

Plain format, for the text of a ticket. The condition in the team's own style (Given / When / Then if that is what they use), then one line that keeps the trace:

```
Given a shop opens its offers, when an offer was chosen by the model, then the screen says offers are
personalised and links to how to ask why.
Evidence: screenshot of the notice. Owner: product.   (AC-US-12-1 · EVR-3 · T2)
```

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

## Document review (P8)

```
Review · <document title> · <date>            Rests on: RAIA record | own screen (self-assessed)
What it proposes: <one sentence>

| # | Gap | Where in the document | Concerns | What would close it |
|---|---|---|---|---|
| 1 | Nobody can intervene in an individual offer | "Offer selection" | EVR-7 · human oversight | A sentence naming who can override an offer, and how |

Questions for the author: <what the document does not say and the screen needs>
Decisions for a person: <table below>
```

## "Responsible AI" section for a product document (P8)

```
Responsible AI
Where AI acts: <what the model produces or decides, and what happens next>
Who is affected: <users; people affected without using it; groups in a vulnerable position>
Tier: <per instrument, whether it binds, and whether from a RAIA record or self-assessed>
Risks we are managing: <up to three, each with the requirement or criterion that answers it>
Human oversight: <who can intervene in an individual case, and how>
What people are told: <notice, explanation, how to contest>
Evidence we will produce: <artifact · owner role>
Open decisions: <decision · owner role · blocking or not>
```

## Board check (P9)

```
Board check · <scope> · <date>
AI items with no ethical criterion: <n> · EVRs (or principles) with no item: <n> · Held by a decision: <n>
· RAI stories idle two sprints or more: <n> · Criteria with no evidence named: <n>

| Item | Problem | Concerns | Next step |
|---|---|---|---|

Next steps (at most five), most pressing first.
```

## One-page brief (P10)

```
<Product> · Responsible AI brief · <date>     Rests on: RAIA record (approved <date>) | own screen (self-assessed)
What it does with AI: <two sentences>
Where it sits: <instrument: tier, binds or reference only>
Most pressing risks: 1. … 2. … 3. …
What answers them: <requirement or criterion · owner role · state>
Decisions needed: <decision · from whom · blocking or not>
Evidence: <what exists> / <what is still missing>
Sources: <the instruments and frameworks behind the above, one line>
```

## Definition-of-done additions (P11)

Propose only the lines the product's tier and data call for:

- Every story that touches AI has at least one ethical criterion, and each criterion names its evidence.
- The evidence named in the criteria is attached to the ticket before the story is called done.
- Where outputs differ between groups of people, the difference was measured and is within the agreed threshold.
- Anyone affected is told AI is involved, where the story changes what they see.
- A person can intervene in an individual case, where the story automates a decision about someone.
- No blocking decision linked to the story is open.

## Tracker export (P6): Jira

Summary: `[<story id>] <title>`. Labels: `raia`, `raia-<story id>`, `raia-<sprint id>` when scheduled, `raia-ethics` for RAI stories. The description carries the story, its requirement links and its criteria, each with its id. A CSV for Jira's importer looks like this (one `Labels` column per label; `Story Points` only when stories are estimated):

{{jira_example}}

Importing: in Jira, use the CSV import for work items, map Summary, Issue Type, Description, Labels and (if present) Story Points, and import.
