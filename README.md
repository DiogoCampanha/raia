# RAIA — Responsible AI Assistant 🛡️

Proof-of-concept implementation of **RAIA**, a multi-agent, LLM-based
architecture that operationalizes Responsible AI (RAI) across the Software
Development Life Cycle. RAIA is the artifact of a master's research project
on Responsible AI (Mackenzie Presbyterian University), developed under the
Design Science Research method.

RAIA does not invent new RAI principles. It integrates the complementary
strengths of four consolidated frameworks — **IEEE 7000-2021**, **NIST AI
RMF 1.0**, **Microsoft Responsible AI Standard v2**, and **ECCOLA** — plus
two legal texts — the **EU AI Act** and the Brazilian bill **PL 2338/2023**
— into a single assistant embedded in the development workflow.

## The Five Agents

| Agent | Layer | SDLC phase | Normative grounding |
|---|---|---|---|
| **Risk Classifier** | 🟦 Product | Conception, value definition | EU AI Act risk tiers; PL 2338/2023 |
| **Requirements Reviewer** | 🟦 Product | Requirements definition | IEEE 7000 VBE; MS Impact Assessments |
| **User Story Refiner** | 🟩 Dev | Iterative development (sprints) | ECCOLA themes; MS RAI v2 verifiable requirements |
| **Auditor** | 🟩 Dev | Development, validation | MS RAI v2 accountability; NIST *Govern* |
| **Drift Monitor** | 🟧 Ops | Deployment, monitoring | NIST *Measure* / *Manage* |

Agents communicate **exclusively** through a Git-versioned shared artifact
repository (a blackboard), and **no agent output is ever persisted without
explicit human approval** — the "H" gates of the architecture. See
[`docs/architecture.md`](docs/architecture.md) for the full UML diagrams
(component, class, sequence, and state) and design-decision traceability.

## Quick Start

Requirements: Python ≥ 3.10, Git (optional but recommended — used to
version the artifact repository).

```bash
git clone https://github.com/DiogoCampanha/raia.git
cd raia
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 1. Configure the LLM
cp .env.example .env          # then put your ANTHROPIC_API_KEY in .env

# 2. Build the normative RAG index (first run downloads a small embedding model)
python ingest.py

# 3. Launch the UI
streamlit run app.py
```

### No API key? Try mock mode

Set `RAIA_LLM_PROVIDER=mock` in `.env` to explore the entire workflow
(stage gates, human checkpoints, Git audit trail) with canned agent
outputs and no network calls.

## Using RAIA

1. **Open the app.** A private workspace — its own local Git repository
   under `workspace/` — is created for your browser session automatically;
   there is nothing to name or configure. **Start over** in the sidebar
   erases it and begins a clean run.
2. **Run the Risk Classifier** with your product brief. Every agent page
   has a **Load example** button with a resume-screening example
   scenario, so you can explore the full pipeline in minutes.
3. **Review the draft** at the mandatory human checkpoint: read it
   rendered, edit it if needed, approve it (your name is recorded in the
   audit trail), or reject it with feedback — the agent regenerates
   addressing your feedback. If sanitization flagged anything suspicious
   in the inputs, a warning is attached to the top of the draft.
   After approving you return to the Overview, which shows the live
   pipeline (agent cards separated by the mandatory human gates) and the
   next suggested stage.
4. **Move down the pipeline.** Stage gates keep the order honest: e.g. the
   Requirements Reviewer stays locked until a risk classification is
   approved. The Drift Monitor only needs the risk classification, so the
   Ops layer is adoptable early — mirroring RAIA's incremental
   adoption design.
5. **Inspect the Audit Trail** page: every approval is a Git commit; every
   artifact records who approved it and when.

## How Reliability Is Handled

- **(a) Mandatory human checkpoints** — implemented with LangGraph's native
  `interrupt()`; the persistence node is unreachable without an explicit
  approve decision.
- **(b) Grounded recommendations** — agents answer via RAG over the
  normative corpus (Chroma); each retrieved excerpt carries its source,
  section, and authority level, and agents must attach these citation tags
  to every claim, making hallucinated obligations detectable at review time.
- **(c) Conflict handling** — recommendations carry a normative authority
  level (**legal > standard > advisory**); cross-level conflicts resolve by
  precedence, same-level conflicts are surfaced as explicit **Open Issues**
  for human arbitration, never resolved silently.
- **(d) Data protection** — all project artifacts stay on your machine in
  `workspace/` (git-ignored); nothing is used to retrain models.
- **(e) Input sanitization** — free-text inputs are cleaned (control
  characters, length caps) and screened for prompt-injection patterns
  (instruction overrides, role reassignment, spoofed citation tags) by
  `raia/sanitize.py`; findings are flagged, never silently removed, and
  appear as a warning attached to the draft at the review gate.
- **(f) Deterministic metrics** — the Drift Monitor computes fairness
  numbers (demographic parity difference, accuracy gaps) with pandas; the
  LLM interprets but never produces metric values.

## Project Structure

```
raia/
├── app.py                     # Streamlit UI (entry point)
├── ingest.py                  # Builds the Chroma normative index
├── requirements.txt
├── .env.example               # Configuration template (local runs)
├── raia/
│   ├── config.py              # Env-driven settings; authority levels
│   ├── deploy.py              # Streamlit-secrets bridge + readiness reporting
│   ├── llm.py                 # Provider-agnostic LLM factory (Claude default)
│   ├── rag.py                 # Chroma RAG: ingestion + cited retrieval
│   ├── repository.py          # Git-versioned artifact blackboard
│   ├── pipeline.py            # LangGraph graph with human-interrupt gates
│   └── agents/
│       ├── base.py            # AgentSpec + shared agent behavior
│       ├── risk_classifier.py
│       ├── requirements_reviewer.py
│       ├── story_refiner.py
│       ├── auditor.py
│       └── drift_monitor.py   # + deterministic fairness metrics
├── corpus/                    # Curated normative corpus (extensible)
│   ├── eu_ai_act.md           #   authority: legal
│   ├── pl_2338_2023.md        #   authority: legal
│   ├── ieee_7000.md           #   authority: standard
│   ├── ms_rai_v2.md           #   authority: standard
│   ├── nist_ai_rmf.md         #   authority: advisory
│   └── eccola.md              #   authority: advisory
├── docs/
│   └── architecture.md        # UML diagrams (Mermaid) + design decisions
└── tests/
    └── smoke_test.py          # Offline end-to-end test (mock LLM)
```

## Extending the Normative Corpus

The shipped corpus consists of **curated summaries** (IEEE 7000 is
paywalled; full legal texts are long). To upgrade grounding quality, drop
richer Markdown files into `corpus/` — e.g. the full EU AI Act text — and
re-run `python ingest.py`. Register new sources in
`raia/config.py::AUTHORITY_LEVELS` and `SOURCE_NAMES` so citations and the
precedence rule work correctly.

## Configuration Reference

| Variable | Default | Purpose |
|---|---|---|
| `RAIA_LLM_PROVIDER` | `anthropic` | `anthropic` \| `openai` \| `mock` |
| `RAIA_LLM_MODEL` | `claude-sonnet-4-5` | Model name for the provider |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | — | Provider credential |
| `RAIA_LLM_TEMPERATURE` | `0.2` | Low for reproducibility |
| `RAIA_RAG_TOP_K` | `6` | Excerpts retrieved per agent query |
| `RAIA_WORKSPACE_DIR` | `./workspace` | Where project blackboards live |

## Hosted Deployment for Testers (Streamlit Community Cloud)

**Testers need nothing at all — just the URL.** No install, no key, no
account, no project setup. The app bootstraps itself: it reads its
configuration from the platform's secrets, builds the RAG index on first
start, ships a modern sqlite for Chroma, and hands each browser session its
own private artifact repository so a whole panel can test concurrently
without seeing or overwriting each other's work.

### The only configuration step: one secret

The API key is set **entirely from the Streamlit UI** — no `.env` file, no
code change, no redeploy:

> **share.streamlit.io → your app → ⋮ → Settings → Secrets**, paste, **Save**.
> The app restarts on its own.

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
```

That single line is the whole setup. `raia/deploy.py` bridges it into the
process environment before configuration is read, and it accepts every shape
a maintainer might reasonably type — `anthropic_api_key`, `CLAUDE_API_KEY`,
a provider-neutral `LLM_API_KEY`, or a section:

```toml
[anthropic]
api_key = "sk-ant-..."
```

Surrounding quotes and stray whitespace from the paste are stripped. An
`OPENAI_API_KEY` on its own also works — the provider switches automatically.
Optional overrides, if you want them:

```toml
RAIA_LLM_MODEL    = "claude-sonnet-4-5"   # any Claude / GPT model id
RAIA_LLM_PROVIDER = "anthropic"           # or "openai", or "mock"
```

**RAIA never silently degrades to canned output.** If the key is missing or
malformed, the app shows a plain "not configured yet" screen with these
instructions instead of serving mock text a tester could mistake for a real
analysis. Mock mode exists, but only as an explicit choice
(`RAIA_LLM_PROVIDER = "mock"`), and it is labeled on every page.

### First-time deployment

1. Go to https://share.streamlit.io and sign in **with GitHub**.
2. **Create app** → *Deploy a public app from GitHub* → repository
   `DiogoCampanha/raia`, branch `main`, main file `app.py`.
3. Paste the `ANTHROPIC_API_KEY` line under **Advanced settings → Secrets**.
4. Deploy. The app gets a public URL and **redeploys automatically on every
   push to `main`**.

Share the URL together with [`docs/TESTERS.md`](docs/TESTERS.md), a
15-minute guided walkthrough for evaluation panels.

### Notes for hosted use

- Each browser session gets a private workspace, keyed by an id carried in
  the URL, so a refresh returns the tester to their own work. **Start over**
  in the sidebar erases it and begins a clean run.
- The container filesystem is ephemeral: workspaces and their Git audit
  trails reset on redeploy or restart. Fine for evaluation sessions, not for
  production use — testers should download any artifact they want to keep
  from the Audit Trail page.
- All testers share the maintainer's LLM key; keep an eye on API usage.

## Testing

```bash
RAIA_LLM_PROVIDER=mock RAIA_FAKE_EMBED=1 python tests/smoke_test.py
```

Exercises ingestion, filtered retrieval with citations, stage gates, the
human-interrupt checkpoint, the rejection loop, Git persistence with
approval provenance, and the deterministic fairness metrics — fully
offline.

## Roadmap (next developments)

- [ ] Jira / Confluence integration via MCP connectors
- [x] Input sanitization against prompt injection through project
      artifacts — `raia/sanitize.py`: control-char stripping, length
      caps, injection-pattern flagging surfaced at the review gate
- [ ] Least-privilege tool-permission hardening (continuation of the
      input-sanitization mechanism)
- [ ] Expert-panel evaluation (Design Science Research)
- [ ] Case studies in real development environments

## Citation & License

If you use this software in academic work, please cite the RAIA research
project (reference to be added after publication). Code released under the MIT
License.

> **Disclaimer**: RAIA is a research prototype. Its outputs are grounded
> recommendations, not legal advice. Humans decide; the corpus summaries
> must be verified against the official normative texts.
