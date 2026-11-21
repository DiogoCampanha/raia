# RAIA — Responsible AI Assistant 🛡️

A multi-agent, LLM-based **software architecture** that operationalizes
Responsible AI across the software development life cycle, implemented as a
working proof of concept.

Four specialized agents, organized in two layers (Product / Dev),
communicate **exclusively** through a versioned shared artifact repository
and are separated by **mandatory human approval gates**. Work is organized in
**projects**: each person signs in, and every project has its own stages,
drafts, answers, open issues and audit trail, shared only with the people
invited to it. Recommendations are
grounded by retrieval over a normative corpus — four consolidated frameworks
(IEEE 7000, NIST AI RMF, Microsoft RAI Standard v2, ECCOLA) and two legal texts
(EU AI Act, Brazilian PL 2338/2023).

What distinguishes this implementation from a set of prompts is where the
reasoning happens. **Each agent runs a deterministic decision procedure before
any model is called**, and **deterministic validators after it**:

| | |
|---|---|
| **1 · Structured intake** | Typed questions whose answers a rule reads — no field exists that code does not consume. |
| **2 · Rule engine** | Computes what is enumerable: matched prohibitions and risk areas, obligation tables, coverage matrices, traceability registers, threshold breaches. Declares the norm excerpts the decision depends on. |
| **3 · Model pass** | Justifies, handles the open-textured judgement a rule table would get wrong, and returns one **standard RAIA record** (JSON validated against the agent's schema). The computed block is ground truth: the model may argue with a verdict, never restate one. |
| **4 · Contract and validators** | Code computes identifiers, risk level and priority, carries every engine issue forward and renders the one layout every artifact follows; checks confirm the schema, citations, coverage, that every finding is answered and every computed id accounted for, and that the verdict is reconciled. |
| **5 · Human gate** | Draft, evidence, computed rationale and check results together. Nothing is persisted until a person approves. |

Where the rule engine and the model disagree, the disagreement is escalated to
the **Open Issues** register rather than averaged away.

**One standard for every project.** Every agent answers in the same record —
summary, findings placed on likelihood and magnitude, actions with a response,
owner, lifecycle stage, review cadence, verification method and evidence
artifact, typed open issues, declared coverage — plus an extension shaped by
the norm the agent operationalises. Every record leads with what to act on and
keeps the analysis for whoever wants it: most stages read as a summary with the
figures that matter, then what to do, then a deep dive; the User Story Refiner
leads with the refined stories, each with its changes marked and ready to copy;
the Auditor reads as an audit report — an opinion rated by code, strengths,
risks, opportunities and the pathway forward. All vocabularies come from the project's
normative sources only. See [`docs/output-contract.md`](docs/output-contract.md),
the agent cards in [`docs/agents/`](docs/agents/) and the JSON Schemas in
[`docs/schema/`](docs/schema/).

## The Agents

| Agent | Layer | Decision procedure | Grounded in |
|---|---|---|---|
| **Risk Classifier** | 🟦 Product | Prohibited-practice screen, high-risk area match for both regimes, AI-system definition check, transparency duties implied by how the AI works, narrow-task exemption handling, role-dependent obligation assembly | EU AI Act, PL 2338/2023 |
| **Requirements Reviewer** | 🟦 Product | Obligation × principle coverage matrix against stated requirements and existing controls; assigns the requirement register; on request, recommends candidate requirements a person adopts or rejects | IEEE 7000, MS RAI v2 |
| **User Story Refiner** | 🟩 Dev | Two modes. *Generate*: approved requirements without a story (a short list, legal obligations first) become RAI stories for the backlog, every requirement covered or justified. *Refine*: ECCOLA card selection per story from risk tier, data categories and capabilities; story register as a counted invariant; criteria written back to the backlog | ECCOLA, MS RAI v2 |
| **Auditor** | 🟩 Dev | Project-wide at each sprint close: the sprint's items matched against evidence (no evidence → NOT VERIFIED by code), where every requirement stands, progress and trend, whether the backlog covers the ethical risks, and what comes next | MS RAI v2, NIST AI RMF |

The RAIA architecture also specifies an **Ops layer** — fairness-drift
monitoring after deployment. It needs production telemetry that a team
designing a product rarely holds, so it is future work and has no agent in
this build (see the roadmap).

**Sprints over one backlog.** Once the requirements are approved, the project
page opens on a **Board**: the backlog (RAI stories generated from the
requirements, product stories from product work), the open sprint and a
computed roadmap. People plan each sprint with a rule-based suggestion, tick
stories done and end the sprint; the Auditor's approved audit closes it,
verifying only what the evidence supports. Jira is optional: a Jira-ready CSV
needs no setup, and a person's own Jira Cloud connection pushes a sprint and
syncs its status back. See the sprint cycle in [`docs/architecture.md`](docs/architecture.md).

## Quick Start

**Requirements.** Python 3.10 or later (CI tests 3.10 and 3.12) on macOS,
Windows or Linux, x86-64 or ARM, and an API key for Claude (Anthropic) or
OpenAI — or neither, in mock mode. `requirements.txt` is a lock that installs
the same versions everywhere; on x86-64 Linux it also installs a modern SQLite
for Chroma, which hosted platforms need.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1. Configure the LLM
cp .env.example .env          # add ANTHROPIC_API_KEY (or OPENAI_API_KEY, see "Model providers")

# 2. Build the normative RAG index (first run downloads a small embedding model)
python ingest.py

# 3. Launch the UI
streamlit run app.py
```

Locally there is nothing else to configure: users and projects live in a
SQLite file under `workspace/`, each project's blackboard is a Git repository,
and you are signed in as a fixed local developer identity (`RAIA_AUTH=dev`,
already set in `.env.example`; without it, or Google sign-in, the app refuses
to open, so a deployment that forgot its sign-in fails closed). A shared deployment
uses Google sign-in and PostgreSQL instead — see
[Hosted deployment](#hosted-deployment-streamlit-community-cloud--neon--google-sign-in).

### No API key? Try mock mode

Set `RAIA_LLM_PROVIDER=mock` in `.env`. The mock model reads the output
contract each agent declares and produces a conforming document, so the whole
chain — decision procedures, retrieval, validators, persistence, audit trail —
can be exercised offline. What it cannot produce is a real analysis, which is
why the app **refuses to serve mock output to an evaluator**: a tester who
could not tell canned text from a real classification would evaluate the wrong
artifact.

### Model providers

| `RAIA_LLM_PROVIDER` | Key | Default model (`RAIA_LLM_MODEL`) |
|---|---|---|
| `anthropic` (default) | `ANTHROPIC_API_KEY` | `claude-sonnet-5-5` — Claude Sonnet 5.5, the reference model |
| `openai` | `OPENAI_API_KEY` | `gpt-6.2-sol` — GPT-6.2 Sol |
| `mock` | none | canned records that satisfy the output contract |

Both provider libraries are installed, so switching is a configuration change;
set `RAIA_LLM_MODEL` to use another model of the same provider. On a hosted
deployment, an OpenAI key on its own selects the `openai` provider. Provider
model ids change: check the provider's model list before relying on a default.

**No temperature is sent by default.** Claude Sonnet 5.5 refuses any
`temperature`, `top_p` or `top_k`, and so do OpenAI's reasoning models, so the
provider's own sampling applies. For a model that accepts one, set
`RAIA_LLM_TEMPERATURE` (a low value such as `0.2` aids reproducibility); if the
model refuses it anyway, RAIA retries once without it. Either way the
provenance of every draft records the temperature actually sent (`null` when
none was). Reproducibility therefore rests on the record itself: the prompt
hash, the excerpt ids, the corpus version and, with `RAIA_TRANSCRIPT_KEY`, the
sealed prompt and raw reply of every run.

Claude Sonnet 5.5 thinks adaptively before it answers, and that thinking counts
against `RAIA_LLM_MAX_TOKENS`; a reply cut off at the limit is detected and
retried once with up to `RAIA_LLM_MAX_TOKENS_CEILING`.

## Using RAIA

0. **Sign in and open a project.** *My projects* lists the projects you own or
   were invited to, with each one's progress derived from its approved
   artifacts. Create one, start from one of the three pre-filled demo projects
   (a B2B marketplace: outside the high-risk lists; a customer-support
   assistant: limited risk; resume screening: high risk and blocked), or accept
   an invitation. Everything below happens inside the open project, and your form
   answers are saved to it as you type.
1. **See what the stage receives, and fill in the structured form.** From the
   second stage on, *What this stage receives* lists the upstream work it
   builds on and the decisions still open from earlier stages, which can be
   taken there. The questions are the ones that decide the outcome — your
   role, target markets, purpose area, decision autonomy, data categories.
   Required fields are marked; the run is refused without them.
2. **Run the stage.** The page shows only that the agent is working, step by
   step: the rule engine computes its verdict, pins the excerpts its decision
   depends on, retrieves more by similarity, and the model writes the analysis.
   The draft then opens at its top.
3. **Read the draft.** It opens with its status and what the status means here
   (*Blocked in its current form* links to **Gaps to close**, each with what
   unblocks it), a hand-off strip (what this stage received, what it
   addressed, what is still open, and — for a revision — what improved since
   the approved version), then compact cards: one line each, the detail on a
   click. The automated checks speak only when a person is needed; what code
   corrected on its own is in a technical log. The other tabs: a structured
   editor for the record, the evidence that was in the prompt, and everything
   the code computed.
4. **Review each card and take the decisions.** Accept or reject every risk,
   action, requirement and new criterion; a rejection needs a reason, and
   unmarked cards are accepted as they are. A rejected card leaves the approved
   record and is kept in its review block; a computed one (a requirement that
   closes a gap the engine found) is kept, marked overridden, and recorded in
   the open issues. Each decision is a choice made on its card — an option and
   why — and taking the blocking ones lifts *Blocked*.
5. **Approve or reject.** Rejections carry a reason code and free-text
   feedback (the rejected cards are listed in it), both recorded. Approval
   commits the Markdown artifact, its structured sidecar and its provenance in
   one recorded version, attributed to your signed-in identity — never to a
   typed name. Decisions taken on the draft reach the Open Issues register,
   decided, in the same step.
6. **Arbitrate what is left.** The Open Issues register holds every issue with
   its status — open, decided, resolved or accepted risk — and a note; owners
   can reopen a decision.
7. **Revise safely.** Revising an approved stage shows first which approved
   stages depend on it. When the revision is approved those stages are marked
   *Needs review*; they are never re-run automatically, and a person either
   revises or re-confirms each one.
8. **Work with others.** Under *People and settings* an owner invites people by
   their sign-in email as **editor** (runs agents, approves) or **reviewer**
   (reviews and approves, does not run agents), and can require a **second
   approver**, so the person who ran a stage cannot approve it.
9. **Assessment** — one page in the top menu, about the software only: what
   you have used so far, consent, three optional profile questions, the
   evaluation plan's five dimensions on a five-point scale (each with a line
   saying where to look), one answer per stage (a score, or *Did not use this
   stage*) and open questions, with drafts. An assessment names no project: it
   is stored with what its author used, and leaves in the research export under
   a participant code of its own.
10. **Work the action plan** — the Project page gathers every action from every
   approved record, sorted by computed priority, filterable by owner and stage,
   and exports it as CSV or JSON.
11. **Follow the thread** — the Traceability tab shows, per obligation and
   requirement, which requirement answers it, which stories implement it and
   what the audit verified, gaps highlighted.
12. **Export a project, or hand it on** — *Download project* (Documents tab):
   artifacts, structured records, the action plan, version history with its
   integrity check, and pseudonymized activity, in one zip. The **One-page
   brief** beside it sums the project up for a manager, a squad or the legal
   team — what the product does with AI, the tier per regime and whether it
   binds, the most pressing risks, the requirements that answer them, the
   decisions still needed and what has been verified — written by code from the
   approved records, naming roles rather than people.
13. **Continue with your own AI assistant** — *Download AI Skill* (Documents
   tab), in four formats: Cursor, ChatGPT, Claude, or one Markdown file for any
   assistant. The skill has two parts. The **fixed part** (`SKILL.md` and its
   references) is the same for every project and every download of a version,
   and nobody edits it. The **project part** is this project's approved outputs
   and `PROJECT_CONTEXT.md`, replaced after new approvals. An assistant a
   person is allowed to use then applies RAIA's records to the real backlog,
   tickets and product documents (triage, ethical acceptance criteria, document
   review, sprint suggestions, self-audits, a one-page brief, tracker export)
   with RAIA's rules, and says when a change needs a new RAIA run. Teams that
   can give RAIA only a generic description reconcile it with the real product
   as the first step. With no RAIA project at all, the assistant screens the
   product itself with the rule engine's tables and labels the result
   self-assessed. The text names no assistant and assumes no connection to a
   tracker. No research data is included, and the skill is not part of the
   assessment. See [`docs/ai-skill/`](docs/ai-skill/).

## How Reliability Is Handled

- **(a) Mandatory human checkpoints** — the state graph's native `interrupt()`;
  the persistence node is unreachable without an explicit approve decision,
  including on the restart-recovery path.
- **(b) Grounded recommendations, verified** — each retrieved excerpt carries
  its source, section, authority level and a stable id. Every citation tag in a
  draft is **checked against the excerpts that were actually retrieved**; a tag
  that resolves to none is removed from the record by code, and the removal is
  recorded in the artifact's provenance. Excerpts the decision procedure
  depends on are *pinned*: they are in the prompt whatever the similarity score.
- **(c) Conflict handling** — authority precedence (**legal > standard >
  advisory**) for cross-level conflicts; same-level conflicts, rule-engine
  disagreements and human-only decisions become tracked entries in the
  **Open Issues** register, each with a status and an arbitration note. A
  person may override a computed item, never silently: the override stays in
  the record and is recorded in the register with its reason.
- **(d) Data protection and access** — every project operation passes one
  authorization check in the service layer (`ProjectService.authorize`), not
  just in the UI; a foreign project is indistinguishable from a missing one.
  Sign-in is delegated to Google, so no password is stored. Research exports
  replace people with keyed participant codes. Nothing is used to retrain
  models.
- **(d′) Tamper-evident history** — locally every approval is a Git commit; in
  the database every recorded version is hash-chained to its parent, and the
  audit trail and each export state whether the chain verifies.
- **(e) Input sanitization** — free text is cleaned and screened for
  prompt-injection patterns in English and Portuguese. Findings are flagged,
  never silently removed. The approved draft is sanitized on its way into the
  repository too, because that is the text every downstream prompt inherits.
- **(f) Deterministic facts** — verdicts, obligation lists, coverage matrices,
  registers, priorities and identifiers are computed by code; the model may
  downgrade a computed verdict, never upgrade one.
- **(g) Declared completeness** — each agent publishes the checklist it must
  account for and declares, per item, `covered`, `not-applicable` or
  `not-grounded` with a reason. Being exhaustive is not the goal; being
  accountable is.
- **(h) Reproducible provenance** — every artifact records the provider and
  model, the temperature actually sent (`null` when none was, the default),
  the build, the corpus version, the id of every excerpt in the prompt, a prompt
  hash, which attempt was approved, whether a human edited it, the rejection
  history, and the result of every check. With `RAIA_TRANSCRIPT_KEY` set, the
  exact prompt and raw replies of each run are also kept, encrypted.
- **(h′) A standard record** — the model returns JSON that must validate
  against its agent's schema; an invalid reply is sent back once (with its
  validation errors, or, when it was cut off at the token limit, with more room
  and an instruction to be compact), then shown as a fallback record that fails
  its check. Priority, identifiers and the layout
  are computed, so two projects are comparable line by line.
- **(i) Transient-failure retry** — provider overloads and rate limits are
  retried with backoff; nothing else is, because retrying a bad request only
  spends budget.

## Project Structure

```
.
├── app.py                     # entry point: sign-in, agreement, page registry (top menu)
├── ingest.py                  # builds the Chroma normative index from corpus/
├── views/                     # one file per page: home, guide, project, stage, agents,
│                              #   assessment, settings, research, legal, login, consent, signout
├── raia/
│   ├── __init__.py            # package version; swaps in a modern sqlite3 where one is installed
│   ├── config.py              # env-driven settings; provider default models; authority, source,
│   │                          #   curated-summary and proposed-law registries
│   ├── deploy.py              # hosted secrets → environment (key aliases), runtime status, friendly errors
│   ├── fields.py              # the structured-intake field model
│   ├── examples.py            # the three example cases (B2B marketplace, customer-support assistant, resume screening)
│   ├── llm.py                 # provider factory (Claude, OpenAI, mock), retry, temperature fallback
│   ├── rag.py                 # retrieval with pinned excerpts and excerpt ids
│   ├── agents/                # the four agent specifications, one module each, and the
│   │                          #   Refiner's generate mode (story_generate.py); base.py runs the turn
│   ├── rationale/             # the deterministic decision procedures
│   │   ├── risk_screen.py     #   prohibitions, risk areas, obligation assembly
│   │   ├── coverage.py        #   obligation × principle coverage matrix, suggestions
│   │   ├── story_map.py       #   ECCOLA card selection, story register (refine mode)
│   │   ├── story_seed.py      #   which requirements a generate run covers (generate mode)
│   │   ├── traceability.py    #   evidence matching, NOT VERIFIED by code
│   │   ├── backlog_coverage.py#   whether the backlog covers the ethical risks
│   │   ├── principles.py      #   the seven adopted principles, machine-readable
│   │   └── types.py           #   the result every procedure returns (verdict, tables, pins, checklist)
│   ├── contract/              # the standard RAIA record
│   │   ├── vocab.py           #   closed vocabularies from the normative sources, record version
│   │   ├── rubric.py          #   likelihood × magnitude matrix, priority floors
│   │   ├── schema.py          #   shared core + one extension per agent
│   │   ├── prompt.py          #   the contract as the model sees it
│   │   ├── assemble.py        #   parse, repair, finalise, fallback
│   │   ├── digest.py          #   the reading order of each record, the refined stories, the audit report
│   │   ├── render.py          #   the Markdown layouts, written from the digest
│   │   ├── checks.py          #   record-level checks
│   │   ├── review.py          #   card verdicts, overrides, decisions and the status they change
│   │   ├── actions.py         #   project action plan and its exports
│   │   ├── mock.py            #   the mock model's contract-conforming replies
│   │   ├── export_schema.py   #   writes docs/schema/
│   │   └── agent_cards.py     #   writes docs/agents/
│   ├── validators.py          # citations, structure, coverage, reconciliation; check codes and audiences
│   ├── provenance.py          # the run record stamped into every artifact (with the build id)
│   ├── sealed.py              # encryption of run transcripts (RAIA_TRANSCRIPT_KEY), with key rotation
│   ├── handoff.py             # what each stage receives, addresses and hands on; the Traceability thread
│   ├── progress.py            # which step a running agent is on, for the working screen
│   ├── repository.py          # blackboard behaviour + the Git backend
│   ├── storage.py             # backend selection; hash-chained database blackboard
│   ├── db.py                  # SQLite locally, PostgreSQL hosted — one SQL dialect, migrations
│   ├── projects.py            # people, projects, roles, invitations, authorization, assessments,
│   │                          #   research export
│   ├── people.py              # people named by reference (user:<id>), resolved for display
│   ├── lineage.py             # stage dependencies and the derived "needs review" flag
│   ├── backlog.py             # the backlog and sprints registers, and what approvals change
│   ├── roadmap.py             # computed roadmap, progress, trend, rule-based sprint suggestion
│   ├── brief.py               # the one-page project brief, written by code
│   ├── jira.py                # optional: Jira CSV, push and sync (httpx)
│   ├── logs.py                # structured JSON logs and the audit log
│   ├── auth.py                # Google sign-in via Streamlit, or a local dev identity
│   ├── pipeline.py            # the graph: generate → human gate → revise or persist
│   ├── sanitize.py            # injection screening (EN + PT), flag-never-delete
│   ├── export.py              # one-zip project export, and the AI Skill download
│   ├── skill/                 # the AI Skill: the fixed part and the four formats (text/ + build.py),
│   │                          #   PROJECT_CONTEXT.md from the blackboard (context.py)
│   └── ui/                    # routes, theme (CSS + icons), components, approval gate, record view,
│                              #   board and Jira panel, agent docs, guide, assessment, legal page
├── corpus/                    # curated summaries of the six normative sources (extensible)
├── docs/
│   ├── architecture.md        # UML diagrams and the traceability table
│   ├── output-contract.md     # the standard record every agent produces
│   ├── agents/                # one generated agent card per agent and mode
│   ├── ai-skill/              # the AI Skill without a project: fixed part, install notes, single file (generated)
│   ├── schema/                # published JSON Schemas of the record (generated)
│   ├── templates/             # agent card and project-log entry templates
│   ├── images/guide/          # the Guide's screenshots, taken from the app
│   ├── PROJECT_LOG.md         # what was wrong, what was decided, what changed
│   ├── legal/PRIVACY_AND_TERMS.md  # public privacy policy and user agreement (also the /privacy page)
│   └── TESTERS.md             # tester guide, generated from raia/ui/guide.py (also the Guide page)
├── static/fonts/              # the self-hosted fonts and their licences
├── tests/
│   ├── test_suites.py         # pytest entry: runs every suite below in its own process, on both stores
│   ├── smoke_test.py          # offline end-to-end, including the invariants
│   ├── test_engines.py        # deterministic unit checks, providers and temperature fallback
│   ├── test_contract.py       # the output contract: vocabularies, rubric, records, layout
│   ├── test_projects.py       # isolation, roles, durability, tamper evidence
│   ├── test_backlog.py        # the sprint cycle: generate, plan, tick, audit, close, change control
│   ├── test_jira.py           # optional Jira: CSV, push, sync, token privacy (mock Jira)
│   ├── test_skill.py          # the AI Skill: generated from the code, frozen fixed part, four formats, no research data
│   ├── test_ui.py             # headless walkthrough of the project-based UI
│   ├── consistency_check.py   # run-to-run agreement of records (use a real model)
│   ├── browser_check.py       # the page stays still, in headless Chromium (Playwright)
│   └── guide_screenshots.py   # re-takes the Guide's screenshots (Playwright)
├── .github/workflows/ci.yml   # tests on Python 3.10 and 3.12 with PostgreSQL 16, coverage, dependency audit
├── .streamlit/                # theme (config.toml) and the hosted secrets template
├── .devcontainer/             # a ready Codespaces / dev container (Python 3.12)
├── requirements.in            # direct dependencies and their allowed ranges
├── requirements.txt           # the lock generated from it (install from this)
├── requirements-dev.txt       # test and CI tools
├── .pip-audit-ignore          # advisories accepted after review, each with its reason
├── CITATION.cff               # how to cite this software
└── LICENSE                    # MIT
```

## Extending the Normative Corpus

Drop a richer `.md` into `corpus/`, register the source key in
`config.AUTHORITY_LEVELS` and `config.SOURCE_NAMES`, and re-run
`python ingest.py`. Missing registration breaks citations and precedence.

Two cautions. Sections pinned by a decision procedure are matched by their
exact heading text, so renaming a heading silently removes a pin — the smoke
test checks every pin still resolves, and it will tell you. And sources listed
in `config.DERIVED_SOURCES` are labelled in the prompt, at the gate and in the
evidence as curated summaries rather than official texts. Today all six files
are curated summaries, the two legal texts included; move a source out of that
set only when its file really is the official wording.

## Configuration Reference

| Var | Default | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | — | the key of the provider in use (hosted secrets also accept common aliases, e.g. `LLM_API_KEY`) |
| `RAIA_LLM_PROVIDER` | `anthropic` | `anthropic` \| `openai` \| `mock`; an OpenAI key on its own selects `openai` on a hosted deployment |
| `RAIA_LLM_MODEL` | per provider | `claude-sonnet-5-5` (anthropic), `gpt-6.2-sol` (openai) |
| `RAIA_LLM_TEMPERATURE` | not sent | a number for a model that accepts one; a model that refuses it is retried without it, and provenance records what was sent |
| `RAIA_LLM_MAX_TOKENS` | `16384` | a standard record for a high-risk system is long; truncation is detected, not tolerated |
| `RAIA_LLM_MAX_TOKENS_CEILING` | `32000` | the budget one retry may raise to after a reply was cut off |
| `RAIA_LLM_RETRIES` | `2` | transient provider failures only |
| `RAIA_LLM_RETRY_BASE_DELAY` | `2.0` | seconds; doubled on each retry |
| `RAIA_CONTRACT_REPAIRS` | `1` | a reply that does not validate against the record schema is returned with its errors this many times |
| `RAIA_RAG_TOP_K` | `12` | plus the excerpts each procedure pins |
| `RAIA_RAG_CHUNK_SIZE` / `_OVERLAP` | `1800` / `200` | chars, at ingestion |
| `RAIA_WORKSPACE_DIR` | `./workspace` | local git blackboards and SQLite registry (git-ignored) |
| `RAIA_DATABASE_URL` | SQLite under the workspace | PostgreSQL URL (e.g. Neon) for a shared deployment |
| `RAIA_STORE` | `git` locally, `database` with PostgreSQL | where project blackboards live |
| `RAIA_AUTH` | `google` if `[auth]` is set | `dev` must be set explicitly; with neither, the app refuses to open |
| `RAIA_DEV_USER_EMAIL` / `_NAME` | `developer@raia.local` / `Local developer` | the fixed identity of `RAIA_AUTH=dev` |
| `RAIA_ADMIN_EMAILS` | — | may download the pseudonymized research dataset |
| `RAIA_PSEUDONYM_KEY` | — | keyed participant codes, stable across exports; the research export is refused until it is set |
| `RAIA_JIRA_KEY` | — | optional: encrypts a person's Jira API token; without it the token is kept for the session only |
| `RAIA_TRANSCRIPT_KEY` | — | encrypts the exact prompt and raw replies of every run, for reproducibility (comma-separated keys: the first encrypts, all decrypt). Without it only the prompt hash and token use are kept |
| `RAIA_LOG_LEVEL` | `INFO` | JSON logs on stderr; security-relevant actions also go to the `audit_log` table |
| `RAIA_CONTACT_EMAIL` | — | contact shown on the public Privacy & terms page (`/privacy`) |
| `RAIA_MAX_RUNS_PER_DAY` | `60` | model calls per person per UTC day; `0` = unlimited |
| `RAIA_CORPUS_DIR` / `RAIA_CHROMA_DIR` | `./corpus` / `./.chroma` | |
| `RAIA_CHROMA_COLLECTION` | `raia_norms` | |
| `RAIA_BUILD` | the Git commit | the build id stamped in every artifact and assessment (`<version>+<commit>`); set it where the deployment has no Git metadata |
| `RAIA_FAKE_EMBED` | `0` | `1` = hash embeddings for CI / offline |
| `RAIA_PROFILE` | `0` | `1` = log each page run's duration and database round trips (diagnosing a slow deployment) |

## Hosted Deployment (Streamlit Community Cloud + Neon + Google sign-in)

A hosted Streamlit process has a disposable disk, so a shared deployment keeps
everything — users, projects, artifacts, paused reviews — in PostgreSQL. Three
pieces of configuration, all pasted into the app's **Secrets**:

```toml
ANTHROPIC_API_KEY = "sk-..."

# 1. Durable storage (Neon: Dashboard → Connect; prefer the direct, non-pooler host)
RAIA_DATABASE_URL = "postgresql://user:password@ep-xxxx.region.aws.neon.tech/neondb?sslmode=require"

# 2. Google sign-in (Google Cloud Console → APIs & Services → Credentials → OAuth client ID, "Web application")
[auth]
redirect_uri = "https://<your-app>.streamlit.app/oauth2callback"
cookie_secret = "<a long random string>"
client_id = "<client id>"
client_secret = "<client secret>"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

Plus `RAIA_ADMIN_EMAILS` (who may export research data) and
`RAIA_PSEUDONYM_KEY` (a long random string; the research export refuses to run
without it), and, as decided for the deployment, `RAIA_TRANSCRIPT_KEY` (keeps
each run's prompt and raw replies, encrypted) and `RAIA_CONTACT_EMAIL` (shown on
`/privacy`, the page to give Google's OAuth consent screen). To use OpenAI
instead of Claude, paste `OPENAI_API_KEY` in place of `ANTHROPIC_API_KEY`.

Choose Python 3.12 in the app's advanced settings (CI tests 3.10 and 3.12).
Tables are created on first start, and later schema changes are applied
automatically on start, once each, and recorded in `schema_migrations`; there
is no migration step to run. The graph checkpointer creates its own tables in
the same database.

The app **fails closed**: with a database configured and no sign-in, it refuses
to open rather than serving projects to anyone with the link. A review paused
at an approval gate is stored by the PostgreSQL graph checkpointer, so a
restart does not lose it; the stored-draft restore path remains as a second
line of defence and still re-enters the gate.

## Testing

```bash
pip install -r requirements-dev.txt
pytest                                             # every suite, each in its own process, on both stores
RAIA_TEST_DATABASE_URL=postgresql://... pytest     # …and on a disposable PostgreSQL database
RAIA_COVERAGE=1 pytest && coverage combine && coverage report
```

CI (`.github/workflows/ci.yml`) runs the same on Python 3.10 and 3.12 with a
PostgreSQL 16 service, reports coverage, and audits the locked dependencies
(`pip-audit` against `requirements.txt`; accepted advisories are listed, with
the reason, in `.pip-audit-ignore`). Dependencies are locked: edit
`requirements.in`, then regenerate `requirements.txt` with the command at its top.

Each suite can also be run on its own:

```bash
RAIA_LLM_PROVIDER=mock RAIA_FAKE_EMBED=1 python tests/smoke_test.py
python tests/test_projects.py                      # git blackboards + SQLite
RAIA_STORE=database python tests/test_projects.py  # database blackboard on SQLite
RAIA_DATABASE_URL=postgresql://... python tests/test_projects.py   # on PostgreSQL
python tests/test_backlog.py                       # the sprint cycle (also with RAIA_STORE=database)
python tests/test_jira.py                          # optional Jira, against a mock Jira Cloud
python tests/test_ui.py                            # headless UI walkthrough
python tests/browser_check.py                      # the page stays still, in headless Chromium (needs Playwright)
python tests/guide_screenshots.py                  # re-take the Guide's screenshots (needs Playwright)
python tests/test_contract.py                      # the output contract (also run by the smoke test)
python tests/test_skill.py                         # the AI Skill and its download
python -m raia.skill.build                         # regenerate docs/ai-skill/ after changing raia/skill/text/
python tests/consistency_check.py --agent risk_classifier --runs 5   # with a real provider
```

The suites run fully offline (mock model, hash embeddings). The smoke test covers ingestion, pinned retrieval, stage gates, required
inputs, every decision procedure, the human-review interrupt, the rejection
loop, approval, provenance, sidecars, the open-issues register, restart
recovery, the export bundle, and the deterministic unit checks. It asserts the
two invariants directly: nothing persists without a human approval, and a
fabricated citation is detected, removed and recorded.

## Roadmap (next developments)

- [x] Structured intake driving deterministic decision procedures, every agent
- [x] Citation verification against retrieved excerpts
- [x] Open Issues register with arbitration, decisions taken on the cards
- [x] Reproducible provenance, structured artifact sidecars and sealed run transcripts
- [x] Input sanitization against prompt injection, including the artifact path
- [x] Projects owned by signed-in people, with editor/reviewer invitations and an optional second approver
- [x] One standard record for every agent, with a project action plan and a one-page brief
- [x] Durable, tamper-evident storage for hosted deployments (PostgreSQL, hash-chained versions and events)
- [x] Sprints over one backlog, a project-wide audit and a computed roadmap; optional Jira Cloud (CSV, push, sync)
- [x] AI Skill: continue with Cursor, ChatGPT, Claude or any assistant
- [x] Claude and OpenAI as providers
- [ ] Expert-panel evaluation (Design Science Research)
- [ ] Python 3.11+, Streamlit 1.67 and Pillow 13 (clears the accepted Pillow advisories)
- [ ] Ops layer: a fairness-drift monitor fed by production telemetry
- [ ] Ingest the official legal texts with article-level citation metadata
- [ ] Confluence, and Jira Server / Data Center
- [ ] An API with background workers; projection tables and managed migrations; agents as plugins
- [ ] Least-privilege tool-permission hardening
- [ ] Case studies in real development environments

## Versions

RAIA `0.3.0` (the build id adds the commit: `0.3.0+<sha>`) · records
`raia-record/1.5` · artifact provenance `raia-artifact/1` · AI Skill fixed part
`2.0.0` · assessment instrument `raia-panel-v3`.

## Citation & License

MIT — see `LICENSE`. To cite this software, use `CITATION.cff` (GitHub's
*Cite this repository*). See `docs/architecture.md` for diagrams and the
traceability table between the architecture and the code, and
`docs/PROJECT_LOG.md` for the record of what was wrong with earlier versions
and what changed.
