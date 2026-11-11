# Screening a product yourself

Use this when there is no project part, or when the reconciliation step shows that the real product differs from what RAIA was told. It is the screen RAIA's rule engine runs, written as questions and tables. What you conclude with it is **self-assessed, not a RAIA record**: nobody approved it, no normative text was retrieved for it, and it is not legal advice. Say so wherever the result is used.

Two instruments are screened. The EU AI Act is in force. PL 2338/2023 is a Brazilian bill, not yet law: its tier says what the law would ask if it passes as it stands. A tier binds only where the product is placed on the market or used; elsewhere it is a reference.

## 1. Ask what decides a classification

Ask only what you cannot read from the material you were given. These are the questions RAIA's Risk Classifier asks, with the answers it accepts.

| Question | Answers (one, or any that apply) |
|---|---|
| What kind of AI does it use? | Rules or thresholds written by people — nothing is learned from data · Machine learning trained on data (including deep learning) — classifies, scores, ranks, predicts or recommends · Generative AI — produces text, images, audio, video or code (for example an LLM) · Logic- or knowledge-based inference — reasons over encoded knowledge (expert system, knowledge graph) |
| Where in the product does the AI act? | Reads or prepares inputs — extraction, transcription, enrichment · Scores, ranks, classifies or predicts · Generates content that people see or receive · Talks with people directly (chat, voice, assistant) · Makes or carries out a decision with no person in between · Monitors people, processes or systems |
| Where does the model come from? | Built and trained by us · A third-party model we fine-tune or otherwise adapt · A third-party model or AI service used as-is (for example through an API) · No trained model — the logic is rules only |
| Your role | Provider — we build it, or place it on the market under our name · Deployer — we operate a system built by someone else · Both — we build it and we operate it ourselves |
| Where will it be placed on the market or used? | European Union / EEA · Brazil · Other jurisdictions only |
| Is it deployed by a public body, or to provide a public service? | Yes · No |
| Are you the provider of a general-purpose AI model? | Yes · No |
| Which of these describes what the system is used for? | Biometric identification, categorisation or emotion recognition · Safety component of critical infrastructure (traffic, water, energy, digital) · Education and vocational training — admission, assessment, proctoring · Employment — recruitment, screening, evaluation, promotion, termination, task allocation, worker monitoring · Access to essential services — credit scoring, insurance pricing, public benefits, emergency triage · Law enforcement or public security · Migration, asylum or border control · Administration of justice or democratic processes · Health applications, including diagnosis support · Autonomous vehicles operating in public spaces · Large-scale content curation or recommendation affecting information integrity · None of these — the purpose is outside every listed area |
| Does the system profile people? | Yes · No |
| Is the AI a safety component of a product already regulated for safety? | Yes · No |
| Does the system do any of these? | Subliminal, manipulative or deceptive techniques that materially distort behaviour · Exploits vulnerabilities of age, disability, or social/economic situation · Social scoring leading to unjustified or disproportionate detrimental treatment · Predicts criminal offence or recidivism risk from profiling or personality traits · Untargeted scraping of facial images to build a recognition database · Infers emotions in the workplace or in educational institutions · Biometric categorisation inferring sensitive attributes · Enables production or dissemination of child sexual abuse material · Autonomous weapons without meaningful human control · Real-time remote biometric identification in public spaces for law enforcement · None of these |
| Does any of these apply? | People interact with the system directly (chatbot, assistant, voice agent) · The system generates or manipulates image, audio, video or text content · The system produces content resembling real people, places or events · The system performs emotion recognition on people · The system performs biometric categorisation · None of these |
| How much does the system decide on its own? | Fully automated — the system's output is the decision · A person confirms the output, but in practice almost always accepts it · A recommendation a person reviews and may override · Purely informational — no decision about a person follows from it |
| Does an output produce legal effects, or otherwise significantly affect a person? | Yes · No · Not sure yet |
| What oversight exists today? | No oversight mechanism designed yet · People can monitor outputs but cannot intervene in a specific case · A person can override an individual output · A person makes the decision; the system only informs it |
| Which of these does the system process? | Biometric data · Health data · Protected attributes (race, gender, age, disability, religion, origin) · Strong proxies for protected attributes (postcode, school, name, photo) · Data about children or adolescents · Location or movement data · Financial or credit data · Private communications content · None of these |
| Where is the system in its lifecycle? | Idea / discovery · In development · Piloting with real users · Live in production |
| Do you intend to claim the narrow-task exemption from high-risk status? | Yes · No |

"Profiling" means using a person's data to evaluate or predict aspects of them. Scoring or ranking applicants, borrowers or users is profiling.

## 2. Prohibited practices

| Practice | Under | Status |
|---|---|---|
| Subliminal, manipulative or deceptive techniques that materially distort behaviour | EU AI Act and PL 2338/2023 | prohibited |
| Exploits vulnerabilities of age, disability, or social/economic situation | EU AI Act and PL 2338/2023 | prohibited |
| Social scoring leading to unjustified or disproportionate detrimental treatment | EU AI Act and PL 2338/2023 | prohibited |
| Predicts criminal offence or recidivism risk from profiling or personality traits | EU AI Act and PL 2338/2023 | prohibited |
| Untargeted scraping of facial images to build a recognition database | EU AI Act | prohibited |
| Infers emotions in the workplace or in educational institutions | EU AI Act | prohibited |
| Biometric categorisation inferring sensitive attributes | EU AI Act | prohibited |
| Enables production or dissemination of child sexual abuse material | PL 2338/2023 | prohibited |
| Autonomous weapons without meaningful human control | PL 2338/2023 | prohibited |
| Real-time remote biometric identification in public spaces for law enforcement | EU AI Act and PL 2338/2023 | restricted: narrow legal exceptions only |

A practice marked prohibited stops the work: tell the user to take it to the legal and compliance owner before anything else. A restricted practice is allowed only under a narrow legal exception that a person must confirm.

## 3. The tier

EU AI Act, first match wins:

1. A prohibited practice: **unacceptable — prohibited practice**.
2. A restricted practice: **prohibited unless a narrow legal exception applies**.
3. A purpose in a listed high-risk area, or a safety component of a product already regulated for safety: **high-risk**. The narrow-task exemption can be claimed only for a listed area and never for a system that profiles people; it must be documented and stays reviewable.
4. A transparency duty applies (below): **limited risk — transparency duties**.
5. Otherwise: **minimal risk**.

PL 2338/2023, first match wins: a prohibited practice, **excessive risk — prohibited**; a restricted practice, **prohibited unless a narrow legal exception applies**; a purpose in a listed area, **high risk**; otherwise **not in the listed high-risk areas**.

High-risk areas:

| Area | EU AI Act, Annex III | PL 2338/2023, art. 17 |
|---|---|---|
| Biometric identification, categorisation or emotion recognition | 1 — Biometrics | 8 — Biometric identification and emotion recognition |
| Safety component of critical infrastructure (traffic, water, energy, digital) | 2 — Critical infrastructure | 1 — Critical infrastructure |
| Education and vocational training — admission, assessment, proctoring | 3 — Education and vocational training | 2 — Education and vocational training |
| Employment — recruitment, screening, evaluation, promotion, termination, task allocation, worker monitoring | 4 — Employment, workers management and access to self-employment | 3 — Recruitment, screening and evaluation of candidates and workers |
| Access to essential services — credit scoring, insurance pricing, public benefits, emergency triage | 5 — Access to essential private and public services | 4 — Access to essential public and private services and benefits |
| Law enforcement or public security | 6 — Law enforcement | 9 — Criminal investigation and public security |
| Migration, asylum or border control | 7 — Migration, asylum and border control | 10 — Migration and border control |
| Administration of justice or democratic processes | 8 — Administration of justice and democratic processes | 5 — Administration of justice |
| Health applications, including diagnosis support | not listed | 7 — Health applications and diagnosis support |
| Autonomous vehicles operating in public spaces | not listed | 6 — Autonomous vehicles in public spaces |
| Large-scale content curation or recommendation affecting information integrity | not listed | 11 — Large-scale content curation and recommendation |

Transparency duties apply when any of these is true:

- People interact with the system directly (chatbot, assistant, voice agent)
- The system generates or manipulates image, audio, video or text content
- The system produces content resembling real people, places or events
- The system performs emotion recognition on people
- The system performs biometric categorisation

A generative system counts as generating content, and a system that talks with people counts as interacting with them, whether or not the user said so.

## 4. The obligations that follow

| Code | Where | Obligation | Applies when |
|---|---|---|---|
| `eu.art9` | EU AI Act | Risk management system across the whole lifecycle | high-risk + provider role |
| `eu.art10` | EU AI Act | Data and data governance, including examination for biases | high-risk + provider role |
| `eu.art11` | EU AI Act | Technical documentation before market placement | high-risk + provider role |
| `eu.art12` | EU AI Act | Automatic record-keeping and logging for traceability | high-risk + provider role |
| `eu.art13` | EU AI Act | Transparency and instructions for use provided to deployers | high-risk + provider role |
| `eu.art14` | EU AI Act | Human oversight designed into the system | high-risk + provider role |
| `eu.art15` | EU AI Act | Accuracy, robustness and cybersecurity | high-risk + provider role |
| `eu.art26` | EU AI Act | Use per instructions, competent human oversight, input-data relevance, log keeping | high-risk + deployer role |
| `eu.art27` | EU AI Act | Fundamental rights impact assessment before first use | deployer is a public body or provides essential services |
| `eu.art6_3_doc` | EU AI Act | Document and keep reviewable the assessment that the narrow-task exemption applies | narrow-task exemption claimed |
| `eu.art50` | EU AI Act | Transparency duties: disclose AI interaction, mark synthetic content, disclose deep fakes, inform people exposed to emotion recognition or biometric categorisation | transparency trigger present |
| `eu.gpai` | EU AI Act | General-purpose model duties: technical documentation, information to downstream providers, copyright policy, training-content summary | provider of a general-purpose model |
| `br.aia` | PL 2338/2023 | Algorithmic Impact Assessment, documented, shared with the authority and kept current | listed high-risk area |
| `br.logging` | PL 2338/2023 | Documentation and automatic logging enabling auditability and traceability | listed high-risk area |
| `br.testing` | PL 2338/2023 | Reliability, robustness and accuracy testing appropriate to intended use | listed high-risk area |
| `br.data_governance` | PL 2338/2023 | Data governance to mitigate discriminatory bias, with representativeness analysis | listed high-risk area |
| `br.explainability` | PL 2338/2023 | Technical explainability sufficient for human review of decisions | listed high-risk area |
| `br.supervision` | PL 2338/2023 | Effective human supervision enabling understanding and intervention | listed high-risk area |
| `br.publicity` | PL 2338/2023 | Additional publicity requirements for public-sector deployment | public-sector deployment |
| `br.governance` | PL 2338/2023 | Governance structures and internal processes for transparency, data governance and security | applies to all AI agents |
| `br.rights` | PL 2338/2023 | Operationalize affected persons' rights: prior information, explanation, contestation, human review, non-discrimination | applies to all AI agents |

## 5. What the screen raises for a person

Raise each of these as a decision, with its owner, and never settle it yourself:

- Whether an output has legal or similarly significant effects on a person is not known: legal and compliance.
- Decisions are fully automated, or a person almost always accepts the output, while nobody can intervene in an individual case. On a high-risk system this blocks the product in its current form (legal and compliance); otherwise it is a risk for the product owner to arbitrate.
- The two instruments classify the system differently and both markets are targeted: legal and compliance.
- Only rules written by people were declared: the product may fall outside the definition of an AI system; a person decides, and until then it is screened as in scope.
- The answers contradict each other (for example, no person in between, yet a person is said to review the output): product.

## 6. What the tier does not settle

A product outside the listed areas is not thereby free of risk. Whatever the tier, go on to the seven principles in `rai-guidelines.md`: how much the system decides on its own against the oversight that exists, the data it uses, and who is affected without using it.
