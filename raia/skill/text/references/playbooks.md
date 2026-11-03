# Playbooks

Each playbook ends with a short list for the user: what you propose, the ids it traces to, the decisions a person must take (with the owner role) and anything not grounded. Nothing you propose changes the RAIA records: the team applies it in their backlog, and material changes go back to RAIA.

## P1 Triage the backlog

Input: the team's backlog (a Jira export, a CSV, pasted stories) and `project/`.

1. Do the reconciliation step in `SKILL.md` first if you have not yet in this conversation.
2. For each item, decide its class:
   - **RAI story** — it implements an approved EVR (it already carries a `raia-RAI-n` label, or its intent matches an EVR's statement). Link the EVR(s).
   - **Product story with ethical impact** — it touches something on the capability list in `rai-guidelines.md` (scores or ranks people, automates a decision about a person, collects personal data, personalises, generates content, explains outcomes, integrates an external data source or model, controls access to data), or it touches a principle probe. It needs ethical criteria (P2).
   - **No ethical impact** — none of the above. Give the one-line reason. Never put a story that scores, ranks, automates decisions about people or handles personal or protected data here.
3. For each item with ethical impact: the EVRs it helps implement, the ECCOLA cards it selects, and its priority — the highest priority of its EVRs (legal-obligation EVRs are at least high). Mark any item linked to a blocking open issue as **held** with the issue id.
4. List the EVRs that no backlog item covers, highest priority first. They go to P3.
5. Output the triage table in `templates.md`, sorted Do now → Plan → Track.

## P2 Refine a story

Input: one story with its description and existing acceptance criteria.

1. Number the existing criteria `<story>-E1`, `-E2`, … (keep the team's wording exactly).
2. Decide what the story touches; select the ECCOLA cards (three always, the rest by touches and the product's risk context).
3. Answer each selected card's question for this story in one or two sentences. If a card raises nothing, say so.
4. Write new ethical criteria `AC-<story>-<n>`: measurable condition with threshold, Microsoft RAI Standard v2 goal, stakeholder group, evidence artifact, owner role, linked EVR(s).
5. Check each existing criterion against the linked EVRs and the cards. If one conflicts (it contradicts a requirement or makes a card impossible to satisfy), flag it: which criterion, what it conflicts with, the problem and a suggested rewrite. The product owner decides; the original stays until then.
6. If the story has no ethical impact, write one line why, and stop.
7. Output the story in the refined-story format of `templates.md`, changes marked.

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
   - **not verified** — no evidence. This is the default. A tick, a merged pull request or "done" in Jira is not evidence that an ethical criterion holds.
3. Rate the sprint with RAIA's rule (in `vocabulary.md`, audit opinion). The rating can never be better than the evidence allows.
4. Say where every EVR stands (no story, planned, in sprint, delivered, verified, at risk), whether the backlog is enough (every EVR and every high or critical risk has a story; every legal-obligation EVR has one; every criterion names its evidence), and what the next sprint should tackle first.
5. Output the self-audit note in `templates.md`. Remind the user that a self-audit is not a RAIA audit: verified status in RAIA comes only from an approved RAIA audit.

## P6 Export to Jira

- **With a Jira connection:** create or update issues with the summary, description and labels below. Never change the status of an issue to done on the team's behalf.
- **Without one:** produce a CSV for Jira's CSV importer in the format in `templates.md`.

Keep RAIA's labels (`raia`, `raia-<story id>`, `raia-<sprint id>`, `raia-ethics` for RAI stories) so the items stay traceable and RAIA can sync them later. Put the ethical criteria in the description, each with its id.

## P7 Check a change

Input: a new feature, model, data source, market, user group or way of using the product.

1. Run the analysis in `rai-guidelines.md`, "Analysing a new issue yourself".
2. Check it against the escalation triggers below. If any applies, the answer to the user starts with: **go back to RAIA** — re-run the Risk Classifier (and the stages after it) with a generic but accurate description of the change.
3. Otherwise, link the change to existing EVRs and write the work (P2 or P3).

### When to go back to RAIA

Recommend a new RAIA run when the change, or the reconciliation step, shows any of the following.

{{escalation_triggers}}

Also go back to RAIA when an approved EVR's statement no longer fits the product, when the team wants to accept a risk, or when the snapshot in `PROJECT_CONTEXT.md` is older than the team's last major release.
