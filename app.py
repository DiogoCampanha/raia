#!/usr/bin/env python3
"""
app.py — RAIA Streamlit user interface.

Run with:
    streamlit run app.py

The UI is organized around the RAIA pipeline:

* an **Overview** page showing the five agents and the mandatory human
  approval gates ("H") that separate them;
* one page per agent, ordered by pipeline stage and grouped by layer
  (Product / Dev / Ops), each with a structured intake form and its human
  approval gate;
* an **Open Issues** page — the register of conflicts the system refused to
  resolve on its own;
* an **Audit Trail** page showing artifacts, provenance and commit history.

Two things shape every screen here.

**The questions are asked, not inferred.** Each agent declares typed fields —
selects, multi-selects, yes/no, uploads — and a rule engine reads them. A field
exists because something in the code consumes it, so filling the form in is
what produces the verdict rather than a prompt guessing at prose.

**The gate shows its evidence.** A reviewer is never asked to approve a claim
with the grounds hidden: the draft arrives alongside the excerpts that were
retrieved, the facts the rule engine computed, and the result of every
automated check. Nothing is persisted until a person approves it.
"""

import re
import uuid
from typing import Any, Dict, List

import streamlit as st

# --- Configuration bridge (MUST run before importing raia.config) ----------
from raia.deploy import apply_secrets  # noqa: E402

apply_secrets()

from raia import config                                     # noqa: E402
from raia.agents import AGENTS                              # noqa: E402
from raia.deploy import friendly_llm_error, runtime_status  # noqa: E402
from raia.examples import EXAMPLES                          # noqa: E402
from raia.export import bundle_name, session_bundle         # noqa: E402
from raia.fields import InputField                          # noqa: E402
from raia.pipeline import StageRunner                       # noqa: E402
from raia.repository import (                               # noqa: E402
    ACCEPTED,
    ARTIFACT_FILES,
    OPEN,
    RESOLVED,
    ArtifactRepository,
)

# Layer identity. Mid-tones chosen to stay legible on light and dark themes.
LAYER_COLORS = {"Product": "#3b82f6", "Dev": "#22c55e", "Ops": "#f97316"}
LAYER_BADGES = {"Product": "🟦 Product", "Dev": "🟩 Dev", "Ops": "🟧 Ops"}

STATUS_COLORS = {"approved": "#22c55e", "ready": "#3b82f6", "blocked": "#94a3b8"}
STATUS_LABELS = {"approved": "Approved", "ready": "Ready to run", "blocked": "Awaiting upstream"}
STATUS_ICONS = {"approved": "✅", "ready": "▶️", "blocked": "🔒"}

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


# ---------------------------------------------------------------------------
# Per-tester session workspace
# ---------------------------------------------------------------------------


def session_project() -> str:
    """Return this browser session's private project id."""
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
    st.query_params.clear()
    st.session_state["flash"] = "Fresh workspace ready — the walkthrough is reset."


def _flash() -> None:
    msg = st.session_state.pop("flash", None)
    if msg:
        st.success(msg)


def _next_step_hint(agent_key: str) -> str:
    keys = list(AGENTS)
    i = keys.index(agent_key)
    if i + 1 < len(keys):
        return f"Next stage: **{AGENTS[keys[i + 1]].spec.name}** (sidebar)."
    return "Pipeline complete — see the **📜 Audit Trail** for the full history."


@st.cache_resource
def get_runner() -> StageRunner:
    """One StageRunner (and its graph checkpointer) per server process."""
    return StageRunner()


@st.cache_resource
def ensure_normative_index() -> bool:
    """Self-bootstrap the RAG index on hosted platforms."""
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


def sidebar(status) -> str:
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
    st.sidebar.progress(n_done / len(AGENTS), text=f"{n_done}/{len(AGENTS)} stages approved")

    layer_dot = {"Product": "🟦", "Dev": "🟩", "Ops": "🟧"}
    pages = {"🏠 Overview": "Overview"}
    for agent in AGENTS.values():
        mark = STATUS_ICONS[_agent_status(agent, repo, done)]
        pages[f"{mark} {layer_dot[agent.spec.layer]} {agent.spec.name}"] = agent.spec.name

    open_count = sum(1 for i in repo.open_issues() if i.get("status") == OPEN)
    pages[f"⚖️ Open Issues ({open_count})" if open_count else "⚖️ Open Issues"] = "Open Issues"
    pages["📜 Audit Trail"] = "Audit Trail"

    label = st.sidebar.radio("Pipeline", list(pages), label_visibility="collapsed")
    st.sidebar.caption("✅ approved · ▶️ ready · 🔒 awaiting upstream approval")

    st.sidebar.divider()
    st.sidebar.caption(
        "This is your own private workspace. Other testers cannot see it, and "
        "it is discarded when the app restarts — export before you leave."
    )
    st.sidebar.download_button(
        "⬇ Export this session",
        data=session_bundle(repo),
        file_name=bundle_name(repo.project),
        mime="application/zip",
        help="Artifacts, structured records, commit history and your feedback, in one zip.",
        use_container_width=True,
    )
    if st.sidebar.button("🔄 Start over", help="Erase this workspace and begin again",
                         use_container_width=True):
        reset_session()
        st.rerun()

    return pages[label]


# ---------------------------------------------------------------------------
# Structured intake form
# ---------------------------------------------------------------------------


def _state_key(agent_key: str, field_key: str) -> str:
    return f"in_{agent_key}_{field_key}"


def _current_inputs(agent_key: str, fields: List[InputField]) -> Dict[str, Any]:
    """What the form currently holds — used to evaluate conditional visibility."""
    out: Dict[str, Any] = {}
    for f in fields:
        value = st.session_state.get(_state_key(agent_key, f.key))
        if value is None:
            value = [] if f.is_multi else (f.default or "")
        out[f.key] = value
    return out


def _render_field(agent_key: str, f: InputField) -> Any:
    key = _state_key(agent_key, f.key)
    label = f.label + (" *" if f.required else "")

    if f.kind == "textarea":
        return st.text_area(label, key=key, help=f.help, height=f.height,
                            placeholder=f.placeholder)
    if f.kind == "text":
        return st.text_input(label, key=key, help=f.help, placeholder=f.placeholder)
    if f.kind == "number":
        return st.number_input(label, key=key, help=f.help, step=1)
    if f.kind in ("select", "boolean"):
        values = [o.value for o in f.options]
        if key not in st.session_state and f.default in values:
            st.session_state[key] = f.default
        if f.kind == "boolean":
            return st.radio(label, values, key=key, help=f.help,
                            format_func=f.label_for, horizontal=True)
        return st.selectbox(label, values, key=key, help=f.help, format_func=f.label_for,
                            index=None, placeholder="Choose one…")
    if f.kind == "multiselect":
        return st.multiselect(label, [o.value for o in f.options], key=key, help=f.help,
                              format_func=f.label_for, placeholder="Choose all that apply…")
    if f.kind in ("csv", "file"):
        upload = st.file_uploader(
            label, key=f"up_{key}", help=f.help,
            type=list(f.file_types) or None,
        )
        if upload is not None:
            try:
                st.session_state[key] = upload.getvalue().decode("utf-8", errors="replace")
                st.caption(f"Loaded **{upload.name}** ({len(st.session_state[key]):,} characters).")
            except Exception:  # noqa: BLE001 - surfaced to the tester
                st.error("That file could not be read as text. Export it as CSV or plain text.")
        if f.kind == "csv":
            return st.text_area("…or paste the rows", key=key, height=f.height,
                                placeholder=f.placeholder)
        return st.session_state.get(key, "")
    return st.text_area(label, key=key, help=f.help, height=f.height)


def intake_form(agent) -> Dict[str, Any]:
    """Render the agent's typed fields, grouped, honouring conditional visibility."""
    spec = agent.spec
    if spec.intro:
        st.info(spec.intro)

    if st.button("📋 Load example (resume-screening scenario)", key=f"ex_{spec.key}"):
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
            _render_field(spec.key, f)

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


def _rating_widget(repo, agent_key: str, agent_name: str) -> None:
    """Capture a per-stage usefulness rating once a stage has been approved."""
    rated = any(
        e.get("kind") == "rating" and e.get("agent") == agent_key for e in repo.events()
    )
    if rated:
        st.caption("Thank you — your rating for this stage is recorded.")
        return
    with st.expander("⭐ Rate this stage (30 seconds, helps the study)", expanded=False):
        useful = st.slider(
            "How useful was this output to a team doing this work?", 1, 5, 3,
            key=f"rate_use_{agent_key}",
            help="1 = not useful at all · 5 = we would act on this as it stands",
        )
        usable = st.slider(
            "How easy was this stage to use?", 1, 5, 3, key=f"rate_easy_{agent_key}",
        )
        comment = st.text_area("Anything you want to add", key=f"rate_note_{agent_key}", height=80)
        if st.button("Submit rating", key=f"rate_go_{agent_key}"):
            repo.record_event(
                "rating",
                {"agent": agent_key, "agent_name": agent_name, "usefulness": useful,
                 "usability": usable, "comment": comment},
            )
            st.session_state["flash"] = "Rating recorded — thank you."
            st.rerun()


def review_gate(agent_key: str, payload: Dict[str, Any]) -> None:
    """The human checkpoint UI: evidence, checks, edit, approve or reject."""
    agent = AGENTS[agent_key]
    repo = get_repo()
    runner = get_runner()

    st.subheader("🧑‍⚖️ Human review required")
    st.caption(
        f"Draft #{payload.get('attempt', 1)} by **{payload['agent_name']}** — nothing is "
        "persisted until you approve. You may edit the text before approving."
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
            "Draft (Markdown, editable)", payload["draft"], height=460, key=f"edit_{agent_key}"
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
    approver = st.text_input(
        "Your name (recorded in the audit trail)", key=f"approver_{agent_key}",
        placeholder="e.g. Ana Souza",
    )

    col_a, col_r = st.columns(2)
    with col_a:
        st.markdown("**Approve**")
        if st.button("✅ Approve & commit", type="primary", key=f"approve_{agent_key}",
                     disabled=not approver.strip(),
                     help="Enter your name first — approvals are attributed."):
            with st.spinner("Committing to the audit trail…"):
                try:
                    result = runner.resume(
                        session_project(), agent_key,
                        {"action": "approve", "content": edited, "approver": approver.strip()},
                    )
                except Exception as exc:  # noqa: BLE001 - surfaced to the tester
                    st.error(friendly_llm_error(exc))
                    return
            st.session_state.pop(f"pending_{agent_key}", None)
            if agent_key == "risk_classifier":
                _persist_product_brief(repo, agent, approver.strip())
            st.session_state["flash"] = (
                f"Approved and committed (`{result.get('commit', '')}`). "
                + _next_step_hint(agent_key)
            )
            st.rerun()
        if not approver.strip():
            st.caption("An approval carries a name. Enter yours to enable the button.")

    with col_r:
        st.markdown("**Reject and regenerate**")
        reason = st.selectbox(
            "Main reason", [c for c, _ in REJECTION_REASONS],
            format_func=lambda c: dict(REJECTION_REASONS)[c],
            key=f"reason_{agent_key}",
        )
        feedback = st.text_area(
            "What should the agent fix?", key=f"fb_{agent_key}", height=90,
            placeholder="Be specific — this goes straight into the next attempt.",
        )
        if st.button("❌ Reject & regenerate", key=f"reject_{agent_key}"):
            with st.spinner("Regenerating with your feedback…"):
                try:
                    result = runner.resume(
                        session_project(), agent_key,
                        {
                            "action": "reject",
                            "feedback": feedback or dict(REJECTION_REASONS)[reason],
                            "reason": reason,
                            "approver": approver.strip() or "reviewer",
                        },
                    )
                except Exception as exc:  # noqa: BLE001 - surfaced to the tester
                    st.error(friendly_llm_error(exc))
                    return
            st.session_state[f"pending_{agent_key}"] = result["payload"]
            st.rerun()


def _persist_product_brief(repo: ArtifactRepository, agent, approver: str) -> None:
    """Record the human-authored brief alongside the approved classification.

    This is the one artifact a person writes rather than an agent: it is
    committed at the moment the classification is approved, under the
    approver's name, so the audit trail shows the input and the output of the
    stage landing together rather than a file appearing before any review.
    """
    fields = [f for f in agent.spec.input_fields if f.is_text and f.group.endswith("The product")]
    parts = []
    for f in fields:
        value = st.session_state.get(_state_key(agent.spec.key, f.key))
        if value:
            parts.append(f"## {f.label}\n{value}")
    if not parts:
        return
    structured = {
        f.key: st.session_state.get(_state_key(agent.spec.key, f.key))
        for f in agent.spec.input_fields
    }
    repo.save_artifact(
        "product_brief",
        "\n\n".join(parts),
        approved_by=approver or "author",
        structured={"intake": structured, "note": "human-authored input, not agent output"},
        run_provenance={"rationale_engine": None, "attempt": 1},
    )


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
    st.title("RAIA — Responsible AI Assistant")
    st.markdown(
        """
RAIA helps development teams apply **Responsible AI** across the software life
cycle. **Five specialized agents**, organized in three layers, analyze your
project and draft recommendations grounded in four consolidated frameworks
(IEEE 7000, NIST AI RMF, Microsoft RAI Standard v2, ECCOLA) and two legal texts
(EU AI Act, Brazilian PL 2338/2023).

Three design principles you will notice everywhere:

- **You are the checkpoint.** No agent output is saved until you review and
  approve it, and no agent ever triggers another one.
- **Code decides what is decidable.** Prohibition lists, risk areas, obligation
  tables, coverage matrices and fairness metrics are computed by rules before
  any model is called. The model explains and argues; it does not produce the
  facts.
- **Everything is cited, checked and versioned.** Citations are verified
  against the excerpts actually retrieved, and every approval becomes a commit.
"""
    )

    st.subheader("Three layers")
    st.markdown(PIPELINE_CSS + layer_cards(), unsafe_allow_html=True)

    st.subheader("Five stages, five human gates")
    st.markdown(pipeline_figure(get_repo()), unsafe_allow_html=True)

    st.subheader("What happens inside one stage")
    st.markdown(turn_figure(), unsafe_allow_html=True)

    st.info(
        "**Start here (~20 min):** open **▶️ 🟦 Risk Classifier** in the sidebar, press "
        "**Load example** to fill in a resume-screening scenario, and run it. Then work down "
        "the sidebar approving each stage, and finish at the **📜 Audit Trail**."
    )


def page_agent(agent_key: str) -> None:
    agent = AGENTS[agent_key]
    spec = agent.spec
    _flash()
    st.title(spec.name)
    st.caption(f"{LAYER_BADGES[spec.layer]} · SDLC phase: {spec.sdlc_phase}")
    st.markdown(spec.description)

    repo = get_repo()
    runner = get_runner()

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
        _rating_widget(repo, agent_key, spec.name)

    # A review in progress: in this process, or recovered from disk.
    pending = st.session_state.get(f"pending_{agent_key}")
    if pending and not runner.has_thread(session_project(), agent_key):
        pending = None
        st.session_state.pop(f"pending_{agent_key}", None)
    if not pending:
        saved = repo.load_pending(agent_key)
        if saved and not current:
            st.warning(
                "A draft from this stage was found on disk — the app restarted while it was "
                "waiting for your review. Restore it to continue where you left off; nothing "
                "was saved without your approval."
            )
            col_restore, col_discard = st.columns(2)
            if col_restore.button("↩️ Restore that review", key=f"restore_{agent_key}"):
                result = runner.restore(session_project(), agent_key, saved)
                st.session_state[f"pending_{agent_key}"] = result["payload"]
                repo.record_event("restore", {"agent": agent_key})
                st.rerun()
            if col_discard.button("🗑️ Discard it and start fresh", key=f"discard_{agent_key}"):
                repo.clear_pending(agent_key)
                st.rerun()
            return

    if pending:
        review_gate(agent_key, pending)
        return

    st.subheader("Inputs")
    inputs = intake_form(agent)

    st.divider()
    if st.button(f"▶ Run {spec.name}", type="primary", key=f"run_{agent_key}"):
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
                result = runner.start(session_project(), agent_key, inputs)
            except Exception as exc:  # noqa: BLE001 - surfaced to the tester
                st.error(friendly_llm_error(exc))
                return
        if result["status"] == "awaiting_review":
            st.session_state[f"pending_{agent_key}"] = result["payload"]
            st.rerun()


def page_open_issues() -> None:
    _flash()
    st.title("⚖️ Open Issues")
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
                if status == OPEN:
                    with st.expander("Arbitrate this issue"):
                        note = st.text_input(
                            "What was decided, and by whom?", key=f"note_{issue['id']}",
                            placeholder="e.g. Legal confirmed the exemption does not apply — Ana, 12 Sep",
                        )
                        who = st.text_input("Your name", key=f"who_{issue['id']}")
                        c1, c2 = st.columns(2)
                        if c1.button("Mark resolved", key=f"res_{issue['id']}",
                                     disabled=not who.strip()):
                            repo.set_issue_status(issue["id"], RESOLVED, note, who.strip())
                            st.session_state["flash"] = f"{issue['id']} marked resolved."
                            st.rerun()
                        if c2.button("Accept the risk", key=f"acc_{issue['id']}",
                                     disabled=not who.strip()):
                            repo.set_issue_status(issue["id"], ACCEPTED, note, who.strip())
                            st.session_state["flash"] = f"{issue['id']} recorded as accepted risk."
                            st.rerun()


def page_audit_trail() -> None:
    _flash()
    st.title("📜 Audit Trail")
    repo = get_repo()
    st.caption(
        "Every artifact below is a file in a Git repository, and every approval is a commit. "
        "Each artifact carries a provenance header — the model, the corpus version, which "
        "attempt was approved, whether you edited it, and what the automated checks said — "
        "and a structured record the next agent reads."
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
                mime="text/markdown", key=f"dl_{key}",
            )
            if data:
                import json as _json

                c2.download_button(
                    "⬇ Structured record (JSON)",
                    _json.dumps(data, indent=2, ensure_ascii=False, default=str),
                    file_name=ARTIFACT_FILES[key].replace(".md", ".json"),
                    mime="application/json", key=f"dlj_{key}",
                )

    st.subheader("Git history (every approval is a commit)")
    history = repo.history()
    if history:
        st.table(history)
    else:
        st.info("No commits yet.")

    events = repo.events()
    if events:
        st.subheader("Your session")
        st.caption(
            "Rejections, approvals and ratings from this walkthrough. This is research data "
            "about the session, kept apart from the project's audit trail."
        )
        st.table(
            [
                {
                    "at": e.get("at", ""),
                    "event": e.get("kind", ""),
                    "stage": e.get("agent", ""),
                    "detail": e.get("reason_code") or e.get("validation") or
                    (f"usefulness {e.get('usefulness')}/5, usability {e.get('usability')}/5"
                     if e.get("kind") == "rating" else ""),
                }
                for e in reversed(events)
            ]
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    st.set_page_config(page_title="RAIA", page_icon="🛡️", layout="wide")

    status = runtime_status()
    if not status.ready:
        page_not_configured(status)
        return

    with st.spinner("Preparing the normative knowledge base (first start only)…"):
        ensure_normative_index()

    page = sidebar(status)

    if page == "Overview":
        page_overview()
    elif page == "Open Issues":
        page_open_issues()
    elif page == "Audit Trail":
        page_audit_trail()
    else:
        for key, agent in AGENTS.items():
            if agent.spec.name == page:
                page_agent(key)
                break


if __name__ == "__main__":
    main()
