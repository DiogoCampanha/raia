# RAIA — Responsible AI Assistant 🛡️

Proof-of-concept implementation of **RAIA**, a multi-agent, LLM-based
architecture that operationalizes Responsible AI (RAI) across the Software
Development Life Cycle, as proposed in the paper *"RAIA: A Multi-Agent
Architecture to Operationalize Responsible AI across the Software
Development Life Cycle"*.

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

1. **Create a project** in the sidebar. Each project gets its own local
   Git repository under `workspace/`.
2. **Run the Risk Classifier** with your product brief. Every agent page
   has a **Load example** button with the paper's resume-screening
   scenario, so you can explore the full pipeline in minutes.
3. **Review the draft** at the mandatory human checkpoint: edit it, approve
   it (your name is recorded in the audit trail), or reject it with
   feedback — the agent regenerates addressing your feedback.
4. **Move down the pipeline.** Stage gates keep the order honest: e.g. the
   Requirements Reviewer stays locked until a risk classification is
   approved. The Drift Monitor only needs the risk classification, so the
   Ops layer is adoptable early — mirroring the paper's incremental
   adoption design.
5. **Inspect the Audit Trail** page: every approval is a Git commit; every
   artifact records who approved it and when.

## How Reliability Is Handled (paper §3.4)

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
- **(e) Deterministic metrics** — the Drift Monitor computes fairness
  numbers (demographic parity difference, accuracy gaps) with pandas; the
  LLM interprets but never produces metric values.

## Project Structure

```
raia/
├── app.py                     # Streamlit UI (entry point)
├── ingest.py                  # Builds the Chroma normative index
├── requirements.txt
├── .env.example               # Configuration template
├── raia/
│   ├── config.py              # Env-driven settings; authority levels
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

## Testing

```bash
RAIA_LLM_PROVIDER=mock RAIA_FAKE_EMBED=1 python tests/smoke_test.py
```

Exercises ingestion, filtered retrieval with citations, stage gates, the
human-interrupt checkpoint, the rejection loop, Git persistence with
approval provenance, and the deterministic fairness metrics — fully
offline.

## Roadmap (from the paper)

- [ ] Jira / Confluence integration via MCP connectors
- [ ] Input sanitization and least-privilege hardening against prompt
      injection through project artifacts (§3.4e)
- [ ] Expert-panel evaluation (Design Science Research)
- [ ] Case studies in real development environments

## Citation & License

If you use this software in academic work, please cite the RAIA paper
(reference to be added after publication). Code released under the MIT
License.

> **Disclaimer**: RAIA is a research prototype. Its outputs are grounded
> recommendations, not legal advice. Humans decide; the corpus summaries
> must be verified against the official normative texts.
