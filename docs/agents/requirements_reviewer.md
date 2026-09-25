# Agent card — Requirements Reviewer

> Generated from the code by `python -m raia.contract.agent_cards`. Follows `docs/templates/agent-card.md`. Do not edit by hand.

## 1. Purpose

Reviews the software requirements against the risk classification and derives verifiable ethical value requirements.

## 2. Place in the lifecycle

| | |
|---|---|
| Layer | Product |
| SDLC phase | Requirements definition |
| When to run | Once the risk classification is approved and a first set of requirements exists. |
| Requires approved | Risk Classifier |
| Reads | product_brief, Risk Classifier |
| Produces | `03_requirements_review.md` — requirements review record |

## 3. Normative grounding

| Source | Authority |
|---|---|
| IEEE 7000-2021 (Value-Based Engineering) | standard |
| Microsoft Responsible AI Standard v2 | standard |

## 4. Inputs

| Group | Question | Kind | Required |
|---|---|---|---|
| Current requirements | Software requirements | textarea | yes |
| Current requirements | How are they written? | select | no |
| What already exists | Which of these are already in place? | multiselect | yes |
| What already exists | Delivery constraints | textarea | no |
| Values and stakeholders | Which principles does your team believe are at stake? | multiselect | no |
| Values and stakeholders | Whose values were elicited? | multiselect | yes |

## 5. What the decision procedure settles in code

- Builds a coverage matrix: every obligation from the approved classification and each of the seven Responsible AI principles, tested against your requirements and existing controls.
- Lists the uncovered cells as gaps, so a gap is computed rather than asserted.
- On request, pre-fills the stakeholder and principle questions you left empty from the approved classification, with a reason per value, and offers a few candidate requirements for the gaps your answers leave. Candidates that cite no retrieved excerpt, address a gap that was not computed or have no testable fit criterion are dropped before you see them.
- Keeps adopted recommendations apart from the requirements the team wrote: coverage that rests on one is marked as such in the record.

Checklist the record must declare:

- `gap_analysis` — Explain every computed GAP row in the team's own context
- `evrs` — Write one ethical value requirement per assigned id, all verifiable
- `stakeholders` — Name the stakeholders and values each requirement protects
- `impact_assessment` — State what an impact assessment would flag for this system
- `tradeoffs` — Surface value trade-offs rather than resolving them
- `open_issues` — Carry forward every open issue raised here, plus any you add

Excerpts pinned for the canonical scenario:

- IEEE 7000-2021 (Value-Based Engineering) — 3. Ethical Requirements Definition (Value-Based Requirements Engineering) (how ethical value requirements are derived)
- IEEE 7000-2021 (Value-Based Engineering) — Writing Good EVRs (Practical Guidance) (what makes a requirement verifiable)
- IEEE 7000-2021 (Value-Based Engineering) — 2. Ethical Values Elicitation and Prioritization (value elicitation and prioritization)
- Microsoft Responsible AI Standard v2 — Practical Requirement Style (What RAIA Borrows) (requirement style)
- Microsoft Responsible AI Standard v2 — Accountability Goals (principle grounding)
- Microsoft Responsible AI Standard v2 — Fairness Goals (principle grounding)
- Microsoft Responsible AI Standard v2 — Privacy & Security and Inclusiveness Goals (principle grounding)
- Microsoft Responsible AI Standard v2 — Reliability & Safety Goals (principle grounding)
- Microsoft Responsible AI Standard v2 — Transparency Goals (principle grounding)

## 6. What a person decides

- Which recommended requirements to adopt, edit or reject, one at a time, and whether pre-filled answers reflect the project. The controls in place are never pre-filled.
- Which proposed ethical value requirements the team adopts.
- How stakeholder values are weighed where they conflict.
- Every open issue the record raises, and whether to approve, edit or reject the record.

## 7. The record it produces

Schema `raia-record/1.2` — `docs/schema/requirements_reviewer.schema.json`. Identifier prefix `RR`. Shared core as in `docs/output-contract.md`; the extension:

| Field | Content |
|---|---|
| `context_of_use` | The operational environment and conditions of use (IEEE 7000 concept of operations). |
| `stakeholders` | Direct and indirect stakeholders and the values at stake for each. |
| `stakeholders[].name` | — |
| `stakeholders[].kind` | direct (uses the system) or indirect (affected without using it). |
| `stakeholders[].values` | — |
| `value_register` | Prioritised core values with threats and opportunities (IEEE 7000 Value Register). |
| `value_register[].value` | The core value. |
| `value_register[].rank` | 1 = highest priority core value. |
| `value_register[].threats` | How the design could harm this value, in one sentence. |
| `value_register[].opportunities` | How the design could advance it, in one sentence. |
| `gap_analysis` | One entry per computed EVR id. |
| `gap_analysis[].evr_id` | A computed EVR id, exactly. |
| `gap_analysis[].explanation` | What is missing and why it matters for this product, in one or two sentences. |
| `gap_analysis[].citations` | Citation tags copied exactly from the retrieved excerpts, e.g. "[Source: ... / authority: legal]". Never invent one. |
| `evrs` | One ethical value requirement per assigned id. |
| `evrs[].id` | An assigned EVR id, exactly. |
| `evrs[].value` | — |
| `evrs[].stakeholders` | — |
| `evrs[].statement` | The requirement, bound to this context of use, in one sentence. |
| `evrs[].fit_criterion` | The measurable condition that settles whether it is met. |
| `evrs[].verification_method` | — |
| `evrs[].traces_to` | Obligation codes or principle refs it derives from. |
| `evrs[].citations` | Citation tags copied exactly from the retrieved excerpts, e.g. "[Source: ... / authority: legal]". Never invent one. |
| `impact_assessment` | Microsoft RAI Standard v2 goal A1 impact assessment. |
| `impact_assessment.intended_uses` | Intended and out-of-scope uses. |
| `impact_assessment.harms_and_benefits` | Potential harms and benefits per stakeholder. |
| `impact_assessment.harms_and_benefits[].stakeholder` | — |
| `impact_assessment.harms_and_benefits[].harms` | — |
| `impact_assessment.harms_and_benefits[].benefits` | — |
| `impact_assessment.mitigations` | The main mitigations, conclusion first. |

Rendered sections: Summary → Action Plan → Open Issues → Findings → Context of Use and Stakeholders → Value Register → Gap Analysis → Ethical Value Requirements → Impact Assessment → Not Grounded in Retrieved Excerpts → Declared Coverage → Verdict Reconciliation.

Verdict keys the agent declares: `gap_count`.

## 8. Checks

- The record conforms to the schema (one repair attempt, then a fallback record)
- Every citation resolves to an excerpt retrieved for this run
- Every checklist item is declared covered, not applicable or not grounded
- Every finding has an action or an open issue
- The rule engine's issues are carried forward; the verdict is reconciled
- Every assigned EVR id has a requirement and a gap note, and no other id appears
- Every requirement carries a testable element
- A recommended candidate is shown only if it addresses a computed gap, cites a retrieved excerpt and has a testable fit criterion

## 9. Limitations

- The normative corpus is a set of curated summaries prepared for the project; a citation resolves to a section of a summary, not to official wording.
- The coverage matrix is lexical: it produces candidate gaps for review and is not evidence that a requirement is absent or adequate.
- Value elicitation is recorded from the declared stakeholders; it does not replace eliciting values from those stakeholders.
- Suggested stakeholders and principles follow fixed rules over the classification: a starting point for elicitation, not a substitute for it. Recommended requirements are candidates; adopting one makes it the team's commitment to deliver.
