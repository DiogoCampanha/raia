# Responsible AI guidelines

Everything RAIA does rests on seven principles and six sources, and nothing else. Use the same base when you analyse new work, so what you add fits what RAIA approved.

## The sources and their weight

{{sources_table}}

**Authority precedence.** Legal > standard > advisory. When two sources point different ways, the higher authority governs; two sources of the same authority that conflict are a decision for a person (`normative_conflict`), not something to average.

How each source is used:

- **EU AI Act and PL 2338/2023** decide *whether* the product is prohibited, high-risk or limited-risk, and *which obligations* follow. Treat them as escalation signals: you can recognise a trigger, but a classification change goes back to RAIA and to legal.
- **NIST AI RMF** gives the lifecycle frame: GOVERN (accountability, roles), MAP (context, impacts as likelihood × magnitude), MEASURE (testing, tracking), MANAGE (responses: mitigate, transfer, avoid, accept).
- **IEEE 7000** turns values into requirements: stakeholders (direct and indirect), the values at stake, and ethical value requirements that are traceable and verifiable by test, audit, measurement or inspection.
- **Microsoft Responsible AI Standard v2** gives the shape of a requirement teams can deliver: a goal, an owner, a review cadence and an evidence artifact.
- **ECCOLA** brings ethics into sprints: 21 cards, selected per story by what the story touches, each a set of questions to answer for that story.

## The seven principles

Use the question in the second column as a probe: if a story touches the principle and nothing in its criteria answers the question, there is a gap.

{{principles_table}}

## ECCOLA cards: which ones a story needs

Three cards apply to every AI product. The rest are selected by what the story touches (and by the product's risk context in `PROJECT_CONTEXT.md`: a high-risk tier, personal or protected data, significant effects on people).

{{eccola_table}}

What the story touches (use these words in the triage table):

{{capabilities_table}}

## Analysing a new issue yourself

When something new comes up — a story, an incident, a design choice, a question from the team — work through it in this order and write the result in the formats of `templates.md`.

1. **Describe it** in one sentence: what the system does, to whom, in which context.
2. **Stakeholders.** Who uses it (direct) and who is affected without using it (indirect)? Vulnerable groups?
3. **Principles.** Which of the seven does it touch? Use the probes above.
4. **Lifecycle.** Where are we in the NIST AI RMF lifecycle? Plan and design, data, model, verify and validate, deploy and use, operate and monitor.
5. **Place the harm.** Magnitude and likelihood on the anchored scales in `vocabulary.md`. Write one line on why. Compute the risk level from the matrix, then apply the floors (legal grounding → at least high; prohibited practice → critical and blocking).
6. **Check the requirements.** Is an approved EVR already about this? Then the work belongs under that EVR, with its priority. If none is, say so: a new requirement is a decision for the product owner and, if the issue is material, a reason to go back to RAIA.
7. **Respond.** Propose a response (mitigate, transfer, avoid; never accept on the team's behalf), an owner role, a lifecycle stage, a review cadence, a verification method and an evidence artifact.
8. **Write it as work.** An ethical acceptance criterion on an existing story, or a new story linked to the EVR. Make the condition measurable, with a threshold.
9. **Record what a person must decide**, with options and the decision owner.

## What good looks like

A good ethical acceptance criterion:

- names the stakeholder group it protects and the Microsoft RAI Standard v2 goal it serves;
- has a measurable condition with a threshold ("the shortlisting rate is reported per gender group on the release test set, and the gap between groups stays within the threshold the product owner set in EVR-3"), not an aspiration ("the model is fair");
- names the evidence artifact that proves it (a test report, an audit log, a screenshot of a notice) and the owner role who produces it;
- links the EVR it helps implement.

A good RAI story implements at least one EVR, is small enough for a sprint, and states the user or affected person it serves ("As a candidate filtered out by the model, I want to be told a model was involved and how to ask for a human review, so that I can contest the outcome").

Common gaps to look for: no human able to intervene in a case-level decision; no notice that AI is involved; fairness not measured per group; personal data collected beyond the purpose; no logging that would let a decision be reconstructed; no route for an affected person to contest or obtain redress; no monitoring after release.

{{ms_goals_table}}
