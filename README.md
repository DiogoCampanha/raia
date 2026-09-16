# RAIA — Responsible AI Assistant 🛡️

A multi-agent, LLM-based **software architecture** that operationalizes
Responsible AI across the software development life cycle, implemented as a
working proof of concept.

Five specialized agents, organized in three layers (Product / Dev / Ops),
communicate **exclusively** through a Git-versioned shared artifact repository
and are separated by **mandatory human approval gates**. Recommendations are
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
| **3 · Model pass** | Justifies, handles the open-textured judgement a rule table would get wrong, writes for humans. The computed block is ground truth: the model may argue with a verdict, never restate one. |
| **4 · Validators** | Citations resolve to excerpts actually retrieved; required sections present; response not truncated; checklist fully declared; engine-raised conflicts carried forward; verdict reconciled. |
| **5 · Human gate** | Draft, evidence, computed rationale and check results together. Nothing is persisted until a person approves. |

Where the rule engine and the model disagree, the disagreement is escalated to
the **Open Issues** register rather than averaged away.

## The Five Agents

| Agent | Layer | Decision procedure | Grounded in |
|---|---|---|---|
| **Risk Classifier** | 🟦 Product | Prohibited-practice screen, high-risk area match for both regimes, narrow-task exemption handling, role-dependent obligation assembly | EU AI Act, PL 2338/2023 |
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

### No API key? Try mock mode

Set `RAIA_LLM_PROVIDER=mock` in `.env`. The mock model reads the output
contract each agent declares and produces a conforming document, so the whole
chain — decision procedures, retrieval, validators, persistence, audit trail —
can be exercised offline. What it cannot produce is a real analysis, which is
why the app **refuses to serve mock output to an evaluator**: a tester who
could not tell canned text from a real classification would evaluate the wrong
artifact.

## Using RAIA

1. **Fill in the structured form.** The questions are the ones that decide the
   outcome — your role, target markets, purpose area, decision autonomy, data
   categories. Required fields are marked; the run is refused without them.
2. **Run the stage.** The rule engine computes its verdict, pins the excerpts
   its decision depends on, retrieves more by similarity, and the model writes
   the analysis.
3. **Review at the gate.** You get four tabs: the rendered draft, an editable
   copy, the evidence that was in the prompt, and everything the code computed.
   Above them, the result of the automated checks.
4. **Approve or reject.** Rejections carry a reason code and free-text
   feedback, both recorded. Approval commits the Markdown artifact, its
   structured sidecar and its provenance in one commit.
5. **Arbitrate the open issues.** Conflicts land in a register with a status
   you set: resolved, or accepted risk, with a note and your name.
6. **Export the session** before you finish — artifacts, structured records,
   commit history and feedback in one zip.

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
- **(d) Data protection** — project artifacts stay in `workspace/`
  (git-ignored); nothing is used to retrain models.
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
- **(i) Transient-failure retry** — provider overloads and rate limits are
  retried with backoff; nothing else is, because retrying a bad request only
  spends budget.

## Project Structure

```
raia/
├── app.py                     # Streamlit UI — structured forms, evidence at the
│                              #   gate, open-issues register, audit trail
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
│   ├── validators.py          # citations, structure, coverage, reconciliation
│   ├── provenance.py          # the run record stamped into every artifact
│   ├── repository.py          # Git blackboard: artifacts, sidecars, open issues
│   ├── pipeline.py            # the graph: generate → human gate → persist
│   ├── sanitize.py            # injection screening (EN + PT), flag-never-delete
│   ├── export.py              # one-zip session export
│   └── agents/                # the five agent specifications
├── corpus/                    # curated normative summaries (extensible)
├── docs/
│   ├── architecture.md        # diagrams and the traceability table
│   ├── PROJECT_LOG.md         # what was wrong, what was decided, what changed
│   └── TESTERS.md             # guided walkthrough for the evaluation panel
└── tests/
    ├── smoke_test.py          # offline end-to-end, including the invariants
    └── test_engines.py        # deterministic unit checks
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
| `RAIA_LLM_MODEL` | `claude-sonnet-4-5` | |
| `RAIA_LLM_TEMPERATURE` | `0.2` | low for reproducibility |
| `RAIA_LLM_MAX_TOKENS` | `8192` | truncation is detected, not tolerated |
| `RAIA_LLM_RETRIES` | `2` | transient provider failures only |
| `RAIA_RAG_TOP_K` | `12` | plus the excerpts each procedure pins |
| `RAIA_RAG_CHUNK_SIZE` / `_OVERLAP` | `1800` / `200` | chars, at ingestion |
| `RAIA_MIN_GROUP_SAMPLES` | `30` | below this, a group figure is indicative only |
| `RAIA_DEFAULT_PARITY_THRESHOLD` | `0.1` | used only when no approved artifact sets one |
| `RAIA_WORKSPACE_DIR` | `./workspace` | per-project git blackboards (git-ignored) |
| `RAIA_CORPUS_DIR` / `RAIA_CHROMA_DIR` | `./corpus` / `./.chroma` | |
| `RAIA_FAKE_EMBED` | `0` | `1` = hash embeddings for CI / offline |

## Hosted Deployment for Testers (Streamlit Community Cloud)

Self-bootstrapping: platform secrets are bridged into configuration, the RAG
index builds itself on first start, a modern sqlite is shimmed in, and every
browser session gets its own private, disposable workspace so concurrent
testers never collide.

Deploy from GitHub with `app.py` as the entry point, and set one secret:

```toml
ANTHROPIC_API_KEY = "sk-..."
```

Optional overrides: `RAIA_LLM_MODEL`, `RAIA_LLM_PROVIDER`.

⚠️ The hosted filesystem is ephemeral — workspaces reset on redeploy, which is
fine for evaluation sessions. Testers should use **Export this session** before
they finish. If the app restarts while a draft is under review, the draft is
recovered from disk and the review re-enters the approval gate; nothing is ever
persisted without an approval.

## Testing

```bash
RAIA_LLM_PROVIDER=mock RAIA_FAKE_EMBED=1 python tests/smoke_test.py
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
- [ ] Ingest the official legal texts with article-level citation metadata
- [ ] Jira / Confluence integration via MCP connectors
- [ ] Least-privilege tool-permission hardening
- [ ] Expert-panel evaluation (Design Science Research)
- [ ] Case studies in real development environments

## Citation & License

MIT. See `docs/architecture.md` for diagrams and the traceability table between
the architecture and the code, and `docs/PROJECT_LOG.md` for the record of what
was wrong with earlier versions and what changed.
