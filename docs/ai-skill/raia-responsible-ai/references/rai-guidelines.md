# Responsible AI guidelines

Everything RAIA does rests on seven principles and six sources, and nothing else. Use the same base when you analyse new work, so what you add fits what RAIA approved.

## The sources and their weight

| Source | Authority |
|---|---|
| EU AI Act (Regulation (EU) 2024/1689) | legal |
| Brazilian AI Bill PL 2338/2023 | legal |
| IEEE 7000-2021 (Value-Based Engineering) | standard |
| Microsoft Responsible AI Standard v2 | standard |
| NIST AI Risk Management Framework 1.0 | advisory |
| ECCOLA Method (21 cards) | advisory |

**Authority precedence.** Legal > standard > advisory. When two sources point different ways, the higher authority governs; two sources of the same authority that conflict are a decision for a person (`normative_conflict`), not something to average.

How each source is used:

- **EU AI Act and PL 2338/2023** decide *whether* the product is prohibited, high-risk or limited-risk, and *which obligations* follow. Treat them as escalation signals: you can recognise a trigger, but a classification change goes back to RAIA and to legal.
- **NIST AI RMF** gives the lifecycle frame: GOVERN (accountability, roles), MAP (context, impacts as likelihood × magnitude), MEASURE (testing, tracking), MANAGE (responses: mitigate, transfer, avoid, accept).
- **IEEE 7000** turns values into requirements: stakeholders (direct and indirect), the values at stake, and ethical value requirements that are traceable and verifiable by test, audit, measurement or inspection.
- **Microsoft Responsible AI Standard v2** gives the shape of a requirement teams can deliver: a goal, an owner, a review cadence and an evidence artifact.
- **ECCOLA** brings ethics into sprints: 21 cards, selected per story by what the story touches, each a set of questions to answer for that story.

## The seven principles

Use the question in the second column as a probe: if a story touches the principle and nothing in its criteria answers the question, there is a gap.

| Principle | Probe: what the work must answer |
|---|---|
| **Accountability** (`accountability`) | Who is answerable for outcomes at each stage, and what evidence records it? |
| **Diversity, non-discrimination and fairness** (`fairness`) | Could outputs disadvantage a group, which fairness measure applies, and how is it checked? |
| **Human agency and oversight** (`human_oversight`) | Can a person understand, intervene in, override or stop the system where impact is significant? |
| **Privacy and data governance** (`privacy`) | What personal data is processed, on what basis, minimised how, and governed by whom? |
| **Technical robustness and safety** (`robustness`) | How is the system tested for accuracy and resilience in its real operating conditions? |
| **Transparency** (`transparency`) | What are affected people and operators told, and can a decision be explained to them? |
| **Social and environmental well-being** (`wellbeing`) | What are the broader effects on affected communities, work and the environment? |

## ECCOLA cards: which ones a story needs

Three cards apply to every AI product. The rest are selected by what the story touches (and by the product's risk context in `PROJECT_CONTEXT.md`: a high-risk tier, personal or protected data, significant effects on people).

| Card | Theme | Selected when |
|---|---|---|
| `#0` Stakeholder Analysis | Analyze | every AI product |
| `#1` Types of Transparency | Analyze | every AI product |
| `#2` Regulation | Analyze | high-risk tier; limited-risk tier (transparency duties) |
| `#3` Traceability | Transparency | high-risk tier; touches `automation`; touches `scoring` |
| `#4` Communication | Transparency | touches `generation`; touches `personalization`; limited-risk tier (transparency duties) |
| `#5` Explainability | Transparency | high-risk tier; significant effects on people; touches `scoring`; touches `explanation` |
| `#6` Privacy and Data | Data | personal data; touches `data_collection` |
| `#7` Data Quality | Data | high-risk tier; touches `scoring`; touches `integration` |
| `#8` Access to Data | Data | personal data; touches `access_control`; touches `data_collection` |
| `#9` Human Agency | Agency | touches `personalization`; touches `generation`; significant effects on people |
| `#10` Human Oversight | Agency | high-risk tier; touches `automation`; significant effects on people |
| `#11` System Reliability | Safety | high-risk tier; live in production |
| `#12` System Security | Safety | personal data; touches `integration`; live in production |
| `#13` System Safety | Safety | high-risk tier; safety component |
| `#14` Accessibility | Fairness | touches `explanation`; touches `personalization`; disability data |
| `#15` Stakeholder Participation | Fairness | high-risk tier |
| `#16` Non-Discrimination / Fairness | Fairness | protected attributes or their proxies; touches `scoring`; touches `automation`; high-risk tier |
| `#17` Societal and Environmental Impact | Wellbeing | touches `generation`; touches `personalization`; high-risk tier |
| `#18` Auditability | Wellbeing | high-risk tier; touches `automation` |
| `#19` Ability to Redress | Wellbeing | significant effects on people; high-risk tier |
| `#20` Accountability | Wellbeing | every AI product |

What the story touches (use these words in the triage table):

| Touches | Meaning |
|---|---|
| `scoring` | Scores, ranks or filters people |
| `automation` | Automates or strongly steers a decision about a person |
| `data_collection` | Collects or enriches personal data |
| `personalization` | Personalizes what a person sees |
| `generation` | Generates content shown to people |
| `explanation` | Explains an outcome to a user or an affected person |
| `analytics` | Reports aggregate metrics internally |
| `integration` | Integrates an external data source or model |
| `access_control` | Controls who can see or reach data |

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

## Microsoft Responsible AI Standard v2 goals

Every ethical acceptance criterion names one.

| Goal | Name |
|---|---|
| `A1` | Impact assessment |
| `A2` | Oversight of significant adverse impacts |
| `A3` | Fit for purpose |
| `A4` | Data governance and management |
| `A5` | Human oversight and control |
| `T1` | System intelligibility for decision-making |
| `T2` | Communication to stakeholders |
| `T3` | Disclosure of AI interaction |
| `F1` | Quality of service |
| `F2` | Allocation of resources and opportunities |
| `F3` | Minimization of stereotyping, demeaning, and erasing outputs |
| `RS1` | Reliability and safety guidance |
| `RS2` | Failures and remediations |
| `RS3` | Ongoing monitoring, feedback, and evaluation |
| `PS1` | Privacy |
| `PS2` | Security |
| `I1` | Inclusiveness |
