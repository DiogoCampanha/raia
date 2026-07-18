# RAIA — Tester Guide

Welcome! You are testing **RAIA (Responsible AI Assistant)**, a research
prototype that helps development teams apply Responsible AI practices
across the software life cycle. Nothing to install — everything runs in
your browser.

## What you are looking at

Five specialized AI agents, each tied to a phase of the development cycle:

1. **Risk Classifier** (Product) — classifies an AI product idea into legal
   risk tiers (EU AI Act, Brazilian PL 2338/2023) and lists the obligations
   that follow.
2. **Requirements Reviewer** (Product) — finds Responsible-AI gaps in the
   requirements and proposes verifiable *ethical value requirements*.
3. **User Story Refiner** (Dev) — adds measurable ethical acceptance
   criteria to backlog stories.
4. **Auditor** (Dev) — audits sprint outcomes against the ethical
   requirements; verdicts must cite concrete evidence.
5. **Drift Monitor** (Ops) — analyzes production fairness telemetry;
   the numbers are computed by code, the agent only interprets them.

Two things to watch for while testing — they are the core of the design:

- **You are the checkpoint.** No agent output is saved until you approve
  it. You can edit the draft, or reject it with feedback and watch the
  agent revise.
- **Everything is cited.** Agent claims carry tags like
  `[Source: EU AI Act — Annex III | authority: legal]`. If a claim has no
  tag, that's a finding worth reporting.

## Suggested 15-minute walkthrough

1. In the sidebar, create a project (any name).
2. Open **Risk Classifier** → click **Load example** (a resume-screening
   product) → **Run**. Read the draft: are the classification and
   obligations plausible and properly cited?
3. Try **rejecting** it with feedback (e.g. "consider candidates with
   disabilities explicitly") — check whether the revision addresses it.
4. **Approve** the revision. Note your name goes into the audit trail.
5. Continue down the sidebar: Requirements Reviewer → User Story Refiner →
   Auditor → Drift Monitor, using **Load example** each time.
6. Open **📜 Audit Trail**: every approval you made is a Git commit.
7. Try to break it: run agents out of order (they should be blocked),
   paste your own product idea, reject repeatedly.

## What feedback helps most

- Were the recommendations **specific enough to act on**, or vague?
- Did any recommendation look **hallucinated or wrongly cited**?
- Was the **human-approval flow** clear? Did you feel in control?
- Would this fit **your team's real workflow**? What's missing?
- Any usability friction (labels, ordering, unclear states)?

Please send feedback to the study coordinator. Thank you!

> Note: if the sidebar shows "Demo mode", the deployment has no LLM key
> configured and outputs are placeholders — tell the coordinator.
