#!/usr/bin/env python3
"""
app.py — RAIA Streamlit user interface.

Run with:
    streamlit run app.py

The UI is organized around the paper's Figure 1:

* a sidebar to select/create a project (each project = one Git-versioned
  artifact repository, the blackboard);
* one page per agent, ordered by pipeline stage and grouped by layer
  (Product / Dev / Ops), each with the mandatory human-approval gate;
* an Audit Trail page showing artifacts and the Git commit history.

The UI NEVER persists an agent output without explicit human approval:
approval/rejection buttons resume the paused LangGraph run (see
raia/pipeline.py). Rejections loop the agent with the reviewer's feedback.
"""

import streamlit as st

from raia import config
from raia.agents import AGENTS
from raia.pipeline import StageRunner
from raia.repository import ARTIFACT_FILES, ArtifactRepository

# ---------------------------------------------------------------------------
# Example inputs (the resume-screening scenario from the paper, Section 3.2)
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

# ---------------------------------------------------------------------------
# Session-level singletons
# ---------------------------------------------------------------------------


@st.cache_resource
def get_runner() -> StageRunner:
    """One StageRunner (and its LangGraph checkpointer) per server process."""
    return StageRunner()


def get_repo() -> ArtifactRepository:
    return ArtifactRepository(st.session_state["project"])


# ---------------------------------------------------------------------------
# Sidebar: project selection + pipeline status
# ---------------------------------------------------------------------------


def sidebar() -> str:
    """Render the sidebar; returns the chosen page name."""
    st.sidebar.title("RAIA")
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
            st.stop()
        st.session_state["project"] = name
    else:
        st.session_state["project"] = choice

    # Provider notice ------------------------------------------------------
    if config.LLM_PROVIDER == "mock":
        st.sidebar.warning(
            "Mock mode: outputs are canned. Set RAIA_LLM_PROVIDER=anthropic "
            "and an ANTHROPIC_API_KEY in .env for real analyses."
        )

    # Navigation with pipeline progress ------------------------------------
    repo = get_repo()
    done = set(repo.existing_artifacts())
    pages = ["🏠 Overview"]
    for key, agent in AGENTS.items():
        mark = "✅" if agent.spec.output_key in done else "▫️"
        pages.append(f"{mark} {agent.spec.name}")
    pages.append("📜 Audit Trail")

    page = st.sidebar.radio("Pipeline", pages, label_visibility="collapsed")
    # Strip the status emoji to recover the logical page name.
    return page.split(" ", 1)[1] if page[0] in "✅▫️🏠📜" else page


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


def page_overview() -> None:
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
    repo = get_repo()
    done = set(repo.existing_artifacts())
    cols = st.columns(len(AGENTS))
    for col, (key, agent) in zip(cols, AGENTS.items()):
        with col:
            ok = agent.spec.output_key in done
            st.metric(
                label=f"{LAYER_BADGES[agent.spec.layer]}",
                value=agent.spec.name,
                delta="approved" if ok else "pending",
                delta_color="normal" if ok else "off",
            )
    st.info(
        "Suggested walkthrough: use the **Load example** button on each agent "
        "page to explore the paper's resume-screening scenario end to end."
    )


def _review_widget(agent_key: str, payload: dict) -> None:
    """The human checkpoint UI: edit / approve / reject a pending draft."""
    st.subheader("🧑‍⚖️ Human review required")
    st.caption(
        f"Draft #{payload['attempt']} by **{payload['agent_name']}** — nothing is "
        "persisted until you approve. You may edit the text before approving."
    )
    edited = st.text_area("Draft (editable)", payload["draft"], height=420, key=f"edit_{agent_key}")

    approver = st.text_input(
        "Your name (recorded in the audit trail)", key=f"approver_{agent_key}", value="reviewer"
    )
    col_a, col_r = st.columns(2)
    with col_a:
        if st.button("✅ Approve & commit", type="primary", key=f"approve_{agent_key}"):
            result = get_runner().resume(
                st.session_state["project"], agent_key,
                {"action": "approve", "content": edited, "approver": approver},
            )
            st.session_state.pop(f"pending_{agent_key}", None)
            st.success(f"Artifact committed ({result.get('commit', '')}).")
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
    st.title(spec.name)
    st.caption(f"{LAYER_BADGES[spec.layer]} · SDLC phase: {spec.sdlc_phase}")
    st.markdown(spec.description)

    repo = get_repo()

    # Stage gate (Figure 1 ordering) ---------------------------------------
    missing = agent.missing_prerequisites(repo)
    if missing:
        names = ", ".join(f"`{m}`" for m in missing)
        st.error(
            f"⛔ Stage gate: approve the upstream artifact(s) {names} before "
            "running this agent."
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
    if st.button("📋 Load example (paper's resume-screening scenario)", key=f"ex_{agent_key}"):
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
    st.title("📜 Audit Trail")
    repo = get_repo()
    st.caption(f"Project workspace: `{repo.path}` (local Git repository)")

    st.subheader("Artifacts")
    existing = repo.existing_artifacts()
    if not existing:
        st.info("No approved artifacts yet.")
    for key in existing:
        with st.expander(f"{ARTIFACT_FILES[key]}"):
            st.markdown(repo.read_artifact(key))

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
    page = sidebar()

    if page == "Overview":
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
