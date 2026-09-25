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
| D21 | Every agent answers in one standard record: a shared core (summary, findings, actions, typed open issues, not grounded, declared coverage) plus one extension per agent. The model returns JSON validated against its schema; code renders the Markdown. | Free prose inside fixed headings made two projects incomparable and made each stage's layout new to the reviewer. A template the model fills in as prose would standardise the look, not the content. |
| D22 | Every vocabulary, scale and field is drawn only from the project's normative sources — the seven adopted principles, NIST AI RMF 1.0, IEEE 7000-2021, Microsoft RAI Standard v2, ECCOLA, the EU AI Act and PL 2338/2023. No other standard is used. | The software operationalises the frameworks the research integrates; importing others would make the artifact evaluate something the research does not claim. A test asserts that the vocabularies occur in the corpus. |
| D23 | The model places findings on likelihood and magnitude; code computes risk level and priority with a published matrix and floors (prohibited practice → critical and blocking; legal grounding → at least high; computed severity is a floor). | NIST AI RMF asks for likelihood and magnitude but fixes no scale. A model-assigned priority varies between runs for no inspectable reason; a computed one carries its basis. The levels and matrix are stated as RAIA's operationalisation. |
| D24 | Reviewers edit the record's fields at the gate, not the rendered text. Persistence re-finalises, re-renders and re-validates the edited record; free-text edits are refused. | Otherwise the standard would stop being one at the exact point a person touched it, and priorities would no longer match placements. |
| D25 | The output-contract work lands on its own branch, committed locally and not pushed. | The panel evaluates a frozen build. Whether this change enters the evaluated build is a decision for the author, taken knowingly rather than by a redeploy. |
| D26 | A page run reads each project's current files and pending drafts once (a snapshot per repository object, dropped by any write to the project in the process), and each membership once (a memo scoped to the run). Single statements run without BEGIN/COMMIT, and a pooled connection is probed only after it sat idle. | On a hosted database every statement is a network round trip. Membership is still checked on every run, so removal still takes effect on the next click; the recorded history is never cached. |
| D27 | *Sign out* is an entry of the Account menu (its own page, `/signout`), not a button inside Settings. It is listed only when there is a sign-in to end. | Ending a session is a navigation action people look for in the account menu; burying it in a settings page made testers hunt for it. |
| D28 | The Risk Classifier asks how the AI works (techniques, where in the product it acts, where the model comes from) and the risk screen reads it. A rules-only product is flagged against the AI-system definition but still screened as in scope; transparency duties implied by the techniques are applied even when the transparency question missed them, and the disagreement is escalated. The product prose is split into guided questions with an example answer each. | Both regimes define an AI system by its capacity to infer, and the transparency duties follow the technique, so the form was missing the facts the classification rests on. The engine may only flag or add, never conclude that a product is out of scope — the conservative direction, with a person deciding. |
| D29 | A **Guide** page in the top menu walks testers through RAIA step by step. Its content lives in `raia/ui/guide.py`, which also generates `docs/TESTERS.md`; the table of what each agent asks is built from the agent specifications. | The tester guide lived only in the repository, which testers never see. One source for the page and the document means they cannot drift, and a form change updates the guide by itself. |
| D30 | The Requirements Reviewer can **recommend ethical requirements** from the approved risk classification, but only as proposals: context questions (stakeholders, principles at stake) are pre-filled only when empty, and candidate requirements enter the requirements one at a time, when a person adopts them. | A blank form stalled testers, and the classification already holds most of the context. Writing requirements into the field directly would let the model close the gaps the engine computes from that same field, so the coverage matrix would be marking the model's own work. |
| D31 | The controls already in place, the requirements the team wrote, its delivery constraints and the requirement format are **never** pre-filled; the controls question is only annotated with the controls the assigned obligations make relevant. | A ticked control discharges obligations. Proposing one would be inventing evidence, not recommending. |
| D32 | Adopted recommendations stay distinguishable: the engine marks coverage that rests only on them as *addressed by an adopted suggestion*, the record says which requirements RAIA recommended and whether they were edited, pre-filled answers must be confirmed before running, and every suggestion, adoption and rejection is an evaluation event. | Accepting a proposal is a weaker claim than writing a requirement. Keeping the two apart lets a reviewer weigh them, and the adoption rate is evidence about automation bias for the evaluation. Candidates use only project data and the normative corpus, never other users' projects. |
| D33 | Every record reads in three tiers — a summary with figures and the main issues, then what to do (actions grouped Do now / Plan / Track, and decisions), then a deep dive behind a dropdown whose sections each open with a conclusion — and the exported document follows the same order. | RAIA is a work tool. Testers faced pages of tables and legal explanation before reaching what to do; the gate is only a safety net if the reviewer can take in the draft. One digest feeds screen and document so they cannot drift. |
| D34 | Shorter records by contract: a one-sentence `headline`, a summary of at most three sentences, lower caps on every free-text field, and a rule that each field leads with its conclusion and does not explain frameworks or law. | Length was the complaint; a prompt asking for brevity without caps was not enough. Leading with the conclusion is also what lets code lift section conclusions without a second model call. |
| D35 | The User Story Refiner takes stories one by one — id, title, description, existing acceptance criteria, and what each story touches — and selects ECCOLA cards per story. | One text box split every line into a story, so a pasted story with its criteria became several stories, and one capability answer for the whole sprint gave every story the same cards. |
| D36 | Existing acceptance criteria stay the team's: the agent adds new ethical criteria and may flag an existing one only when it conflicts; code turns each conflict into a decision for the product owner, with the suggested rewrite as an option. | Rewriting a team's criteria silently would take a product decision out of human hands; ignoring conflicts would let an unethical criterion ship. |
| D37 | A value over its length limit is shortened by code and reported, never a reason to discard the reply. | Limits exist for readability; losing a complete analysis over a few characters costs the reviewer far more than a trimmed sentence, and the warning keeps the trim visible. |

---

## 3. Changelog

Entries are added as work lands. Each names the finding IDs it closes.

<!-- CHANGELOG:START -->
### 2026-09-25 — A reply a few characters too long is shortened, not discarded (branch `agent-output-revamp`)

Decision D37.

#### What was wrong

- **TST-9** A real Risk Classifier run failed the output contract because the
  headline was over its 160-character limit, and the retry was over it again.
  The whole analysis was replaced by the fallback record: no findings, no
  actions, every coverage and obligation check failed.

#### What changed

- `raia/contract/assemble.py` — `parse_record` shortens values over their
  `maxLength` (at a sentence end, else a word end with an ellipsis) and keeps
  the first entries of over-long lists, then validates again; only other errors
  go to repair. Each change is kept in the record's `shortened` list and
  becomes a `SHORTENED:` contract note.
- `raia/contract/checks.py` — a *Length limits* warning lists what was
  shortened.
- `raia/contract/schema.py` — the headline limit is 200 characters, and its
  description asks for one sentence of at most 25 words.

#### Tests

- `tests/test_contract.py` — a reply whose only fault is length is accepted
  without a repair, every value ends inside its limit, each shortening is
  recorded and reported as a warning, and a reply with another error still goes
  to repair with only that error.

### 2026-09-24 — Agent outputs a person can act on, and stories entered one by one (branch `agent-output-revamp`)

Decisions D33–D36.

#### What was wrong

- **TST-7** Every agent's draft was a wall of text: a metadata header, a
  verdict table, ten-column findings and action tables, then coverage and a
  visible machine block, all expanded. What to do came after the analysis,
  and the prose explained frameworks and law the reader did not ask about.
- **TST-8** The User Story Refiner took the backlog as one text box and split
  it line by line, so a story pasted with its description and acceptance
  criteria became several stories. Existing criteria could not be told apart
  from the story, and one capability answer applied to the whole sprint.

#### What changed

- `raia/contract/digest.py` (new) — the reading order of every record, as
  data: status, headline, four figures, main issues, risk areas; actions
  grouped by computed priority with owner, when and "done when"; decisions;
  deep-dive sections, each with a computed conclusion; the traceability
  appendix; paste-ready stories for the Story Refiner.
- `raia/contract/render.py` — the Markdown is written from the digest in the
  same order: Summary, Action Plan, Open Issues, then Findings, the agent's
  sections and the appendix (new section: Verdict Reconciliation). All
  identifiers, citations, open issues and the machine block are kept, so every
  existing check still reads the document.
- `raia/ui/record_view.py` (new), `raia/ui/theme.css` — the three tiers on
  screen: status banner, figure cards, main issues, colour-coded action and
  decision cards with an owner filter, and the deep dive behind a dropdown
  with one tab per section. Used for the draft at the gate (and its edited
  preview), the approved version on the stage page and the project documents.
- `raia/contract/schema.py`, `vocab.py`, `prompt.py`, `agents/base.py` —
  `raia-record/1.1`: `headline` (required of the model, optional on read),
  shorter caps, a work-tool writing rule; `sprint_ethics_log` is a list (an
  older paragraph reads as one entry); `stories[].conflicts`.
- `raia/contract/assemble.py` — one `value_tradeoff` decision per flagged
  conflict; issues raised by the engine or by code are recomputed on every
  finalisation, so one a reviewer's edit resolved does not linger.
- `raia/fields.py`, `raia/rationale/story_map.py`,
  `raia/agents/story_refiner.py`, `raia/ui/gate.py`, `raia/examples.py` — a
  `stories` field kind: one card per story with add, duplicate, remove and
  "paste several at once"; a backlog parser that keeps criteria with their
  story; stable story ids and `<story>-E<n>` ids for existing criteria; card
  selection per story; answers saved as one text box are converted on load,
  with the sprint's old capability answer applied to each story.
- `raia/ui/gate.py` — an untouched draft is not re-validated against the
  schema, so a draft written under 1.0 stays approvable after the upgrade.
- Guide, `docs/TESTERS.md`, agent cards, `docs/schema/` and
  `docs/output-contract.md` regenerated or updated.

#### Tests

- `tests/test_contract.py` — the figures are the record's counts, every action
  appears once and in the group of its priority, a blocking finding leads the
  main issues, every deep-dive section has a conclusion, the document follows
  the screen's order, a record without a headline still reads and validates;
  a conflict opens exactly one decision, is not duplicated on re-finalising and
  disappears when a reviewer removes it; the paste-ready stories mark it.
- `tests/test_engines.py` — pasted criteria stay with their story, the team's
  ids are kept, duplicate ids are replaced, cards are selected per story,
  existing criteria are registered, a story without its capabilities is
  reported.
- `tests/test_ui.py` — the draft reads summary first then what to do, the deep
  dive is present; the demo project's stories open as cards; a story card can
  be added and removed.

#### Still open, by decision

- Conclusions are computed or lifted from the first sentence of a field; no
  second model call summarises the analysis.
- The record editor at the gate is unchanged apart from the headline; stories
  are still edited there through the extension JSON.

### 2026-09-24 — Recommend ethical requirements (branch `recommend-requirements`)

Decisions D30–D32.

#### What was wrong

- **TST-6** The Requirements Reviewer opened on a blank form with required
  questions the approved risk classification could already inform (who is
  affected, which principles are at stake). Testers without a written
  requirements list had nowhere to start.

#### What changed

- `raia/rationale/coverage.py` — `suggest_intake` proposes stakeholder groups
  and principles at stake from the approved classification's structured data
  (areas, data categories, autonomy, oversight, transparency triggers,
  obligations), with a reason per value; principles are proposed on specific
  facts, not all seven for any high-risk system. `relevant_controls` lists the
  controls the assigned obligations make relevant. `next_requirement` appends
  an adopted requirement in the team's own format with the id the parser will
  give it. `read_origin` compares what was suggested or adopted with the
  answers at run time; `run` now marks cells covered only by an adopted
  recommendation as *addressed by an adopted suggestion* and reports adopted
  requirements and pre-filled answers as findings.
- `raia/agents/requirements_reviewer.py` — `recommend()` computes the gaps the
  current answers leave (as a run would), retrieves from the agent's grounding
  sources, asks the model for at most five candidates and checks each in code:
  it must address a computed gap once, cite an excerpt retrieved for it and
  have a testable fit criterion, or it is dropped with the reason shown.
- `raia/agents/base.py` — `AgentSpec.suggest` hook; a draft's provenance
  carries `intake_origin`.
- `raia/validators.py` — `is_verifiable` and `resolve_citations`, shared by
  the requirement-quality check and the candidate check.
- `raia/projects.py` — `suggest_intake`, `recommend_requirements` (counts one
  run against the daily allowance) and `record_recommendation_decision`; events
  `intake_suggested`, `requirements_recommended`, `recommendation_adopted`,
  `recommendation_rejected`, pseudonymized on export like every event.
- `raia/ui/gate.py`, `views/stage.py` — a **Recommend ethical requirements**
  button; captions under pre-filled fields with the reason per value; the
  controls question annotated, never answered; a candidate panel with Adopt /
  Reject and editable text; a confirmation before running when pre-filled
  answers are unchanged.
- `raia/contract/render.py` — the Gap Analysis section states, computed, which
  inputs RAIA proposed and a person adopted.
- `raia/contract/mock.py` — mock candidates, so the flow runs offline.
- Guide, `docs/TESTERS.md` and the Requirements Reviewer agent card
  regenerated.

#### Tests

- `tests/test_engines.py` — only context questions are ever suggested, every
  value has a reason, a low-stakes tool gets no principle suggestion, adopted
  requirements get the next id and parse back, an adopted requirement closes a
  gap but is marked as such, edited and deleted adoptions are reported
  correctly, an origin record cannot mark controls as suggested, and the
  candidate check drops invented gaps, duplicates, unresolved citations and
  untestable fit criteria.
- `tests/test_ui.py` — section 5b: an answer the team gave is left alone, the
  controls are never ticked, nothing is added before adoption, adoption adds
  the next id, running is refused until pre-filled answers are confirmed, and
  the approved record, provenance and activity log all show what RAIA proposed.

#### Still open, by decision

- The suggestion rules and the candidate check are lexical and transparent, by
  design; whether candidates are *good* is for the panel to judge.
- Only the Requirements Reviewer recommends. The hook is generic; other agents
  can adopt it after the panel.

### 2026-09-23 — A Guide page for testers (branch `tester-feedback`)

Decision D29.

- **TST-5** Nothing in the app explained how to use it or its agents. The tester
  guide existed only as `docs/TESTERS.md`, in a repository testers never open.
- `raia/ui/guide.py` holds the guide: the menu, ten numbered steps (create a
  project; answer the Risk Classifier's questions; run and read the draft;
  approve or reject; continue through the stages; revise and re-check; use the
  results; work with a colleague; the assessment; your data and signing out),
  what each agent asks and needs approved first (built from the agent specs),
  the stage statuses, what to look for, what to try to break, what feedback
  helps, and what to do if something goes wrong.
- `views/guide.py` lays it out; `app.py` lists **Guide** second in the top
  menu; Home points newcomers to it until their first approval, and the pointer
  can be hidden.
- `docs/TESTERS.md` is now generated by `python -m raia.ui.guide`.
- `tests/test_ui.py` — the page renders every step and agent, has no emoji,
  `docs/TESTERS.md` matches the generator, and the Home pointer shows and hides.

### 2026-09-23 — The Risk Classifier asks what it needs to know (branch `tester-feedback`)

Decision D28.

#### What was wrong

- **TST-3** The first group of the Risk Classifier form was three free-text
  boxes — product brief, intended use, target users — each with a one-line
  tip. Every other group is a structured question the rule engine reads, so
  this was the one place a tester had to guess what to write and how much.
- **TST-4** Nothing asked how the AI works. That decides two things the screen
  was blind to: whether the product is an AI system at all (both regimes
  define one by its capacity to infer; rules written only by people may fall
  outside), and whether the transparency duties apply (a generative product
  whose transparency answer was *None* was screened as minimal risk).

#### What changed

- `raia/agents/risk_classifier.py` — *The product* now asks *What is the
  product?*, *What does the AI produce or decide?* (new), *Where, how and by
  whom will it be used?*, *Who uses it, and who is affected by its outputs?* and
  *What should it not be used for?* (new, optional), each with an example
  answer. A new group, *How the AI works*, asks the techniques used, where in
  the product the AI acts, and where the model comes from. Existing keys are
  kept, so saved answers and approved projects are unaffected.
- `raia/rationale/risk_screen.py` — reads the new answers: a rules-only product
  raises an open issue, pins both definitions and adds the `ai_scope` checklist
  item, while the tiers are computed as if it were in scope; generative output
  or direct interaction adds the matching transparency triggers when they were
  not selected, and says so; three inconsistencies are escalated (no trained
  model but a learning technique; general-purpose model provider but a third
  party's model used as-is; a deciding AI with a human-review autonomy answer).
  An intake saved before these questions existed screens exactly as before.
- `corpus/eu_ai_act.md`, `corpus/pl_2338_2023.md` — the scope sections now
  state each instrument's definition of an AI system, so the new issue is
  grounded in a retrievable, pinnable excerpt. The normative index rebuilds
  itself because the corpus version changed.
- `raia/pipeline.py` — the approved product brief carries the *How the AI
  works* answers, so later stages read them.
- The example scenario, the agent documentation (`raia/ui/agent_docs.py`,
  regenerated agent cards) and the README describe the new questions.

#### Tests

- `tests/test_engines.py` — rules-only flagged but not taken out of scope;
  implied triggers applied once and escalated; each inconsistency questioned;
  a legacy intake screens as before.
- `tests/test_ui.py` — the form shows the new questions and the approved brief
  carries the new answers.

#### Still open

- The two definition paragraphs are curated summaries like the rest of the
  corpus; check them against the official texts before the panel.

### 2026-09-23 — Sign out from the Account menu (branch `tester-feedback`)

Decision D27.

- **TST-2** Signing out meant opening Settings and scrolling to a *Session*
  section; the Account menu only listed Settings and Privacy & terms.
- `views/signout.py` clears the session and hands over to the identity
  provider's logout. `app.py` lists it as the last entry of the Account menu
  when sign-in is on; `raia/ui/routes.py` documents the route. The button in
  Settings is gone; the agreement page keeps its own, since it has no menu.
- `tests/test_ui.py` section 11 signs in as a Google identity (the auth layer
  is substituted in the test), checks the menu lists Sign out, opens it and
  checks the session is cleared and the provider logout called; section 10
  checks Settings no longer carries the button and developer mode lists none.

### 2026-09-23 — Pages redraw without a wait (branch `tester-feedback`)

Decision D26.

#### What was wrong

- **TST-1** Changing any answer on a stage page left the page blank or faded for
  seconds. Every change re-runs the page, and one re-run of a stage page issued
  26 SQL statements in 24 transactions. On PostgreSQL each of those cost about
  four network round trips — a liveness probe on checkout, BEGIN, the statement,
  COMMIT — so roughly a hundred round trips per changed answer. The causes:
  every file read was its own query (a stage's status checks each
  prerequisite, so the same files were read over and over); the same membership
  was looked up five times per run; the account was re-created (`sign_in`, a
  write) on every click; the graph thread was looked up twice; and the project
  page zipped the whole project, re-verifying the hash chain, on every redraw,
  twice.

#### What changed

- `raia/db.py` — a lone statement runs on an autocommit connection without
  BEGIN/COMMIT (it is already atomic); a pooled connection is probed only if it
  sat idle for more than 30 seconds, and idle connections are closed after four
  minutes, below the point where a managed database suspends. `Database.stats`
  counts statements and explicit transactions.
- `raia/storage.py` — `DatabaseRepository` reads the current version of every
  file, and every pending draft, in one query per repository object. A write to
  the project anywhere in the process invalidates the snapshot; history,
  chain verification and events are not cached.
- `raia/projects.py` — `ProjectService.request_scope()` remembers membership
  answers for one page run; methods that change projects or memberships run
  without the memo and drop it. `app.py` wraps each run in it.
- `app.py` — the account is created or refreshed once per browser session; later
  runs re-read it with one query (an accepted agreement or a deleted account is
  still seen on the next click). `RAIA_PROFILE=1` logs each run's duration and
  round trips.
- `raia/ui/gate.py` — the intake fields are a fragment: changing an answer
  redraws the form and saves it, not the whole page.
- `views/project.py`, `views/settings.py` — downloads are built when the button
  is pressed.

Measured on the demo project with the database backend, statements per redraw:
stage page 26 → 8, project page 62 → 14, Home 22 → 8, none of them in an
explicit transaction.

#### Tests

- `tests/test_ui.py` section 3b holds the stage, project and Home pages to a
  round-trip budget on each backend.
- The suite passes on the Git backend, the database backend on SQLite, and on
  PostgreSQL 16 (`tests/test_projects.py`, `tests/test_ui.py`).

#### Still open

- The graph checkpointer's own queries (one lookup per stage page on
  PostgreSQL) are not counted by `Database.stats`.
- Neon's scale-to-zero still makes the first request after an idle period slow;
  that is a hosting setting, not code.

### 2026-09-23 — A cut-off reply no longer wastes a stage (branch `contract-token-budget`)

#### What was wrong

- **OUT-7** Found on a live run of the Risk Classifier with a real model, on a
  high-risk employment product: the reply was cut off at the token limit part
  way through the fourth finding, so the record could not be parsed and the
  stage showed a fallback record. The agent had produced good analysis and all
  of it was thrown away. Three consequences followed from that single cause —
  no findings, no declared coverage, and no obligation notes — and the check
  text blamed "the RAIA record schema" and claimed a repair attempt that never
  happened, because truncation was explicitly excluded from the repair loop.
  The root cause was a budget too small for a record with fifteen obligation
  notes and several findings, and nothing in the contract bounded the length of
  what the model wrote.

#### What changed

- Truncation is now the one condition worth retrying: the reply comes back with
  a larger budget (`RAIA_LLM_MAX_TOKENS_CEILING`, default 32000) and an
  instruction to send the whole record compactly. The truncated text is not
  resent, only noted, so the retry is not paid for twice.
- `RAIA_LLM_MAX_TOKENS` default raised from 8192 to 16384;
  `llm.get_chat_model` and `invoke_chat` take a per-call budget, so a retry can
  have more room without changing what the rest of the session reports.
- Every free-text field in the record now has a `maxLength`, and the contract
  asks for at most three sentences per field, one or two per obligation note,
  and for obligations met by the same work to be grouped. A record that does
  not fit one reply is a record nobody reads at the gate either.
- The fallback record and the contract check now say whether the reply was cut
  off or malformed, name the limit it hit and the number of retries that really
  ran, and point at the setting to change. Provenance records the budget the
  approved draft was written with.

#### Tests

- `tests/smoke_test.py` — section 17b reproduces the live failure (a reply
  halved and marked `max_tokens`): the retry gets a larger budget, the record
  comes back complete, and provenance records the budget. A reply that keeps
  being cut off yields a fallback record that says so.

#### Still open

- The live quality of the analyses is still unmeasured beyond this one run; the
  consistency script needs a real provider to mean anything.
### 2026-09-17 — One standard record for every agent, on branch `output-contract`

Decisions D21–D25. New finding prefix **OUT-** (output consistency).

#### What was wrong

- **OUT-1** Inside the required headings everything was free prose. Nothing
  said what a recommendation must contain, so owners, deadlines and
  verification appeared in one run and not the next, and two projects could not
  be compared.
- **OUT-2** Each agent used its own vocabulary for the same things
  (*Recommendations for the Team*, *Recommended Actions*, *Upcoming Ethical
  Checkpoints*), with no shared fields for risk, response, owner or priority.
- **OUT-3** How serious a finding was depended on the model's tone everywhere
  except the Drift Monitor.
- **OUT-4** Structure was recovered from prose with regular expressions (the
  machine block, acceptance-criterion ids, open-issue bullets), which is where
  run-to-run drift entered the blackboard.
- **OUT-5** Open issues were plain strings: no type, no deciding role, no
  blocking flag.
- **OUT-6** A reviewer's edit at the gate was free text, so an approved artifact
  could leave any structure the draft had.

#### What changed

- `raia/contract/` — the RAIA record (`raia-record/1.0`): closed vocabularies
  from the normative sources (`vocab.py`), the likelihood × magnitude matrix and
  priority floors (`rubric.py`), one schema per agent (`schema.py`), the
  contract as shown to the model (`prompt.py`), parse → bounded repair →
  finalise → fallback (`assemble.py`), the one rendered layout (`render.py`),
  record checks (`checks.py`), the project action plan (`actions.py`), and
  generators for `docs/schema/` and `docs/agents/`.
- Agent extensions follow their sources: legal screens, tier justifications,
  obligation notes, oversight, rights and impact assessments (EU AI Act,
  PL 2338/2023); context of use, direct and indirect stakeholders, value
  register, gap analysis, ethical value requirements with fit criteria and
  verification method, and an impact assessment (IEEE 7000, Microsoft RAI
  Standard v2 A1); ECCOLA cards with their discussion, acceptance criteria in
  the verifiable-requirement pattern, and a sprint ethics log; audit items,
  accountability log and checkpoints (Microsoft RAI Standard v2 accountability,
  NIST AI RMF GOVERN); alerts, representativeness, sample adequacy and a
  response plan with deactivation criteria and community feedback (NIST AI RMF
  MEASURE and MANAGE).
- Rule engines raise typed issues (`RationaleResult.raise_issue`); code carries
  them into every record, opens an issue for every declared disagreement and
  every accepted risk, restores an upgraded audit verdict or a restated drift
  severity and reports it, and raises the overall status where required.
- `raia/agents/base.py` — the turn now parses and repairs the record
  (`RAIA_CONTRACT_REPAIRS`, default 1), finalises and renders it, and runs the
  record checks beside the existing validators. The sidecar carries the whole
  approved record; downstream engines read requirement wording and criteria
  from it instead of from prose.
- `raia/pipeline.py` — approval accepts an edited record, re-finalises,
  re-renders and re-validates it; free-text edits are refused. Typed issues
  reach the register.
- Gate: a structured record editor replaces the Markdown text box. Project
  page: an **Action plan** tab with priority/owner/stage filters and CSV/JSON
  export; typed issues shown with their deciding role and blocking flag. The
  project download includes the action plan.
- The mock model builds a conforming record from machine-readable contract
  hints, exercising every field offline.
- Docs: `docs/output-contract.md` (the standard), `docs/agents/*.md` (generated
  agent cards), `docs/schema/*.schema.json`, `docs/templates/` (agent card,
  project-log entry); README, architecture and tester guide updated.

#### Tests

- `tests/test_contract.py` — vocabularies occur in the corpus; the matrix is
  monotonic and the floors apply; parsing, repair prompt and fallback;
  finalisation (ids, priorities, carried and code-opened issues, evidence
  discipline, status floor, idempotence); the layout and the model-facing
  schema; published schemas and agent cards are current; the action plan.
- `tests/smoke_test.py` — every approved artifact carries a record and follows
  the layout; the register is typed; the action plan and export; a free-text
  edit is refused and a field edit recomputes priority; an invalid reply is
  repaired, and one that stays invalid yields a fallback record with a failed
  check.
- `tests/test_ui.py` — the gate shows the record editor and the standard
  layout; the project page has the action plan and its export.
- `tests/consistency_check.py` — run-to-run agreement of records. With the mock
  model it is 1.0 by construction; it is meant for a live run.

#### Still open, by decision

- Not merged or pushed (D25). A live run with a real API key is needed to see
  whether the model fills the record well and to measure consistency.
- The magnitude and likelihood levels, the matrix and the floors are the
  project's operationalisation; they are documented as such and should be
  reviewed by the panel.
### 2026-09-17 — Models that reject a temperature

- **DEP-T1** A live run on a newer model failed with `400 invalid_request_error:
  temperature is deprecated for this model`. RAIA always sent `temperature=0.2`.
- `RAIA_LLM_TEMPERATURE` now accepts `none` (or empty) to omit the parameter.
- `raia.llm.invoke_chat` recognises a temperature rejection, retries once without
  it, and stops sending it for the rest of the process; provenance then records
  `temperature: null`, so artifacts state what was actually sent.
- Default model id updated to `claude-sonnet-5`.
- Test: `tests/test_engines.py` (models that reject a temperature).

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
