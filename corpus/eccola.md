# ECCOLA Method (Curated Summary)

> **Authority level: ADVISORY (academic method).** Curated summary for RAG
> grounding, prepared for the RAIA proof of concept. Based on Vakkuri et al.,
> "ECCOLA — a method for implementing ethically aligned AI systems" (Journal
> of Systems and Software, 2021). The card deck is publicly available.

## Purpose

ECCOLA is a card-based method that brings AI ethics into agile development.
It packs ethical themes into **21 cards** grouped into thematic modules;
teams pick the relevant cards during sprint planning, discuss the questions
on each card for the features at hand, and document the outcome. It is
deliberately lightweight: it creates awareness and actionable discussion
rather than formal verification.

## How ECCOLA Is Used in Sprints

1. **Prepare**: the team reviews the deck and selects cards relevant to the
   product and the sprint's stories (relevance changes sprint to sprint).
2. **Use**: during planning, each selected card's questions are discussed
   for the affected stories; concrete actions or acceptance notes are
   agreed.
3. **Document**: decisions and rationales are written down (transparency of
   the process itself is part of the method — a "sprint ethics log").
4. **Iterate**: card selection and depth deepen as the product matures.

## The Thematic Modules and Cards

### Analyze (context setting)

- **#0 Stakeholder Analysis**: who develops, deploys, uses, and is affected
  (directly or indirectly)? What are their stakes and vulnerabilities?
- **#1 Types of Transparency**: which kinds of transparency matter here —
  of data, algorithms, decisions, or the development process itself?
- **#2 Regulation**: which laws and regulations apply to this system and
  domain (data protection, sector rules, AI regulation)?

### Transparency

- **#3 Traceability**: can you trace how the system was built — data
  provenance, model versions, decisions — well enough to reproduce and
  audit outcomes?
- **#4 Communication**: are the system's capabilities and limitations
  communicated honestly to users and stakeholders?
- **#5 Explainability**: can the system's decisions be explained to the
  people affected by them, in terms they understand?

### Data (privacy and governance)

- **#6 Privacy and Data**: what personal data is processed? Is it
  minimized, secured, and lawfully processed?
- **#7 Data Quality**: is the data accurate, representative of the affected
  population, and fit for the intended purpose? How is quality maintained?
- **#8 Access to Data**: who can access which data, and how is access
  controlled and logged?

### Agency and Oversight

- **#9 Human Agency**: does the system respect users' autonomy and avoid
  manipulative or coercive patterns?
- **#10 Human Oversight**: can humans monitor, intervene in, and override
  the system's decisions where impacts are significant?

### Safety and Security

- **#11 System Reliability**: how is reliability tested and assured for
  the intended operating conditions?
- **#12 System Security**: how is the system protected against misuse and
  attacks (including AI-specific attacks)?
- **#13 System Safety**: what harm could the system cause if it fails, and
  how are failure modes constrained?

### Fairness

- **#14 Accessibility**: can people with different abilities and contexts
  actually use the system?
- **#15 Stakeholder Participation**: are affected groups consulted or
  involved in design and evaluation?
- **#16 Non-Discrimination / Fairness**: could outputs discriminate against
  groups? Which fairness definition applies, and how is it checked?

### Wellbeing and Society

- **#17 Societal and Environmental Impact**: broader effects on society,
  work, and the environment (including energy footprint).
- **#18 Auditability**: could a third party assess the system's behavior
  and claims? What evidence would they need?
- **#19 Ability to Redress**: if the system harms someone, how can they
  contest and obtain remedy?
- **#20 Accountability**: who is answerable for the system's outcomes at
  each stage?

## Strengths and Limits (Design Notes for Tooling)

ECCOLA has been validated with real development teams and fits agile
rituals with low ceremony. Its limits: coverage concentrates on early and
mid development, it imposes no formal verification, and outcomes depend on
the team's discussion quality. Tooling that builds on ECCOLA should keep
its lightness (context-aware selection of relevant themes per story) while
adding what it lacks: verifiable acceptance criteria and traceable
documentation of the decisions taken.
