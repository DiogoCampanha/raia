#!/usr/bin/env python3
"""
app.py — RAIA Streamlit user interface.

Run with:
    streamlit run app.py

The UI is organized around the RAIA pipeline:

* a sidebar to select/create a project (each project = one Git-versioned
  artifact repository, the blackboard);
* one page per agent, ordered by pipeline stage and grouped by layer
  (Product / Dev / Ops), each with the mandatory human-approval gate;
* an Audit Trail page showing artifacts and the Git commit history.

The UI NEVER persists an agent output without explicit human approval:
approval/rejection buttons resume the paused LangGraph run (see
raia/pipeline.py). Rejections loop the agent with the reviewer's feedback.

Hosted-deployment ready (e.g. Streamlit Community Cloud): secrets are
bridged from st.secrets to the environment, the RAG index self-builds on
first startup, and the app degrades to mock mode when no API key is set --
so testers only need the URL, nothing local.
"""

import os

import streamlit as st

# --- Secrets bridge (MUST run before importing raia.*) ----------------------
# On Streamlit Community Cloud, configuration lives in st.secrets rather than
# a .env file. raia.config reads the environment at import time, so we copy
# secrets into the environment first. Locally (no secrets.toml) this is a
# silent no-op and .env keeps working as before.
try:
    for _key, _value in st.secrets.items():
        if isinstance(_value, str) and _key not in os.environ:
            os.environ[_key] = _value
except Exception:
    pass  # no secrets file configured — normal for local runs

from raia import config                                   # noqa: E402
from raia.agents import AGENTS                            # noqa: E402
from raia.pipeline import StageRunner                     # noqa: E402
from raia.repository import ARTIFACT_FILES, ArtifactRepository  # noqa: E402

# --- Graceful key fallback ---------------------------------------------------
# If a real provider is selected but its API key is missing (e.g. a fork of
# the repo deployed without secrets), fall back to mock mode instead of
# crashing on the first agent run. The sidebar shows a clear notice.
_KEY_VARS = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
MISSING_KEY = (
    config.LLM_PROVIDER in _KEY_VARS and not os.environ.get(_KEY_VARS[config.LLM_PROVIDER])
)
if MISSING_KEY:
    config.LLM_PROVIDER = "mock"

# ---------------------------------------------------------------------------
# Example inputs (the project's canonical resume-screening scenario)
# ---------------------------------------------------------------------------

EXAMPLES = {
    "risk_classifier": {
        "product_brief": (
            "TalentFlow is a resume-screening platform. An ML model ranks and "
            "filters job applications, producing a shortlist for recruiters. "
            "The AI component scores each resume against the job description "
            "and historical hiring data."
        ),
        "intended_use": (
            "Used by corporate HR departments in Brazil and the EU to screen "
            "high-volume vacancies. Recruiters see the ranked shortlist and "
            "decide whom to interview."
        ),
        "target_users": (
            "Users: recruiters and HR managers. Affected people: all job "
            "applicants, including members of protected groups; candidates "
            "filtered out never interact with the system directly."
        ),
    },
    "requirements_reviewer": {
        "requirements": (
            "R1. The system shall rank applications by predicted job fit.\n"
            "R2. The system shall process at least 10,000 resumes per hour.\n"
            "R3. Recruiters shall be able to export the shortlist to CSV.\n"
            "R4. The system shall integrate with the corporate SSO.\n"
            "R5. Model retraining shall occur monthly on new hiring data."
        ),
    },
    "story_refiner": {
        "user_stories": (
            "S1. As a recruiter, I want to see the top-20 ranked candidates for "
            "a vacancy so that I can build an interview shortlist quickly.\n"
            "S2. As a recruiter, I want to filter candidates by minimum "
            "qualification criteria so that unqualified applications are "
            "excluded automatically.\n"
            "S3. As an HR manager, I want a dashboard of screening throughput "
            "so that I can report hiring KPIs."
        ),
    },
    "auditor": {
        "sprint_outcomes": (
            "Sprint 7 delivered: ranking API v2 (S1) with disaggregated "
            "evaluation report — demographic parity difference measured at "
            "0.08 across gender and 0.12 across race groups on validation "
            "data; qualification filter (S2) shipped without disaggregated "
            "testing; audit-log storage for ranking decisions enabled."
        ),
        "planned_epics": (
            "Next: explanation UI for recruiters (why a candidate was "
            "ranked); candidate-facing contestation form; retraining pipeline "
            "automation."
        ),
    },
    "drift_monitor": {
        "telemetry_csv": (
            "window,group,selection_rate,accuracy\n"
            "2026-04,gender=F,0.31,0.86\n"
            "2026-04,gender=M,0.36,0.87\n"
            "2026-05,gender=F,0.28,0.85\n"
            "2026-05,gender=M,0.38,0.87\n"
            "2026-06,gender=F,0.24,0.83\n"
            "2026-06,gender=M,0.39,0.88\n"
        ),
        "context_notes": (
            "A new job board was integrated as an application source in May, "
            "roughly doubling application volume."
        ),
    },
}

LAYER_BADGES = {"Product": "🟦 Product", "Dev": "🟩 Dev", "Ops": "🟧 Ops"}
LAYER_COLORS = {"Product": "#2563eb", "Dev": "#16a34a", "Ops": "#ea580c"}

# Maps artifact keys to the agent that produces them (for friendly gate messages).
PRODUCER_OF = {agent.spec.output_key: agent.spec.name for agent in AGENTS.values()}


def _flash() -> None:
    """Show a one-shot success message that survives st.rerun()."""
    msg = st.session_state.pop("flash", None)
    if msg:
        st.success(msg)


def _next_step_hint(agent_key: str) -> str:
    """Where the walkthrough goes after this agent is approved."""
    keys = list(AGENTS)
    i = keys.index(agent_key)
    if i + 1 < len(keys):
        return f"Next stage: **{AGENTS[keys[i + 1]].spec.name}** (sidebar)."
    return "Pipeline complete — see the **📜 Audit Trail** for the full Git history."

# ---------------------------------------------------------------------------
# Session-level singletons
# ---------------------------------------------------------------------------


@st.cache_resource
def get_runner() -> StageRunner:
    """One StageRunner (and its LangGraph checkpointer) per server process."""
    return StageRunner()


@st.cache_resource
def ensure_normative_index() -> bool:
    """Self-bootstrap the RAG index on hosted platforms.

    Fresh containers (Streamlit Cloud redeploys, restarts) have no Chroma
    index; build it from the bundled corpus automatically so testers never
    run ingest.py themselves. Cached so it happens once per process.
    """
    from raia.rag import index_exists, ingest_corpus

    if not index_exists():
        ingest_corpus(verbose=False)
    return True


def get_repo() -> ArtifactRepository:
    return ArtifactRepository(st.session_state["project"])


# ---------------------------------------------------------------------------
# Sidebar: project selection + pipeline status
# ---------------------------------------------------------------------------


def sidebar() -> "str | None":
    """Render the sidebar; returns the chosen page name (None = no project yet)."""
    st.sidebar.title("🛡️ RAIA")
    st.sidebar.caption("Responsible AI Assistant — multi-agent PoC")

    # Project picker -------------------------------------------------------
    projects = ArtifactRepository.list_projects()
    choice = st.sidebar.selectbox(
        "Project", ["➕ New project…", *projects],
        index=1 if projects else 0,
        help="Each project has its own Git-versioned artifact repository.",
    )
    if choice == "➕ New project…":
        name = st.sidebar.text_input("New project name", placeholder="e.g. talentflow")
        if not name:
            st.sidebar.info("Name a project to begin.")
            return None
        st.session_state["project"] = name
    else:
        st.session_state["project"] = choice

    # Provider notice ------------------------------------------------------
    if MISSING_KEY:
        st.sidebar.warning(
            "🧪 Demo mode: no LLM is connected, so agent outputs are canned "
            "placeholders. The full workflow (reviews, approvals, audit "
            "trail) still works — tell the study coordinator if you expected "
            "real analyses."
        )
    elif config.LLM_PROVIDER == "mock":
        st.sidebar.warning(
            "🧪 Mock mode: outputs are canned placeholders (no LLM calls). "
            "Maintainers: set RAIA_LLM_PROVIDER=anthropic and an API key in "
            ".env for real analyses."
        )

    # Navigation with pipeline progress ------------------------------------
    repo = get_repo()
    done = set(repo.existing_artifacts())
    n_done = sum(1 for a in AGENTS.values() if a.spec.output_key in done)
    st.sidebar.progress(
        n_done / len(AGENTS), text=f"{n_done}/{len(AGENTS)} stages approved"
    )

    layer_dot = {"Product": "🟦", "Dev": "🟩", "Ops": "🟧"}
    pages = {"🏠 Overview": "Overview"}
    for key, agent in AGENTS.items():
        if agent.spec.output_key in done:
            mark = "✅"
        elif agent.missing_prerequisites(repo):
            mark = "🔒"
        else:
            mark = "▶️"
        pages[f"{mark} {layer_dot[agent.spec.layer]} {agent.spec.name}"] = agent.spec.name
    pages["📜 Audit Trail"] = "Audit Trail"

    label = st.sidebar.radio("Pipeline", list(pages), label_visibility="collapsed")
    st.sidebar.caption("✅ approved · ▶️ ready · 🔒 awaiting upstream approval")
    return pages[label]


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


def page_welcome() -> None:
    """Landing page shown before any project exists (never a blank screen)."""
    st.title("🛡️ RAIA — Responsible AI Assistant")
    st.markdown(
        """
RAIA helps development teams apply **Responsible AI** practices across the
software life cycle. **Five specialized agents** — organized in Product,
Dev, and Ops layers — analyze your project and draft recommendations
grounded in four consolidated frameworks (IEEE 7000, NIST AI RMF,
Microsoft RAI Standard v2, ECCOLA) and two legal texts (EU AI Act,
Brazilian PL 2338/2023).

Two design principles you will notice everywhere:

- **You are the checkpoint** — no agent output is saved until a human
  reviews and approves it, and no agent ever triggers another one.
- **Everything is cited and versioned** — every claim carries a tag
  pointing to the norm excerpt that grounds it, and every approval becomes
  a Git commit in the project's audit trail.
"""
    )
    cols = st.columns(3)
    layer_blurbs = {
        "Product": "Risk classification and ethical value requirements at conception time.",
        "Dev": "Ethical acceptance criteria and accountability audits inside sprints.",
        "Ops": "Fairness-drift monitoring after deployment.",
    }
    for col, (layer, blurb) in zip(cols, layer_blurbs.items()):
        agents_in = [a.spec.name for a in AGENTS.values() if a.spec.layer == layer]
        with col:
            st.markdown(
                f"""<div style="border:1px solid #e2e8f0;border-top:4px solid {LAYER_COLORS[layer]};
border-radius:8px;padding:0.9rem 1rem;min-height:9.5rem;">
<strong>{LAYER_BADGES[layer]}</strong><br>
<span style="font-size:0.9rem;">{blurb}</span><br>
<span style="font-size:0.85rem;color:#64748b;">{" · ".join(agents_in)}</span>
</div>""",
                unsafe_allow_html=True,
            )
    st.info(
        "👈 **To begin, name a project in the sidebar** (any name works — "
        "e.g. `talentflow`). Each project gets its own Git-versioned "
        "artifact repository."
    )


def _agent_status(agent, repo, done: set) -> str:
    if agent.spec.output_key in done:
        return "approved"
    if agent.missing_prerequisites(repo):
        return "blocked"
    return "ready"


_STATUS_LABEL = {
    "approved": ("✅ approved", "#16a34a"),
    "ready": ("▶️ ready to run", "#2563eb"),
    "blocked": ("🔒 awaiting upstream", "#94a3b8"),
}


def _pipeline_figure(repo) -> str:
    """The RAIA pipeline as HTML: agent cards separated by H gates."""
    done = set(repo.existing_artifacts())
    cards = []
    for key, agent in AGENTS.items():
        status = _agent_status(agent, repo, done)
        label, color = _STATUS_LABEL[status]
        cards.append(
            f"""<div style="flex:1 1 150px;border:1px solid #e2e8f0;
border-top:4px solid {LAYER_COLORS[agent.spec.layer]};border-radius:8px;
padding:0.6rem 0.7rem;background:#ffffff;">
<div style="font-size:0.75rem;color:{LAYER_COLORS[agent.spec.layer]};font-weight:600;">
{LAYER_BADGES[agent.spec.layer]}</div>
<div style="font-weight:700;line-height:1.25;margin:0.15rem 0;">{agent.spec.name}</div>
<div style="font-size:0.8rem;color:{color};font-weight:600;">{label}</div>
</div>"""
        )
    gate = (
        '<div style="align-self:center;text-align:center;flex:0 0 auto;padding:0 0.15rem;" '
        'title="Mandatory human approval gate">'
        '<div style="width:1.7rem;height:1.7rem;border-radius:50%;border:2px solid #0f172a;'
        'display:flex;align-items:center;justify-content:center;font-weight:700;'
        'font-size:0.85rem;margin:0 auto;">H</div>'
        '<div style="font-size:0.65rem;color:#64748b;">gate</div></div>'
    )
    return (
        '<div style="display:flex;gap:0.5rem;flex-wrap:wrap;align-items:stretch;">'
        + gate.join(cards)
        + "</div>"
        + '<div style="font-size:0.8rem;color:#64748b;margin-top:0.4rem;">'
        + "Ⓗ = mandatory human approval gate: nothing advances to the next stage "
        + "until you review and approve it.</div>"
    )


def page_overview() -> None:
    _flash()
    st.title("RAIA — Responsible AI Assistant")
    st.markdown(
        """
RAIA operationalizes Responsible AI across the SDLC through **five
specialized agents** in three layers, grounded via RAG in four consolidated
frameworks (IEEE 7000, NIST AI RMF, Microsoft RAI Standard v2, ECCOLA) and
two legal texts (EU AI Act, Brazilian PL 2338/2023).

**How it works** — pick an agent in the sidebar, provide its inputs, and
review its draft. Nothing is written to the shared repository until **you
approve it** (the mandatory human checkpoint). Approved artifacts are
Git-versioned and become the context for downstream agents.
"""
    )
    st.subheader("Pipeline")
    st.markdown(_pipeline_figure(get_repo()), unsafe_allow_html=True)
    st.info(
        "Suggested walkthrough (~15 min): start with **Risk Classifier** in "
        "the sidebar and use the **Load example** button on each agent page "
        "to explore the resume-screening example scenario end to end."
    )


def _review_widget(agent_key: str, payload: dict) -> None:
    """The human checkpoint UI: edit / approve / reject a pending draft."""
    st.subheader("🧑‍⚖️ Human review required")
    st.caption(
        f"Draft #{payload['attempt']} by **{payload['agent_name']}** — nothing is "
        "persisted until you approve. You may edit the text before approving."
    )
    tab_read, tab_edit = st.tabs(["📖 Rendered draft", "✏️ Edit before approving"])
    with tab_edit:
        edited = st.text_area(
            "Draft (Markdown, editable)", payload["draft"], height=420,
            key=f"edit_{agent_key}",
        )
    with tab_read:
        st.markdown(edited)

    approver = st.text_input(
        "Your name (recorded in the audit trail)", key=f"approver_{agent_key}", value="reviewer"
    )
    col_a, col_r = st.columns(2)
    with col_a:
        if st.button("✅ Approve & commit", type="primary", key=f"approve_{agent_key}"):
            with st.spinner("Committing to the audit trail…"):
                result = get_runner().resume(
                    st.session_state["project"], agent_key,
                    {"action": "approve", "content": edited, "approver": approver},
                )
            st.session_state.pop(f"pending_{agent_key}", None)
            st.session_state["flash"] = (
                f"Approved and committed (`{result.get('commit', '')}`). "
                + _next_step_hint(agent_key)
            )
            st.rerun()
    with col_r:
        feedback = st.text_input("Rejection feedback", key=f"fb_{agent_key}",
                                 placeholder="What should the agent fix?")
        if st.button("❌ Reject & regenerate", key=f"reject_{agent_key}"):
            with st.spinner("Regenerating with your feedback…"):
                result = get_runner().resume(
                    st.session_state["project"], agent_key,
                    {"action": "reject", "feedback": feedback or "Please revise."},
                )
            st.session_state[f"pending_{agent_key}"] = result["payload"]
            st.rerun()


def page_agent(agent_key: str) -> None:
    agent = AGENTS[agent_key]
    spec = agent.spec
    _flash()
    st.title(spec.name)
    st.caption(f"{LAYER_BADGES[spec.layer]} · SDLC phase: {spec.sdlc_phase}")
    st.markdown(spec.description)

    repo = get_repo()

    # Stage gate (pipeline ordering) ---------------------------------------
    missing = agent.missing_prerequisites(repo)
    if missing:
        producers = ", ".join(
            f"**{PRODUCER_OF.get(m, m)}**" + (f" (`{m}`)" if m in PRODUCER_OF else "")
            for m in missing
        )
        st.warning(
            f"🔒 **Stage gate** — this agent builds on upstream work that is "
            f"not approved yet. First run and approve: {producers}. "
            "This ordering is intentional: it is how RAIA guarantees each "
            "stage inherits human-approved context."
        )
        return

    # Show the currently approved artifact, if any --------------------------
    current = repo.read_artifact(spec.output_key)
    if current:
        with st.expander("📄 Current approved artifact", expanded=False):
            st.markdown(current)

    # If a draft is awaiting review, show the checkpoint UI ------------------
    pending = st.session_state.get(f"pending_{agent_key}")
    if pending:
        _review_widget(agent_key, pending)
        return

    # Input form -------------------------------------------------------------
    st.subheader("Inputs")
    if st.button("📋 Load example (resume-screening scenario)", key=f"ex_{agent_key}"):
        for f in spec.input_fields:
            st.session_state[f"in_{agent_key}_{f.key}"] = EXAMPLES.get(agent_key, {}).get(f.key, "")
        st.rerun()

    inputs = {}
    for f in spec.input_fields:
        inputs[f.key] = st.text_area(
            f.label, help=f.help, key=f"in_{agent_key}_{f.key}", height=140
        )

    if st.button(f"▶ Run {spec.name}", type="primary", key=f"run_{agent_key}"):
        if not any(v.strip() for v in inputs.values()):
            st.warning("Provide at least one input first.")
            return
        # The Risk Classifier's human-authored inputs double as the
        # product-brief artifact consumed by downstream agents.
        if agent_key == "risk_classifier":
            brief = "\n\n".join(
                f"## {f.label}\n{inputs.get(f.key, '')}" for f in spec.input_fields
            )
            repo.save_artifact("product_brief", brief, approved_by="author")
        with st.spinner(f"{spec.name} is reading the norms and drafting…"):
            result = get_runner().start(st.session_state["project"], agent_key, inputs)
        if result["status"] == "awaiting_review":
            st.session_state[f"pending_{agent_key}"] = result["payload"]
            st.rerun()


def page_audit_trail() -> None:
    _flash()
    st.title("📜 Audit Trail")
    repo = get_repo()
    st.caption(
        f"Project `{st.session_state['project']}` — every artifact below is a "
        "file in a Git repository; every approval is a commit."
    )

    st.subheader("Artifacts")
    existing = repo.existing_artifacts()
    if not existing:
        st.info(
            "No approved artifacts yet. Approve an agent draft (e.g. the "
            "Risk Classifier's) and it will appear here."
        )
    for key in existing:
        content = repo.read_artifact(key)
        with st.expander(f"📄 {ARTIFACT_FILES[key]}"):
            st.markdown(content)
            st.download_button(
                "⬇ Download Markdown", content or "",
                file_name=ARTIFACT_FILES[key], mime="text/markdown",
                key=f"dl_{key}",
            )

    st.subheader("Git history (every approval is a commit)")
    history = repo.history()
    if history:
        st.table(history)
    else:
        st.info("No commits yet.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    st.set_page_config(page_title="RAIA", page_icon="🛡️", layout="wide")

    # Self-bootstrap the RAG index (no-op if already built).
    with st.spinner("Preparing the normative knowledge base (first start only)…"):
        ensure_normative_index()

    page = sidebar()

    if page is None:
        page_welcome()
    elif page == "Overview":
        page_overview()
    elif page == "Audit Trail":
        page_audit_trail()
    else:
        # Map the agent display name back to its key.
        for key, agent in AGENTS.items():
            if agent.spec.name == page:
                page_agent(key)
                break


if __name__ == "__main__":
    main()
