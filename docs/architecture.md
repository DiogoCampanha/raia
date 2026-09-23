# RAIA — Architecture & UML Diagrams

This document describes the structure of the RAIA proof of concept and maps
it back to the RAIA architecture as specified in the master's research
project it implements. All diagrams are in Mermaid and render natively on
GitHub.

## 1. Component Diagram (system overview)

Five agents in three layers communicate **exclusively** through the
Git-versioned shared artifact repository (blackboard). Every agent output
passes a mandatory human checkpoint (H) before persistence.

```mermaid
flowchart TB
    subgraph UI["Streamlit UI (app.py)"]
        FORM["Structured intake forms<br/>(raia/fields.py)"]
        REVIEW["Human approval gate<br/>draft · evidence · rationale · checks"]
        ISSUES["Open Issues register"]
        TRAIL["Audit trail + provenance"]
    end

    subgraph PIPE["LangGraph Pipeline (raia/pipeline.py)"]
        GEN["generate node<br/>(intake → rules → model → checks)"]
        HUM{{"human_review node<br/>interrupt() = H gate"}}
        PERS["persist node"]
        GEN --> HUM
        HUM -- approve --> PERS
        HUM -- reject + feedback --> GEN
    end

    subgraph AGENTS["Agents (raia/agents/)"]
        subgraph PROD["🟦 Product layer"]
            RC["Risk Classifier"]
            RR["Requirements Reviewer"]
        end
        subgraph DEV["🟩 Dev layer"]
            SR["User Story Refiner"]
            AU["Auditor"]
        end
        subgraph OPS["🟧 Ops layer"]
            DM["Drift Monitor"]
        end
    end

    subgraph REASON["Deterministic reasoning (raia/rationale/, raia/validators.py)"]
        ENG["Rule engines<br/>risk_screen · coverage · story_map<br/>traceability · drift"]
        VAL["Validators<br/>citations · structure · coverage<br/>reconciliation · evidence discipline"]
    end

    subgraph KNOW["Knowledge layer"]
        RAG["NormativeRetriever<br/>(raia/rag.py)"]
        CHROMA[("Chroma vector store<br/>.chroma/")]
        CORPUS["Normative corpus (corpus/*.md)<br/>EU AI Act · PL 2338/2023 · IEEE 7000<br/>NIST AI RMF · MS RAI v2 · ECCOLA"]
    end

    subgraph STATE["Shared state (blackboard)"]
        REPO[("ArtifactRepository<br/>workspace/&lt;project&gt;/<br/>Git-versioned Markdown artifacts")]
    end

    LLM["LLM factory (raia/llm.py)<br/>Claude (default) · OpenAI · Mock"]

    FORM --> PIPE
    REVIEW <--> HUM
    TRAIL --> REPO
    ISSUES <--> REPO
    GEN --> AGENTS
    AGENTS -- "1. compute what is enumerable" --> ENG
    ENG -- "pinned sections + query facets" --> RAG
    AGENTS -- "3. check the result" --> VAL
    VAL --> REVIEW
    ENG --> REVIEW
    AGENTS --> RAG
    RAG --> CHROMA
    CORPUS -- "ingest.py" --> CHROMA
    AGENTS --> LLM
    AGENTS -- "read upstream artifacts" --> REPO
    PERS -- "git commit (after approval only)" --> REPO
```

## 1b. The Agent Turn (where the reasoning happens)

Every agent runs the same five-step turn. Steps 1, 2 and 4 are deterministic;
only step 3 calls a model, and step 5 is a person. This is the generalisation
of the one place in the earliest version where a claim was enforced by code
rather than requested in a prompt.

```mermaid
flowchart LR
    A["1 · Structured intake<br/><i>typed fields a rule reads</i>"] --> B
    B["2 · Rule engine<br/><i>verdict · tables · pins · checklist</i>"] --> C
    C["3 · Model pass<br/><i>justify · judge · fill the record</i>"] --> D
    D["4 · Contract + validators<br/><i>ids · priority · layout · checks</i>"] --> E
    E{{"5 · Human approval gate"}}
    E -- approve --> F[("Git commit:<br/>Markdown + JSON sidecar<br/>+ provenance")]
    E -- reject + reason code --> C
    B -. "conflicts" .-> G[["Open Issues register"]]
    D -. "disagreements" .-> G
    E -. "arbitration" .-> G
```

**The division of labour is the point.** Prohibition lists, high-risk area
lists, obligation tables, coverage matrices, traceability registers and metric
thresholds are enumerable, so they are computed. Whether a narrow-task
exemption really holds, whether a harm is significant, whether a lexical match
is real evidence — those are open-textured, so they are argued by the model and
settled by a person. Where the two disagree, neither wins silently: the
disagreement is recorded as an open issue.

**Every turn ends in the same record.** The model's reply is one JSON object
validated against the agent's schema (`raia/contract/`): a shared core —
summary, findings placed on likelihood and magnitude, actions, typed open
issues, declared coverage — and an extension shaped by the agent's normative
source. Code assigns the identifiers, computes risk level and priority,
carries the engine's issues forward, and renders the one layout every artifact
follows. A reviewer edits the record's fields at the gate, never its prose.
The standard is specified in `docs/output-contract.md`.

```mermaid
flowchart LR
    R["Model reply"] --> P{"validates against<br/>the agent's schema?"}
    P -- no --> RP["retry once<br/>errors, or more room<br/>if it was cut off"] --> P2{"validates?"}
    P2 -- no --> FB["fallback record<br/>raw reply shown · check fails"]
    P -- yes --> FIN
    P2 -- yes --> FIN["finalise<br/>ids · risk level · priority floors<br/>engine issues · disagreement · acceptance<br/>evidence discipline · status floor"]
    FB --> FIN
    FIN --> REN["render the standard layout<br/>+ machine block"] --> CHK["checks"] --> GATE{{"human gate<br/>edits fields → finalise again"}}
    GATE -- approve --> SIDE[("artifact + sidecar with the record<br/>typed issues → register<br/>actions → action plan")]
```

## 1b′. Interface: page map

The interface is a set of pages behind a top menu (`app.py` registers them with
`st.navigation`; the map is documented in `raia/ui/routes.py`).

```mermaid
flowchart LR
    PUB["/privacy<br/>public"]
    LOGIN["Sign in"] --> CONSENT["Accept agreement"] --> HOME
    subgraph MENU["Top menu"]
      HOME["/ Home<br/>attention list · projects"]
      AGENTS["/agents<br/>architecture · agent docs"]
      ASSESS["/assessment"]
      SET["/settings"]
    end
    HOME -->|"?id="| PROJECT["/project<br/>overview · documents · issues · activity · people"]
    PROJECT -->|"?project=&agent="| STAGE["/stage<br/>run · review gate · read · revise · re-confirm"]
    STAGE --> PROJECT
```

Project progress, including the *Needs review* flag, is derived on every load
by `raia/lineage.py` from the blackboard and the event log: an approved stage
needs review when a stage it depends on (through `upstream_keys`, transitively)
was approved after it was last approved or re-confirmed. Nothing is re-run.

## 1c. People, Projects and Storage

The blackboard belongs to a **project**, and a person reaches a project only
through a membership. Every project operation — reading, running an agent,
approving, arbitrating, inviting, exporting — goes through one authorization
check in `ProjectService`, below the UI.

```mermaid
flowchart LR
    ID["Google identity<br/>(st.login, OIDC)"] --> AUTH["raia/auth.py"]
    AUTH --> SVC["ProjectService<br/>(raia/projects.py)<br/>authorize(user, project, action)"]
    UI["app.py + views/<br/>(raia/ui)"] --> SVC
    SVC --> RUN["StageRunner<br/>(raia/pipeline.py)"]
    SVC --> OPENREPO["open_repository(project)<br/>(raia/storage.py)"]
    RUN --> OPENREPO
    OPENREPO -->|"RAIA_STORE=git"| GIT[("ArtifactRepository<br/>workspace/&lt;project&gt;/ — Git")]
    OPENREPO -->|"RAIA_STORE=database"| DBR[("DatabaseRepository<br/>append-only, hash-chained")]
    RUN --> CP[("Checkpointer<br/>PostgresSaver · MemorySaver")]
    SVC --> REG[("Registry tables<br/>users · projects · members<br/>invitations · ratings · usage")]
```

```mermaid
erDiagram
    USERS ||--o{ PROJECT_MEMBERS : "belongs via"
    PROJECTS ||--o{ PROJECT_MEMBERS : has
    PROJECTS ||--o{ INVITATIONS : "invites by email"
    PROJECTS ||--o{ PROJECT_COMMITS : "hash chain"
    PROJECT_COMMITS ||--|{ PROJECT_FILES : writes
    PROJECTS ||--o{ PENDING_REVIEWS : "drafts at the gate"
    PROJECTS ||--o{ INTAKE_DRAFTS : "form answers"
    PROJECTS ||--o{ PROJECT_EVENTS : "evaluation events"
    USERS ||--o{ EXPERIENCE_RATINGS : submits
```

| Role | View | Run agents, edit answers | Approve / reject, arbitrate | Invite, settings, delete |
|---|---|---|---|---|
| owner | ✓ | ✓ | ✓ | ✓ |
| editor | ✓ | ✓ | ✓ | |
| reviewer | ✓ | | ✓ | |

Three rules the tests enforce:

- **Stage is derived, never stored.** A project's progress is computed from
  its approved artifacts and pending drafts on every read.
- **Identity comes from the session.** The approver recorded at a gate is the
  signed-in person; any approver name in the caller's payload is overwritten.
  With *require a second approver* set, the person who ran a stage cannot
  approve it — including after a restore.
- **History is tamper-evident on both backends.** Git objects locally; in the
  database each version's digest covers its parent digest, its message, its
  timestamp and the SHA-256 of every file it wrote, and `verify_history()`
  recomputes all of them.

## 2. Class Diagram (code structure)

```mermaid
classDiagram
    class AgentSpec {
        +str key
        +str name
        +str layer
        +str sdlc_phase
        +List~str~ grounding_sources
        +List~str~ upstream_keys
        +List~str~ required_upstream
        +str output_key
        +List~InputField~ input_fields
        +str task_prompt
    }

    class InputField {
        +str key
        +str label
        +str help
        +str kind
    }

    class BaseAgent {
        +AgentSpec spec
        +missing_prerequisites(repo) List~str~
        +build_retrieval_query(inputs) str
        +run(repo, inputs, feedback) str
    }

    class RiskClassifierAgent
    class RequirementsReviewerAgent
    class UserStoryRefinerAgent
    class AuditorAgent
    class DriftMonitorAgent {
        +run(repo, inputs, feedback) str
        +compute_fairness_summary(csv) str
    }
    note for DriftMonitorAgent "Fairness metrics computed with pandas
    before the LLM call — the model interprets, never invents numbers"

    class ArtifactRepository {
        +str project
        +Path path
        +read_artifact(key) str
        +upstream_context(keys) str
        +save_artifact(key, content, approved_by) str
        +append_open_issue(issue, raised_by)
        +history(limit) List
        +reset()
        +list_projects() List~str~
    }
    note for ArtifactRepository "One instance == one project folder. The hosted
    evaluation deployment gives each browser session its own project, so a
    whole panel can test concurrently without sharing a blackboard"


    class NormativeRetriever {
        +retrieve(query, top_k, sources) List~NormChunk~
        +format_context(chunks) str
    }

    class NormChunk {
        +str text
        +str source
        +str authority
        +str section
        +citation() str
    }

    class StageRunner {
        -MemorySaver _checkpointer
        -CompiledGraph _graph
        +check_gate(project, agent_key) List~str~
        +start(project, agent_key, inputs) dict
        +resume(project, agent_key, decision) dict
    }

    BaseAgent <|-- RiskClassifierAgent
    BaseAgent <|-- RequirementsReviewerAgent
    BaseAgent <|-- UserStoryRefinerAgent
    BaseAgent <|-- AuditorAgent
    BaseAgent <|-- DriftMonitorAgent
    BaseAgent *-- AgentSpec
    AgentSpec *-- InputField
    BaseAgent ..> NormativeRetriever : retrieves norms
    BaseAgent ..> ArtifactRepository : reads upstream state
    NormativeRetriever ..> NormChunk : returns
    StageRunner ..> BaseAgent : runs via graph nodes
    StageRunner ..> ArtifactRepository : persists after approval
```

## 3. Sequence Diagram (one agent run with the human checkpoint)

```mermaid
sequenceDiagram
    actor Human
    participant UI as Streamlit UI
    participant SR as StageRunner (LangGraph)
    participant AG as Agent
    participant RAG as NormativeRetriever
    participant LLM as LLM (Claude)
    participant REPO as ArtifactRepository (Git)

    Human->>UI: fill stage inputs, click Run
    UI->>SR: start(project, agent_key, inputs)
    SR->>SR: check stage gate (required upstream artifacts)
    SR->>AG: generate node → run(repo, inputs)
    AG->>REPO: read upstream artifacts (blackboard)
    AG->>RAG: retrieve(query, sources=grounding)
    RAG-->>AG: norm excerpts + citations + authority levels
    AG->>LLM: system + task prompt + excerpts + upstream + inputs
    LLM-->>AG: draft (every claim cited)
    AG-->>SR: draft
    SR-->>UI: interrupt() — awaiting_review (H gate)
    UI-->>Human: show editable draft

    alt Human rejects
        Human->>UI: feedback
        UI->>SR: resume({action: reject, feedback})
        SR->>AG: regenerate with feedback
        AG-->>SR: new draft
        SR-->>UI: awaiting_review again
    else Human approves (possibly edited)
        Human->>UI: approve (name recorded)
        UI->>SR: resume({action: approve, content, approver})
        SR->>REPO: save_artifact() → git commit
        REPO-->>SR: commit hash
        SR-->>UI: approved + commit
        UI-->>Human: artifact committed, downstream gate opens
    end
```

## 4. Pipeline / State Diagram (SDLC-wide stage gates)

Agents never trigger each other; a stage only unlocks when the human has
approved the upstream artifact it requires.

```mermaid
stateDiagram-v2
    [*] --> ProductBrief : human writes brief
    ProductBrief --> RiskClassification : Risk Classifier + H
    RiskClassification --> RequirementsReview : Requirements Reviewer + H
    RequirementsReview --> RefinedStories : User Story Refiner + H
    RequirementsReview --> AuditReport : Auditor + H
    RiskClassification --> DriftReport : Drift Monitor + H (Ops adoptable early)
    RefinedStories --> AuditReport
    AuditReport --> [*]
    DriftReport --> [*]

    note right of RiskClassification
        Artifacts are Markdown files
        committed to Git on approval:
        02_risk_classification.md, ...
    end note
```

## 5. Design Decisions (traceability to the RAIA architecture)

| Architecture element | Implementation | Enforced by |
|---|---|---|
| Five agents, three layers | `raia/agents/` — one module per agent; `AGENTS` registry in pipeline order | structure |
| Blackboard per project, versioned | `raia/repository.py` (Git) and `raia/storage.py` (hash-chained database); every approval is one recorded version carrying the Markdown artifact *and* its JSON sidecar; approval provenance stamped in the header | code |
| Mandatory human checkpoints "H" | `interrupt()` in the `human_review` node; the persist node is unreachable without an approve decision, including on the restart-recovery path | code + smoke test |
| Agents never trigger agents | stage gates via `AgentSpec.required_upstream`; no agent-to-agent call exists | structure |
| Grounded recommendations | `raia/rag.py` — excerpts carry source, section, authority and a stable id; agents must cite them | prompt |
| Citations are real | `validators.check_citations` matches every tag against the excerpts actually retrieved for that run | code |
| The decisive excerpt is never missing | each decision procedure declares `Pin`s, fetched by exact metadata match and merged ahead of similarity results | code + smoke test |
| Decision procedures, not prompts | `raia/rationale/` — one rule engine per agent computes the verdict, the tables and the identifiers before any model call | code |
| Verdicts are reconciled, not averaged | `validators.check_reconciliation` requires the agent to declare agreement or disagreement; disagreement becomes an open issue | code |
| Conflict precedence legal > standard > advisory | `config.AUTHORITY_LEVELS`, reinforced by excerpt ordering in the prompt | prompt |
| Same-level conflicts escalated | `ArtifactRepository.append_open_issues` — a tracked register with statuses, populated from both the engine and the approved draft | code |
| Declared completeness | each engine emits a checklist; `validators.check_coverage` requires a status per key | code |
| Anti-ethics-washing audit | `rationale/traceability.py` assigns NOT VERIFIED where no evidence exists; `validators.check_forbidden_verdicts` prevents an upgrade | code |
| Metrics come from code | `rationale/drift.py` computes every figure; `validators.check_numbers` rejects any number not in the computed set | code |
| One standard output for every agent | `raia/contract/` — schema per agent (shared core + extension), closed vocabularies from the normative sources, code-computed identifiers, risk level and priority, one rendered layout, bounded repair and an honest fallback; published in `docs/schema/` and `docs/output-contract.md` | code + test_contract |
| Every identified risk is responded to | `contract.checks.check_responses` — every finding has an action or an open issue; accepting a risk opens an issue | code |
| Structured human editing | the gate edits record fields; persistence re-finalises, re-renders and re-validates what was approved; free-text edits are refused | code + smoke test |
| Project action plan | `contract.actions` — every action from every approved record, sorted by computed priority, exported as CSV/JSON | code |
| Reproducible audit trail | `raia/provenance.py` — model, temperature, corpus version, excerpt ids, prompt hash, attempt, edits, rejection history, check results | code |
| Data protection | projects are reachable only through a membership, checked in `ProjectService.authorize`; sign-in delegated to Google (no stored passwords); research exports pseudonymized with keyed participant codes; no retraining | code + test_projects |
| Accountable approval | the approver is the authenticated identity; optional second-approver rule makes the runner ineligible to approve | code + test_projects |
| Durable review state | `PostgresSaver` checkpointer and stored drafts; a restored review re-enters the gate | code + test_projects |
| Input sanitization | `raia/sanitize.py` — control characters, length caps, injection patterns in English and Portuguese; applied to form input *and* to the approved artifact | code |
| Provider-agnostic LLM | `raia/llm.py` factory and a single `invoke_chat` call site | structure |

**Not yet implemented** (tracked in the README roadmap): ingesting the official
legal texts with article-level citation metadata, Jira/Confluence MCP
connectors, and least-privilege tool-permission hardening.

**Known limitations, stated plainly.** The corpus is a set of curated summaries
prepared for this project, so a citation resolves to a section of a summary
rather than to the official wording; sources in `config.DERIVED_SOURCES` are
labelled as such in the prompt and at the approval gate. Injection detection is
regex-based and will not catch a careful paraphrase — the controls that carry
the weight are the approval gate and the citation validator, not the pattern
list. The lexical matchers in the coverage and traceability engines are
deliberately coarse and conservative: they produce candidate gaps and
conservative verdicts for a human to review, and are not evidence of absence.
