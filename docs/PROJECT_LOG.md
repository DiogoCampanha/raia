# RAIA — Project Log

A running record of the state of the proof of concept, the problems found in it,
and the work done to fix them. Newest entries at the top of the changelog.

The purpose of this file is traceability: anyone (including future maintainers)
should be able to read it and understand *what was wrong*, *what was decided*,
and *what changed in the code as a result* — without re-deriving the analysis.

---

## 1. Baseline: state of the PoC before this work

**Reviewed:** `main` at `44d5770` · 2,850 lines of Python · 6 corpus files · 5 agents
**Date of review:** 13 September 2026
**Context:** the expert panel evaluates this build. Usability and utility scores from
that panel are the project's evaluation evidence, so defects in the walkthrough are
defects in the research instrument.

### 1.1 What was already sound and was deliberately kept

| Element | Why it was kept |
|---|---|
| Human approval gates via the state-graph interrupt | The persistence node is genuinely unreachable without an explicit approve decision. The invariant held under test. |
| Git-versioned blackboard, one repo per project | Every approval is a commit with approver provenance. Agents never call each other. |
| Refusal to fall back to canned output when unconfigured | A tester who cannot tell mock text from real analysis would evaluate the wrong artifact. This is a deliberate research decision, not a missing feature. |
| Sanitization that flags rather than deletes | Silent removal would itself break auditability. The finding is attached to the draft and survives into the approved artifact. |
| Deterministic fairness metrics with the model as interpreter | The only place in the system where a claim was enforced by code rather than requested in a prompt. It became the pattern for everything else. |
| Per-session private workspaces keyed into the URL | Correct design for concurrent panel testing. |

### 1.2 Problems found

Severity: **C** critical · **H** high · **M** medium.
IDs are referenced by the changelog in section 3.

#### Usability and input design

| ID | Sev | Problem |
|---|---|---|
| UX-1 | C | The system never asked the questions that determine the answer. Provider vs deployer, target markets, high-risk area, biometric or emotion inference, decision autonomy, data categories — all left for the model to infer from prose, with no signal about what it guessed. |
| UX-2 | H | Input types were declared and ignored. `InputField.kind` already carried `"textarea" \| "text" \| "csv"`; the UI rendered every field as a 140px text area regardless. |
| UX-3 | H | No file attachment anywhere in the product. A team with a requirements document or a telemetry export had to paste text. |
| UX-4 | H | The reviewer at the approval gate could not see the evidence. Retrieved excerpts were discarded when the agent returned, so a citation could not be checked without leaving the app. |
| UX-5 | H | A server restart destroyed in-flight work: the checkpointer was in-process, so the UI still showed a pending draft whose graph thread no longer existed. |
| UX-6 | M | The gate collected almost nothing analysable — one free-text approver name, one free-text rejection reason, no per-stage rating, no structured reason codes. |
| UX-7 | M | The flow had no rationale. Five identically-shaped pages; nothing adapted to the risk classification the system had already produced. |
| UX-8 | M | One write path skipped the gate (`product_brief` was committed before the agent ran) and no input field was ever required. |
| UX-9 | M | Telemetry analysis reported parity differences with no group sizes, no trend, no schema validation before the run. |
| UX-10 | M | No way to take the evidence home: artifacts downloaded one at a time while the workspace is destroyed on restart. |

#### Reliability and guardrails

| ID | Sev | Problem |
|---|---|---|
| REL-1 | C | Citations were never verified. The model emitted a citation tag and nothing compared it to the excerpts actually retrieved, so an unsupported obligation reached a commit unchallenged. |
| REL-2 | C | The Open Issues mechanism was dead code. `append_open_issue()` was never called; `07_open_issues.md` was never written. Conflicts existed only as a heading the model might emit. |
| REL-3 | H | No output contract. Prompts specified exact sections; nothing verified they arrived, and nothing detected a response truncated at the token limit. |
| REL-4 | H | Injection defenses guarded only the input form. The largest free-text surface — the human-editable draft, which is committed and then injected into every downstream prompt — was unsanitized. Patterns were English-only. |
| REL-5 | H | The audit trail could not answer "why did it say that?". Artifact headers recorded approver and timestamp, not model, temperature, corpus version, retrieved excerpts or attempt number. |
| REL-6 | M | Computed fairness numbers were never cross-checked against the narrative the model wrote about them. |
| REL-7 | M | No retry on transient provider errors; a single overload response lost the attempt. |

#### Depth of knowledge and agent reasoning

| ID | Sev | Problem |
|---|---|---|
| DEP-1 | C | Retrieval discarded most of a corpus that fits whole in a prompt. The corpus is 57 chunks; the Risk Classifier filtered to a pool of ~20 and took the top 6 — so the excerpt carrying the high-risk area list could simply not be retrieved, and the output would still look confidently grounded. |
| DEP-2 | C | Citations resolved to a curated summary written for this project, not to the norm. |
| DEP-3 | H | No agent had a decision procedure. Four of five were: concatenate upstream markdown, retrieve six chunks, send one prompt, render the string. |
| DEP-4 | H | The retrieval query was built from prose — SDLC phase plus the first 400 characters of each input — never from what the system already knew about the project. |
| DEP-5 | M | Cross-agent consistency was asserted in prompts and never checked: nothing verified that a criterion traced to an ethical value requirement that exists, or that every input story came back. |
| DEP-6 | M | The seven adopted Responsible AI principles existed nowhere the code could enumerate them, so principle coverage could not be computed. |

### 1.3 Corrections to the analysis

Recorded so the log stays honest about its own errors.

- **DEP-6 was partly wrong.** The first review stated that the ECCOLA corpus summary
  contained seven themes rather than the full card set. It does contain all 21 cards
  (`#0`–`#20`) grouped into seven modules. The card-mapping engine therefore maps to
  real card identifiers, which is better than the analysis assumed. The remaining part
  of DEP-6 — that the seven adopted Responsible AI principles are not machine-readable
  anywhere — stood, and is addressed.

---

## 2. Decisions taken

| # | Decision | Rationale |
|---|---|---|
| D1 | The panel evaluates the hardened build, not the reviewed baseline. | Likert data cannot be pooled across two materially different artifacts, and the baseline loses points on exactly the dimensions the panel scores. |
| D2 | All five agents get a deterministic decision procedure, not just the first one. | The decision procedure is the substance of the contribution. Two agents done well would score better than five done shallowly, but five done well is what the architecture actually claims. |
| D3 | Keep the curated normative summaries; fix the retrieval defect instead. | The real defect was retrieval silently dropping decisive text. Pinning mandatory excerpts fixes that with no network dependency and no re-ingest risk before the freeze. Ingesting official legal texts remains scheduled, after the panel. |
| D4 | Work on a branch, commit locally, do not push. | Pushing to the default branch auto-redeploys the instance the panel uses. Nothing reaches testers until the build is reviewed and deliberately released. |
| D5 | Interface stays in English. | The normative corpus is in English and the panel is bilingual; a second language doubles the label surface that the new structured forms introduce, right before a freeze. |
| D6 | Replace "answers as thorough as possible" with declared completeness. | Long drafts degrade review quality at the approval gate, which is the architecture's only real safety net. Each agent now publishes the checklist it must cover and declares, per item, whether it was covered, is not applicable, or is not grounded in the retrieved excerpts. |
| D7 | Keep rules for what is enumerable; leave open-textured judgement to the model. | Prohibition lists, high-risk area lists and obligation tables are enumerable and belong in code. Narrow-task exemptions and "significant risk of harm" are judgement calls a rule table would get confidently wrong. |
| D8 | When the rule engine and the model disagree, surface both and open an issue. | Never average them, never let either win silently. This reconciliation channel is the mechanism that makes grounded-and-human-arbitrated concrete rather than aspirational. |
| D9 | Organize the software around projects owned by signed-in people, and land it **before** the panel. | A browser session was the only unit of work, so nobody could keep work across days or hold two projects at different stages. The panel had not started, so it evaluates this build and D1 still holds. |
| D10 | Google sign-in via Streamlit's native OpenID Connect, not a home-made password system. | No password storage, resets or brute-force protection to get wrong; the verified email becomes the approver identity. |
| D11 | PostgreSQL (Neon) for hosted deployments; Git per project stays the local backend. | The hosted disk is erased on redeploy. Both backends share every behaviour above the storage primitives, and the database backend keeps tamper evidence with a hash chain. |
| D12 | Build reviewer invitations now: roles owner / editor / reviewer, plus an optional second-approver rule. | Separation of duties at the approval gate is a responsible-AI control in its own right, and it is cheap once identity exists. |
| D13 | Evaluation events stay inside each project; research exports are pseudonymized. | Keeps the evidence next to the work it describes, and keeps names and emails out of the dataset. |
| D14 | Replace the per-stage rating widget with one highlighted *Rate your experience* page. | One submission rating every stage gives comparable, complete responses and stops rating prompts from interrupting the walkthrough. |
| D15 | Rebuild the interface as separate pages on Streamlit (Home, Project, Stage, Agents, Assessment, Settings, public Privacy & terms) rather than rewriting it as a separate web front end. | A rewrite would rebuild sign-in, storage and tests inside the panel window. Streamlit's page routing, hidden pages and theming cover the page map; a separate front end remains possible after the panel. |
| D16 | Top navigation menu; project and stage pages are hidden from the menu and take their context from the URL. | A top menu with four entries matches current product conventions and leaves the full width to the work. URL context makes a stage shareable between members; membership is re-checked on every load. |
| D17 | No emoji in the interface; Material Symbols icons and one status vocabulary with text labels. | Emoji render differently per platform and read as informal; status carried by colour or pictogram alone fails accessibility. |
| D18 | Revising an approved stage flags the approved stages that depend on it as *Needs review*. Nothing is re-run automatically; a person revises or re-confirms each one, and both are recorded. | An automatic re-run would call the model and produce drafts nobody requested, against the rule that nothing advances without a person. The flag is derived from the event log, like all progress. |
| D19 | The tester assessment uses the evaluation plan's five dimensions (utility, completeness, usability, methodological rigor, generalizability) on a five-point agreement scale, plus open questions, optional broad profile questions and optional per-stage items. Instrument id `raia-panel-v1`. | The plan's success criterion is computed over exactly these dimensions. The earlier per-stage usefulness/ease/trust items did not map to it. The plan defines the dimensions but not item wording, so each statement is the plan's definition of its dimension, translated to English; the id changes if the wording does. |
| D20 | A public Privacy Policy and User Agreement page, served by the app without sign-in from `docs/legal/PRIVACY_AND_TERMS.md`; people re-accept when its effective date changes. | Google's OAuth consent screen requires a public policy URL. One Markdown source serves both the app and any external copy. |

---

## 3. Changelog

Entries are added as work lands. Each names the finding IDs it closes.

<!-- CHANGELOG:START -->
### 2026-09-17 — Interface rebuilt as separate pages on branch `ui-revamp`

Decisions D15–D20.

#### What was wrong

- **UX-R1** One page with a sidebar radio did everything: project switching,
  the five stages, open issues, audit trail, people, ratings and account. There
  was no overview across projects and no way to link to a stage.
- **UX-R2** Emoji carried status and navigation (✅ 🧑‍⚖️ ▶️ 🔒), rendering
  inconsistently and without text labels.
- **UX-R3** Re-running an approved stage silently left every stage built on it
  approved against a version that no longer existed.
- **EVAL-R1** The rating form asked usefulness, ease and trust per stage plus
  four overall items; none mapped to the evaluation plan's five dimensions.
- **LEGAL-R1** The privacy notice was only visible after signing in; Google's
  consent screen needs a public policy URL.
- **UX-R4** Form answers disappeared from the screen after visiting another
  page and returning (Streamlit discards state of widgets not drawn in a run).

#### What changed

- `app.py` is now only the entry point: sign-in, agreement acceptance and the
  page registry (`st.navigation`, top position). Pages live in `views/`; the
  page map is documented in `raia/ui/routes.py`.
- `raia/ui/`: `theme.css` (design tokens and components, targeting stable
  `data-testid` selectors), `theme.py` (icons, status and risk vocabulary),
  `components.py` (page header, stat tiles, badges, stage tracker, empty
  states), `gate.py` (intake form and approval gate, moved from `app.py`),
  `agent_docs.py`, `assessment.py`, `legal.py`, `state.py`.
- `.streamlit/config.toml`: Inter typography, light and dark palettes, radii,
  borders. Streamlit pinned to 1.63.x because the CSS layer depends on it.
- **Home** — attention list (drafts at the gate, stages needing review), stat
  tiles, project table with risk level, progress, next step and role.
- **Project** — primary next action, stage tracker, tabs for Documents, Open
  issues, Activity, People and settings.
- **Stage** — read the approved version, revise it with the impact shown first,
  re-confirm a flagged stage, or run and review; the gate itself is unchanged.
- **Agents** — interactive architecture diagram (HTML/CSS/JS) and per-agent
  documentation read from each `AgentSpec`.
- **Assessment** — consent, optional profile, five required Likert items,
  optional per-stage items, open questions, save draft (UX-R4, EVAL-R1).
- **Settings** — profile, legal documents, download my data, sign out, delete
  account. **Privacy & terms** is public (LEGAL-R1).
- `raia/lineage.py` — stage dependencies derived from `upstream_keys`, and the
  derived *Needs review* status (UX-R3). `ProjectService` gains
  `revision_impact`, `reconfirm_stage`, assessment drafts and
  `my_data_export`; `stage_summary` adds stale stages and the risk label.
- Events on the database backend carry microsecond timestamps so an approval
  and a re-confirmation in the same second keep their order.
- Automated-check summaries and the sanitization notice inside artifacts use
  words instead of emoji.

#### Invariants added to the tests

- Re-approving a stage flags exactly its approved dependents and **re-runs
  nothing** (no draft appears at any downstream gate).
- A revision waiting at its gate flags nothing: the approved version is still
  in force.
- Only a flagged stage can be re-confirmed; re-confirmation is attributed and
  names its cause; a non-member cannot do it.
- Assessment drafts never reach the research export.
- The legal page opens without signing in; no page shows emoji.

### 2026-09-16 — Users, projects and durable storage on branch `projects`

Decisions D9–D14.

#### What was wrong

- **UX-P1** The unit of work was the browser session: `session_project()` built a
  throwaway project from a `?s=` URL parameter. Nobody could return to work,
  hold two projects, or share one.
- **SEC-P1** That URL parameter was the only access control — anyone with the
  link opened the workspace.
- **SEC-P2** Drafts and form answers were keyed by agent in `st.session_state`,
  not by project, and form answers were never stored server-side.
- **ACC-P1** The approver at every gate was a typed name.
- **DEP-P1** The hosted filesystem and the in-memory checkpointer lose all data
  on redeploy.

#### What changed

- `raia/auth.py` — Google sign-in through `st.login`; a `dev` identity for
  laptops and tests; fails closed on a database-backed deployment without
  sign-in.
- `raia/db.py` — one small SQL layer over SQLite (local) and PostgreSQL
  (hosted); schema created on start.
- `raia/repository.py` — split into `BaseRepository` (all blackboard behaviour)
  and the Git backend; `raia/storage.py` adds `DatabaseRepository`
  (append-only, hash-chained, `verify_history()`), backend selection and the
  PostgreSQL graph checkpointer.
- `raia/projects.py` — users, projects, memberships, invitations by email,
  roles, second-approver rule, derived stage summary, daily model-call
  allowance, experience ratings, pseudonymized research export, account and
  project deletion. Every operation authorized in one place.
- `raia/pipeline.py` — runs carry the actor; drafts record who ran them and the
  inputs used; the human-authored product brief is now committed inside the
  classification's approval node instead of by the UI afterwards; approver id
  and runner id land in provenance and events.
- `app.py` — sign-in and consent pages; *My projects* (invitations, create,
  demo project, progress cards); project switcher; project-scoped widget and
  session keys; answers autosaved to the project; navigation by stable page
  ids (approving a stage no longer resets the sidebar selection); *People &
  settings*; audit trail shows the integrity check and attributes activity;
  per-stage rating widget removed; highlighted *⭐ Rate your experience* page
  rating every stage in one form; *Account & privacy* with account deletion;
  admin-only research data page.
- `raia/export.py` — project export with integrity statement, hash chain and
  pseudonymized events.

#### Tests

- `tests/smoke_test.py` and `tests/test_engines.py` pass unchanged.
- `tests/test_projects.py` (new) — isolation for eleven operations, a foreign
  project indistinguishable from a missing one, independence of two projects at
  different stages, identity-bound approvals (a forged approver name is
  ignored), invitations (single-use, addressee-only), reviewer restrictions,
  last-owner guard, second approver including after a restore, durability
  across a simulated restart, tamper detection on content and on messages,
  usage allowance, ratings, no identity leaks in research or project exports,
  leaving and deleting, fail-closed sign-in configuration. Run on three
  configurations: Git + SQLite, database store on SQLite, and PostgreSQL 16
  (where the paused graph thread itself survives the restart).
- `tests/test_ui.py` (new) — headless walkthrough: consent, demo project, run
  and approve, second project with no bleed-through, switching, invitation,
  whole-experience rating, audit trail attribution.

### 2026-09-13 — Hardening pass on branch `hardening`

The whole of P0 plus the depth work from P1, implemented together because the
panel evaluates this build (decision D1). Grouped by what changed, with the
finding IDs each item closes.

#### Every agent now runs a decision procedure (D2, D7 — closes DEP-3)

New package `raia/rationale/`, one engine per agent. Each computes what is
enumerable, declares the norm excerpts its decision depends on, and publishes
the checklist the output must account for.

| Engine | What it computes |
|---|---|
| `risk_screen.py` | Prohibited-practice screen and high-risk area match for both regimes; narrow-task exemption handling; role-dependent obligation assembly from a table. |
| `coverage.py` | Obligation × principle coverage matrix against the stated requirements and declared controls; the gap list is derived; requirement identifiers are assigned by the engine. |
| `story_map.py` | ECCOLA card selection from risk tier, data categories and sprint capabilities, each card recording why it applies; the story register as a counted invariant. |
| `traceability.py` | Evidence matching against the approved register; anything with no trace is NOT VERIFIED before the model is asked anything. |
| `drift.py` | Thresholds parsed out of the approved artifacts, breach detection, trend, representativeness shift, and sample adequacy per group. |
| `principles.py` | The seven adopted Responsible AI principles as a structure the code enumerates (closes DEP-6). |

Where an engine and the agent disagree, the agent must declare it and the
disagreement becomes an open issue (D8). It is never averaged.

#### Structured intake (closes UX-1, UX-2, UX-3, UX-7, UX-8, DEP-4)

- New `raia/fields.py`: typed fields with `select`, `multiselect`, `boolean`,
  `number`, `csv` and `file` kinds, required rules, grouped sections and
  conditional visibility. One renderer in `app.py` honours all of it.
- The Risk Classifier now asks the eighteen questions that actually decide a
  classification, instead of inferring them from prose. Option vocabularies
  live next to the rule that reads them, so the coupling is greppable — the
  rule that no field ships unless code consumes it.
- File upload on the telemetry and document inputs, with the uploaded text
  sanitized on the same path as pasted text.
- Required fields are enforced before a run (`BaseAgent.missing_inputs`).
- Retrieval queries are built from the computed verdict and matched areas
  rather than the first 400 characters of pasted prose.
- The product brief is now committed at the moment the classification is
  approved, under the approver's name and labelled as human-authored input,
  instead of appearing before any review.

#### The approval gate shows its evidence (closes UX-4, UX-5, UX-6, UX-10)

- The gate has four tabs: rendered draft, editable draft, **the excerpts that
  were actually retrieved**, and **everything the rule engine computed**.
  Pinned excerpts are marked with the reason they were required; curated
  summaries are labelled as not being the official text.
- Automated check results are shown above the draft, colour-coded, with the
  standing caveat that checks inform and never block.
- Approval requires a name. Rejection requires a reason code from a fixed list
  plus free text; both are recorded as events.
- A per-stage usefulness and usability rating appears once a stage is approved.
- **Export this session** produces one zip: artifacts, structured sidecars,
  commit history and evaluation events.
- Restart recovery: an in-review draft is written to disk, and if the process
  restarts the review is re-entered through the graph so it stops at the
  approval gate again. Nothing is persisted that a human did not approve.

#### Reliability (closes REL-1, REL-2, REL-3, REL-4, REL-5, REL-6, REL-7)

- New `raia/validators.py`. Citations are matched against the excerpts actually
  retrieved for that run; required sections, declared coverage, truncation,
  verdict reconciliation, engine-raised conflicts, upstream traceability,
  invented identifiers, unverifiable requirements, upgraded verdicts and
  invented metric values are all checked deterministically.
- The **Open Issues register is wired**: `append_open_issues` is called on
  every approval, from both the engine's conflicts and the draft's own Open
  Issues section, with de-duplication, statuses (open / accepted / resolved)
  and an arbitration page in the UI.
- Output contract: each agent declares required sections and a machine-readable
  block; `max_tokens` raised to 8192 and the provider's stop reason is checked,
  so truncation is detected instead of shipping a draft that merely looks
  finished.
- New `raia/provenance.py`: model, temperature, corpus version, the id of every
  excerpt in the prompt, a prompt hash, which attempt was approved, whether the
  human edited it, the rejection history and the check results — in the
  artifact header and in the JSON sidecar.
- Sanitization extended to Portuguese patterns and to the artifact write path,
  which is the text every downstream prompt inherits. The limits of regex
  detection are now stated in the code and the docs rather than implied.
- Transient provider failures are retried with backoff in a single `invoke_chat`
  call site; nothing else is retried.

#### Retrieval (closes DEP-1, partially DEP-2)

- Decision procedures pin the sections they depend on; pinned excerpts are
  fetched by exact metadata match and merged ahead of similarity results, so
  the passage that decides a classification can no longer be dropped by a
  similarity score. The smoke test fails if any pin stops resolving.
- `RAIA_RAG_TOP_K` raised from 6 to 12, and every excerpt now carries a stable
  id recorded in provenance.
- Sources whose corpus text is a curated summary are listed in
  `config.DERIVED_SOURCES` and labelled as such in the prompt and at the gate.
  Per decision D3, ingesting the official legal texts stays scheduled for after
  the panel; this is the honest interim statement of the limitation.

#### The blackboard holds structure (root cause, section 2)

Every artifact is written twice in the same commit: the Markdown a person reads
and a JSON sidecar the next agent's decision procedure consumes. Nothing
downstream parses prose to recover a value any more — the coverage matrix, the
traceability register and the threshold checks all read the sidecar.

#### Tests

- `tests/test_engines.py` — deterministic unit checks for all five engines, the
  validators, the sanitizer and the principles registry.
- `tests/smoke_test.py` — rewritten: ingestion, pin resolution, pinned
  retrieval, stage gates, required inputs, all five agents end to end,
  rejection loop, provenance, sidecars, cross-agent structure flow, the open
  issues register, restart recovery, the export bundle, and a direct assertion
  that a fabricated citation is detected. It asserts the persistence invariant
  three times, including on the recovery path.
- The mock model was made a proper test double: it reads the output contract
  from the prompt and produces a conforming document citing a real excerpt, so
  the whole chain is exercisable offline. Everything runs with
  `RAIA_LLM_PROVIDER=mock RAIA_FAKE_EMBED=1 python tests/smoke_test.py`.
- The UI itself was exercised headlessly with Streamlit's app-test harness: the
  full five-stage walkthrough, including the empty-form refusal, the
  approver-name gate and the open-issues page.
- The pushed branch was verified independently: cloned from GitHub into a clean
  environment, installed from `requirements.txt` alone, and run end to end. This
  is what surfaced defect 3 below, and it also confirms no needed file was
  accidentally left untracked.

#### Two defects the new tests found in the new code

Recorded because a log that only lists successes is not worth keeping.

1. `check_requirement_quality` accepted "the system shall be fair" as
   verifiable, because `shall` was in the list of measurable tokens and the
   requirement's own identifier (`EVR-1`) supplied the digit. Both were wrong:
   `shall` and `must` are the modal verb of every requirement ever written, and
   an identifier is not evidence of measurability. Fixed.
2. Principle keyword matching was plain substring matching, so `log` matched
   `catalog`. Anchored to word boundaries.
3. **A stale or half-written vector index was trusted.** Found by cloning the
   pushed branch into a clean environment and running it from scratch: an
   ingest that fails part-way leaves a collection that *exists*, so the
   self-bootstrap skipped rebuilding it, and the app then failed at the first
   retrieval with "collection not found" — permanently, until someone deleted
   `.chroma` by hand. On a hosted deployment that is a dead app with a
   confusing error, and it would have been triggered by any interrupted first
   start or by a change to `RAIA_FAKE_EMBED` between deploys. The collection is
   now stamped with the corpus version, the embedding function and the exact
   chunk count it should hold, and any mismatch causes a rebuild instead of a
   failure. Covered by a new smoke-test section.

#### Still open, by decision

- Official legal texts in the corpus (DEP-2) — scheduled after the panel (D3).
- Jira / Confluence MCP connectors and least-privilege tool permissions — named
  as future work, not built.
- Interface stays English (D5).

<!-- CHANGELOG:END -->
