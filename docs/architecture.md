# RAIA — Architecture & UML Diagrams

This document describes the structure of the RAIA proof of concept and maps
it back to the paper *"RAIA: A Multi-Agent Architecture to Operationalize
Responsible AI across the Software Development Life Cycle"*. All diagrams
are in Mermaid and render natively on GitHub.

## 1. Component Diagram (system overview)

Five agents in three layers communicate **exclusively** through the
Git-versioned shared artifact repository (blackboard). Every agent output
passes a mandatory human checkpoint (H) before persistence.

```mermaid
flowchart TB
    subgraph UI["Streamlit UI (app.py)"]
        FORM["Stage input forms"]
        REVIEW["Human review widget<br/>(approve / edit / reject)"]
        TRAIL["Audit trail viewer"]
    end

    subgraph PIPE["LangGraph Pipeline (raia/pipeline.py)"]
        GEN["generate node"]
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
    GEN --> AGENTS
    AGENTS --> RAG
    RAG --> CHROMA
    CORPUS -- "ingest.py" --> CHROMA
    AGENTS --> LLM
    AGENTS -- "read upstream artifacts" --> REPO
    PERS -- "git commit (after approval only)" --> REPO
```

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
        +list_projects() List~str~
    }

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
        UI-->>Human: artifact committed; downstream gate opens
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

## 5. Design Decisions (traceability to the paper)

| Paper element | Implementation |
|---|---|
| Five agents, three layers (Table 2) | `raia/agents/` — one module per agent; `AGENTS` registry in pipeline order |
| Blackboard shared state, Git-versioned (§3.3) | `raia/repository.py` — every approval = one local Git commit; approval provenance stamped in the artifact header |
| Mandatory human checkpoints "H" (§3.4a) | LangGraph `interrupt()` in the `human_review` node; persistence unreachable without an approve decision |
| Grounded recommendations via RAG (§3.4b) | `raia/rag.py` — Chroma; every chunk carries source/section/authority metadata; agents must cite excerpt tags |
| Conflict precedence legal > standard > advisory (§3.4c) | Authority levels in `config.AUTHORITY_LEVELS`, enforced in the shared system preamble; same-level conflicts routed to "Open Issues" |
| Data protection (§3.4d) | Artifacts stay in local `workspace/`; nothing leaves the machine except LLM API calls; no retraining |
| Provider-agnostic LLM (§3.3) | `raia/llm.py` factory — Claude default, OpenAI or mock via one env var |
| Anti-ethics-washing Auditor (§5) | Auditor prompt forbids "satisfied" verdicts without quoted evidence from versioned artifacts |
| Hallucination-free metrics (Ops) | Drift Monitor computes fairness numbers with pandas; the LLM only interprets |

**Not yet implemented** (future work tracked in the README): Jira/Confluence
MCP connectors, and the input-sanitization / least-privilege hardening noted
in §3.4e beyond prompt-level instructions.
