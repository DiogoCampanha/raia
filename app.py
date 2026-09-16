#!/usr/bin/env python3
"""
app.py — RAIA Streamlit user interface.

Run with:
    streamlit run app.py

The UI is organized around **projects**. A person signs in, lands on *My
projects*, and opens one; everything below the project switcher then belongs
to that project alone:

* an **Overview** page showing the five agents, the mandatory human approval
  gates ("H") that separate them, and where this project stands;
* one page per agent, ordered by pipeline stage and grouped by layer
  (Product / Dev / Ops), each with a structured intake form and its human
  approval gate;
* an **Open Issues** page — the register of conflicts the system refused to
  resolve on its own;
* an **Audit Trail** page showing artifacts, provenance and version history;
* a **People & settings** page for inviting collaborators and reviewers.

Two pages sit outside any project: **Rate your experience**, where a person
evaluates every stage in one go, and **My projects**.

Two things shape every screen here.

**The questions are asked, not inferred.** Each agent declares typed fields —
selects, multi-selects, yes/no, uploads — and a rule engine reads them. A field
exists because something in the code consumes it, so filling the form in is
what produces the verdict rather than a prompt guessing at prose.

**The gate shows its evidence.** A reviewer is never asked to approve a claim
with the grounds hidden: the draft arrives alongside the excerpts that were
retrieved, the facts the rule engine computed, and the result of every
automated check. Nothing is persisted until a signed-in person approves it,
and the approval is recorded under that person's verified identity.

Access control does not live here. Every project operation goes through
:class:`raia.projects.ProjectService`, which refuses what a person's role does
not allow; this module only decides what to show.
"""

import json
from typing import Any, Dict, List, Optional

import streamlit as st

# --- Configuration bridge (MUST run before importing raia.config) ----------
from raia.deploy import apply_secrets  # noqa: E402

apply_secrets()

from raia import auth, config                               # noqa: E402
from raia.agents import AGENTS                              # noqa: E402
from raia.deploy import friendly_llm_error, runtime_status  # noqa: E402
from raia.examples import EXAMPLES                          # noqa: E402
from raia.export import bundle_name, session_bundle         # noqa: E402
from raia.fields import InputField                          # noqa: E402
from raia.pipeline import StageRunner                       # noqa: E402
from raia.projects import (                                 # noqa: E402
    EDITOR,
    OWNER,
    REVIEWER,
    ROLE_LABELS,
    AccessDenied,
    Project,
    ProjectService,
    UsageLimitReached,
    User,
)
from raia.repository import ACCEPTED, ARTIFACT_FILES, OPEN, RESOLVED  # noqa: E402

# Layer identity. Mid-tones chosen to stay legible on light and dark themes.
LAYER_COLORS = {"Product": "#3b82f6", "Dev": "#22c55e", "Ops": "#f97316"}
LAYER_BADGES = {"Product": "🟦 Product", "Dev": "🟩 Dev", "Ops": "🟧 Ops"}

STATUS_COLORS = {"approved": "#22c55e", "in_review": "#a855f7", "ready": "#3b82f6", "blocked": "#94a3b8"}
STATUS_LABELS = {"approved": "Approved", "in_review": "Awaiting review", "ready": "Ready to run",
                 "blocked": "Awaiting upstream"}
STATUS_ICONS = {"approved": "✅", "in_review": "🧑‍⚖️", "ready": "▶️", "blocked": "🔒"}

CHECK_ICON = {"pass": "✅", "warn": "⚠️", "fail": "❌"}

#: Structured reasons a reviewer can give when rejecting a draft. Free text
#: alone cannot be counted; these can, which is what turns an evaluation
#: session into data rather than a recollection.
REJECTION_REASONS = [
    ("wrong_verdict", "The classification or verdict is wrong"),
    ("missing", "Something important is missing"),
    ("unsupported", "A claim is unsupported or wrongly cited"),
    ("too_vague", "Too vague to act on"),
    ("wrong_context", "Does not fit how we actually work"),
    ("too_long", "Too long to review properly"),
    ("other", "Something else"),
]

PRODUCER_OF = {agent.spec.output_key: agent.spec.name for agent in AGENTS.values()}





PAGE_PROJECTS = "projects"
PAGE_RATE = "rate"
PAGE_ACCOUNT = "account"
PAGE_RESEARCH = "research"
PAGE_OVERVIEW = "overview"
PAGE_ISSUES = "issues"
PAGE_AUDIT = "audit"
PAGE_PEOPLE = "people"
GLOBAL_PAGES = {PAGE_PROJECTS, PAGE_RATE, PAGE_ACCOUNT, PAGE_RESEARCH}


# ---------------------------------------------------------------------------
# Who is here, and which project they are in
# ---------------------------------------------------------------------------


@st.cache_resource
def get_runner() -> StageRunner:
    """One StageRunner (and its graph checkpointer) per server process."""
    return StageRunner()


@st.cache_resource
def get_service() -> ProjectService:
    """One project service per server process (it holds the database pool)."""
    return ProjectService(runner=get_runner())


@st.cache_resource
def ensure_normative_index() -> bool:
    """Self-bootstrap the RAG index on hosted platforms."""
    from raia.rag import index_exists, ingest_corpus

    if not index_exists():
        ingest_corpus(verbose=False)
    return True


def current_user() -> User:
    return st.session_state["_user"]


def active_project() -> Optional[Project]:
    """The project this browser session is working in, re-checked every run.

    Membership is looked up again on every rerun rather than cached, so a
    person removed from a project loses access on their next click.
    """
    pid = st.session_state.get("project_id")
    if not pid:
        return None
    try:
        return get_service().get_project(current_user(), pid)
    except AccessDenied:
        st.session_state.pop("project_id", None)
        st.session_state["page"] = PAGE_PROJECTS
        return None


def project() -> Project:
    p = active_project()
    if p is None:
        raise AccessDenied("No project is open.")
    return p


def pkey(*parts: str) -> str:
    """Widget/session key scoped to the open project.

    Two projects open one after the other in the same browser must never share
    a draft, a form answer or a half-typed rejection note.
    """
    return "::".join([st.session_state.get("project_id", "-"), *parts])


def get_repo():
    return get_service().repository(current_user(), project().id, "view")


def go(page: str, project_id: Optional[str] = None) -> None:
    """Navigation callback."""
    if project_id is not None:
        st.session_state["project_id"] = project_id
    st.session_state["page"] = page
    pid = st.session_state.get("project_id")
    if pid:
        nav_key = f"{pid}::nav"
        st.session_state[nav_key] = None if page in GLOBAL_PAGES else page


def _flash() -> None:
    msg = st.session_state.pop("flash", None)
    if msg:
        st.success(msg)


def _next_step_hint(agent_key: str) -> str:
    keys = list(AGENTS)
    i = keys.index(agent_key)
    if i + 1 < len(keys):
        return f"Next stage: **{AGENTS[keys[i + 1]].spec.name}** (sidebar)."
    return ("Pipeline complete — see the **📜 Audit Trail** for the full history, and please "
            "**⭐ rate your experience** when you are done.")


def _agent_status(agent, repo, done: set, pending: Optional[set] = None) -> str:
    if agent.spec.output_key in done:
        return "approved"
    if pending is None:
        pending = set(repo.pending_agents())
    if agent.spec.key in pending:
        return "in_review"
    if agent.missing_prerequisites(repo):
        return "blocked"
    return "ready"


def _role_badge(role: str) -> str:
    return {OWNER: "👑 owner", EDITOR: "✏️ editor", REVIEWER: "🔍 reviewer"}.get(role, role)


# ---------------------------------------------------------------------------
# The pipeline figure
# ---------------------------------------------------------------------------

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

.raia-layers { display: flex; flex-wrap: wrap; gap: .6rem; }
.raia-layer-card {
  flex: 1 1 230px; border: 1px solid rgba(128,128,128,.28);
  border-top: 3px solid var(--raia-accent); border-radius: 12px;
  background: rgba(128,128,128,.06); padding: .7rem .85rem .8rem;
}
.raia-blurb { font-size: .88rem; line-height: 1.45; margin-top: .25rem; }
.raia-members { font-size: .78rem; opacity: .6; margin-top: .4rem; }

.raia-turn { display: flex; flex-wrap: wrap; gap: .4rem; margin: .3rem 0 .2rem; }
.raia-step { flex: 1 1 150px; border: 1px solid rgba(128,128,128,.25);
             border-left: 3px solid var(--raia-accent); border-radius: 8px;
             background: rgba(128,128,128,.05); padding: .5rem .65rem .6rem; }
.raia-step-k { font-size: .64rem; font-weight: 700; letter-spacing: .08em;
               text-transform: uppercase; opacity: .65; }
.raia-step-n { font-weight: 700; font-size: .88rem; margin-top: .1rem; }
.raia-step-d { font-size: .78rem; opacity: .72; line-height: 1.4; margin-top: .15rem; }
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


TURN_STEPS = [
    ("Deterministic", "Structured intake", "Typed questions whose answers a rule reads."),
    ("Deterministic", "Rule engine", "Computes the verdict, the tables and the required excerpts."),
    ("Generative", "Model pass", "Justifies, handles judgement calls, writes for humans."),
    ("Deterministic", "Automated checks", "Citations, structure, coverage, reconciliation."),
    ("Human", "Approval gate", "You decide, with the evidence in front of you."),
]


def turn_figure() -> str:
    colors = ["#3b82f6", "#3b82f6", "#a855f7", "#f59e0b", "#22c55e"]
    cards = "".join(
        f"""<div class="raia-step" style="--raia-accent:{c};">
  <div class="raia-step-k">{k}</div><div class="raia-step-n">{n}</div>
  <div class="raia-step-d">{d}</div></div>"""
        for (k, n, d), c in zip(TURN_STEPS, colors)
    )
    return PIPELINE_CSS + f'<div class="raia-turn">{cards}</div>'


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


SIDEBAR_CSS = """
<style>
section[data-testid="stSidebar"] div.raia-rate-note {
  font-size: .78rem; opacity: .75; margin: -.35rem 0 .4rem; text-align: center;
}
</style>
"""


def sidebar(status) -> str:
    user = current_user()
    svc = get_service()
    st.sidebar.title("🛡️ RAIA")
    st.sidebar.caption("Responsible AI Assistant")

    if status.explicit_mock:
        st.sidebar.warning(
            "🧪 **Mock mode is on.** Agent outputs are canned placeholders — "
            "no model is being called. Maintainers: remove the "
            "`RAIA_LLM_PROVIDER` line from the app's secrets to run for real."
        )
    else:
        st.sidebar.caption(f"🟢 Connected · `{status.model}`")

    # The study's evaluation, set apart from any project and deliberately loud.
    st.sidebar.markdown(SIDEBAR_CSS, unsafe_allow_html=True)
    rated = svc.my_latest_rating(user) is not None
    st.sidebar.button(
        "⭐ Rate your experience" if not rated else "⭐ Update your rating",
        type="primary", use_container_width=True, on_click=go, args=(PAGE_RATE,),
        key="nav_rate",
    )
    st.sidebar.markdown(
        '<div class="raia-rate-note">'
        + ("All five stages in one form · about 3 minutes" if not rated
           else "Thank you — you can revise it any time")
        + "</div>",
        unsafe_allow_html=True,
    )

    st.sidebar.divider()
    projects = svc.list_projects(user)
    invites = svc.my_invitations(user)
    st.sidebar.button(
        "🗂️ My projects" + (f"  ·  {len(invites)} invitation(s)" if invites else ""),
        use_container_width=True, on_click=go, args=(PAGE_PROJECTS,), key="nav_projects",
    )

    page = st.session_state.get("page", PAGE_PROJECTS)
    current = active_project()

    if projects:
        ids = [p.id for p in projects]
        names = {p.id: p.name for p in projects}
        if current and current.id not in names:  # archived but open
            ids.insert(0, current.id)
            names[current.id] = current.name + " (archived)"

        def _switch() -> None:
            chosen = st.session_state.get("project_switch")
            if chosen:
                go(PAGE_OVERVIEW, chosen)

        if current:
            st.session_state["project_switch"] = current.id
        else:
            st.session_state.setdefault("project_switch", None)
        st.sidebar.selectbox(
            "Project", ids, format_func=lambda i: names.get(i, i), key="project_switch",
            on_change=_switch, placeholder="Open a project…",
        )

    if current is None:
        _account_block(user)
        return page if page in GLOBAL_PAGES else PAGE_PROJECTS

    repo = get_repo()
    done = set(repo.existing_artifacts())
    pending = set(repo.pending_agents())
    n_done = sum(1 for a in AGENTS.values() if a.spec.output_key in done)
    st.sidebar.caption(f"{_role_badge(current.role)} on this project")
    st.sidebar.progress(n_done / len(AGENTS), text=f"{n_done}/{len(AGENTS)} stages approved")

    layer_dot = {"Product": "🟦", "Dev": "🟩", "Ops": "🟧"}
    open_count = sum(1 for i in repo.open_issues() if i.get("status") == OPEN)
    labels: Dict[str, str] = {PAGE_OVERVIEW: "🏠 Overview"}
    for agent in AGENTS.values():
        mark = STATUS_ICONS[_agent_status(agent, repo, done, pending)]
        labels[agent.spec.key] = f"{mark} {layer_dot[agent.spec.layer]} {agent.spec.name}"
    labels[PAGE_ISSUES] = f"⚖️ Open Issues ({open_count})" if open_count else "⚖️ Open Issues"
    labels[PAGE_AUDIT] = "📜 Audit Trail"
    labels[PAGE_PEOPLE] = "👥 People & settings"

    # Options are stable page ids and only the *labels* change as work
    # progresses, so approving a stage no longer resets the selection.
    nav_key = f"{current.id}::nav"
    if nav_key not in st.session_state:
        st.session_state[nav_key] = page if page in labels else (
            None if page in GLOBAL_PAGES else PAGE_OVERVIEW)

    def _nav() -> None:
        chosen = st.session_state.get(nav_key)
        if chosen:
            st.session_state["page"] = chosen

    st.sidebar.radio("Pipeline", list(labels), format_func=labels.get, key=nav_key,
                     on_change=_nav, label_visibility="collapsed")
    st.sidebar.caption("✅ approved · 🧑‍⚖️ awaiting review · ▶️ ready · 🔒 awaiting upstream")

    st.sidebar.download_button(
        "⬇ Export this project",
        data=session_bundle(repo, current.name),
        file_name=bundle_name(current.name),
        mime="application/zip",
        help="Artifacts, structured records, version history and pseudonymized events, in one zip.",
        use_container_width=True,
    )
    _account_block(user)

    if page in GLOBAL_PAGES:
        return page
    return page if page in labels else PAGE_OVERVIEW


def _account_block(user: User) -> None:
    st.sidebar.divider()
    with st.sidebar.expander(f"👤 {user.name or user.email}"):
        st.caption(user.email)
        if user.is_admin:
            st.button("📊 Research data", on_click=go, args=(PAGE_RESEARCH,),
                      use_container_width=True, key="nav_research")
        st.button("Account & privacy", on_click=go, args=(PAGE_ACCOUNT,),
                  use_container_width=True, key="nav_account")
        if auth.mode() != "dev":
            if st.button("Log out", use_container_width=True, key="logout"):
                for k in list(st.session_state):
                    del st.session_state[k]
                auth.logout()


# ---------------------------------------------------------------------------
# Structured intake form
# ---------------------------------------------------------------------------


def _state_key(agent_key: str, field_key: str) -> str:
    return pkey("in", agent_key, field_key)


def _current_inputs(agent_key: str, fields: List[InputField]) -> Dict[str, Any]:
    """What the form currently holds — used to evaluate conditional visibility."""
    out: Dict[str, Any] = {}
    for f in fields:
        value = st.session_state.get(_state_key(agent_key, f.key))
        if value is None:
            value = [] if f.is_multi else (f.default or "")
        out[f.key] = value
    return out


def _render_field(agent_key: str, f: InputField, disabled: bool) -> Any:
    key = _state_key(agent_key, f.key)
    label = f.label + (" *" if f.required else "")

    if f.kind == "textarea":
        return st.text_area(label, key=key, help=f.help, height=f.height,
                            placeholder=f.placeholder, disabled=disabled)
    if f.kind == "text":
        return st.text_input(label, key=key, help=f.help, placeholder=f.placeholder,
                             disabled=disabled)
    if f.kind == "number":
        return st.number_input(label, key=key, help=f.help, step=1, disabled=disabled)
    if f.kind in ("select", "boolean"):
        values = [o.value for o in f.options]
        if key not in st.session_state and f.default in values:
            st.session_state[key] = f.default
        if f.kind == "boolean":
            return st.radio(label, values, key=key, help=f.help,
                            format_func=f.label_for, horizontal=True, disabled=disabled)
        return st.selectbox(label, values, key=key, help=f.help, format_func=f.label_for,
                            index=None, placeholder="Choose one…", disabled=disabled)
    if f.kind == "multiselect":
        return st.multiselect(label, [o.value for o in f.options], key=key, help=f.help,
                              format_func=f.label_for, placeholder="Choose all that apply…",
                              disabled=disabled)
    if f.kind in ("csv", "file"):
        if not disabled:
            upload = st.file_uploader(
                label, key=pkey("up", agent_key, f.key), help=f.help,
                type=list(f.file_types) or None,
            )
            if upload is not None:
                try:
                    st.session_state[key] = upload.getvalue().decode("utf-8", errors="replace")
                    st.caption(f"Loaded **{upload.name}** ({len(st.session_state[key]):,} characters).")
                except Exception:  # noqa: BLE001 - surfaced to the tester
                    st.error("That file could not be read as text. Export it as CSV or plain text.")
        if f.kind == "csv":
            return st.text_area("…or paste the rows" if not disabled else label, key=key,
                                height=f.height, placeholder=f.placeholder, disabled=disabled)
        return st.session_state.get(key, "")
    return st.text_area(label, key=key, help=f.help, height=f.height, disabled=disabled)


def _load_saved_intake(spec) -> None:
    """Fill the form from the project's saved answers, once per session."""
    flag = pkey("loaded", spec.key)
    if flag in st.session_state:
        return
    saved = get_service().load_intake(current_user(), project().id, spec.key)
    for f in spec.input_fields:
        value = saved.get(f.key)
        if value in (None, "", []):
            continue
        if f.options and not f.is_multi and value not in [o.value for o in f.options]:
            continue
        st.session_state[_state_key(spec.key, f.key)] = value
    st.session_state[flag] = True
    st.session_state[pkey("saved", spec.key)] = _snapshot(spec)


def _snapshot(spec) -> Dict[str, Any]:
    out = {}
    for f in spec.input_fields:
        value = st.session_state.get(_state_key(spec.key, f.key))
        if value not in (None, "", []):
            out[f.key] = value
    return out


def _autosave_intake(spec) -> None:
    """Keep the project's answers on the server as they are typed.

    Answers belong to the project, not to the browser: they survive switching
    projects, signing out, and a teammate opening the same stage.
    """
    snap = _snapshot(spec)
    if snap != st.session_state.get(pkey("saved", spec.key)):
        get_service().save_intake(current_user(), project().id, spec.key, snap)
        st.session_state[pkey("saved", spec.key)] = snap


def intake_form(agent, can_run: bool) -> Dict[str, Any]:
    """Render the agent's typed fields, grouped, honouring conditional visibility."""
    spec = agent.spec
    _load_saved_intake(spec)
    if spec.intro:
        st.info(spec.intro)
    if not can_run:
        st.caption("🔍 You are a reviewer on this project: you can read the inputs, but only "
                   "owners and editors change them and run agents.")
    elif st.button("📋 Load example (resume-screening scenario)", key=pkey("ex", spec.key)):
        for f in spec.input_fields:
            value = EXAMPLES.get(spec.key, {}).get(f.key)
            if value is not None:
                st.session_state[_state_key(spec.key, f.key)] = value
        st.rerun()

    for group in spec.field_groups():
        fields = [f for f in spec.input_fields if f.group == group]
        current = _current_inputs(spec.key, spec.input_fields)
        visible = [f for f in fields if f.visible(current)]
        if not visible:
            continue
        st.markdown(f"##### {group}")
        for f in visible:
            _render_field(spec.key, f, disabled=not can_run)

    if can_run:
        _autosave_intake(spec)
        st.caption("💾 Answers are saved to this project as you type.")

    current = _current_inputs(spec.key, spec.input_fields)
    return {f.key: current[f.key] for f in spec.input_fields if f.visible(current)}


# ---------------------------------------------------------------------------
# The human approval gate
# ---------------------------------------------------------------------------


def _validation_panel(validation: Dict[str, Any]) -> None:
    items = validation.get("items") or []
    if not items:
        return
    level = validation.get("level", "pass")
    headline = validation.get("headline", "")
    box = st.error if level == "fail" else (st.warning if level == "warn" else st.success)
    box(f"**Automated checks — {headline}**")
    with st.expander("What was checked", expanded=level == "fail"):
        for item in items:
            st.markdown(
                f"{CHECK_ICON.get(item['level'], '•')} **{item['title']}** — {item['detail']}"
            )
            for sub in item.get("items", [])[:12]:
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;• `{sub}`")
        st.caption(
            "Checks inform; they never block. A failed check on an otherwise sound draft "
            "is a reason to look closely, not a reason for the software to overrule you."
        )


def _evidence_panel(evidence: List[Dict[str, Any]]) -> None:
    if not evidence:
        st.caption("No excerpts were retrieved for this run.")
        return
    pinned = [e for e in evidence if e.get("pinned")]
    st.caption(
        f"{len(evidence)} excerpt(s) were in the prompt, {len(pinned)} of them required by the "
        "decision procedure. Every citation in the draft is checked against exactly this set."
    )
    for e in evidence:
        badge = "📌 " if e.get("pinned") else ""
        title = f"{badge}{e['source_name'] if 'source_name' in e else e['source']} — {e['section']}"
        with st.expander(f"{title}  ·  _{e['authority']}_"):
            if e.get("pinned") and e.get("pin_reason"):
                st.caption(f"Required by the decision procedure: {e['pin_reason']}")
            if e.get("derived"):
                st.caption(
                    "⚠️ This text is a curated summary prepared for the project, not the "
                    "official source. Verify anything consequential against the original."
                )
            st.markdown(f"`{e['citation']}`")
            st.text(e["text"])


def review_gate(agent_key: str, payload: Dict[str, Any]) -> None:
    """The human checkpoint UI: evidence, checks, edit, approve or reject."""
    user = current_user()
    proj = project()
    svc = get_service()

    st.subheader("🧑‍⚖️ Human review required")
    ran_by = payload.get("run_by_name")
    st.caption(
        f"Draft #{payload.get('attempt', 1)} by **{payload['agent_name']}**"
        + (f", run by {ran_by}" if ran_by else "")
        + " — nothing is persisted until it is approved. You may edit the text before approving."
    )
    if payload.get("restored"):
        st.info(
            "This review was restored after the app restarted. The draft is exactly as it was; "
            "approving it still goes through the normal gate."
        )
    if payload.get("sanitization"):
        st.warning(
            "**Input sanitization notice** — patterns often used for prompt injection were "
            "found in the inputs: " + "; ".join(payload["sanitization"])
        )

    _validation_panel(payload.get("validation") or {})

    tab_read, tab_edit, tab_evidence, tab_reason = st.tabs(
        ["📖 Rendered draft", "✏️ Edit before approving", "📚 Evidence", "🧮 What the code computed"]
    )
    with tab_edit:
        edited = st.text_area(
            "Draft (Markdown, editable)", payload["draft"], height=460,
            key=pkey("edit", agent_key, str(payload.get("attempt", 1))),
        )
    with tab_read:
        st.markdown(edited)
    with tab_evidence:
        _evidence_panel(payload.get("evidence") or [])
    with tab_reason:
        st.caption(
            "Computed before the model was called. These facts, tables and identifiers are "
            "ground truth for the agent: it may argue with a verdict, but it cannot restate one."
        )
        st.markdown(payload.get("rationale_md") or "_No rule engine for this agent._")

    st.divider()
    blocked_by_four_eyes = svc.second_approver_blocks(user, proj.id, payload)

    col_a, col_r = st.columns(2)
    with col_a:
        st.markdown("**Approve**")
        st.caption(f"Recorded in the audit trail as **{user.label}** — your signed-in identity.")
        if blocked_by_four_eyes:
            st.warning(
                "This project requires a **second approver**: you ran this stage, so someone "
                "else must approve it. Invite a reviewer under **👥 People & settings**."
            )
        if st.button("✅ Approve & commit", type="primary", key=pkey("approve", agent_key),
                     disabled=blocked_by_four_eyes):
            with st.spinner("Committing to the audit trail…"):
                try:
                    result = svc.resume(user, proj.id, agent_key,
                                        {"action": "approve", "content": edited})
                except AccessDenied as exc:
                    st.error(str(exc))
                    return
                except Exception as exc:  # noqa: BLE001 - surfaced to the tester
                    st.error(friendly_llm_error(exc))
                    return
            st.session_state.pop(pkey("pending", agent_key), None)
            st.session_state["flash"] = (
                f"Approved and committed (`{result.get('commit', '')}`). "
                + _next_step_hint(agent_key)
            )
            st.rerun()

    with col_r:
        st.markdown("**Reject and regenerate**")
        reason = st.selectbox(
            "Main reason", [c for c, _ in REJECTION_REASONS],
            format_func=lambda c: dict(REJECTION_REASONS)[c],
            key=pkey("reason", agent_key),
        )
        feedback = st.text_area(
            "What should the agent fix?", key=pkey("fb", agent_key), height=90,
            placeholder="Be specific — this goes straight into the next attempt.",
        )
        if st.button("❌ Reject & regenerate", key=pkey("reject", agent_key)):
            with st.spinner("Regenerating with your feedback…"):
                try:
                    result = svc.resume(
                        user, proj.id, agent_key,
                        {
                            "action": "reject",
                            "feedback": feedback or dict(REJECTION_REASONS)[reason],
                            "reason": reason,
                        },
                    )
                except (AccessDenied, UsageLimitReached) as exc:
                    st.error(str(exc))
                    return
                except Exception as exc:  # noqa: BLE001 - surfaced to the tester
                    st.error(friendly_llm_error(exc))
                    return
            st.session_state[pkey("pending", agent_key)] = result["payload"]
            st.rerun()


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


def page_not_configured(status) -> None:
    """Shown instead of the app when no usable model credential is present."""
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
    proj = project()
    st.title(proj.name)
    st.caption(f"{_role_badge(proj.role)} · RAIA — Responsible AI Assistant")
    if proj.description:
        st.markdown(proj.description)

    summary = get_service().stage_summary(current_user(), proj.id)
    c1, c2, c3 = st.columns(3)
    c1.metric("Stages approved", f"{summary['approved']}/{summary['total']}")
    c2.metric("Awaiting review", len(summary["in_review"]))
    c3.metric("Open issues", summary["open_issues"])
    if summary["in_review"]:
        st.info("🧑‍⚖️ Waiting for a human decision: **" + "**, **".join(summary["in_review"]) + "**.")
    elif summary["next"]:
        st.info(f"▶️ Next stage to run: **{summary['next']}** (sidebar).")

    st.subheader("Five stages, five human gates")
    st.markdown(pipeline_figure(get_repo()), unsafe_allow_html=True)

    with st.expander("How RAIA works", expanded=summary["approved"] == 0):
        st.markdown(
            """
RAIA helps development teams apply **Responsible AI** across the software life
cycle. **Five specialized agents**, organized in three layers, analyze your
project and draft recommendations grounded in four consolidated frameworks
(IEEE 7000, NIST AI RMF, Microsoft RAI Standard v2, ECCOLA) and two legal texts
(EU AI Act, Brazilian PL 2338/2023).

Three design principles you will notice everywhere:

- **You are the checkpoint.** No agent output is saved until a person reviews
  and approves it, and no agent ever triggers another one.
- **Code decides what is decidable.** Prohibition lists, risk areas, obligation
  tables, coverage matrices and fairness metrics are computed by rules before
  any model is called. The model explains and argues; it does not produce the
  facts.
- **Everything is cited, checked and versioned.** Citations are verified
  against the excerpts actually retrieved, and every approval becomes a
  recorded version attributed to the person who approved it.
"""
        )
        st.markdown(PIPELINE_CSS + layer_cards(), unsafe_allow_html=True)
        st.markdown("**What happens inside one stage**")
        st.markdown(turn_figure(), unsafe_allow_html=True)

    if summary["approved"] == 0:
        st.info(
            "**Start here (~20 min):** open **▶️ 🟦 Risk Classifier** in the sidebar, press "
            "**Load example** to fill in a resume-screening scenario, and run it. Then work down "
            "the sidebar approving each stage, finish at the **📜 Audit Trail**, and "
            "**⭐ rate your experience**."
        )


def page_agent(agent_key: str) -> None:
    agent = AGENTS[agent_key]
    spec = agent.spec
    user = current_user()
    proj = project()
    svc = get_service()
    _flash()
    st.title(spec.name)
    st.caption(f"{proj.name} · {LAYER_BADGES[spec.layer]} · SDLC phase: {spec.sdlc_phase}")
    st.markdown(spec.description)

    repo = get_repo()

    missing = agent.missing_prerequisites(repo)
    if missing:
        producers = ", ".join(
            f"**{PRODUCER_OF.get(m, m)}**" + (f" (`{m}`)" if m in PRODUCER_OF else "")
            for m in missing
        )
        st.warning(
            f"🔒 **Stage gate** — this agent builds on upstream work that is not approved "
            f"yet. First run and approve: {producers}. This ordering is intentional: it is "
            "how RAIA guarantees each stage inherits human-approved context."
        )
        return

    current = repo.read_artifact(spec.output_key)
    if current:
        with st.expander("📄 Current approved artifact", expanded=False):
            st.markdown(current)

    # A review in progress: in this process, or recovered from storage.
    pending = st.session_state.get(pkey("pending", agent_key))
    if pending and not svc.has_thread(user, proj.id, agent_key):
        pending = None
        st.session_state.pop(pkey("pending", agent_key), None)
    if not pending and svc.has_thread(user, proj.id, agent_key):
        # Someone (possibly a teammate, possibly this person in another
        # session) left a draft at the gate; the graph is still waiting.
        pending = repo.load_pending(agent_key)
    if not pending:
        saved = repo.load_pending(agent_key)
        if saved and not current:
            st.warning(
                "A draft from this stage was found in storage — the app restarted while it was "
                "waiting for review. Restore it to continue where you left off; nothing "
                "was saved without an approval."
            )
            col_restore, col_discard = st.columns(2)
            if col_restore.button("↩️ Restore that review", key=pkey("restore", agent_key)):
                result = svc.restore(user, proj.id, agent_key)
                st.session_state[pkey("pending", agent_key)] = result["payload"]
                st.rerun()
            if proj.can("run") and col_discard.button("🗑️ Discard it and start fresh",
                                                      key=pkey("discard", agent_key)):
                svc.discard_pending(user, proj.id, agent_key)
                st.rerun()
            return

    if pending:
        review_gate(agent_key, pending)
        return

    can_run = proj.can("run")
    st.subheader("Inputs")
    inputs = intake_form(agent, can_run)
    if not can_run:
        return

    st.divider()
    if st.button(f"▶ Run {spec.name}", type="primary", key=pkey("run", agent_key)):
        blanks = agent.missing_inputs(inputs)
        if blanks:
            st.error(
                "These answers decide the outcome, so they are required: **"
                + "**, **".join(blanks)
                + "**."
            )
            return
        with st.spinner(f"{spec.name} is applying its decision procedure and reading the norms…"):
            try:
                result = svc.start_run(user, proj.id, agent_key, inputs)
            except (AccessDenied, UsageLimitReached) as exc:
                st.error(str(exc))
                return
            except Exception as exc:  # noqa: BLE001 - surfaced to the tester
                st.error(friendly_llm_error(exc))
                return
        if result["status"] == "awaiting_review":
            st.session_state[pkey("pending", agent_key)] = result["payload"]
            st.rerun()


def page_open_issues() -> None:
    _flash()
    st.title("⚖️ Open Issues")
    user = current_user()
    proj = project()
    repo = get_repo()
    st.caption(
        "Conflicts the system refused to resolve on its own: normative conflicts at the same "
        "authority level, disagreements between a rule engine and an agent, and gaps only a "
        "person can close. Nothing here is settled by the software."
    )

    issues = repo.open_issues()
    if not issues:
        st.info(
            "No open issues yet. They are raised automatically when a decision procedure or an "
            "agent finds a conflict, and recorded when you approve the stage that raised them."
        )
        return

    groups = [(OPEN, "Open", "🔴"), (ACCEPTED, "Accepted risk", "🟡"), (RESOLVED, "Resolved", "🟢")]
    for status, title, icon in groups:
        group = [i for i in issues if i.get("status") == status]
        if not group:
            continue
        st.subheader(f"{icon} {title} ({len(group)})")
        for issue in group:
            with st.container(border=True):
                st.markdown(f"**{issue['id']}** — {issue['text']}")
                st.caption(
                    f"raised by {issue.get('raised_by', '?')} · {issue.get('raised_at', '?')}"
                    + (f" · artifact `{issue['artifact']}`" if issue.get("artifact") else "")
                    + (f" · commit `{issue['commit']}`" if issue.get("commit") else "")
                )
                if issue.get("resolution_note"):
                    st.caption(f"_{issue['resolution_note']}_ — {issue.get('resolved_by', '')}")
                if status == OPEN and proj.can("review"):
                    with st.expander("Arbitrate this issue"):
                        note = st.text_input(
                            "What was decided, and on what basis?", key=pkey("note", issue["id"]),
                            placeholder="e.g. Legal confirmed the exemption does not apply",
                        )
                        st.caption(f"Recorded as decided by **{user.label}**.")
                        c1, c2 = st.columns(2)
                        if c1.button("Mark resolved", key=pkey("res", issue["id"]),
                                     disabled=not note.strip()):
                            get_service().set_issue_status(user, proj.id, issue["id"], RESOLVED, note)
                            st.session_state["flash"] = f"{issue['id']} marked resolved."
                            st.rerun()
                        if c2.button("Accept the risk", key=pkey("acc", issue["id"]),
                                     disabled=not note.strip()):
                            get_service().set_issue_status(user, proj.id, issue["id"], ACCEPTED, note)
                            st.session_state["flash"] = f"{issue['id']} recorded as accepted risk."
                            st.rerun()


def page_audit_trail() -> None:
    _flash()
    st.title("📜 Audit Trail")
    user = current_user()
    proj = project()
    repo = get_repo()
    st.caption(
        "Every approval is a recorded version that cannot be silently changed afterwards. "
        "Each artifact carries a provenance header — the model, the corpus version, which "
        "attempt was approved and by whom, whether the draft was edited, and what the automated "
        "checks said — and a structured record the next agent reads."
    )

    integrity = repo.verify_history()
    (st.success if integrity["ok"] else st.error)(
        ("🔐 History integrity verified — " if integrity["ok"] else "⚠️ History integrity FAILED — ")
        + integrity["detail"]
    )

    st.subheader("Artifacts")
    existing = repo.existing_artifacts()
    if not existing:
        st.info(
            "No approved artifacts yet. Approve an agent draft (e.g. the Risk Classifier's) "
            "and it will appear here."
        )
    for key in existing:
        content = repo.read_artifact(key) or ""
        data = repo.read_data(key)
        with st.expander(f"📄 {ARTIFACT_FILES[key]}"):
            prov = (data.get("provenance") or {})
            if prov:
                model = prov.get("model", {})
                corpus = prov.get("corpus", {})
                approval = prov.get("approval", {})
                cols = st.columns(4)
                cols[0].metric("Attempt approved", prov.get("attempt", "—"))
                cols[1].metric("Excerpts in prompt", len(corpus.get("excerpts", [])) or "—")
                cols[2].metric("Edited by hand", "yes" if approval.get("human_edited_draft") else "no")
                cols[3].metric("Checks", (prov.get("validation") or {}).get("level", "—"))
                st.caption(
                    f"approved by **{approval.get('approved_by', '?')}** · "
                    f"model `{model.get('provider','?')}/{model.get('name','?')}` · "
                    f"temperature {model.get('temperature','?')} · "
                    f"corpus `{corpus.get('version','?')}` · "
                    f"prompt `{prov.get('prompt_sha256_16','?')}` · "
                    f"engine `{prov.get('rationale_engine') or 'none'}`"
                )
            st.markdown(content)
            c1, c2 = st.columns(2)
            c1.download_button(
                "⬇ Markdown", content, file_name=ARTIFACT_FILES[key],
                mime="text/markdown", key=pkey("dl", key),
            )
            if data:
                c2.download_button(
                    "⬇ Structured record (JSON)",
                    json.dumps(data, indent=2, ensure_ascii=False, default=str),
                    file_name=ARTIFACT_FILES[key].replace(".md", ".json"),
                    mime="application/json", key=pkey("dlj", key),
                )

    st.subheader("Version history (every approval is a recorded version)")
    history = repo.history()
    if history:
        st.table(history)
    else:
        st.info("No versions yet.")

    events = repo.events()
    if events:
        names = {m["user_id"]: (m["name"] or m["email"])
                 for m in get_service().members(user, proj.id)}
        st.subheader("Activity")
        st.caption(
            "Runs, rejections with their reasons, approvals, restores and arbitrations. "
            "Research exports replace names with participant codes."
        )
        st.table(
            [
                {
                    "at": e.get("at", ""),
                    "who": names.get(e.get("user", ""), "former member" if e.get("user") else ""),
                    "event": e.get("kind", ""),
                    "stage": e.get("agent", ""),
                    "detail": e.get("reason_code") or e.get("validation") or e.get("status") or "",
                }
                for e in reversed(events)
            ]
        )


def page_people() -> None:
    _flash()
    user = current_user()
    proj = project()
    svc = get_service()
    st.title("👥 People & settings")
    st.caption(proj.name)

    st.subheader("Members")
    members = svc.members(user, proj.id)
    manage = proj.can("manage")
    for m in members:
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 1])
            who = (m["name"] or m["email"]) + (" (you)" if m["user_id"] == user.id else "")
            c1.markdown(f"**{who}**  \n{m['email']}")
            if manage:
                roles = [OWNER, EDITOR, REVIEWER]
                new_role = c2.selectbox("Role", roles, index=roles.index(m["role"]),
                                        format_func=_role_badge, key=pkey("role", m["user_id"]),
                                        label_visibility="collapsed")
                if new_role != m["role"]:
                    try:
                        svc.change_role(user, proj.id, m["user_id"], new_role)
                        st.session_state["flash"] = f"{m['email']} is now {new_role}."
                    except ValueError as exc:
                        st.session_state["flash"] = None
                        st.error(str(exc))
                    else:
                        st.rerun()
            else:
                c2.markdown(_role_badge(m["role"]))
            if (manage and m["user_id"] != user.id) and c3.button("Remove", key=pkey("rm", m["user_id"])):
                try:
                    svc.remove_member(user, proj.id, m["user_id"])
                    st.session_state["flash"] = f"{m['email']} was removed from the project."
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

    with st.expander("What each role can do"):
        for role in (OWNER, EDITOR, REVIEWER):
            st.markdown(f"- **{_role_badge(role)}** — {ROLE_LABELS[role].split('— ', 1)[1]}")

    if manage:
        st.subheader("Invite someone")
        st.caption(
            "Invite people by the Google address they sign in with. No email is sent: tell them "
            "the app's address, and the invitation is waiting on their **My projects** page."
        )
        with st.form(pkey("invite"), clear_on_submit=True):
            email = st.text_input("Email address", placeholder="name@example.com")
            role = st.selectbox("Role", [REVIEWER, EDITOR, OWNER], format_func=ROLE_LABELS.get)
            if st.form_submit_button("Send invitation", type="primary"):
                try:
                    inv = svc.invite(user, proj.id, email, role)
                    st.session_state["flash"] = f"Invitation for {inv['email']} ({inv['role']}) created."
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        invites = svc.project_invitations(user, proj.id)
        if invites:
            st.markdown("**Pending invitations**")
            for inv in invites:
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"{inv['email']} · {_role_badge(inv['role'])} · _{inv['created_at'][:10]}_")
                if c2.button("Revoke", key=pkey("revoke", inv["id"])):
                    svc.revoke_invitation(user, proj.id, inv["id"])
                    st.rerun()

        st.subheader("Project settings")
        with st.form(pkey("settings")):
            name = st.text_input("Name", value=proj.name)
            description = st.text_area("Description", value=proj.description, height=90)
            second = st.checkbox(
                "Require a second approver",
                value=proj.require_second_approver,
                help="The person who ran a stage cannot approve that stage's draft. "
                     "Separation of duties, enforced by the software.",
            )
            if st.form_submit_button("Save settings"):
                try:
                    svc.update_project(user, proj.id, name=name, description=description,
                                       require_second_approver=second)
                    st.session_state["flash"] = "Settings saved."
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

        st.subheader("Danger zone")
        c1, c2 = st.columns(2)
        with c1:
            if proj.archived_at:
                if st.button("Unarchive project", key=pkey("unarchive")):
                    svc.set_archived(user, proj.id, False)
                    st.rerun()
            elif st.button("Archive project", key=pkey("archive"),
                           help="Hidden from My projects; nothing is deleted."):
                svc.set_archived(user, proj.id, True)
                go(PAGE_PROJECTS)
                st.session_state.pop("project_id", None)
                st.rerun()
        with c2:
            confirm = st.text_input("Type the project name to delete it permanently",
                                    key=pkey("delete_confirm"))
            if st.button("Delete project", key=pkey("delete"), disabled=confirm.strip() != proj.name):
                svc.delete_project(user, proj.id)
                st.session_state.pop("project_id", None)
                st.session_state["page"] = PAGE_PROJECTS
                st.session_state["flash"] = f"Project “{proj.name}” and all its data were deleted."
                st.rerun()
    else:
        st.divider()
        if st.button("Leave this project", key=pkey("leave")):
            try:
                svc.remove_member(user, proj.id, user.id)
                st.session_state.pop("project_id", None)
                st.session_state["page"] = PAGE_PROJECTS
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))


def _seed_demo_project(user: User) -> Project:
    svc = get_service()
    proj = svc.create_project(
        user, "Demo — resume screening",
        "A worked example: an AI system that ranks job applicants. Every stage's form is "
        "pre-filled, so you can walk the whole pipeline in about 20 minutes.",
    )
    for agent_key, values in EXAMPLES.items():
        if agent_key in AGENTS:
            svc.save_intake(user, proj.id, agent_key, values)
    return proj


def page_projects() -> None:
    _flash()
    user = current_user()
    svc = get_service()
    st.title("🗂️ My projects")
    st.caption(
        "Each project has its own stages, drafts, answers, open issues and audit trail. "
        "You can be refining stories in one and classifying risk in another."
    )

    for inv in svc.my_invitations(user):
        with st.container(border=True):
            st.markdown(
                f"📨 **{inv.get('invited_by_name') or inv.get('invited_by_email') or 'Someone'}** "
                f"invited you to **{inv['project_name']}** as {_role_badge(inv['role'])}."
            )
            c1, c2, _ = st.columns([1, 1, 4])
            if c1.button("Accept", type="primary", key=f"inv_ok_{inv['id']}"):
                p = svc.respond_to_invitation(user, inv["id"], True)
                go(PAGE_OVERVIEW, p.id)
                st.session_state["flash"] = f"You joined “{p.name}”."
                st.rerun()
            if c2.button("Decline", key=f"inv_no_{inv['id']}"):
                svc.respond_to_invitation(user, inv["id"], False)
                st.rerun()

    with st.expander("➕ New project", expanded=not svc.list_projects(user, include_archived=True)):
        with st.form("new_project", clear_on_submit=True):
            name = st.text_input("Project name", placeholder="e.g. Credit-limit recommender")
            description = st.text_area("What is it? (optional)", height=80)
            if st.form_submit_button("Create project", type="primary"):
                try:
                    p = svc.create_project(user, name, description)
                    go(PAGE_OVERVIEW, p.id)
                    st.session_state["flash"] = f"Project “{p.name}” created."
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        st.caption("New to RAIA? Start with a pre-filled example instead:")
        if st.button("🧪 Create the demo project (resume screening)", key="demo_project"):
            p = _seed_demo_project(user)
            go(PAGE_OVERVIEW, p.id)
            st.session_state["flash"] = "Demo project created — every form is pre-filled."
            st.rerun()

    show_archived = st.toggle("Show archived projects", key="show_archived")
    projects = svc.list_projects(user, include_archived=show_archived)
    if not projects:
        st.info("You have no projects yet. Create one above, or accept an invitation.")
        return

    for p in projects:
        summary = svc.stage_summary(user, p.id)
        with st.container(border=True):
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"### {p.name}" + ("  _(archived)_" if p.archived_at else ""))
            c1.caption(f"{_role_badge(p.role)} · last activity {p.updated_at[:16].replace('T', ' ')} UTC")
            if p.description:
                c1.markdown(p.description[:280] + ("…" if len(p.description) > 280 else ""))
            icons = " ".join(STATUS_ICONS[s["status"]] for s in summary["stages"])
            state = f"{icons} · {summary['approved']}/{summary['total']} approved"
            if summary["in_review"]:
                state += " · awaiting review: " + ", ".join(summary["in_review"])
            elif summary["next"]:
                state += f" · next: {summary['next']}"
            if summary["open_issues"]:
                state += f" · ⚖️ {summary['open_issues']} open issue(s)"
            c1.markdown(state)
            c2.button("Open", key=f"open_{p.id}", type="primary", on_click=go,
                      args=(PAGE_OVERVIEW, p.id), use_container_width=True)


RATING_SCALE = [1, 2, 3, 4, 5]
STAGE_QUESTIONS = [
    ("usefulness", "Usefulness — would a team act on this output?"),
    ("ease", "Ease of use — was the stage easy to work through?"),
    ("trust", "Trust — did the evidence and checks let you judge the draft?"),
]
OVERALL_QUESTIONS = [
    ("overall_satisfaction", "Overall, how satisfied are you with RAIA?"),
    ("control", "The human approval gates kept me in control of the outcome."),
    ("would_use", "I would use RAIA on a real project."),
    ("grounding", "The recommendations were grounded in the relevant norms."),
]
SCALE_HELP = "1 = very poor / strongly disagree · 5 = excellent / strongly agree"


def _scale(label: str, key: str, previous: Optional[int]) -> Optional[int]:
    options = ["—"] + RATING_SCALE
    index = options.index(previous) if previous in RATING_SCALE else 0
    value = st.radio(label, options, index=index, horizontal=True, key=key, help=SCALE_HELP)
    return None if value == "—" else int(value)


def page_rate() -> None:
    _flash()
    user = current_user()
    svc = get_service()
    st.title("⭐ Rate your experience")
    st.markdown(
        "One form for the whole experience: rate **each stage** you used, then RAIA as a whole. "
        "Leave a stage at **—** if you did not use it. It takes about three minutes and is the "
        "evidence the study depends on."
    )
    previous = svc.my_latest_rating(user) or {}
    if previous:
        st.caption(f"You last submitted on {previous['submitted_at'][:16].replace('T', ' ')} UTC. "
                   "Submitting again records a new version; the latest one counts.")
    st.caption("Research exports identify you only by a participant code, never by name or email.")

    prev_stages = previous.get("stages", {})
    with st.form("experience_rating"):
        stages: Dict[str, Any] = {}
        for agent in AGENTS.values():
            spec = agent.spec
            before = prev_stages.get(spec.key, {})
            with st.container(border=True):
                st.markdown(f"#### {LAYER_BADGES[spec.layer]} · {spec.name}")
                answers = {q: _scale(label, f"rate_{spec.key}_{q}", before.get(q))
                           for q, label in STAGE_QUESTIONS}
                comment = st.text_input("Anything specific about this stage? (optional)",
                                        value=before.get("comment", ""),
                                        key=f"rate_{spec.key}_comment")
                stages[spec.key] = {**answers, "comment": comment.strip()}

        st.markdown("#### RAIA as a whole")
        overall = {q: _scale(label, f"rate_overall_{q}", previous.get("overall", {}).get(q))
                   for q, label in OVERALL_QUESTIONS}
        improve = st.text_area("What should change first?", value=previous.get("improve", ""),
                               height=90)
        role = st.selectbox(
            "Which best describes your background?",
            ["—", "Product / project management", "Software engineering", "Data science / ML",
             "Legal / compliance", "Ethics / social science", "Other"],
            index=0,
        )
        submitted = st.form_submit_button("Submit rating", type="primary")

    if submitted:
        if overall["overall_satisfaction"] is None:
            st.error("Please answer at least the overall satisfaction question.")
            return
        svc.submit_rating(user, {
            "stages": stages,
            "overall": overall,
            "improve": improve.strip(),
            "background": None if role == "—" else role,
            "stages_rated": sum(1 for s in stages.values()
                                if any(s[q] is not None for q, _ in STAGE_QUESTIONS)),
        })
        st.session_state["flash"] = "Thank you — your rating was recorded."
        st.rerun()


def page_account() -> None:
    _flash()
    user = current_user()
    svc = get_service()
    st.title("Account & privacy")
    st.markdown(f"Signed in as **{user.name or user.email}** ({user.email}).")
    st.markdown(PRIVACY_NOTICE)
    st.subheader("Delete my account")
    st.caption(
        "Deletes your account, your ratings, your memberships and every project you are the only "
        "owner of, with all its data. Approvals you recorded on projects that other people own "
        "stay in those projects' audit trails. This cannot be undone."
    )
    confirm = st.text_input("Type DELETE to confirm", key="delete_account_confirm")
    if st.button("Delete my account", disabled=confirm.strip() != "DELETE"):
        svc.delete_account(user)
        for k in list(st.session_state):
            del st.session_state[k]
        if auth.mode() != "dev":
            auth.logout()
        else:
            st.session_state["flash"] = "Account deleted."
            st.rerun()


def page_research() -> None:
    user = current_user()
    st.title("📊 Research data")
    if not user.is_admin:
        st.error("Only study coordinators can see this page.")
        return
    st.markdown(
        "A pseudonymized export of every project's evaluation events and every experience "
        "rating. Participants are codes, projects are numbered, and no names or email addresses "
        "are included. Free-text comments are exported as written — read them before publishing."
    )
    if st.button("Prepare export", type="primary"):
        st.session_state["_research_zip"] = get_service().research_export(user)
    data = st.session_state.get("_research_zip")
    if data:
        st.download_button("⬇ Download research data (zip)", data=data,
                           file_name="raia-research-data.zip", mime="application/zip")


PRIVACY_NOTICE = """
**What RAIA stores about you**

- From your Google sign-in: your **email address and name**. RAIA never sees
  your password.
- The **projects** you create or join, and everything in them: form answers,
  drafts, approved artifacts, open issues and the activity log. Only members of
  a project can see it.
- Your **experience ratings**.

**Why:** RAIA is the software artifact of a master's research project on
Responsible AI. Your approvals are attributed to you because accountability is
the point of the approval gates.

**Where:** in the deployment's managed PostgreSQL database. The agents send
project content to the configured language-model provider to draft their
analyses.

**Research use:** evaluation events and ratings are analysed only in
pseudonymized form — you appear as a participant code, never by name or email.

**Your control:** you can delete any project you own, leave projects, and
delete your account at any time from this page.
"""


def page_login() -> None:
    st.title("🛡️ RAIA — Responsible AI Assistant")
    st.markdown(
        "RAIA helps teams apply Responsible AI across the software life cycle: five specialized "
        "agents, grounded in legal texts and frameworks, with a human approval gate after every "
        "stage.\n\nSign in to see your projects and the ones you have been invited to."
    )
    if st.button("Sign in with Google", type="primary"):
        auth.login()


def page_consent(user: User) -> Optional[User]:
    st.title("Before you start")
    st.markdown(PRIVACY_NOTICE)
    agree = st.checkbox("I have read this and agree to RAIA storing my data as described.")
    c1, c2 = st.columns([1, 4])
    if c1.button("Continue", type="primary", disabled=not agree):
        get_service().record_consent(user)
        st.rerun()
    if auth.mode() != "dev" and c2.button("No thanks, sign me out"):
        auth.logout()
    return None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    st.set_page_config(page_title="RAIA", page_icon="🛡️", layout="wide")

    status = runtime_status()
    if not status.ready:
        page_not_configured(status)
        return

    problem = auth.configuration_problem()
    if problem:
        st.title("🛡️ RAIA")
        st.error("**Sign-in is not configured, so the app will not open.** " + problem)
        return

    identity = auth.current_identity()
    if identity is None:
        page_login()
        return

    user = get_service().sign_in(identity.email, identity.name)
    st.session_state["_user"] = user
    if not user.consented_at:
        page_consent(user)
        return

    with st.spinner("Preparing the normative knowledge base (first start only)…"):
        ensure_normative_index()

    page = sidebar(status)

    if page == PAGE_RATE:
        page_rate()
    elif page == PAGE_ACCOUNT:
        page_account()
    elif page == PAGE_RESEARCH:
        page_research()
    elif page == PAGE_PROJECTS or active_project() is None:
        page_projects()
    elif page == PAGE_ISSUES:
        page_open_issues()
    elif page == PAGE_AUDIT:
        page_audit_trail()
    elif page == PAGE_PEOPLE:
        page_people()
    elif page in AGENTS:
        page_agent(page)
    else:
        page_overview()


if __name__ == "__main__":
    main()
