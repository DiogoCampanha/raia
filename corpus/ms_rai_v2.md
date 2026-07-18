# Microsoft Responsible AI Standard v2 (Curated Summary)

> **Authority level: STANDARD (corporate standard, publicly released June
> 2022).** Curated summary for RAG grounding, prepared for the RAIA proof of
> concept. Official document: "Microsoft Responsible AI Standard, v2 —
> General Requirements" (https://aka.ms/RAIStandardPDF).

## Purpose and Structure

The Standard translates Microsoft's six responsible AI principles into
concrete, verifiable requirements organized as **Goals**, each with
requirements, applicable tools, and practices. Goals are grouped by
principle: Accountability (A), Transparency (T), Fairness (F), Reliability
& Safety (RS), Privacy & Security (PS), and Inclusiveness (I). Its defining
trait is specificity: requirements are written to be checked, not admired.

## Accountability Goals

- **A1 — Impact assessment**: teams MUST complete an Impact Assessment for
  each AI system, identifying intended uses, stakeholders (including
  indirect/marginalized groups), potential harms and benefits per
  stakeholder, and mitigation plans; the assessment is reviewed and kept
  current as the system changes.
- **A2 — Oversight of significant adverse impacts**: systems that may have
  significant adverse impacts on people undergo additional review and
  restricted-use oversight (sensitive-use triage).
- **A3 — Fit for purpose**: teams assess and document evidence that the
  system is fit for its intended purpose — including evidence that the AI
  is a valid solution for the problem (not merely feasible).
- **A4 — Data governance and management**: documented provenance,
  collection consent/legal basis, quality, and management of the data used.
- **A5 — Human oversight and control**: define the role of humans in
  system operation; ensure humans can be effective in oversight roles
  (training, interface support, time to intervene); define system behavior
  when humans are unavailable; support human accountability for decisions.

## Transparency Goals

- **T1 — System intelligibility for decision-making**: when the system
  supports decisions about people, stakeholders who make decisions get the
  information they need to interpret outputs correctly (feature importance,
  confidence, limitations).
- **T2 — Communication to stakeholders**: publish capabilities and
  limitations; intended uses and out-of-scope uses are documented (e.g.
  Transparency Notes).
- **T3 — Disclosure of AI interaction**: people are informed when they are
  interacting with an AI system or consuming AI-generated content where
  misidentification could cause harm.

## Fairness Goals

- **F1 — Quality of service**: the system provides a similar quality of
  service for identified demographic groups, including marginalized
  groups; teams identify affected groups, define fairness metrics, and
  **evaluate and document performance disaggregated by group**, with
  remediation when disparities are found.
- **F2 — Allocation of resources and opportunities**: for systems used in
  decisions about employment, education, finance, housing, and similar
  opportunities, teams identify demographic groups at risk, **measure
  disparities in system outputs across those groups, document results, and
  minimize unjustified differences** (e.g. selection-rate parity analyses).
- **F3 — Minimization of stereotyping, demeaning, and erasing outputs**:
  generative and descriptive outputs must be evaluated for stereotyping or
  demeaning content affecting identified demographic groups.

## Reliability & Safety Goals

- **RS1 — Reliability and safety guidance**: define and document safe and
  reliable behavior for the intended uses, including operational factors
  and environments; establish performance thresholds before release.
- **RS2 — Failures and remediations**: identify foreseeable failure modes
  and harms; define remediation and incident-response plans; communicate
  known failure modes to users.
- **RS3 — Ongoing monitoring, feedback, and evaluation**: monitor deployed
  performance against defined metrics, collect and triage user feedback,
  and re-evaluate when the system, data, or context changes.

## Privacy & Security and Inclusiveness Goals

- **PS1/PS2**: comply with Microsoft privacy and security policies and
  standards (data minimization, security development lifecycle).
- **I1**: comply with accessibility standards and inclusive design
  practices so systems work for people with disabilities.

## Practical Requirement Style (What RAIA Borrows)

The Standard's hallmark is the verifiable requirement pattern:

1. Name the goal and affected stakeholder group.
2. State the requirement with a measurable condition and threshold
   (e.g. "demographic parity difference across gender and race groups
   <= 0.1 on validation data" as a fairness acceptance criterion).
3. Name the evidence artifact that demonstrates compliance (evaluation
   report, disaggregated metrics table, Transparency Note section).
4. Assign an owner and a review cadence.

Requirements written this way can be embedded directly into user-story
acceptance criteria and audited from versioned evidence — which is exactly
how RAIA's User Story Refiner and Auditor agents use this standard.
