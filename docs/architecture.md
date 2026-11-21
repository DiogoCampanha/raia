# RAIA — Architecture & UML Diagrams

This document describes the structure of the RAIA proof of concept and maps
it back to the RAIA architecture as specified in the master's research
project it implements. All diagrams are in Mermaid and render natively on
GitHub.

## 1. Component Diagram (system overview)

Four agents in two layers communicate **exclusively** through the shared
artifact repository (blackboard), versioned in Git locally and hash-chained in
the database on a hosted deployment. Every agent output passes a mandatory
human checkpoint (H) before persistence. Everything a person does reaches the
graph and the blackboard through one service layer that authorizes each
operation. The RAIA architecture also specifies an Ops layer (fairness-drift
monitoring after deployment); it is drawn dashed below because this build does
not implement it: it needs production telemetry that a team designing a product
rarely holds, and is future work.

```mermaid
flowchart TB
    subgraph UI["Streamlit UI (app.py, views/, raia/ui/)"]
        FORM["Structured intake forms<br/>(raia/fields.py)"]
        REVIEW["Human approval gate<br/>draft · edit the record · evidence · computed"]
        BOARD["Board · backlog · sprints · roadmap"]
        PROJ["Project page<br/>action plan · traceability · open issues<br/>documents · activity · people"]
        ASSESS["Guide · Agents · Assessment<br/>Settings · Research export · /privacy"]
    end

    subgraph SVC["Service layer"]
        AUTH["raia/auth.py<br/>Google sign-in · local dev identity"]
        PS["ProjectService (raia/projects.py)<br/>authorize(user, project, action)<br/>runs · approvals · decisions · board · assessments"]
        DERIVE["Derived views<br/>lineage · handoff · roadmap · actions · brief"]
        OUT["Exports<br/>project zip · AI Skill · research export · Jira"]
    end

    subgraph PIPE["LangGraph pipeline (raia/pipeline.py)"]
        GEN["generate<br/>(intake → rules → model → contract → checks)"]
        HUM{{"human_review<br/>interrupt() = H gate"}}
        REV["revise<br/>(rejection reason → next attempt)"]
        PERS["persist"]
        GEN --> HUM
        HUM -- approve --> PERS
        HUM -- "reject + reason" --> REV --> GEN
    end

    subgraph AGENTS["Agents (raia/agents/)"]
        subgraph PROD["🟦 Product layer"]
            RC["Risk Classifier"]
            RR["Requirements Reviewer<br/>(+ recommend requirements)"]
        end
        subgraph DEV["🟩 Dev layer"]
            SR["User Story Refiner<br/>generate mode · refine mode"]
            AU["Auditor"]
        end
        subgraph OPS["🟧 Ops layer (planned)"]
            DM["Fairness-drift monitor<br/>not in this build"]
        end
    end

    subgraph REASON["Deterministic reasoning (raia/rationale/, raia/contract/, raia/validators.py)"]
        ENG["Rule engines<br/>risk_screen · coverage · story_seed<br/>story_map · traceability · backlog_coverage"]
        CON["Output contract<br/>schema · ids · priority · layout · repair"]
        VAL["Validators<br/>citations · structure · coverage<br/>reconciliation · evidence discipline"]
    end

    subgraph KNOW["Knowledge layer"]
        RAG["NormativeRetriever<br/>(raia/rag.py)"]
        CHROMA[("Chroma vector store<br/>.chroma/")]
        CORPUS["Curated summaries (corpus/*.md)<br/>EU AI Act · PL 2338/2023 (bill) · IEEE 7000<br/>NIST AI RMF · MS RAI v2 · ECCOLA"]
    end

    subgraph STATE["Storage (raia/storage.py, raia/db.py)"]
        REPO[("Blackboard per project<br/>Git repository (local) or<br/>hash-chained database (hosted)")]
        REG[("Registry and logs<br/>users · projects · members · assessments<br/>events · audit log · sealed transcripts")]
        CP[("Graph checkpointer<br/>PostgresSaver · MemorySaver")]
    end

    LLM["LLM factory (raia/llm.py)<br/>Claude (default) · OpenAI · Mock"]

    UI --> AUTH --> PS
    UI --> PS
    PS --> PIPE
    PS --> DERIVE
    PS --> OUT
    REVIEW <--> HUM
    GEN --> AGENTS
    AGENTS -- "1. compute what is enumerable" --> ENG
    ENG -- "pinned sections + query facets" --> RAG
    AGENTS -- "3. finalise and check the record" --> CON --> VAL
    VAL --> REVIEW
    AGENTS --> RAG
    RAG --> CHROMA
    CORPUS -- "ingest.py" --> CHROMA
    AGENTS --> LLM
    AGENTS -- "read upstream artifacts" --> REPO
    PERS -- "one recorded version (after approval only)" --> REPO
    PIPE --> CP
    PS --> REG
    DERIVE --> REPO
    style OPS stroke-dasharray: 5 5
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
source. Not every stage fills the whole core: the Risk Classifier analyses
risk and writes no actions; the Requirements Reviewer answers the approved
risks with requirements and writes neither findings nor actions (each
requirement carries the risks behind its gap and their priority). Code
assigns the identifiers, computes risk level and priority, carries the
engine's issues forward, and renders each artifact's layout — the risks and
the decisions on them for the Risk Classifier; the requirements first for the
Requirements Reviewer; the refined stories first for the User Story Refiner;
an audit report, rated by code, for the Auditor — on screen
and in the document alike (`raia/contract/digest.py`). A reviewer edits the record's fields at the gate, never its prose.
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
      HOME["/ Home<br/>attention list · projects · new project"]
      GUIDE["/guide<br/>tester guide"]
      AGENTS["/agents<br/>architecture · agent docs"]
      ASSESS["/assessment"]
      subgraph ACCOUNT["Account"]
        SET["/settings<br/>profile · Jira · your data · delete"]
        RES["/research<br/>admins only"]
        PRIV["/privacy"]
        OUT["/signout"]
      end
    end
    HOME -->|"?id="| PROJECT["/project<br/>Board · Overview · Documents · Action plan<br/>Traceability · Open issues · Activity · People and settings"]
    PROJECT -->|"?project=&agent="| STAGE["/stage<br/>receives · run · review gate · read · revise · re-confirm"]
    STAGE --> PROJECT
```

*Sign out* is listed only when there is someone to sign out: the local
developer identity has no sign-in.

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
    SVC --> REG[("Registry tables<br/>users · projects · members · invitations<br/>assessments · usage · Jira · audit log")]
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
    PROJECTS ||--o{ PROJECT_EVENTS : "decisions and events (hash chain)"
    PROJECTS ||--o{ RUN_TRANSCRIPTS : "sealed prompt and replies per run"
    USERS ||--o{ EXPERIENCE_RATINGS : "submits (never linked to a project)"
    EXPERIENCE_RATINGS ||--|{ ASSESSMENT_ITEMS : "one row per answer"
    USERS ||--o{ USAGE_COUNTERS : "model calls per day"
    USERS ||--o| JIRA_CONNECTIONS : "own Jira Cloud token (encrypted)"
    USERS ||--o{ AUDIT_LOG : "account-wide actions"
```

`PROJECT_FILES`, `PROJECT_COMMITS`, `PENDING_REVIEWS`, `INTAKE_DRAFTS` and
`PROJECT_EVENTS` hold the database blackboard; with `RAIA_STORE=git` the same
content lives in each project's Git repository. An assessment is stored with
what its author used, never with a project: the `project_id` columns of
`EXPERIENCE_RATINGS` and `ASSESSMENT_ITEMS` remain only for answers recorded
before instrument `raia-panel-v3` and are never written or exported. The
graph checkpointer (`PostgresSaver`) creates and manages its own `checkpoint*`
tables, which are deleted with a project.

Schema changes after the first release are applied once each by the migration
runner in `raia/db.py` and recorded in `schema_migrations`; an existing
database is upgraded in place on start.

| Role | View | Run agents, edit answers | Approve / reject, arbitrate | Invite, settings, delete |
|---|---|---|---|---|
| owner | ✓ | ✓ | ✓ | ✓ |
| editor | ✓ | ✓ | ✓ | |
| reviewer | ✓ | | ✓ | |

Rules the tests enforce:

- **Stage is derived, never stored.** A project's progress is computed from
  its approved artifacts and pending drafts on every read.
- **Identity comes from the session.** The approver recorded at a gate is the
  signed-in person; any approver name in the caller's payload is overwritten.
  With *require a second approver* set, the person who ran a stage cannot
  approve it — including after a restore.
- **History is tamper-evident on both backends.** Git objects locally; in the
  database each version's digest covers its parent digest, its message, its
  timestamp and the SHA-256 of every file it wrote, and `verify_history()`
  recomputes all of them. The event log — re-confirmations, card verdicts,
  rejections, which a stage's *Needs review* status is computed from — is
  hash-chained the same way and verified with it.
- **A decision names its draft.** Approve and reject carry the id of the draft
  the person saw; a decision on a draft another run has replaced is refused.
  Approving over failed checks a reviewer must act on needs a recorded reason.
- **No lost update.** The registers (backlog, sprints, open issues) are read,
  changed and written in one optimistic step: a write computed from an old
  read is refused and recomputed on the new state.
- **People are named by reference.** Everything recorded names a person as
  `user:<id>`; pages and exports resolve the reference to a name. No name or
  email enters the hash chain or a model prompt, so deleting an account
  leaves nobody named.

## 1d. The sprint cycle: backlog, sprints and roadmap

Once the risk classification and the ethical requirements are approved, a
project runs as a loop of sprints over one backlog. Requirements are
constants; the work they need is spread over many sprints. There are still
four agents: the backlog, the sprints and the roadmap are **shared state on the
blackboard**, not an agent, and people plan the sprints.

```mermaid
flowchart TB
    subgraph ONCE["Once per project"]
      RC["Risk Classifier + H"] --> RR["Requirements Reviewer + H<br/>(constants, change-controlled)"]
    end
    RR --> GEN["User Story Refiner · generate mode + H<br/>requirements without a story → RAI-n"]
    GEN --> BL[("08_backlog<br/>RAI-n and US-n stories")]
    subgraph SPRINT["Every sprint (09_sprints)"]
      PLAN["Plan: rule-based suggestion,<br/>a person decides"] --> REF["User Story Refiner · refine mode + H<br/>product stories get ethical criteria"]
      REF --> TICK["Tick done by hand<br/>(or optional Jira sync)"]
      TICK --> AUD["Auditor + H<br/>project-wide audit"]
    end
    BL --> PLAN
    AUD -->|"approval closes the sprint:<br/>verified or carried over"| BL
    AUD --> RM["Roadmap (computed)<br/>state per requirement · series · trend"]
    RR -. "a revision flags only<br/>the stories it touches" .-> BL
```

| Piece | Where | Rule |
|---|---|---|
| Backlog register | `raia/backlog.py`, `08_backlog.md` + `.json` | Stable ids (`RAI-n` from requirements, `US-n` product). An RAI story links at least one requirement. Statuses: backlog, in sprint, done, verified, needs review, obsolete |
| Sprints register | `raia/backlog.py`, `09_sprints.md` + `.json` | One open sprint at a time: planning → active → awaiting audit → closed. It closes only on an approved audit, which records its numbers |
| Per-sprint copies | `04_refined_stories.SPR-n.md`, `05_audit_report.SPR-n.md` | The same commit as the approval that wrote them |
| Roadmap | `raia/roadmap.py` | Computed, never generated: where each requirement stands, verified requirements per sprint, the trend, the sprints-left estimate, and the next-sprint suggestion (rules only, no model) |
| Generate mode | `raia/agents/story_generate.py`, `raia/rationale/story_seed.py` | A mode of the User Story Refiner with its own record. Short list by default (five), widened on request |
| Project-wide audit | `raia/rationale/traceability.py`, `raia/rationale/backlog_coverage.py` | This sprint's items audited; the rest reported where it stands; the backlog checked against the ethical risks |
| Change control | `backlog.compare_requirements`, `backlog.change_control` | A changed requirement flags its stories; a removed one proposes obsolete; the stages of the sprint cycle are never flagged wholesale (`lineage.CYCLIC`) |
| Jira (optional) | `raia/jira.py`, `raia/ui/jira_panel.py` | CSV with no setup; push and sync with a person's own token. Done in Jira means delivered; a sync never overwrites a manual change and never verifies |

Who may do what on the board: owners and editors add stories, plan, start and
end sprints and push to Jira; every member, reviewers included, can tick a
story done and sync from Jira. Only an approved Auditor run sets a story
verified.

## 1e. The review loop and the hand-off between stages

Every stage page runs the same loop, and what a person decides in it travels to
the next stage through the blackboard — never through a call between agents.

```mermaid
flowchart TB
    REC["1 · What this stage receives<br/>upstream items, open decisions,<br/>cards a person excluded (raia/handoff.py)"]
    WORK["2 · Working screen<br/>form set aside; steps reported by raia/progress.py"]
    DRAFT["3 · Draft<br/>status and its meaning, Gaps to close,<br/>hand-off strip, compact cards"]
    CARDS["4 · Card review<br/>accept / reject with a reason<br/>(raia/contract/review.py)"]
    DEC["5 · Decisions<br/>an option and why, on the card"]
    APP{{"6 · Approve (H)"}}
    REG[("Open Issues register<br/>open · decided · resolved · accepted")]
    BB[("Blackboard<br/>artifact + sidecar, review block")]
    NEXT["Next stage<br/>starts at 1 with what was handed on"]
    REC --> WORK --> DRAFT --> CARDS --> DEC --> APP
    CARDS -- "reject and regenerate" --> WORK
    APP -- "one commit" --> BB
    APP -- "decisions, overrides" --> REG
    BB --> NEXT
    REG --> NEXT
```

- **Card review.** A rejected card the model wrote leaves the approved record
  and is kept in its `review.rejected` block with who and why. A rejected card
  a rule engine computed (an ethical value requirement exists because the
  coverage matrix found a gap) is kept, marked `overridden`, recorded in the
  register as a decided disagreement with code, and not handed on: no story is
  generated for it and it is not audited. Unmarked cards are accepted.
- **Decisions.** Each open issue carries options (the engine's, the agent's, or
  a default per issue type). On a draft, a decision is kept with the pending
  draft and reaches the register already decided on approval; on an approved
  record it is written to the register at once. A decision is identified by
  its wording, so renumbering cannot lose it.
- **Status.** A record is *Blocked in its current form* when anything in it is
  blocking. The status shown is derived, like stage staleness: once every
  blocking decision is taken it reads as needing attention, and says which
  decision lifted it. The committed record is never rewritten.
- **Hand-off.** Items are tracked on identifiers code assigns and keeps across
  stages — obligation codes, `EVR-n`, story ids, audit item ids — never on
  per-record ids such as `RC-F1`. The next agent's prompt lists the decisions
  people took and the items they excluded upstream. The project's
  Traceability tab draws the whole thread, obligation → requirement → story →
  audit verdict.
- **Checks.** Every check still runs and is persisted. Each check code has an
  audience (`raia.validators.CHECKS`): the reviewer is asked to act only where a
  person is needed; what code already corrected (a fabricated citation is
  removed, an upgraded verdict restored) goes to the technical log.

## 1f. Recommend ethical requirements (outside the graph)

The Requirements Reviewer can propose candidate requirements before its stage
runs. This is a separate, shorter path (`RequirementsReviewerAgent.recommend`,
reached through `ProjectService.recommend_requirements`), and it persists
nothing: the candidates go back to the form, where a person adopts, edits or
rejects each one.

```mermaid
flowchart LR
    F["Form answers<br/>(requirements, controls)"] --> G["coverage engine<br/>gaps, computed as in a run"]
    G --> P["prioritised gaps<br/>(short list, never repeated)"]
    P --> M["model pass<br/>candidates with fit criteria"]
    M --> C{"checked in code"}
    C -- "addresses no computed gap<br/>cites no retrieved excerpt<br/>nothing testable" --> D["dropped, reported"]
    C -- ok --> H["person: adopt · edit · reject (reason)"]
    H --> F2["adopted requirements join the form,<br/>marked as recommended"]
    F2 --> RUN["stage run → H gate as usual"]
```

Pre-filling the stakeholder and principle questions (`AgentSpec.suggest`) is
rule-based and calls no model; it fills only empty fields, never the controls in
place, and each value says why. Every offer and decision is recorded in the
project's event log, and the approved record says which requirements were
recommended and adopted. The Risk Classifier has no such path: its answers
decide the verdict, so they are asked, never suggested.

## 1g. Model providers

`raia/llm.py` is the one place a model is called (`invoke_chat`). The provider
is configuration: `anthropic` (Claude, the reference model, default
`claude-sonnet-5-5`), `openai` (default `gpt-6.2-sol`) or `mock` (a test double
that returns records conforming to the output contract, refused to evaluators).
Both provider libraries are installed. No sampling temperature is sent unless
`RAIA_LLM_TEMPERATURE` sets one, because current Claude models and OpenAI's
reasoning models refuse it; a refused value is dropped and retried once. Each
provenance record states the provider, the model and the temperature actually
sent (`null` by default). Transient failures (overload, rate limit, timeout)
are retried with backoff; nothing else is.

## 2. Class Diagram (code structure)

The main classes and the methods the rest of the code calls. Agents and modes
are registered in `raia/agents/__init__.py` (`AGENTS`, `MODES`, `RUNNABLE`);
the UI reaches the graph and the blackboard only through `ProjectService`.

```mermaid
classDiagram
    class AgentSpec {
        +str key
        +str name
        +str layer
        +str sdlc_phase
        +str description
        +List~str~ grounding_sources
        +List~str~ upstream_keys
        +List~str~ required_upstream
        +str output_key
        +List~InputField~ input_fields
        +Callable engine
        +Callable suggest
        +str parent
        +str mode_label
        +List~str~ collapsed_groups
    }

    class InputField {
        +str key
        +str label
        +str kind
        +Sequence~Option~ options
        +bool required
        +ShowIf show_if
        +str group
    }

    class BaseAgent {
        +AgentSpec spec
        +missing_prerequisites(repo) List~str~
        +missing_inputs(inputs) List~str~
        +rationale_for(repo, inputs) RationaleResult
        +converse(system, user, parse) Turn
        +run(repo, inputs, feedback) AgentRun
    }

    class AgentRun {
        +str draft
        +dict record
        +List~NormChunk~ chunks
        +RationaleResult rationale
        +ValidationReport validation
        +dict provenance
        +dict transcript
        +to_payload() dict
    }

    class RationaleResult {
        +str engine
        +dict verdict
        +List~Finding~ findings
        +List~ChecklistItem~ checklist
        +List~Pin~ pins
        +List~str~ open_issues
        +dict tables
        +dict data
    }

    class RiskClassifierAgent
    class RequirementsReviewerAgent {
        +recommend(repo, inputs, exclude) dict
    }
    class UserStoryRefinerAgent
    class StoryGeneratorMode
    class AuditorAgent

    class BaseRepository {
        <<abstract>>
        +read_artifact(key) str
        +read_data(key) dict
        +upstream_bundle(keys) dict
        +save_artifact(key, content, approved_by, structured, run_provenance) str
        +atomic(build) tuple
        +append_open_issues(issues, raised_by) int
        +record_event(kind, payload)
        +save_pending(agent_key, payload)
        +save_transcript(agent_key, draft_id, transcript)
        +verify_history() dict
    }
    class ArtifactRepository {
        Git repository per project
    }
    class DatabaseRepository {
        append-only, hash-chained rows
    }

    class NormativeRetriever {
        +retrieve(query, top_k, sources, pins) List~NormChunk~
        +fetch_section(source, section) List~NormChunk~
        +format_context(chunks) str
    }

    class NormChunk {
        +str text
        +str source
        +str authority
        +str section
        +str chunk_id
        +bool pinned
        +bool derived
        +citation() str
    }

    class StageRunner {
        -checkpointer
        -graph
        +check_gate(project, agent_key) List~str~
        +start(project, agent_key, inputs, actor) dict
        +resume(project, agent_key, decision) dict
        +restore(project, agent_key, payload) dict
        +draft_at_gate(project, agent_key) dict
    }

    class ProjectService {
        +authorize(user, project_id, action) Project
        +start_run(user, project_id, agent_key, inputs) dict
        +resume(user, project_id, agent_key, decision) dict
        +recommend_requirements(user, project_id, agent_key, inputs) dict
        +decide_issue(user, project_id, issue_id, choice, rationale) bool
        +board(user, project_id) dict
        +submit_rating(user, payload)
        +research_export(user) bytes
    }

    BaseAgent <|-- RiskClassifierAgent
    BaseAgent <|-- RequirementsReviewerAgent
    BaseAgent <|-- UserStoryRefinerAgent
    BaseAgent <|-- StoryGeneratorMode
    BaseAgent <|-- AuditorAgent
    StoryGeneratorMode ..> UserStoryRefinerAgent : mode of (spec.parent)
    BaseAgent *-- AgentSpec
    AgentSpec *-- InputField
    BaseAgent ..> RationaleResult : spec.engine computes
    BaseAgent ..> NormativeRetriever : retrieves norms
    BaseAgent ..> BaseRepository : reads upstream state
    BaseAgent ..> AgentRun : returns
    NormativeRetriever ..> NormChunk : returns
    BaseRepository <|-- ArtifactRepository
    BaseRepository <|-- DatabaseRepository
    StageRunner ..> BaseAgent : runs via graph nodes
    StageRunner ..> BaseRepository : persists after approval
    ProjectService ..> StageRunner : runs and resumes stages
    ProjectService ..> BaseRepository : open_repository(project)
```

## 3. Sequence Diagram (one agent run with the human checkpoint)

```mermaid
sequenceDiagram
    actor Human
    participant UI as Streamlit UI
    participant PS as ProjectService
    participant SR as StageRunner (LangGraph)
    participant AG as Agent
    participant ENG as Rule engine
    participant RAG as NormativeRetriever
    participant LLM as LLM (Claude · OpenAI)
    participant REPO as Blackboard (Git or database)

    Human->>UI: fill the structured form, click Run
    UI->>PS: start_run(user, project, agent_key, inputs)
    PS->>PS: authorize "run" · count the call · save the answers
    PS->>SR: start(project, agent_key, inputs, actor)
    SR->>SR: stage gate (required upstream approved?)
    SR->>AG: generate node → run(repo, inputs)
    AG->>AG: sanitize free text (flag, never delete)
    AG->>REPO: read approved upstream records
    AG->>ENG: decision procedure
    ENG-->>AG: verdict · tables · ids · pins · checklist · issues
    AG->>RAG: retrieve(query, sources, pins)
    RAG-->>AG: pinned + similar excerpts (ids, authority, curated-summary label)
    AG->>LLM: contract + computed block + excerpts + upstream + inputs
    LLM-->>AG: one JSON record
    AG->>AG: parse · repair once if invalid or cut off · finalise<br/>(ids, priority, engine issues, layout) · validators
    AG-->>SR: draft + evidence + computed + checks + provenance
    SR->>REPO: keep the pending draft and the sealed transcript
    SR-->>UI: interrupt() — awaiting_review (H gate)
    UI-->>Human: draft · edit the record · evidence · what the code computed

    alt Human rejects
        Human->>UI: reason code + feedback (rejected cards listed)
        UI->>PS: resume(reject, draft_id)
        PS->>SR: resume
        SR->>SR: revise node → generate again with the feedback
        SR-->>UI: awaiting_review again
    else Human approves (card verdicts, decisions, field edits)
        Human->>UI: Approve and commit
        UI->>PS: resume(approve, draft_id, review, override_reason?)
        PS->>PS: same draft? second approver? reason for failed checks?<br/>approver = signed-in user (user:id)
        PS->>SR: resume
        SR->>SR: persist node: re-finalise, re-render, re-check the approved record
        SR->>REPO: one version: Markdown + JSON sidecar + provenance,<br/>decisions → open issues, registers updated
        REPO-->>SR: version id
        SR-->>UI: approved
        UI-->>Human: What's next — downstream stages can run
    end
```

## 4. Pipeline / State Diagram (SDLC-wide stage gates)

Agents never trigger each other; a stage only unlocks when a person has
approved the upstream artifact it requires. The product description is a field
of the Risk Classifier's form; it is committed as `01_product_brief.md` in the
same version as the approved classification.

```mermaid
stateDiagram-v2
    [*] --> RiskClassification : Risk Classifier + H (writes 01 and 02)
    RiskClassification --> RequirementsReview : Requirements Reviewer + H
    RequirementsReview --> RaiBacklog : User Story Refiner, generate mode + H
    RaiBacklog --> SprintPlanned : a person plans the sprint
    RequirementsReview --> RefinedStories : User Story Refiner, refine mode + H
    SprintPlanned --> RefinedStories : refine the sprint's product stories
    SprintPlanned --> AuditReport : sprint ended, Auditor + H
    RefinedStories --> AuditReport : sprint ended, Auditor + H
    AuditReport --> SprintPlanned : approval closes the sprint, next sprint
    AuditReport --> [*]

    note right of RiskClassification
        Artifacts are Markdown files with a JSON sidecar,
        recorded on approval: 01_product_brief.md,
        02_risk_classification.md, 03_requirements_review.md,
        04a_rai_backlog.md, 04_refined_stories.md,
        05_audit_report.md; registers 07 to 09
    end note
```

## 5. Design Decisions (traceability to the RAIA architecture)

| Architecture element | Implementation | Enforced by |
|---|---|---|
| Agents in layers | `raia/agents/` — one module per agent; `AGENTS` registry in pipeline order. Product and Dev layers run; the Ops layer is specified and not implemented in this build | structure |
| Blackboard per project, versioned | `raia/repository.py` (Git) and `raia/storage.py` (hash-chained database); every approval is one recorded version carrying the Markdown artifact *and* its JSON sidecar; approval provenance stamped in the header | code |
| Mandatory human checkpoints "H" | `interrupt()` in the `human_review` node; the persist node is unreachable without an approve decision, including on the restart-recovery path | code + smoke test |
| Agents never trigger agents | stage gates via `AgentSpec.required_upstream`; no agent-to-agent call exists | structure |
| Grounded recommendations | `raia/rag.py` — excerpts carry source, section, authority and a stable id; agents must cite them | prompt |
| Citations are real | `validators.check_citations` matches every tag against the excerpts actually retrieved for that run; `assemble.finalize` removes a tag that resolves to none and records the removal (`pruned_citations`, `PRUNED_CITATION` notes in provenance) | code + smoke test |
| The decisive excerpt is never missing | each decision procedure declares `Pin`s, fetched by exact metadata match and merged ahead of similarity results | code + smoke test |
| Decision procedures, not prompts | `raia/rationale/` — one rule engine per agent computes the verdict, the tables and the identifiers before any model call | code |
| Verdicts are reconciled, not averaged | `validators.check_reconciliation` requires the agent to declare agreement or disagreement; disagreement becomes an open issue | code |
| Conflict precedence legal > standard > advisory | `config.AUTHORITY_LEVELS`, reinforced by excerpt ordering in the prompt | prompt |
| Same-level conflicts escalated | `ArtifactRepository.append_open_issues` — a tracked register with statuses, populated from both the engine and the approved draft | code |
| Declared completeness | each engine emits a checklist; `validators.check_coverage` requires a status per key | code |
| Anti-ethics-washing audit | `rationale/traceability.py` assigns NOT VERIFIED where no evidence exists; `validators.check_forbidden_verdicts` prevents an upgrade | code |
| One standard output for every agent | `raia/contract/` — schema per agent (shared core + extension), closed vocabularies from the normative sources, code-computed identifiers, risk level and priority, one rendered layout, bounded repair and an honest fallback; published in `docs/schema/` and `docs/output-contract.md` | code + test_contract |
| Every identified risk is responded to | `contract.checks.check_responses` — every finding has an action or an open issue; accepting a risk opens an issue. The Risk Classifier hands its risks on; the Requirements Reviewer answers them with requirements, one per gap, each naming the risks it answers | code |
| Structured human editing | the gate edits record fields; persistence re-finalises, re-renders and re-validates what was approved; free-text edits are refused | code + smoke test |
| Project action plan | `contract.actions` — every action from every approved record, sorted by computed priority, exported as CSV/JSON | code |
| Continuing outside RAIA | `raia.skill` + `export.skill_bundle` — a portable skill in two parts: a fixed part (`SKILL.md` and references generated from the code, versioned, identical for every project) and a project part (`PROJECT_CONTEXT.md` computed from the blackboard, with the approved outputs), in four formats (Cursor, ChatGPT, Claude, one Markdown file), so an assistant a person is allowed to use applies the approved records to the real backlog and documents with RAIA's rules, or screens a product itself when there is no project; research data left out | code + test_skill |
| Reproducible audit trail | `raia/provenance.py` — build id, provider and model, the temperature actually sent (`null` when none), corpus version, excerpt ids, prompt hash, attempt, edits, rejection history, check results; with `RAIA_TRANSCRIPT_KEY`, the exact prompt and raw replies sealed per run (`raia/sealed.py`) with their token use | code + smoke test |
| Data protection | projects are reachable only through a membership, checked in `ProjectService.authorize`; sign-in delegated to Google (no stored passwords); research exports pseudonymized with keyed participant codes; no retraining | code + test_projects |
| Accountable approval | the approver is the authenticated identity; optional second-approver rule makes the runner ineligible to approve | code + test_projects |
| Durable review state | `PostgresSaver` checkpointer and stored drafts; a restored review re-enters the gate | code + test_projects |
| Input sanitization | `raia/sanitize.py` — control characters, length caps, injection patterns in English and Portuguese; applied to form input *and* to the approved artifact | code |
| Provider-agnostic LLM | `raia/llm.py` factory and a single `invoke_chat` call site; Claude (default `claude-sonnet-5-5`) and OpenAI (default `gpt-6.2-sol`) both installed; a temperature is sent only when configured, and a refused one is dropped and recorded | structure + test_engines |
| The sources say what they are | `config.DERIVED_SOURCES` — every corpus file is a curated summary and is labelled so in the prompt, at the gate and in the evidence; `config.PROPOSED_SOURCES` — PL 2338/2023 is a bill and every tier or obligation from it is labelled "bill, not in force"; each tier says whether it binds the product, from the declared markets | code + test_engines, test_ui |
| Recommendations a person adopts | `RequirementsReviewerAgent.recommend` — candidate requirements for computed gaps only, checked in code before a person sees them, never persisted until adopted in the form; `AgentSpec.suggest` pre-fills context questions by rule; every offer and decision recorded as an event | code + test_engines, test_ui |
| Approval over failed checks is explained | `ProjectService.resume` refuses an approval over checks a reviewer must act on without a recorded reason (`OverrideRequired`); the reason is kept with the approval | code + test_projects |
| Accountable use of the system | security-relevant actions with account-wide reach (exports, deletions, refused access) go to the `audit_log` table and to structured JSON logs (`raia/logs.py`); model calls are limited per person per day (`RAIA_MAX_RUNS_PER_DAY`) | code + test_projects |
| An evaluation that cannot be joined to projects | `raia/ui/assessment.py` (instrument `raia-panel-v3`) — an assessment names no project and is stored with what its author used; the research export gives assessments and project activity separate keyed participant codes and refuses to run without `RAIA_PSEUDONYM_KEY` | code + test_projects, test_ui |
| Something to hand on | `raia/brief.py` — a one-page brief written by code from the approved records, naming roles, not people | code + test_ui |
| Iterative development across sprints | a backlog and sprints on the blackboard (`raia/backlog.py`); the Refiner's generate and refine modes write to it only through their gates; the roadmap and the sprint suggestion are computed (`raia/roadmap.py`) | code + test_backlog |
| The audit covers the whole project | `traceability.run` audits the sprint's items and reports the rest where it stands; `backlog_coverage` checks the backlog against the ethical risks; progress and trend are computed from the final verdicts | code + test_backlog |
| A person reviews each card | `contract.review` — accept or reject per card with a reason; a rejected model card leaves the record into its review block, a rejected computed card is kept as an override and recorded in the register | code + test_contract, test_ui |
| Decisions are taken where they are raised | the decision card writes to the pending draft, then the register on approval (`append_open_issues` with a decision), or to the register directly on an approved record (`ProjectService.decide_issue`); a `decided` status | code + smoke test, test_ui |
| Stages hand on, visibly | `raia/handoff.py` — what each stage receives and addresses on stable identifiers, what changed since the approved version, the Traceability thread, and the decisions and exclusions the next prompt is told about | code + test_backlog |
| Only an audit verifies | `backlog.apply_audit` runs only on an approved audit of an ended sprint; ticks and Jira syncs set *done*, never *verified* | code + test_backlog, test_jira |

**Not yet implemented** (tracked in the README roadmap): the Ops layer (a
fairness-drift monitor fed by production telemetry), ingesting the official
legal texts with article-level citation metadata, Confluence, Jira Server or
Data Center (Jira Cloud is supported, optionally), an API with background
workers in place of model calls on the page's own thread, and least-privilege
tool-permission hardening.

**Known limitations, stated plainly.** The corpus is a set of curated summaries
prepared for this project — all six sources, the two legal texts included — so
a citation resolves to a section of a summary rather than to the official
wording; every source is in `config.DERIVED_SOURCES` and labelled as such in
the prompt and at the approval gate. The default models take no sampling
temperature, so two runs on the same answers can differ; the rule engine fixes
what is enumerable, the record makes the rest comparable, and
`tests/consistency_check.py` measures the agreement with a real model. Injection detection is
regex-based and will not catch a careful paraphrase — the controls that carry
the weight are the approval gate and the citation validator, not the pattern
list. The lexical matchers in the coverage and traceability engines are
deliberately coarse and conservative: they produce candidate gaps and
conservative verdicts for a human to review, and are not evidence of absence.
