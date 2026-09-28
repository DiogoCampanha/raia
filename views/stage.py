"""Stage: one agent inside one project — run it, review its draft, or read and revise it.

The page wears its agent's identity (colour, icon, question, header pattern —
``raia.ui.theme.AGENT_LOOK``) so a person always knows which agent they are
working with, keeps the five stages in view, and ends with the previous and
next stage whatever state this one is in.
"""

import streamlit as st

from raia import backlog as B
from raia.agents import AGENTS, RUNNABLE, identity_key
from raia.deploy import friendly_llm_error
from raia.projects import AccessDenied, UsageLimitReached
from raia.ui import routes
from raia.ui.components import (agent_header, artifact_body, next_step_card, stage_footer,
                                stage_rail)
from raia.rationale.coverage import ORIGIN_KEY
from raia.ui.gate import intake_form, pending_suggestions, prefill, review_gate
from raia.ui.record_view import record_from_data, record_view
from raia.ui.state import current_user, flash, get_service, open_project, pkey, show_flash
from raia.ui.theme import I, look_key

user = current_user()
svc = get_service()
proj = open_project("project")
agent_key = st.query_params.get("agent", "")
if agent_key not in RUNNABLE:
    st.error("Unknown stage.", icon=I.ERROR)
    if st.button("Back to the project", icon=I.BACK, key="stage_unknown_back"):
        routes.go(routes.PROJECT, id=proj.id)
    st.stop()

agent = RUNNABLE[agent_key]
spec = agent.spec
ident = identity_key(agent_key)          # a mode wears its parent agent's identity
repo = svc.repository(user, proj.id, "view")
summary = svc.stage_summary(user, proj.id)
stages = summary["stages"]
state = next(s for s in stages if s["agent"] == ident)
if agent_key != ident:
    # A mode has its own draft and its own record; its status is its own.
    missing = agent.missing_prerequisites(repo)
    own = ("in_review" if agent_key in repo.pending_agents() else
           "approved" if repo.read_artifact(spec.output_key) is not None else
           "blocked" if missing else "ready")
    state = {**state, "agent": agent_key, "status": own, "missing": missing, "stale_because": [],
             "stale_because_names": []}
step = list(AGENTS).index(ident) + 1
board = svc.board(user, proj.id) if repo.read_artifact("requirements_review") is not None else {}
open_sprint = (board or {}).get("open_sprint")
FAMILY = {"story_refiner": "story_generate", "story_generate": "story_refiner"}

# The "what's next" card belongs to the stage that was just approved; opening
# any other stage retires it.
just = st.session_state.get("just_approved")
if just and (just.get("project") != proj.id or just.get("agent") != agent_key):
    st.session_state.pop("just_approved", None)
    just = None


def modes_and_sprint() -> None:
    """The Refiner's two modes, and the sprint a sprint-cycle stage works on."""
    if agent_key in FAMILY:
        other = RUNNABLE[FAMILY[agent_key]].spec
        with st.container(horizontal=True, vertical_alignment="center"):
            st.markdown(f"**Mode:** {spec.mode_label}")
            if st.button(f"Switch to: {other.mode_label}", key=pkey("mode", agent_key), type="tertiary",
                         icon=":material/swap_horiz:"):
                routes.go(routes.STAGE, project=proj.id, agent=other.key)
    if agent_key in ("story_refiner", "auditor") and board:
        if open_sprint:
            st.caption(f"{I.INFO} Working on **{open_sprint['name']}** "
                       f"({B.SPRINT_STATE_LABELS.get(open_sprint['state'], open_sprint['state']).lower()})."
                       + (" Approving this audit closes it." if agent_key == "auditor"
                          and open_sprint["state"] == B.REVIEW else ""))
        elif agent_key == "auditor":
            st.caption(f"{I.INFO} No sprint is open: this audit reports on the whole project and closes nothing.")


def sprint_prefill() -> None:
    """Fill the form from the board: the sprint's product stories, or the sprint to audit."""
    if not (board and open_sprint and proj.can("run")):
        return
    stories = B.in_sprint(board["backlog"], open_sprint["id"])
    if agent_key == "story_refiner":
        product = [x for x in stories if x.get("origin") == B.PRODUCT]
        if product and st.button(f"Use the {len(product)} product stories in {open_sprint['name']}",
                                 key=pkey("use_sprint", agent_key), icon=":material/view_kanban:"):
            prefill(agent_key, {"user_stories": [{
                "id": x["id"], "title": x.get("title", ""), "description": x.get("description", ""),
                "acceptance_criteria": "\n".join(c.get("text", "") for c in x.get("criteria") or []
                                                  if c.get("kind") != "ethical"),
                "capabilities": list(x.get("touches") or [])} for x in product],
                "sprint_goal": open_sprint.get("goal", "")})
            st.rerun()
    if agent_key == "auditor":
        done = [x for x in stories if x["status"] == B.DONE]
        if st.button(f"Fill in {open_sprint['name']}", key=pkey("use_sprint", agent_key),
                     icon=":material/view_kanban:"):
            outcomes = ("Delivered this sprint: " + "; ".join(f"{x['id']} — {x.get('title') or ''}".strip(" —")
                                                               for x in done) + "."
                        if done else "No story was marked done this sprint.")
            prefill(agent_key, {"sprint_id": open_sprint["name"],
                                "sprint_outcomes": outcomes + "\n\nWhat was tested, and the evidence it produced: "})
            st.rerun()
        st.caption("Filling in names the sprint and lists the stories ticked done. Describe what was tested: "
                   "an item is verified only by evidence named in the outcomes.")


def body() -> None:
    """Everything between the header and the footer. Returns early instead of
    stopping the script, so the stage navigation below is always drawn."""
    modes_and_sprint()
    # ---- Blocked by the stage gate ---------------------------------------------------

    if state["missing"]:
        producers = {a.spec.output_key: (k, a.spec.name) for k, a in AGENTS.items()}
        with st.container(border=True):
            st.markdown(f"{I.LOCK} **Waiting on upstream work**")
            st.caption("This agent builds on upstream work that is not approved yet. This ordering "
                       "is intentional: each stage inherits human-approved context.")
            for m in state["missing"]:
                key, name = producers.get(m, (None, m))
                if key and st.button(f"Open {name}", key=f"missing_{key}", icon=I.OPEN):
                    routes.go(routes.STAGE, project=proj.id, agent=key)
        return

    # ---- A review in progress: in this session, or recovered from storage ------------

    current = repo.read_artifact(spec.output_key)
    pending = st.session_state.get(pkey("pending", agent_key))
    thread_alive = svc.has_thread(user, proj.id, agent_key)
    if pending and not thread_alive:
        pending = None
        st.session_state.pop(pkey("pending", agent_key), None)
    if not pending and thread_alive:
        pending = repo.load_pending(agent_key)
    if not pending:
        saved = repo.load_pending(agent_key)
        if saved:
            st.warning("A draft from this stage was found in storage: the app restarted while it was "
                       "waiting for review. Restore it to continue where you left off. Nothing was "
                       "saved without an approval.", icon=I.RESTORE)
            row = st.container(horizontal=True)
            if row.button("Restore that review", key=pkey("restore", agent_key), icon=I.RESTORE):
                result = svc.restore(user, proj.id, agent_key)
                st.session_state[pkey("pending", agent_key)] = result["payload"]
                st.rerun()
            if proj.can("run") and row.button("Discard it", key=pkey("discard", agent_key), icon=I.DISCARD):
                svc.discard_pending(user, proj.id, agent_key)
                st.rerun()
            return

    if pending:
        if current:
            with st.expander("Currently approved version", icon=I.DOCS):
                record, computed = record_from_data(repo.read_data(spec.output_key))
                record_view(agent_key, record, computed, key=pkey("approved_now", agent_key), nested=True,
                            fallback_markdown=artifact_body(current))
        review_gate(proj, agent_key, pending)
        return

    # ---- Approved: read it, re-confirm it, or revise it --------------------------------

    revising_key = pkey("revising", agent_key)
    can_run = proj.can("run")

    if current and not st.session_state.get(revising_key):
        if just and board and agent_key in ("story_generate", "story_refiner", "auditor"):
            board_card(just)
        elif just:
            next_step_card(proj.id, stages, agent_key, just, can_run)
        if state["status"] == "stale":
            with st.container(border=True):
                st.markdown(f"{I.WARN} **This stage needs review**")
                st.caption("It was approved before these upstream stages changed: **"
                           + "**, **".join(state["stale_because_names"]) + "**. Check whether it "
                           "still holds. Nothing was re-run automatically.")
                if proj.can("review"):
                    note = st.text_input("Why it still holds (optional)", key=pkey("reconfirm_note", agent_key))
                    row = st.container(horizontal=True)
                    if row.button("Confirm it still holds", key=pkey("reconfirm", agent_key),
                                 type="primary", icon=I.CONFIRM):
                        svc.reconfirm_stage(user, proj.id, agent_key, note)
                        flash(f"{spec.name} confirmed as still valid, recorded as {user.label}.")
                        st.rerun()
                    if can_run and row.button("Revise it", key=pkey("revise_stale", agent_key), icon=I.REVISE):
                        st.session_state[revising_key] = True
                        st.session_state.pop("just_approved", None)
                        st.rerun()

        st.subheader("Approved version", anchor=False)
        data = repo.read_data(spec.output_key)
        approval = (data.get("provenance") or {}).get("approval", {})
        if approval:
            st.caption(f"Approved by **{approval.get('approved_by', '?')}**. The full provenance and "
                       "version history are in the project's Documents and Activity tabs.")
        record, computed = record_from_data(data)
        record_view(agent_key, record, computed, key=pkey("approved", agent_key),
                    fallback_markdown=artifact_body(current))
        st.download_button("Download (Markdown)", artifact_body(current), file_name=f"{spec.output_key}.md",
                           mime="text/markdown", key=pkey("dl_approved", agent_key), icon=I.DOWNLOAD,
                           type="tertiary")

        if can_run and state["status"] != "stale":
            impact = svc.revision_impact(user, proj.id, agent_key)
            cyclic = bool(board) and agent_key in ("story_generate", "story_refiner", "auditor")
            with st.container(border=True):
                if cyclic:
                    label = {"story_generate": "Generate more stories",
                             "story_refiner": f"Refine stories for {open_sprint['name']}" if open_sprint else "Refine more stories",
                             "auditor": f"Audit {open_sprint['name']}" if open_sprint else "Audit the project again"}[agent_key]
                    st.markdown(f"{I.RUN} **{label}**")
                    st.caption("Each run is its own record. The one shown above stays in the history (and, for "
                               "a sprint, in that sprint's copy).")
                else:
                    st.markdown(f"{I.REVISE} **Revise this stage**")
                    st.caption("Revising runs the agent again with updated answers. The approved version "
                               "stays in force, and in the history, until a new draft is approved.")
                if impact:
                    st.warning("Approving a revision will flag these approved stages for review: **"
                               + "**, **".join(impact) + "**. They are not re-run automatically.",
                               icon=I.WARN)
                if st.button(label if cyclic else "Revise this stage", key=pkey("revise", agent_key),
                             icon=I.RUN if cyclic else I.REVISE):
                    st.session_state[revising_key] = True
                    st.session_state.pop("just_approved", None)
                    st.rerun()
        return

    # ---- Inputs and run ------------------------------------------------------------------

    if current:
        c1, c2 = st.columns([4, 1], vertical_alignment="center")
        if bool(board) and agent_key in ("story_generate", "story_refiner", "auditor"):
            c1.info("A new run. The previous record stays in the history.", icon=I.RUN)
        else:
            c1.info("You are revising an approved stage. The approved version remains in force until a "
                    "new draft is approved.", icon=I.REVISE)
        if c2.button("Cancel revision", key=pkey("cancel_revise", agent_key)):
            st.session_state.pop(revising_key, None)
            st.rerun()

    st.subheader("Inputs", anchor=False)
    if agent_key == "story_generate" and board and not board.get("uncovered"):
        st.success("Every approved requirement already has a story in the backlog. Nothing to generate: "
                   "plan the next sprint on the board, or refine product stories.", icon=I.OK)
    elif agent_key == "story_generate" and board:
        st.caption(f"{len(board['uncovered'])} approved requirement(s) have no story yet; this run covers "
                   "the five with the highest priority unless you widen it or name them.")
    sprint_prefill()
    inputs = intake_form(proj, agent, can_run)
    if not can_run:
        return

    # Answers RAIA pre-filled are the team's only once a person says so.
    ack_key = pkey("suggest_ack", agent_key)
    unreviewed = pending_suggestions(agent_key)
    if unreviewed:
        st.checkbox("I reviewed the pre-filled answers (" + ", ".join(unreviewed) + ") and they "
                    "reflect this project", key=ack_key)

    if st.button(f"Run {spec.name}", type="primary", key=pkey("run", agent_key), icon=I.RUN):
        blanks = agent.missing_inputs(inputs)
        if blanks:
            st.error("These answers decide the outcome, so they are required: **"
                     + "**, **".join(blanks) + "**.")
            return
        if pending_suggestions(agent_key) and not st.session_state.get(ack_key):
            st.error("Some answers were pre-filled by RAIA and have not been reviewed. Check them, "
                     "then confirm above that they reflect this project.", icon=I.WARN)
            return
        if ORIGIN_KEY in inputs:
            inputs[ORIGIN_KEY] = {**inputs[ORIGIN_KEY], "reviewed_by": user.label}
        with st.spinner(f"{spec.name} is applying its decision procedure and reading the norms"):
            try:
                result = svc.start_run(user, proj.id, agent_key, inputs)
            except (AccessDenied, UsageLimitReached) as exc:
                st.error(str(exc))
                return
            except Exception as exc:  # noqa: BLE001 - surfaced to the person
                st.error(friendly_llm_error(exc))
                return
        if result["status"] == "awaiting_review":
            st.session_state[pkey("pending", agent_key)] = result["payload"]
            st.rerun()


def board_card(done) -> None:
    """After an approval in the sprint cycle, the way back is the Board."""
    with st.container(border=True, key=look_key(ident, "done")):
        commit = str(done.get("commit") or "")
        st.markdown(f"{I.OK} **Approved and committed**" + (f" `{commit}`" if commit else ""))
        st.caption({"story_generate": "The stories are in the backlog as RAI-n. Plan them into a sprint on the board.",
                    "story_refiner": "The criteria and requirement links are on the stories in the backlog.",
                    "auditor": "The audit is recorded; if it closed a sprint, its stories are verified or "
                               "carried over, and the roadmap is updated."}[agent_key])
        if st.button("Back to the board", type="primary", icon=I.OPEN, icon_position="right", key="next_board"):
            st.session_state.pop("just_approved", None)
            routes.go(routes.PROJECT, id=proj.id)


with st.container(key=look_key(ident, "page")):
    agent_header(ident, spec.name, spec.description,
                 eyebrow=f"{spec.layer} layer · Step {step} of {len(AGENTS)} · "
                         + (f"{spec.mode_label} · " if spec.mode_label else "") + spec.sdlc_phase,
                 status=state["status"], back=(proj.name, routes.PROJECT, {"id": proj.id}))
    stage_rail(proj.id, stages, current=ident)
    show_flash()
    body()
    stage_footer(proj.id, stages, ident)
