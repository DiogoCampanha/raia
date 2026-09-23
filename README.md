# RAIA — Responsible AI Assistant 🛡️

A multi-agent, LLM-based **software architecture** that operationalizes
Responsible AI across the software development life cycle, implemented as a
working proof of concept.

Five specialized agents, organized in three layers (Product / Dev / Ops),
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
the norm the agent operationalises. All vocabularies come from the project's
normative sources only. See [`docs/output-contract.md`](docs/output-contract.md),
the agent cards in [`docs/agents/`](docs/agents/) and the JSON Schemas in
[`docs/schema/`](docs/schema/).

## The Five Agents

| Agent | Layer | Decision procedure | Grounded in |
|---|---|---|---|
| **Risk Classifier** | 🟦 Product | Prohibited-practice screen, high-risk area match for both regimes, AI-system definition check, transparency duties implied by how the AI works, narrow-task exemption handling, role-dependent obligation assembly | EU AI Act, PL 2338/2023 |
| **Requirements Reviewer** | 🟦 Product | Obligation × principle coverage matrix against stated requirements and existing controls; assigns the requirement register | IEEE 7000, MS RAI v2 |
| **User Story Refiner** | 🟩 Dev | ECCOLA card selection from risk tier, data categories and sprint capabilities; story register as a counted invariant | ECCOLA, MS RAI v2 |
| **Auditor** | 🟩 Dev | Evidence matching against the approved register; items with no evidence are marked NOT VERIFIED by code | MS RAI v2, NIST AI RMF |
| **Drift Monitor** | 🟧 Ops | Fairness metrics, thresholds parsed from approved artifacts, breach and trend detection, sample-adequacy flags | NIST AI RMF |

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1. Configure the LLM
cp .env.example .env          # add ANTHROPIC_API_KEY

# 2. Build the normative RAG index (first run downloads a small embedding model)
python ingest.py

# 3. Launch the UI
streamlit run app.py
```

Locally there is nothing else to configure: users and projects live in a
SQLite file under `workspace/`, each project's blackboard is a Git repository,
and you are signed in as a fixed local developer identity. A shared deployment
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

## Using RAIA

0. **Sign in and open a project.** *My projects* lists the projects you own or
   were invited to, with each one's progress derived from its approved
   artifacts. Create one, start from the pre-filled demo project, or accept an
   invitation. Everything below happens inside the open project, and your form
   answers are saved to it as you type.
1. **Fill in the structured form.** The questions are the ones that decide the
   outcome — your role, target markets, purpose area, decision autonomy, data
   categories. Required fields are marked; the run is refused without them.
2. **Run the stage.** The rule engine computes its verdict, pins the excerpts
   its decision depends on, retrieves more by similarity, and the model writes
   the analysis.
3. **Review at the gate.** You get four tabs: the draft in the standard layout,
   a structured editor for the record (summary, findings' placement, actions,
   the agent's issues, the agent-specific sections), the evidence that was in
   the prompt, and everything the code computed. Above them, the result of the
   automated checks. Edits are re-computed and re-rendered before approval.
4. **Approve or reject.** Rejections carry a reason code and free-text
   feedback, both recorded. Approval commits the Markdown artifact, its
   structured sidecar and its provenance in one recorded version, attributed to
   your signed-in identity — never to a typed name.
5. **Arbitrate the open issues.** Conflicts land in a register with a status
   you set: resolved, or accepted risk, with a note.
6. **Revise safely.** Revising an approved stage shows first which approved
   stages depend on it. When the revision is approved those stages are marked
   *Needs review*; they are never re-run automatically, and a person either
   revises or re-confirms each one.
7. **Work with others.** Under *People and settings* an owner invites people by
   their sign-in email as **editor** (runs agents, approves) or **reviewer**
   (reviews and approves, does not run agents), and can require a **second
   approver**, so the person who ran a stage cannot approve it.
8. **Assessment** — one page in the top menu: consent, optional profile, the
   evaluation plan's five dimensions on a five-point scale, optional per-stage
   ratings and open questions, with drafts.
9. **Work the action plan** — the Project page gathers every action from every
   approved record, sorted by computed priority, filterable by owner and stage,
   and exports it as CSV or JSON.
10. **Export a project** — artifacts, structured records, the action plan,
   version history with its integrity check, and pseudonymized activity, in one zip.

## How Reliability Is Handled

- **(a) Mandatory human checkpoints** — the state graph's native `interrupt()`;
  the persistence node is unreachable without an explicit approve decision,
  including on the restart-recovery path.
- **(b) Grounded recommendations, verified** — each retrieved excerpt carries
  its source, section, authority level and a stable id. Every citation tag in a
  draft is **checked against the excerpts that were actually retrieved**, and
  unresolvable tags are reported at the gate. Excerpts the decision procedure
  depends on are *pinned*: they are in the prompt whatever the similarity score.
- **(c) Conflict handling** — authority precedence (**legal > standard >
  advisory**) for cross-level conflicts; same-level conflicts, rule-engine
  disagreements and human-only decisions become tracked entries in the
  **Open Issues** register, each with a status and an arbitration note.
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
- **(f) Deterministic metrics** — fairness numbers come from pandas, and every
  figure in the narrative is checked against the computed set.
- **(g) Declared completeness** — each agent publishes the checklist it must
  account for and declares, per item, `covered`, `not-applicable` or
  `not-grounded` with a reason. Being exhaustive is not the goal; being
  accountable is.
- **(h) Reproducible provenance** — every artifact records the model,
  temperature, corpus version, the id of every excerpt in the prompt, a prompt
  hash, which attempt was approved, whether a human edited it, the rejection
  history, and the result of every check.
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
raia/
├── app.py                     # entry point: sign-in, agreement, page registry (top menu)
├── views/                     # one file per page: home, guide, project, stage, agents,
│                              #   assessment, settings, research, legal, login, consent, signout
├── ingest.py                  # Builds the Chroma normative index from corpus/
├── raia/
│   ├── config.py              # env-driven settings; authority + source registries
│   ├── fields.py              # the structured-intake field model
│   ├── examples.py            # the canonical resume-screening walkthrough
│   ├── llm.py                 # provider-agnostic factory, retry, contract-aware mock
│   ├── rag.py                 # retrieval with pinned excerpts and excerpt ids
│   ├── rationale/             # the deterministic decision procedures
│   │   ├── risk_screen.py     #   prohibitions, risk areas, obligation assembly
│   │   ├── coverage.py        #   obligation × principle coverage matrix
│   │   ├── story_map.py       #   ECCOLA card selection, story register
│   │   ├── traceability.py    #   evidence matching, NOT VERIFIED by code
│   │   ├── drift.py           #   thresholds, breaches, trend, sample adequacy
│   │   └── principles.py      #   the seven adopted principles, machine-readable
│   ├── contract/              # the standard RAIA record
│   │   ├── vocab.py           #   closed vocabularies from the normative sources
│   │   ├── rubric.py          #   likelihood × magnitude matrix, priority floors
│   │   ├── schema.py          #   shared core + one extension per agent
│   │   ├── prompt.py          #   the contract as the model sees it
│   │   ├── assemble.py        #   parse, repair, finalise, fallback
│   │   ├── render.py          #   the one Markdown layout
│   │   ├── checks.py          #   record-level checks
│   │   ├── actions.py         #   project action plan and its exports
│   │   ├── export_schema.py   #   writes docs/schema/
│   │   └── agent_cards.py     #   writes docs/agents/
│   ├── validators.py          # citations, structure, coverage, reconciliation
│   ├── provenance.py          # the run record stamped into every artifact
│   ├── repository.py          # blackboard behaviour + the Git backend
│   ├── storage.py             # backend selection; hash-chained database blackboard
│   ├── db.py                  # SQLite locally, PostgreSQL hosted — one SQL dialect
│   ├── projects.py            # people, projects, roles, invitations, authorization
│   ├── lineage.py             # stage dependencies and the derived "needs review" flag
│   ├── ui/                    # routes, theme (CSS + icons), components, approval gate,
│   │                          #   agent docs, tester guide, assessment instrument, legal page
│   ├── auth.py                # Google sign-in via Streamlit, or a local dev identity
│   ├── pipeline.py            # the graph: generate → human gate → persist
│   ├── sanitize.py            # injection screening (EN + PT), flag-never-delete
│   ├── export.py              # one-zip project export
│   └── agents/                # the five agent specifications
├── corpus/                    # curated normative summaries (extensible)
├── docs/
│   ├── architecture.md        # diagrams and the traceability table
│   ├── output-contract.md     # the standard record every agent produces
│   ├── agents/                # one generated agent card per agent
│   ├── schema/                # published JSON Schemas of the record
│   ├── templates/             # agent card and project-log entry templates
│   ├── PROJECT_LOG.md         # what was wrong, what was decided, what changed
│   ├── legal/PRIVACY_AND_TERMS.md  # public privacy policy and user agreement
│   └── TESTERS.md             # tester guide, generated from raia/ui/guide.py (also the Guide page)
└── tests/
    ├── smoke_test.py          # offline end-to-end, including the invariants
    ├── test_engines.py        # deterministic unit checks
    ├── test_contract.py       # the output contract: vocabularies, rubric, records, layout
    ├── consistency_check.py   # run-to-run agreement of records (use a real model)
    ├── test_projects.py       # isolation, roles, durability, tamper evidence
    └── test_ui.py             # headless walkthrough of the project-based UI
```

## Extending the Normative Corpus

Drop a richer `.md` into `corpus/`, register the source key in
`config.AUTHORITY_LEVELS` and `config.SOURCE_NAMES`, and re-run
`python ingest.py`. Missing registration breaks citations and precedence.

Two cautions. Sections pinned by a decision procedure are matched by their
exact heading text, so renaming a heading silently removes a pin — the smoke
test checks every pin still resolves, and it will tell you. And sources listed
in `config.DERIVED_SOURCES` are labelled in the prompt and at the gate as
curated summaries rather than official texts; move a source out of that set
only when its file really is the official wording.

## Configuration Reference

| Var | Default | Notes |
|---|---|---|
| `RAIA_LLM_PROVIDER` | `anthropic` | `anthropic` \| `openai` \| `mock` |
| `RAIA_LLM_MODEL` | `claude-sonnet-5` | |
| `RAIA_LLM_TEMPERATURE` | `0.2` | low for reproducibility; `none` omits it (models that reject a temperature are also detected and retried without it) |
| `RAIA_LLM_MAX_TOKENS` | `16384` | a standard record for a high-risk system is long; truncation is detected, not tolerated |
| `RAIA_LLM_MAX_TOKENS_CEILING` | `32000` | the budget one retry may raise to after a reply was cut off |
| `RAIA_LLM_RETRIES` | `2` | transient provider failures only |
| `RAIA_CONTRACT_REPAIRS` | `1` | a reply that does not validate against the record schema is returned with its errors this many times |
| `RAIA_RAG_TOP_K` | `12` | plus the excerpts each procedure pins |
| `RAIA_RAG_CHUNK_SIZE` / `_OVERLAP` | `1800` / `200` | chars, at ingestion |
| `RAIA_MIN_GROUP_SAMPLES` | `30` | below this, a group figure is indicative only |
| `RAIA_DEFAULT_PARITY_THRESHOLD` | `0.1` | used only when no approved artifact sets one |
| `RAIA_WORKSPACE_DIR` | `./workspace` | local git blackboards and SQLite registry (git-ignored) |
| `RAIA_DATABASE_URL` | SQLite under the workspace | PostgreSQL URL (e.g. Neon) for a shared deployment |
| `RAIA_STORE` | `git` locally, `database` with PostgreSQL | where project blackboards live |
| `RAIA_AUTH` | `google` if `[auth]` is set, else `dev` | a PostgreSQL deployment never falls back to `dev` |
| `RAIA_ADMIN_EMAILS` | — | may download the pseudonymized research dataset |
| `RAIA_PSEUDONYM_KEY` | — | keyed participant codes, stable across exports |
| `RAIA_CONTACT_EMAIL` | — | contact shown on the public Privacy & terms page (`/privacy`) |
| `RAIA_MAX_RUNS_PER_DAY` | `60` | model calls per person per UTC day; `0` = unlimited |
| `RAIA_CORPUS_DIR` / `RAIA_CHROMA_DIR` | `./corpus` / `./.chroma` | |
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

Plus, recommended: `RAIA_ADMIN_EMAILS` (who may export research data) and
`RAIA_PSEUDONYM_KEY` (a long random string). Tables are created on first
start; there is no migration step to run.

The app **fails closed**: with a database configured and no sign-in, it refuses
to open rather than serving projects to anyone with the link. A review paused
at an approval gate is stored by the PostgreSQL graph checkpointer, so a
restart does not lose it; the stored-draft restore path remains as a second
line of defence and still re-enters the gate.

## Testing

```bash
RAIA_LLM_PROVIDER=mock RAIA_FAKE_EMBED=1 python tests/smoke_test.py
python tests/test_projects.py                      # git blackboards + SQLite
RAIA_STORE=database python tests/test_projects.py  # database blackboard on SQLite
RAIA_DATABASE_URL=postgresql://... python tests/test_projects.py   # on PostgreSQL
python tests/test_ui.py                            # headless UI walkthrough
python tests/test_contract.py                      # the output contract (also run by the smoke test)
python tests/consistency_check.py --agent risk_classifier --runs 5   # with a real provider
```

Runs fully offline. Covers ingestion, pinned retrieval, stage gates, required
inputs, all five decision procedures, the human-review interrupt, the rejection
loop, approval, provenance, sidecars, the open-issues register, restart
recovery, the export bundle, and the deterministic unit checks. It asserts the
two invariants directly: nothing persists without a human approval, and a
fabricated citation is detected.

## Roadmap (next developments)

- [x] Structured intake driving deterministic decision procedures, all five agents
- [x] Citation verification against retrieved excerpts
- [x] Open Issues register with arbitration
- [x] Reproducible provenance and structured artifact sidecars
- [x] Input sanitization against prompt injection, including the artifact path
- [x] Projects owned by signed-in people, with editor/reviewer invitations and an optional second approver
- [x] One standard record for every agent, with a project action plan
- [x] Durable, tamper-evident storage for hosted deployments (PostgreSQL, hash-chained versions)
- [ ] Ingest the official legal texts with article-level citation metadata
- [ ] Jira / Confluence integration via MCP connectors
- [ ] Least-privilege tool-permission hardening
- [ ] Expert-panel evaluation (Design Science Research)
- [ ] Case studies in real development environments

## Citation & License

MIT. See `docs/architecture.md` for diagrams and the traceability table between
the architecture and the code, and `docs/PROJECT_LOG.md` for the record of what
was wrong with earlier versions and what changed.
