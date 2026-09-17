# Agent card — Risk Classifier

> Generated from the code by `python -m raia.contract.agent_cards`. Follows `docs/templates/agent-card.md`. Do not edit by hand.

## 1. Purpose

Classifies the AI system into a legal risk tier and lists the obligations that follow from that classification.

## 2. Place in the lifecycle

| | |
|---|---|
| Layer | Product |
| SDLC phase | Conception and value definition |
| When to run | At conception, before requirements are written, and again whenever the product's purpose, markets or data change. |
| Requires approved | nothing — first stage |
| Reads | nothing |
| Produces | `02_risk_classification.md` — risk classification record |

## 3. Normative grounding

| Source | Authority |
|---|---|
| EU AI Act (Regulation (EU) 2024/1689) | legal |
| Brazilian AI Bill PL 2338/2023 | legal |

## 4. Inputs

| Group | Question | Kind | Required |
|---|---|---|---|
| The product | Product brief | textarea | yes |
| The product | Intended use | textarea | yes |
| The product | Target users and affected people | textarea | yes |
| Legal footprint | Your role | select | yes |
| Legal footprint | Where will it be placed on the market or used? | multiselect | yes |
| Legal footprint | Is it deployed by a public body, or to provide a public service? | boolean | no |
| Legal footprint | Are you the provider of a general-purpose AI model? | boolean | no |
| Purpose and practices | Which of these describes what the system is used for? | multiselect | yes |
| Purpose and practices | Is the AI a safety component of a product already regulated for safety? | boolean | no |
| Purpose and practices | Does the system do any of these? | multiselect | yes |
| Purpose and practices | Does any of these apply? | multiselect | yes |
| How decisions are made | How much does the system decide on its own? | select | yes |
| How decisions are made | Does an output produce legal effects, or otherwise significantly affect a person? | select | yes |
| How decisions are made | What oversight exists today? | select | yes |
| Data | Which of these does the system process? | multiselect | yes |
| Status and exemptions | Where is the system in its lifecycle? | select | yes |
| Status and exemptions | Do you intend to claim the narrow-task exemption from high-risk status? | boolean | no |
| Status and exemptions | On what basis? | textarea | no |

## 5. What the decision procedure settles in code

- Matches the declared purpose and practices against the prohibited-practice and high-risk area lists of the EU AI Act and the Brazilian PL 2338/2023.
- Derives the risk tier for each jurisdiction and the obligations that follow from that tier and from your role (provider or deployer).
- Identifies the legal excerpts that must be in front of the reviewer.

Checklist the record must declare:

- `prohibited_screen` — State the result of the prohibited-practice screen for both regimes
- `tier_eu` — Justify the EU tier, naming the specific area or article
- `tier_br` — Justify the Brazilian tier, naming the specific area
- `obligations` — Explain every assembled obligation in the team's own context
- `oversight` — Assess whether the declared oversight design meets the obligations
- `data_governance` — Address the declared data categories and bias exposure
- `next_steps` — Give concrete next steps for this lifecycle stage
- `open_issues` — Carry forward every open issue raised here, plus any you add

Excerpts pinned for the canonical scenario:

- EU AI Act (Regulation (EU) 2024/1689) — Article 5 — Prohibited AI Practices (Unacceptable Risk) (prohibited-practice screen)
- EU AI Act (Regulation (EU) 2024/1689) — Article 6 and Annex III — High-Risk AI Systems (high-risk area determination)
- Brazilian AI Bill PL 2338/2023 — Excessive Risk (Prohibited) Systems (excessive-risk screen)
- Brazilian AI Bill PL 2338/2023 — High-Risk Systems (Art. 17 area list) (high-risk area determination)
- EU AI Act (Regulation (EU) 2024/1689) — Obligations for High-Risk Systems (Articles 8–15) (provider obligations)
- EU AI Act (Regulation (EU) 2024/1689) — Deployer Obligations (Art. 26) and Fundamental Rights Impact Assessment (Art. 27) (deployer obligations)
- Brazilian AI Bill PL 2338/2023 — Governance Obligations (governance obligations)
- Brazilian AI Bill PL 2338/2023 — Rights of Affected Persons (rights of affected persons)

## 6. What a person decides

- Whether a narrow-task exemption actually holds for your system.
- Whether the classification fits how the product is really used.
- Every open issue the record raises, and whether to approve, edit or reject the record.

## 7. The record it produces

Schema `raia-record/1.0` — `docs/schema/risk_classifier.schema.json`. Identifier prefix `RC`. Shared core as in `docs/output-contract.md`; the extension:

| Field | Content |
|---|---|
| `prohibited_screen` | Result of the EU AI Act Art. 5 and PL 2338 excessive-risk screen. |
| `eu_tier_justification` | Why the EU tier holds, naming the area or article. |
| `br_tier_justification` | Why the Brazilian tier holds, naming the area. |
| `obligations` | One note per computed obligation code. |
| `obligations[].code` | An obligation code from the computed table, exactly. |
| `obligations[].meaning_for_this_product` | — |
| `obligations[].citations` | Citation tags copied exactly from the retrieved excerpts, e.g. "[Source: ... / authority: legal]". Never invent one. |
| `human_oversight_assessment` | Whether the declared oversight design meets the oversight obligations. |
| `affected_persons_rights` | How affected persons' rights are operationalised in the product. |
| `impact_assessments` | Which impact assessments the instruments require (fundamental rights / algorithmic). |

Rendered sections: Summary → Findings → Risk Classification → Applicable Legal Obligations → Human Oversight and Affected Persons → Action Plan → Open Issues → Not Grounded in Retrieved Excerpts → Declared Coverage.

Verdict keys the agent declares: `eu_tier`, `br_tier`.

## 8. Checks

- The record conforms to the schema (one repair attempt, then a fallback record)
- Every citation resolves to an excerpt retrieved for this run
- Every checklist item is declared covered, not applicable or not grounded
- Every finding has an action or an open issue
- The rule engine's issues are carried forward; the verdict is reconciled
- Every computed obligation code has a note, and no other code appears

## 9. Limitations

- The normative corpus is a set of curated summaries prepared for the project; a citation resolves to a section of a summary, not to official wording.
- The screens match declared answers against enumerated lists; a purpose the person does not declare is not screened.
- Whether the narrow-task exemption holds is open-textured and always left to a person.
