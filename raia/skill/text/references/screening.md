# Screening a product yourself

Use this when there is no project part, or when the reconciliation step shows that the real product differs from what RAIA was told. It is the screen RAIA's rule engine runs, written as questions and tables. What you conclude with it is **self-assessed, not a RAIA record**: nobody approved it, no normative text was retrieved for it, and it is not legal advice. Say so wherever the result is used.

Two instruments are screened. The EU AI Act is in force. PL 2338/2023 is a Brazilian bill, not yet law: its tier says what the law would ask if it passes as it stands. A tier binds only where the product is placed on the market or used; elsewhere it is a reference.

## 1. Ask what decides a classification

Ask only what you cannot read from the material you were given. These are the questions RAIA's Risk Classifier asks, with the answers it accepts.

{{screening_questions}}

"Profiling" means using a person's data to evaluate or predict aspects of them. Scoring or ranking applicants, borrowers or users is profiling.

## 2. Prohibited practices

{{prohibited_table}}

A practice marked prohibited stops the work: tell the user to take it to the legal and compliance owner before anything else. A restricted practice is allowed only under a narrow legal exception that a person must confirm.

## 3. The tier

EU AI Act, first match wins:

1. A prohibited practice: **{{tier_unacceptable}}**.
2. A restricted practice: **{{tier_restricted}}**.
3. A purpose in a listed high-risk area, or a safety component of a product already regulated for safety: **{{tier_high}}**. The narrow-task exemption can be claimed only for a listed area and never for a system that profiles people; it must be documented and stays reviewable.
4. A transparency duty applies (below): **{{tier_limited}}**.
5. Otherwise: **{{tier_minimal}}**.

PL 2338/2023, first match wins: a prohibited practice, **{{br_excessive}}**; a restricted practice, **{{tier_restricted}}**; a purpose in a listed area, **{{br_high}}**; otherwise **{{br_not_listed}}**.

High-risk areas:

{{areas_table}}

Transparency duties apply when any of these is true:

{{transparency_table}}

A generative system counts as generating content, and a system that talks with people counts as interacting with them, whether or not the user said so.

## 4. The obligations that follow

{{obligations_table}}

## 5. What the screen raises for a person

Raise each of these as a decision, with its owner, and never settle it yourself:

- Whether an output has legal or similarly significant effects on a person is not known: legal and compliance.
- Decisions are fully automated, or a person almost always accepts the output, while nobody can intervene in an individual case. On a high-risk system this blocks the product in its current form (legal and compliance); otherwise it is a risk for the product owner to arbitrate.
- The two instruments classify the system differently and both markets are targeted: legal and compliance.
- Only rules written by people were declared: the product may fall outside the definition of an AI system; a person decides, and until then it is screened as in scope.
- The answers contradict each other (for example, no person in between, yet a person is said to review the output): product.

## 6. What the tier does not settle

A product outside the listed areas is not thereby free of risk. Whatever the tier, go on to the seven principles in `rai-guidelines.md`: how much the system decides on its own against the oversight that exists, the data it uses, and who is affected without using it.
