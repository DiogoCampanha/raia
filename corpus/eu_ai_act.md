# EU AI Act — Regulation (EU) 2024/1689 (Curated Summary)

> **Authority level: LEGAL.** Curated summary for RAG grounding, prepared for the
> RAIA proof of concept. Not legal advice. Always verify against the official
> text: https://eur-lex.europa.eu/eli/reg/2024/1689/oj

## Scope and Approach

The EU AI Act is a risk-based regulation: obligations scale with the risk an
AI system poses to health, safety, and fundamental rights. It applies to
providers placing AI systems on the EU market and to deployers using them in
the EU, regardless of where the provider is established (Art. 2).

## Article 5 — Prohibited AI Practices (Unacceptable Risk)

The following practices are prohibited (Art. 5(1)):

- Subliminal, manipulative, or deceptive techniques that materially distort
  behavior and cause or are likely to cause significant harm.
- Exploitation of vulnerabilities due to age, disability, or social/economic
  situation, causing or likely to cause significant harm.
- Social scoring by or on behalf of public authorities or private actors
  leading to detrimental or unfavourable treatment that is unjustified or
  disproportionate.
- Risk assessment of natural persons to predict criminal offences based
  solely on profiling or personality traits.
- Untargeted scraping of facial images from the internet or CCTV to build
  facial recognition databases.
- Emotion inference in workplaces and educational institutions (except for
  medical or safety reasons).
- Biometric categorisation inferring sensitive attributes (race, political
  opinions, trade union membership, religious beliefs, sex life, sexual
  orientation), with narrow law-enforcement exceptions.
- Real-time remote biometric identification in publicly accessible spaces
  for law enforcement, subject to narrow exceptions and authorisation.

## Article 6 and Annex III — High-Risk AI Systems

An AI system is high-risk if it is a safety component of a regulated product
(Annex I) or falls in an Annex III area (Art. 6(2)), unless it does not pose
a significant risk of harm (Art. 6(3) filter, to be documented). Annex III
areas include:

1. Biometrics (remote biometric identification, biometric categorisation,
   emotion recognition where not prohibited).
2. Critical infrastructure (safety components in traffic, water, gas,
   heating, electricity, digital infrastructure).
3. Education and vocational training (access/admission, evaluation of
   learning outcomes, level assignment, proctoring).
4. **Employment, workers management and access to self-employment:
   recruitment and selection (advertising, screening or filtering
   applications, evaluating candidates), decisions on promotion,
   termination, task allocation based on behavior or traits, monitoring
   and evaluation of performance.**
5. Access to essential private and public services (creditworthiness
   scoring, risk assessment and pricing in life/health insurance, triage of
   emergency calls, eligibility for public assistance benefits).
6. Law enforcement (specified use cases).
7. Migration, asylum and border control management.
8. Administration of justice and democratic processes.

## Obligations for High-Risk Systems (Articles 8–15)

Providers of high-risk AI systems must implement:

- **Art. 9 — Risk management system**: continuous, iterative, across the
  entire lifecycle; identify, estimate, and mitigate foreseeable risks.
- **Art. 10 — Data and data governance**: training/validation/testing data
  shall be relevant, sufficiently representative, and to the best extent
  possible free of errors and complete in view of the intended purpose;
  examination for possible biases likely to affect health, safety, or
  fundamental rights or lead to prohibited discrimination.
- **Art. 11 — Technical documentation** (Annex IV) before market placement.
- **Art. 12 — Record-keeping**: automatic logging of events over the
  system's lifetime, ensuring traceability.
- **Art. 13 — Transparency and provision of information to deployers**:
  instructions for use; characteristics, capabilities, and limitations.
- **Art. 14 — Human oversight**: systems shall be designed so they can be
  effectively overseen by natural persons; measures to prevent or minimise
  risks; oversight persons must be able to understand capacities and
  limitations, remain aware of automation bias, correctly interpret output,
  decide not to use the system, and intervene or stop it.
- **Art. 15 — Accuracy, robustness and cybersecurity**: appropriate levels
  declared in the instructions; resilience to errors, faults,
  inconsistencies, and to attempts to alter use or performance
  (including data poisoning and adversarial examples).

## Deployer Obligations (Art. 26) and Fundamental Rights Impact Assessment (Art. 27)

Deployers of high-risk systems must use them per instructions, assign human
oversight to competent persons, ensure input data relevance, monitor
operation, and keep logs. Certain deployers (public bodies, private entities
providing public services, and deployers of credit-scoring/insurance-pricing
systems) must perform a fundamental rights impact assessment before first use.

## Article 50 — Transparency Obligations (Limited Risk)

- Persons interacting with an AI system (e.g. chatbots) must be informed
  they are interacting with AI, unless obvious from context.
- Synthetic audio/image/video/text content must be marked machine-readable
  as artificially generated or manipulated.
- Deployers of emotion recognition or biometric categorisation must inform
  exposed persons.
- Deep fakes must be disclosed.

## General-Purpose AI Models (Arts. 51–55)

Providers of general-purpose AI models must maintain technical
documentation, provide information to downstream providers, respect EU
copyright law, and publish a training-content summary. Models with systemic
risk (very large training compute) face additional evaluation, adversarial
testing, incident reporting, and cybersecurity obligations.

## Penalties (Art. 99)

Administrative fines up to EUR 35 million or 7% of worldwide annual turnover
for prohibited-practice violations; up to EUR 15 million or 3% for most
other obligations; up to EUR 7.5 million or 1% for supplying incorrect
information.

## Practical Classification Heuristics for Teams

- Recruitment/resume screening, credit scoring, exam grading, and public
  benefit eligibility systems are presumptively HIGH-RISK (Annex III).
- A system that only supports narrow procedural tasks or improves the result
  of a previously completed human activity may fall outside high-risk via
  the Art. 6(3) filter — but this must be documented and is reviewable.
- Chatbots and content generators generally trigger Art. 50 transparency
  duties even when not high-risk.
