# Playbooks

Each playbook ends with a short list for the user: what you propose, what it traces to (ids, or a principle when there is no project part), the decisions a person must take (with the owner role), anything not grounded, and whether it rests on a RAIA record or on your own screen. Nothing you propose changes the RAIA records: the team applies it in their backlog, and material changes go back to RAIA.

"The project part" below means what the user brought from a RAIA project (`SKILL.md`, "Two parts"). Where a playbook needs it and there is none, do the screen in `screening.md` first and work from the principles in `rai-guidelines.md`.

## Before you write anywhere

Some assistants can change a tracker or a document through a connection. If you can:

1. Read first. Say which items or pages you read, and the query or scope you used; let the user correct the scope.
2. Show the exact change (the text to add, where, and to which items) and wait for a yes. One confirmation covers the items shown, not later ones.
3. Add, never replace. Put ethical criteria in a block that starts with the line `Responsible AI (RAIA)` or in a comment, so that a second run updates that block instead of adding another.
4. Never change an item's status, assignee, sprint or priority, and never edit an existing acceptance criterion (rule 4).
5. Ask once how the team records acceptance criteria and which labels it allows, and keep to it.

Without a connection, produce the text or the table for the user to paste or import.

## P1 Triage the backlog

Input: the team's backlog (an export, a CSV, pasted stories, or items read through a connection).

1. Do the reconciliation step in `SKILL.md` first if there is a project part and you have not yet in this conversation.
2. For each item, decide its class:
   - **RAI story** — it implements an approved EVR (it already carries a `raia-RAI-n` label, or its intent matches an EVR's statement). Link the EVR(s).
   - **Product story with ethical impact** — it touches something on the capability list in `rai-guidelines.md` (scores or ranks people, automates a decision about a person, collects personal data, personalises, generates content, explains outcomes, integrates an external data source or model, controls access to data), or it touches a principle probe. It needs ethical criteria (P2).
   - **No ethical impact** — none of the above. Give the one-line reason. Never put a story that scores, ranks, automates decisions about people or handles personal or protected data here.
3. For each item with ethical impact: the EVRs it helps implement (or, with no project part, the principles it touches), the ECCOLA cards it selects, and its priority — the highest priority of its EVRs (legal-obligation EVRs are at least high). Mark any item linked to a blocking open issue as **held** with the issue id.
4. List the EVRs that no backlog item covers, highest priority first. They go to P3.
5. Output the triage table in `templates.md`, sorted Do now → Plan → Track.

## P2 Refine a story

Input: one story with its description and existing acceptance criteria.

1. Number the existing criteria `<story>-E1`, `-E2`, … (keep the team's wording exactly).
2. Decide what the story touches; select the ECCOLA cards (three always, the rest by touches and the product's risk context).
3. Answer each selected card's question for this story in one or two sentences. If a card raises nothing, say so.
4. Write new ethical criteria `AC-<story>-<n>`: measurable condition with threshold, Microsoft RAI Standard v2 goal, stakeholder group, evidence artifact, owner role, linked EVR(s) or principle.
5. Check each existing criterion against the linked EVRs and the cards. If one conflicts (it contradicts a requirement or makes a card impossible to satisfy), flag it: which criterion, what it conflicts with, the problem and a suggested rewrite. The product owner decides; the original stays until then.
6. If the story has no ethical impact, write one line why, and stop.
7. Output the story in the refined-story format of `templates.md`, changes marked. For text that goes into a tracker, use the plain criterion format unless the team asks for the full one.

## P3 Cover a requirement

Input: EVRs with no live story (from `roadmap.csv`: state `no_story`, or P1 step 4).

1. Take a short list: the five highest priority, legal obligations first, unless the user names others.
2. For each EVR, draft at most three stories that together satisfy its fit criterion, each a user story with its ECCOLA cards and ethical criteria (as in P2).
3. If an EVR needs no story (already satisfied by a control, or covered by process rather than product work), say why under "not a story". Every EVR in scope is covered or justified.
4. Number drafts `RAI-new-1`, `RAI-new-2`, …: the real ids are assigned when the team adds them (in RAIA, generate mode gives them `RAI-n`).

## P4 Plan a sprint

Input: the backlog, the open decisions, the team's capacity (stories or points; RAIA's default is five stories).

Rank the candidate stories (status backlog, dependencies already verified or chosen) in this order, and fill the capacity:

1. Stories carried over from the last sprint.
2. RAI stories that close a legal-obligation gap.
3. Stories by the highest priority among their EVRs.
4. Then the ones waiting longest.

Never suggest a story linked (directly or through its EVR) to an open **blocking** decision: list it as held, with the issue that releases it. List stories waiting for a dependency separately. Give each suggestion a one-line reason. Point out if the sprint has no RAI story while legal-obligation EVRs are still unscheduled.

## P5 Self-audit a sprint

Input: the stories of the sprint, their ethical criteria and the evidence the team can show.

1. One item per ethical criterion of the sprint's stories, plus each EVR whose stories the sprint completes.
2. Verdict per item, with the evidence named:
   - **satisfied** — evidence exists and meets the criterion's threshold;
   - **partially satisfied** — evidence exists but does not fully meet it;
   - **at risk** — evidence shows it is not met, or the work regressed;
   - **not verified** — no evidence. This is the default. A tick, a merged change or "done" in the tracker is not evidence that an ethical criterion holds.
3. Rate the sprint with RAIA's rule (in `vocabulary.md`, audit opinion). The rating can never be better than the evidence allows.
4. Say where every EVR stands (no story, planned, in sprint, delivered, verified, at risk), whether the backlog is enough (every EVR and every high or critical risk has a story; every legal-obligation EVR has one; every criterion names its evidence), and what the next sprint should tackle first.
5. Output the self-audit note in `templates.md`. Remind the user that a self-audit is not a RAIA audit: verified status in RAIA comes only from an approved RAIA audit.

## P6 Export to a tracker

- **With a connection:** follow "Before you write anywhere". Create or update items with the summary, description and labels below.
- **Without one:** produce a table the user can import. For Jira, use the CSV format in `templates.md`; for another tracker, the same columns in the format it imports.

Keep RAIA's labels where the team allows them (`raia`, `raia-<story id>`, `raia-<sprint id>`, `raia-ethics` for RAI stories) so the items stay traceable and RAIA can sync them later. Put the ethical criteria in the description, each with its id.

## P7 Check a change

Input: a new feature, model, data source, market, user group or way of using the product.

1. Run the analysis in `rai-guidelines.md`, "Analysing a new issue yourself".
2. Check it against the escalation triggers below. If any applies, the answer to the user starts with: **go back to RAIA** — re-run the Risk Classifier (and the stages after it) with a description of the change that is generic but accurate. Until then, redo the screen with `screening.md` and treat the stricter reading as applying.
3. Otherwise, link the change to existing EVRs and write the work (P2 or P3).

## P8 Review a product document

Input: a requirements document, a one-pager, a design page or a decision record, pasted, attached or read through a connection.

1. Say in one sentence what the document proposes, for whom, and where AI acts in it.
2. With a project part: check it against the approved EVRs and the open decisions. With none: run the screen in `screening.md` on what the document says, and the principle probes in `rai-guidelines.md`.
3. List the gaps, most pressing first. For each: what is missing or contradicts a requirement, where in the document, the EVR or principle it concerns, and the sentence or section that would close it.
4. Note what the document does not say and the screen needs (who is affected without using the product, how much is automated, what data is used, where it will be offered). These are questions for the author, not findings.
5. Offer the "Responsible AI" section in `templates.md`, filled for this document, for the author to paste.
6. Output the document review in `templates.md`. Leave comments or edits only under "Before you write anywhere".

## P9 Check the board

Input: the board or backlog as it stands (an export, or read through a connection with a scope the user confirms).

Report, in this order:

1. Items that touch AI and carry no ethical criterion.
2. EVRs with no item (with a project part), or principles no item addresses (without one).
3. Items held by an open blocking decision, with the decision.
4. RAI stories untouched for two sprints or more.
5. Criteria that name no evidence.

Give counts first, then the items, in the board-check format of `templates.md`. Propose at most five next steps.

## P10 Write a one-page brief

Input: the project part, or the result of your own screen. For a manager, a squad, or the legal and privacy owners.

One page, in the brief format of `templates.md`: what the product does with AI; where it sits (tier per instrument, whether it binds, and whether that comes from a RAIA record or your own screen); the three most pressing risks; the requirements or criteria that answer them; the decisions needed and from whom; what has evidence and what does not. No framework names in the body; put the sources in one closing line.

## P11 Support a sprint ceremony

- **Refinement.** For each story on the table: its class (P1 step 2), the criteria it still needs (P2), and whether a blocking decision holds it. Stop at the stories the team will actually discuss.
- **Definition of done.** Propose the additions in `templates.md`, cut to what the product's tier and data call for. The team owns its definition of done: these are proposals.
- **Sprint review.** For each delivered story with ethical criteria: what evidence was shown, and the verdict it supports (P5). Do not call anything verified.
- **Retrospective.** Three questions: which ethical criterion was hardest to evidence, and why; which decision waited longest for an owner; what would have been cheaper to settle earlier.

### When to go back to RAIA

Recommend a new RAIA run when the change, or the reconciliation step, shows any of the following.

**A purpose in a high-risk area** that RAIA was not told about:

- Biometric identification, categorisation or emotion recognition (EU AI Act Annex III, point 1 — Biometrics; PL 2338/2023 art. 17, item 8 — Biometric identification and emotion recognition)
- Safety component of critical infrastructure (traffic, water, energy, digital) (EU AI Act Annex III, point 2 — Critical infrastructure; PL 2338/2023 art. 17, item 1 — Critical infrastructure)
- Education and vocational training — admission, assessment, proctoring (EU AI Act Annex III, point 3 — Education and vocational training; PL 2338/2023 art. 17, item 2 — Education and vocational training)
- Employment — recruitment, screening, evaluation, promotion, termination, task allocation, worker monitoring (EU AI Act Annex III, point 4 — Employment, workers management and access to self-employment; PL 2338/2023 art. 17, item 3 — Recruitment, screening and evaluation of candidates and workers)
- Access to essential services — credit scoring, insurance pricing, public benefits, emergency triage (EU AI Act Annex III, point 5 — Access to essential private and public services; PL 2338/2023 art. 17, item 4 — Access to essential public and private services and benefits)
- Law enforcement or public security (EU AI Act Annex III, point 6 — Law enforcement; PL 2338/2023 art. 17, item 9 — Criminal investigation and public security)
- Migration, asylum or border control (EU AI Act Annex III, point 7 — Migration, asylum and border control; PL 2338/2023 art. 17, item 10 — Migration and border control)
- Administration of justice or democratic processes (EU AI Act Annex III, point 8 — Administration of justice and democratic processes; PL 2338/2023 art. 17, item 5 — Administration of justice)
- Health applications, including diagnosis support (PL 2338/2023 art. 17, item 7 — Health applications and diagnosis support)
- Autonomous vehicles operating in public spaces (PL 2338/2023 art. 17, item 6 — Autonomous vehicles in public spaces)
- Large-scale content curation or recommendation affecting information integrity (PL 2338/2023 art. 17, item 11 — Large-scale content curation and recommendation)

**Any practice on the prohibited or excessive-risk lists** — stop the work and escalate to legal and compliance at once:

- Subliminal, manipulative or deceptive techniques that materially distort behaviour
- Exploits vulnerabilities of age, disability, or social/economic situation
- Social scoring leading to unjustified or disproportionate detrimental treatment
- Predicts criminal offence or recidivism risk from profiling or personality traits
- Untargeted scraping of facial images to build a recognition database
- Infers emotions in the workplace or in educational institutions
- Biometric categorisation inferring sensitive attributes
- Enables production or dissemination of child sexual abuse material
- Autonomous weapons without meaningful human control
- Real-time remote biometric identification in public spaces for law enforcement (restricted, not flatly banned)

**A new category of data:**

- Biometric data
- Health data
- Protected attributes (race, gender, age, disability, religion, origin)
- Strong proxies for protected attributes (postcode, school, name, photo)
- Data about children or adolescents
- Location or movement data
- Financial or credit data
- Private communications content

**A new way people meet the AI** (transparency duties):

- People interact with the system directly (chatbot, assistant, voice agent)
- The system generates or manipulates image, audio, video or text content
- The system produces content resembling real people, places or events
- The system performs emotion recognition on people
- The system performs biometric categorisation

**More automation or less oversight than RAIA was told.** Autonomy, from least to most: Purely informational — no decision about a person follows from it → A recommendation a person reviews and may override → A person confirms the output, but in practice almost always accepts it → Fully automated — the system's output is the decision. Any move towards the right, or removing a person's ability to intervene in an individual case.

**A new market** (European Union / EEA, Brazil, Other jurisdictions only), a change of role (building the system vs. operating someone else's), a change of model source (in-house, adapted third-party, third-party as-is), or the product going from development to real users.

Also go back to RAIA when an approved EVR's statement no longer fits the product, when the team wants to accept a risk, or when the snapshot in `PROJECT_CONTEXT.md` is older than the team's last major release.
