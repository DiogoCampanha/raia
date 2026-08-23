#!/usr/bin/env python3
"""
app.py — RAIA Streamlit user interface.

Run with:
    streamlit run app.py

The UI is organized around the RAIA pipeline:

* an **Overview** page showing the five agents and the mandatory human
  approval gates ("H") that separate them;
* one page per agent, ordered by pipeline stage and grouped by layer
  (Product / Dev / Ops), each with its human-approval gate;
* an **Audit Trail** page showing artifacts and the Git commit history.

The UI NEVER persists an agent output without explicit human approval:
approval/rejection buttons resume the paused LangGraph run (see
raia/pipeline.py). Rejections loop the agent with the reviewer's feedback.

Built for zero-setup evaluation
-------------------------------
Testers only need the URL. Configuration comes from Streamlit secrets
(see raia/deploy.py), the RAG index self-builds on first startup, and every
browser session gets its own private, disposable artifact repository, so
concurrent testers never see or overwrite each other's work. If the
deployment is missing its API key the app says so plainly rather than
quietly serving canned text.
"""

import re
import uuid

import streamlit as st

# --- Configuration bridge (MUST run before importing raia.config) ----------
# On Streamlit Community Cloud there is no .env file: the maintainer pastes
# configuration into the app's Secrets box. raia.config snapshots the
# environment at import time, so secrets are copied into it first. Locally
# (no secrets.toml) this is a silent no-op and .env keeps working.
from raia.deploy import apply_secrets  # noqa: E402

apply_secrets()

from raia import config                                     # noqa: E402
from raia.agents import AGENTS                              # noqa: E402
from raia.deploy import friendly_llm_error, runtime_status  # noqa: E402
from raia.pipeline import StageRunner                       # noqa: E402
from raia.repository import ARTIFACT_FILES, ArtifactRepository  # noqa: E402

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

# Layer identity. These three hues are mid-tones chosen to stay legible on
# both the light and the dark Streamlit themes.
LAYER_COLORS = {"Product": "#3b82f6", "Dev": "#22c55e", "Ops": "#f97316"}
LAYER_BADGES = {"Product": "🟦 Product", "Dev": "🟩 Dev", "Ops": "🟧 Ops"}

# Status vocabulary, used identically by the sidebar and the pipeline figure.
STATUS_COLORS = {"approved": "#22c55e", "ready": "#3b82f6", "blocked": "#94a3b8"}
STATUS_LABELS = {
    "approved": "Approved",
    "ready": "Ready to run",
    "blocked": "Awaiting upstream",
}
STATUS_ICONS = {"approved": "✅", "ready": "▶️", "blocked": "🔒"}

# Maps artifact keys to the agent that produces them (for friendly gate messages).
PRODUCER_OF = {agent.spec.output_key: agent.spec.name for agent in AGENTS.values()}


# ---------------------------------------------------------------------------
# Per-tester session workspace
# ---------------------------------------------------------------------------


def session_project() -> str:
    """Return this browser session's private project id.

    The hosted deployment is evaluated by several people at the same URL at
    the same time. Each session therefore gets its own artifact repository:
    testers never see, block, or overwrite one another's work, and nobody has
    to invent a project name before starting.

    The id is mirrored into the URL query string so an accidental page
    refresh returns the tester to their own workspace instead of a blank one.
    """
    sid = st.session_state.get("sid")
    if sid:
        return f"session-{sid}"

    raw = str(st.query_params.get("s", ""))
    if not re.fullmatch(r"[0-9a-f]{12}", raw):
        raw = uuid.uuid4().hex[:12]
        st.query_params["s"] = raw
    st.session_state["sid"] = raw
    return f"session-{raw}"


def reset_session() -> None:
    """Discard this tester's workspace and start a clean one."""
    try:
        ArtifactRepository(session_project()).reset()
    except Exception:  # noqa: BLE001 - a failed cleanup must not block the reset
        pass
    for key in list(st.session_state):
        del st.session_state[key]
    # Dropping the id retires the old LangGraph threads too, so no paused
    # draft can leak into the fresh walkthrough.
    st.query_params.clear()
    st.session_state["flash"] = "Fresh workspace ready — the walkthrough is reset."


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
    """One StageRunner (and its LangGraph checkpointer) per server process.

    Shared safely across concurrent testers because every graph thread is
    keyed by ``(project, agent)`` and each session has its own project.
    """
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
    return ArtifactRepository(session_project())


def _agent_status(agent, repo, done: set) -> str:
    if agent.spec.output_key in done:
        return "approved"
    if agent.missing_prerequisites(repo):
        return "blocked"
    return "ready"


# ---------------------------------------------------------------------------
# The pipeline figure
# ---------------------------------------------------------------------------

# One stylesheet, injected with the figure. Design constraints:
#   * theme-proof -- no hard-coded text or surface colours; text inherits the
#     Streamlit theme's foreground and depth comes from translucent greys, so
#     the figure is legible on both the light and the dark themes;
#   * never truncated -- the layout is a *container* query, so the five
#     stages sit in a row only when the content area is genuinely wide enough
#     for the agent names, and stack vertically otherwise (which is also what
#     happens on a phone);
#   * aligned -- stretched cards with bottom-pinned status lines, so the five
#     stages read as one row however long a name or SDLC phase runs.
PIPELINE_CSS = """
<style>
.raia-wrap { container-type: inline-size; margin: .1rem 0 .35rem; }
.raia-flow { display: flex; flex-direction: column; gap: .1rem; }

.raia-stage {
  border: 1px solid rgba(128,128,128,.28);
  border-top: 3px solid var(--raia-accent);
  border-radius: 12px;
  background: rgba(128,128,128,.06);
  padding: .6rem .8rem .7rem;
  display: flex; flex-direction: column; gap: .25rem;
  overflow-wrap: break-word; hyphens: none;
}
.raia-stage.is-blocked { opacity: .6; }

.raia-head { display: flex; align-items: center; gap: .4rem; }
.raia-dot { width: .55rem; height: .55rem; border-radius: 50%;
            background: var(--raia-accent); flex: 0 0 auto; }
.raia-layer { font-size: .68rem; font-weight: 700; letter-spacing: .07em;
              text-transform: uppercase; opacity: .75; }
.raia-num { margin-left: auto; font-size: .72rem; font-weight: 700; opacity: .45; }
.raia-name { font-weight: 700; font-size: 1rem; line-height: 1.25; }
.raia-phase { font-size: .74rem; line-height: 1.3; opacity: .6; }
.raia-status { display: flex; align-items: center; gap: .38rem;
               font-size: .78rem; font-weight: 600; margin-top: .15rem; }
.raia-sdot { width: .5rem; height: .5rem; border-radius: 50%;
             background: var(--raia-state); flex: 0 0 auto; }

.raia-gate { position: relative; display: flex; align-items: center;
             gap: .5rem; padding: .1rem 0 .1rem 1.15rem; }
.raia-h { width: 1.55rem; height: 1.55rem; border-radius: 50%; flex: 0 0 auto;
          border: 2px solid currentColor; opacity: .8;
          display: flex; align-items: center; justify-content: center;
          font-size: .78rem; font-weight: 800; line-height: 1; }
.raia-gate-label { font-size: .72rem; font-weight: 600; opacity: .6; }

.raia-legend { font-size: .8rem; opacity: .7; margin-top: .55rem; line-height: 1.5; }

/* Wide content area: lay the pipeline out left-to-right.
   `align-items: stretch` equalises the card heights and `margin-top: auto`
   pins every status line to the bottom, so the five stages read as one row
   however many lines an agent's name or SDLC phase happens to take. */
@container (min-width: 820px) {
  .raia-flow { flex-direction: row; align-items: stretch; gap: 0; }
  .raia-stage { flex: 1 1 0; min-width: 0; padding: .6rem .7rem .65rem; }
  .raia-name { font-size: .95rem; }
  .raia-status { margin-top: auto; padding-top: .35rem; }
  .raia-gate { flex: 0 0 auto; padding: 0 .35rem; }
  .raia-gate-label { display: none; }
  .raia-gate::before, .raia-gate::after {
    content: ""; position: absolute; top: 50%; height: 1px; width: .35rem;
    background: rgba(128,128,128,.4);
  }
  .raia-gate::before { left: 0; }
  .raia-gate::after { right: 0; }
}

/* The three-layer strip above the pipeline. */
.raia-layers { display: flex; flex-wrap: wrap; gap: .6rem; }
.raia-layer-card {
  flex: 1 1 230px; border: 1px solid rgba(128,128,128,.28);
  border-top: 3px solid var(--raia-accent); border-radius: 12px;
  background: rgba(128,128,128,.06); padding: .7rem .85rem .8rem;
}
.raia-blurb { font-size: .88rem; line-height: 1.45; margin-top: .25rem; }
.raia-members { font-size: .78rem; opacity: .6; margin-top: .4rem; }
</style>
"""


def _stage_card(index: int, agent, status: str) -> str:
    accent = LAYER_COLORS[agent.spec.layer]
    state = STATUS_COLORS[status]
    blocked = " is-blocked" if status == "blocked" else ""
    return f"""<div class="raia-stage{blocked}" style="--raia-accent:{accent};--raia-state:{state};">
  <div class="raia-head">
    <span class="raia-dot"></span>
    <span class="raia-layer">{agent.spec.layer}</span>
    <span class="raia-num">{index}</span>
  </div>
  <div class="raia-name">{agent.spec.name}</div>
  <div class="raia-phase">{agent.spec.sdlc_phase}</div>
  <div class="raia-status"><span class="raia-sdot"></span>{STATUS_LABELS[status]}</div>
</div>"""


_GATE = """<div class="raia-gate" title="Mandatory human approval gate">
  <span class="raia-h">H</span><span class="raia-gate-label">human approval gate</span>
</div>"""


def pipeline_figure(repo) -> str:
    """The RAIA pipeline: five agent cards separated by the H gates."""
    done = set(repo.existing_artifacts())
    cards = [
        _stage_card(i, agent, _agent_status(agent, repo, done))
        for i, agent in enumerate(AGENTS.values(), start=1)
    ]
    return (
        PIPELINE_CSS
        + '<div class="raia-wrap"><div class="raia-flow">'
        + _GATE.join(cards)
        + "</div>"
        + '<div class="raia-legend"><strong>H</strong> = mandatory human approval '
        + "gate. Nothing advances to the next stage until you review and approve "
        + "it, and no agent ever triggers another one.</div></div>"
    )


def layer_cards() -> str:
    """The three RAIA layers, as an intro strip above the pipeline."""
    blurbs = {
        "Product": "Risk classification and ethical value requirements, at conception time.",
        "Dev": "Ethical acceptance criteria and accountability audits, inside sprints.",
        "Ops": "Fairness-drift monitoring, after deployment.",
    }
    cards = []
    for layer, blurb in blurbs.items():
        members = " · ".join(a.spec.name for a in AGENTS.values() if a.spec.layer == layer)
        cards.append(
            f"""<div class="raia-layer-card" style="--raia-accent:{LAYER_COLORS[layer]};">
  <div class="raia-head"><span class="raia-dot"></span>
    <span class="raia-layer">{layer}</span></div>
  <div class="raia-blurb">{blurb}</div>
  <div class="raia-members">{members}</div>
</div>"""
        )
    return '<div class="raia-layers">' + "".join(cards) + "</div>"


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def sidebar(status) -> str:
    """Render the sidebar; returns the chosen page name."""
    st.sidebar.title("🛡️ RAIA")
    st.sidebar.caption("Responsible AI Assistant — multi-agent PoC")

    if status.explicit_mock:
        st.sidebar.warning(
            "🧪 **Mock mode is on.** Agent outputs are canned placeholders — "
            "no model is being called. Maintainers: remove the "
            "`RAIA_LLM_PROVIDER` line from the app's secrets to run for real."
        )
    else:
        st.sidebar.caption(f"🟢 Connected · `{status.model}`")

    repo = get_repo()
    done = set(repo.existing_artifacts())
    n_done = sum(1 for a in AGENTS.values() if a.spec.output_key in done)
    st.sidebar.progress(
        n_done / len(AGENTS), text=f"{n_done}/{len(AGENTS)} stages approved"
    )

    layer_dot = {"Product": "🟦", "Dev": "🟩", "Ops": "🟧"}
    pages = {"🏠 Overview": "Overview"}
    for agent in AGENTS.values():
        mark = STATUS_ICONS[_agent_status(agent, repo, done)]
        pages[f"{mark} {layer_dot[agent.spec.layer]} {agent.spec.name}"] = agent.spec.name
    pages["📜 Audit Trail"] = "Audit Trail"

    label = st.sidebar.radio("Pipeline", list(pages), label_visibility="collapsed")
    st.sidebar.caption("✅ approved · ▶️ ready · 🔒 awaiting upstream approval")

    st.sidebar.divider()
    st.sidebar.caption(
        "This is your own private workspace. Other testers cannot see it, and "
        "it is discarded when the app restarts."
    )
    if st.sidebar.button("🔄 Start over", help="Erase this workspace and begin again"):
        reset_session()
        st.rerun()

    return pages[label]


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


def page_not_configured(status) -> None:
    """Shown instead of the app when no usable model credential is present.

    RAIA deliberately does NOT fall back to canned output here: a tester who
    could not tell mock text from a real analysis would end up evaluating the
    wrong artifact.
    """
    st.title("🛡️ RAIA")
    st.error(
        "**This deployment is not fully configured yet, so the agents cannot "
        "run.** Nothing is wrong on your side — please let the study "
        "coordinator know you saw this screen."
    )
    st.caption(status.problem or "")
    with st.expander("Maintainer setup (2 minutes)"):
        st.markdown(
            f"""
Open the app on **share.streamlit.io → ⋮ → Settings → Secrets**, paste the
line below, and click **Save**. The app restarts on its own.

```toml
{status.key_env_var or "ANTHROPIC_API_KEY"} = "sk-..."
```

That is the whole setup — no `.env` file, no redeploy, no code change.
Optional overrides:

```toml
RAIA_LLM_MODEL    = "{config.LLM_MODEL}"   # any Claude / GPT model id
RAIA_LLM_PROVIDER = "anthropic"            # or "openai", or "mock" for canned output
```

An `OPENAI_API_KEY` on its own also works: the provider switches to OpenAI
automatically.
"""
        )


def page_overview() -> None:
    _flash()
    st.title("RAIA — Responsible AI Assistant")
    st.markdown(
        """
RAIA helps development teams apply **Responsible AI** across the software
life cycle. **Five specialized agents**, organized in three layers, analyze
your project and draft recommendations grounded via RAG in four consolidated
frameworks (IEEE 7000, NIST AI RMF, Microsoft RAI Standard v2, ECCOLA) and
two legal texts (EU AI Act, Brazilian PL 2338/2023).

Two design principles you will notice everywhere:

- **You are the checkpoint.** No agent output is saved until you review and
  approve it, and no agent ever triggers another one.
- **Everything is cited and versioned.** Every claim carries a tag pointing
  to the norm excerpt that grounds it, and every approval becomes a Git
  commit in your audit trail.
"""
    )

    st.subheader("Three layers")
    st.markdown(PIPELINE_CSS + layer_cards(), unsafe_allow_html=True)

    st.subheader("Five stages, five human gates")
    st.markdown(pipeline_figure(get_repo()), unsafe_allow_html=True)

    st.info(
        "**Start here (~15 min):** open **▶️ 🟦 Risk Classifier** in the "
        "sidebar, press **Load example** to fill in a resume-screening "
        "scenario, and run it. Then work down the sidebar approving each "
        "stage, and finish at the **📜 Audit Trail**."
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
                    session_project(), agent_key,
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
                try:
                    result = get_runner().resume(
                        session_project(), agent_key,
                        {"action": "reject", "feedback": feedback or "Please revise."},
                    )
                except Exception as exc:  # noqa: BLE001 - surfaced to the tester
                    st.error(friendly_llm_error(exc))
                    return
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
            try:
                result = get_runner().start(session_project(), agent_key, inputs)
            except Exception as exc:  # noqa: BLE001 - surfaced to the tester
                st.error(friendly_llm_error(exc))
                return
        if result["status"] == "awaiting_review":
            st.session_state[f"pending_{agent_key}"] = result["payload"]
            st.rerun()


def page_audit_trail() -> None:
    _flash()
    st.title("📜 Audit Trail")
    repo = get_repo()
    st.caption(
        "Every artifact below is a file in a Git repository, and every "
        "approval is a commit. This is your session's own repository."
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

    status = runtime_status()
    if not status.ready:
        page_not_configured(status)
        return

    # Self-bootstrap the RAG index (no-op if already built).
    with st.spinner("Preparing the normative knowledge base (first start only)…"):
        ensure_normative_index()

    page = sidebar(status)

    if page == "Overview":
        page_overview()
    elif page == "Audit Trail":
        page_audit_trail()
    else:
        for key, agent in AGENTS.items():
            if agent.spec.name == page:
                page_agent(key)
                break


if __name__ == "__main__":
    main()
