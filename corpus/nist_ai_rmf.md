# NIST AI Risk Management Framework 1.0 (Curated Summary)

> **Authority level: ADVISORY (voluntary framework).** Curated summary for
> RAG grounding, prepared for the RAIA proof of concept. Based on NIST AI
> 100-1 (January 2023) and its Playbook. Official text:
> https://www.nist.gov/itl/ai-risk-management-framework

## Purpose

The NIST AI RMF is a voluntary framework to help organizations manage risks
to individuals, organizations, and society associated with AI, and to
cultivate trustworthy and responsible AI across the full lifecycle. It is
sector- and use-case-agnostic and covers the entire AI lifecycle: plan and
design; collect and process data; build and use models; verify and
validate; deploy and use; operate and monitor.

## Trustworthiness Characteristics

Trustworthy AI systems are: valid and reliable; safe; secure and resilient;
accountable and transparent; explainable and interpretable;
privacy-enhanced; and fair with harmful bias managed. NIST distinguishes
three bias categories to be managed: systemic bias, computational and
statistical bias, and human-cognitive bias.

## The Four Core Functions

### GOVERN (cross-cutting)

Cultivates a risk-management culture. Key practices:

- GOVERN 1: Policies, processes, and procedures for mapping, measuring,
  and managing AI risks are in place, transparent, and implemented
  effectively; legal and regulatory requirements are understood and managed.
- GOVERN 2: Accountability structures — roles, responsibilities, and lines
  of communication for AI risk are documented and clear; teams are
  empowered and trained.
- GOVERN 3: Workforce diversity, equity, inclusion, and accessibility are
  prioritized; decision-making benefits from diverse perspectives.
- GOVERN 4: Organizational culture prioritizes safety-first mindset,
  critical thinking about risks, and communication of risks and impacts.
- GOVERN 5: Processes for robust engagement with relevant AI actors and
  external stakeholders (feedback, appeal, redress).
- GOVERN 6: Policies address third-party risks (supply chain, pre-trained
  models, data providers).

### MAP (context and risk identification)

Establishes context and identifies risks:

- MAP 1: Context (intended purposes, settings, laws, norms, expectations,
  potential beneficial and harmful impacts) is understood and documented.
- MAP 2: Categorization of the AI system (task, methods, knowledge limits).
- MAP 3: AI capabilities, targeted usage, goals, and expected benefits and
  costs are understood.
- MAP 4: Risks and benefits are mapped for all components, including
  third-party software and data.
- MAP 5: Impacts to individuals, groups, communities, organizations, and
  society are characterized, with likelihood and magnitude.

### MEASURE (analysis and tracking)

Employs quantitative and qualitative methods to analyze and monitor risks:

- MEASURE 1: Appropriate methods and metrics are identified and applied;
  metrics selection involves consultation and is documented; effectiveness
  of measurements is assessed over time.
- MEASURE 2: Systems are evaluated for trustworthy characteristics —
  including validity, reliability, safety, security, resilience,
  transparency, accountability, explainability, privacy, and **fairness
  and harmful-bias evaluation with results documented**; evaluations
  involve the measurement of performance in conditions similar to
  deployment, and of **data representativeness relative to the population
  affected**.
- MEASURE 3: Mechanisms for tracking identified risks over time are in
  place (including risks that emerge only in production).
- MEASURE 4: Feedback about measurement efficacy is gathered and assessed,
  including from affected communities.

### MANAGE (response and recovery)

Allocates resources to treat mapped and measured risks:

- MANAGE 1: Risks are prioritized and responded to (mitigate, transfer,
  avoid, accept) based on impact, likelihood, and available resources.
- MANAGE 2: Strategies to maximize benefits and minimize negative impacts
  are planned and documented, including sustainment plans and mechanisms to
  supersede, disengage, or **deactivate systems that demonstrate
  performance or outcomes inconsistent with intended use** (rollback and
  decommissioning criteria).
- MANAGE 3: Risks from third-party entities are managed and monitored.
- MANAGE 4: Risk treatments, including response, recovery, and
  communication plans for identified and measured risks, are documented and
  monitored regularly; **post-deployment monitoring plans capture and
  evaluate input from users and affected communities, incident response,
  recovery, and change management**.

## Post-Deployment Monitoring Guidance (Measure/Manage in Practice)

For deployed systems, the RMF expects: continual monitoring of performance
and trustworthiness metrics against pre-defined thresholds; drift detection
for both data distribution and outcome equity across demographic groups;
documented escalation paths when thresholds are breached; incident
response, rollback, and deactivation procedures; and periodic re-evaluation
of metrics themselves (metrics can become stale as context shifts).

## Using the RMF with Other Norms

The RMF is deliberately non-prescriptive: it tells organizations WHAT
outcomes to achieve, not HOW. It is designed to be used alongside legal
requirements (e.g. the EU AI Act) and more prescriptive standards; its
Playbook maps each subcategory to suggested actions and references.
