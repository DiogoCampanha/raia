"""
raia.ui.board
=============

The project's Board: the backlog, the open sprint and the roadmap.

It opens once the ethical requirements are approved and becomes the project's
main view. Every control here is manual and none needs Jira: a person plans a
sprint (with a rule-based suggestion), ticks stories done, ends the sprint and
sends it to the Auditor, whose approved audit closes it. The Jira actions sit
beside those controls as optional extras (:mod:`raia.ui.jira_panel`).

Lists start short — the first ten rows, highest priority first — with "Show
all" to expand them.
"""

from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

from raia import backlog as B
from raia import roadmap as R
from raia.projects import AccessDenied
from raia.rationale.story_map import CAPABILITY_OPTIONS, parse_backlog

from . import routes
from .components import empty_state, esc, stat_tiles
from .state import flash, pkey
from .theme import I

SHORT = 10
VIEWS = ("Sprint", "Backlog", "Roadmap")
CAP_LABELS = {o.value: o.label for o in CAPABILITY_OPTIONS if o.value != "none"}
STATUS_COLOR = {B.BACKLOG: "gray", B.IN_SPRINT: "blue", B.DONE: "violet", B.VERIFIED: "green",
                B.NEEDS_REVIEW: "orange", B.OBSOLETE: "gray"}
TREND_LABEL = {"improving": "Improving", "flat": "Flat", "declining": "Declining",
               "first_sprint": "First sprint on record", "none": "No sprint closed yet"}


def _act(fn, *args, ok: str = "", **kwargs) -> Any:
    """Run a service call; show its refusal instead of a stack trace."""
    try:
        result = fn(*args, **kwargs)
    except (ValueError, AccessDenied) as exc:
        st.error(str(exc), icon=I.WARN)
        return None
    if ok:
        flash(ok)
    st.rerun()
    return result


def _title(s: Dict[str, Any]) -> str:
    return s.get("title") or (s.get("description") or "")[:80] or s["id"]


def _short_list(rows: List[Any], key: str) -> List[Any]:
    """The first rows, and a button to show every one."""
    if len(rows) <= SHORT or st.session_state.get(key):
        return rows
    if st.button(f"Show all ({len(rows)})", key=key + "_btn", type="tertiary", icon=":material/unfold_more:"):
        st.session_state[key] = True
        st.rerun()
    return rows[:SHORT]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def sprint_step(proj, stages: List[Dict[str, Any]], data: Dict[str, Any], pending: List[str]):
    """The project's next step once the board is open, or ``None`` to defer to the stages.

    A draft awaiting review or a flagged product stage comes first; after that
    the step follows the sprint cycle. It only points: nothing here runs.
    """
    for s in stages:
        if s["agent"] in ("risk_classifier", "requirements_reviewer") and s["status"] in ("in_review", "stale"):
            return None
    for key, what in (("story_generate", "the generated stories"), ("story_refiner", "the refined stories"),
                      ("auditor", "the audit")):
        if key in pending:
            return {"label": f"Review {what}", "why": "A draft is waiting for a human decision.",
                    "button": "Review", "agent": key, "icon": I.READ}
    bl, x = data["backlog"], data["open_sprint"]
    if data["uncovered"] and not any(s.get("origin") == B.RAI for s in bl["stories"]):
        return {"label": "Generate the RAI backlog", "button": "Generate stories", "agent": "story_generate",
                "icon": I.SUGGEST,
                "why": f"{len(data['uncovered'])} approved requirement(s) have no story yet; five at a time."}
    if x is None:
        n = int(data["sprints"].get("counter") or 0) + 1
        return {"label": f"Plan Sprint {n}", "button": "Open the board", "view": "Sprint", "icon": I.ADD,
                "why": "Pick the sprint's stories: the board suggests them by rules, you decide."}
    if x["state"] == B.PLANNING:
        return {"label": f"Start {x['name']}", "button": "Open the board", "view": "Sprint", "icon": I.RUN,
                "why": "Add its stories, then start it."}
    if x["state"] == B.ACTIVE:
        raw = [s for s in B.in_sprint(bl, x["id"]) if s.get("origin") == B.PRODUCT
               and not B.ethical_criteria(s) and not s.get("no_impact_reason")]
        if raw:
            return {"label": "Refine the product stories", "button": "Refine", "agent": "story_refiner",
                    "icon": I.REVISE,
                    "why": f"{len(raw)} product story(ies) in {x['name']} have no ethical criteria yet."}
        return {"label": f"Tick stories done, then end {x['name']}", "button": "Open the board",
                "view": "Sprint", "icon": I.CONFIRM,
                "why": "A tick means delivered; the sprint's audit decides what is verified."}
    return {"label": f"Audit {x['name']}", "button": "Audit", "agent": "auditor", "icon": I.SHIELD,
            "why": "The sprint has ended; its approved audit closes it."}


def board_tab(proj, user, svc, data: Dict[str, Any] = None) -> None:
    data = data or svc.board(user, proj.id)
    if not data["ready"]:
        empty_state("The board opens with the requirements",
                    "Approve the Risk Classifier and the Requirements Reviewer first. The board then "
                    "holds the backlog, the sprints and the roadmap.")
        return
    view = st.segmented_control("View", VIEWS, default="Sprint", key=pkey("board_view", proj.id),
                                label_visibility="collapsed") or "Sprint"
    if view == "Sprint":
        _sprint_view(proj, user, svc, data)
    elif view == "Backlog":
        _backlog_view(proj, user, svc, data)
    else:
        _roadmap_view(proj, data)


# ---------------------------------------------------------------------------
# Sprint
# ---------------------------------------------------------------------------


def _sprint_view(proj, user, svc, data) -> None:
    bl, sp, x = data["backlog"], data["sprints"], data["open_sprint"]
    can_run = proj.can("run")
    uncovered = data["uncovered"]
    if uncovered and not any(s.get("origin") == B.RAI for s in bl["stories"]):
        with st.container(border=True):
            st.markdown(f"{I.SUGGEST} **Start with the RAI backlog**")
            st.caption(f"{len(uncovered)} approved requirement(s) have no story yet. The User Story Refiner's "
                       "generate mode writes them, five at a time; you approve them at the gate.")
            if can_run and st.button("Generate stories from the requirements", type="primary",
                                     icon=I.OPEN, key=pkey("gen_first", proj.id)):
                routes.go(routes.STAGE, project=proj.id, agent="story_generate")

    if x is None:
        _plan_form(proj, svc, user, sp, can_run)
        _past_sprints(sp)
        return

    stories = B.in_sprint(bl, x["id"])
    unit = x.get("unit") or "stories"
    used = sum(((s.get("estimate") or 1) if unit == "points" else 1) for s in stories)
    with st.container(border=True):
        c1, c2 = st.columns([3, 2], vertical_alignment="center")
        c1.markdown(f"### {esc(x['name'])}")
        c1.caption(" · ".join(b for b in (
            B.SPRINT_STATE_LABELS.get(x["state"], x["state"]),
            " to ".join(d for d in (x.get("start"), x.get("end")) if d),
            f"Goal: {x['goal']}" if x.get("goal") else "") if b))
        cap = x.get("capacity") or 0
        if cap:
            c2.progress(min(1.0, used / cap), text=f"{used} of {cap} {unit} planned")
        with st.expander("Sprint details", icon=I.REVISE):
            _sprint_details(proj, svc, user, x, can_run)

    if x["state"] == B.PLANNING:
        _suggestions(proj, svc, user, can_run)
    if x["state"] in (B.PLANNING, B.ACTIVE):
        _add_from_backlog(proj, svc, user, bl, can_run)

    st.markdown(f"**Stories in {esc(x['name'])}** · {len(stories)}")
    if not stories:
        st.caption("No story yet. Add the suggested ones, or pick from the backlog.")
    for s in stories:
        _sprint_row(proj, svc, user, x, s)

    row = st.container(horizontal=True)
    if x["state"] == B.PLANNING and can_run:
        if row.button(f"Start {x['name']}", type="primary", icon=I.RUN, key=pkey("start", proj.id),
                      disabled=not stories):
            _act(svc.start_sprint, user, proj.id, ok=f"{x['name']} started.")
    if x["state"] in (B.PLANNING, B.ACTIVE) and can_run:
        product = [s for s in stories if s.get("origin") == B.PRODUCT]
        if product and row.button("Refine the product stories", icon=look_icon("story_refiner"),
                                  key=pkey("refine", proj.id)):
            routes.go(routes.STAGE, project=proj.id, agent="story_refiner")
    if x["state"] == B.ACTIVE and can_run:
        if row.button(f"End {x['name']}", icon=":material/flag:", key=pkey("end", proj.id)):
            _act(svc.end_sprint, user, proj.id, ok=f"{x['name']} ended. Audit it to close it.")
    if x["state"] == B.REVIEW:
        st.info(f"**{x['name']} has ended.** The Auditor's approved audit closes it: it verifies what the "
                "evidence supports and carries the rest over.", icon=I.INFO)
        if can_run and row.button(f"Audit {x['name']}", type="primary", icon=look_icon("auditor"),
                                  key=pkey("audit", proj.id)):
            routes.go(routes.STAGE, project=proj.id, agent="auditor")
        if can_run and row.button("Reopen the sprint", icon=I.RESTORE, key=pkey("reopen", proj.id)):
            _act(svc.reopen_sprint, user, proj.id, ok=f"{x['name']} reopened.")
    if stories and x["state"] in (B.PLANNING, B.ACTIVE, B.REVIEW):
        from .jira_panel import jira_actions

        jira_actions(proj, user, svc, x, stories)
    _past_sprints(sp)


def look_icon(agent_key: str) -> str:
    from .theme import look

    return look(agent_key).material


def _plan_form(proj, svc, user, sp, can_run) -> None:
    n = int(sp.get("counter") or 0) + 1
    with st.container(border=True):
        st.markdown(f"{I.ADD} **Plan Sprint {n}**")
        if not can_run:
            st.caption("Owners and editors plan sprints. You can tick stories done once a sprint is running.")
            return
        with st.form(pkey("plan", proj.id), clear_on_submit=True, border=False):
            c1, c2 = st.columns(2)
            name = c1.text_input("Name", value=f"Sprint {n}")
            goal = c2.text_input("Goal (optional)")
            d1, d2, d3, d4 = st.columns(4)
            start = d1.date_input("Starts", value=None)
            end = d2.date_input("Ends", value=None)
            unit = d3.selectbox("Capacity in", ["stories", "points"])
            cap = d4.number_input("Capacity", min_value=1, value=R.DEFAULT_CAPACITY, step=1)
            if st.form_submit_button("Plan the sprint", type="primary", icon=I.ADD):
                _act(svc.create_sprint, user, proj.id, name=name, goal=goal,
                     start=start.isoformat() if start else "", end=end.isoformat() if end else "",
                     capacity=int(cap), unit=unit, ok=f"{name} planned. Add its stories, then start it.")


def _sprint_details(proj, svc, user, x, can_run) -> None:
    if not can_run or x["state"] == B.CLOSED:
        st.caption("Only owners and editors change a sprint.")
        return
    with st.form(pkey("sprint_edit", proj.id), border=False):
        c1, c2 = st.columns(2)
        name = c1.text_input("Name", value=x.get("name", ""))
        goal = c2.text_input("Goal", value=x.get("goal", ""))
        d1, d2 = st.columns(2)
        unit = d1.selectbox("Capacity in", ["stories", "points"], index=0 if x.get("unit") != "points" else 1)
        cap = d2.number_input("Capacity", min_value=1, value=int(x.get("capacity") or R.DEFAULT_CAPACITY))
        if st.form_submit_button("Save", icon=I.SAVE):
            _act(svc.update_sprint, user, proj.id, x["id"],
                 {"name": name, "goal": goal, "unit": unit, "capacity": int(cap)}, ok="Sprint saved.")


def _suggestions(proj, svc, user, can_run) -> None:
    sugg = svc.suggest_sprint(user, proj.id)
    with st.container(border=True):
        st.markdown(f"{I.SUGGEST} **Suggested for this sprint**")
        st.caption("Ranked by rules, no model: carried-over stories first, then stories closing a legal "
                   "obligation, then by the priority of their requirements, then the longest waiting. "
                   "You decide what goes in.")
        if not sugg["suggested"]:
            st.caption("Nothing to suggest: the sprint is full, or the backlog is empty.")
        picked = []
        for c in sugg["suggested"]:
            if st.checkbox(f"**{c['id']}** · {c['title']}", value=True, key=pkey("sg", proj.id, c["id"]),
                           help=c["reason"], disabled=not can_run):
                picked.append(c["id"])
            st.caption(f"{B.ORIGIN_LABELS.get(c['origin'], '')} story · {c['reason']}")
        for b in sugg["blocked"][:5]:
            st.caption(f"{I.LOCK} {b['id']}: {b['reason']}")
        for w in sugg["waiting"][:5]:
            st.caption(f"{w['id']}: {w['reason']}")
        if can_run and sugg["suggested"] and st.button(f"Add {len(picked)} to the sprint", icon=I.ADD,
                                                      key=pkey("sg_add", proj.id), disabled=not picked):
            _act(svc.schedule, user, proj.id, picked, ok=f"{len(picked)} story(ies) added to the sprint.")


def _add_from_backlog(proj, svc, user, bl, can_run) -> None:
    if not can_run:
        return
    ready = [s for s in bl["stories"] if s["status"] == B.BACKLOG]
    if not ready:
        return
    with st.expander("Add stories from the backlog", icon=I.ADD):
        chosen = st.multiselect("Stories", [s["id"] for s in ready],
                                format_func=lambda sid: f"{sid} · {_title(B.story(bl, sid))}",
                                key=pkey("pick", proj.id), label_visibility="collapsed",
                                placeholder="Choose stories")
        if st.button("Add to the sprint", icon=I.ADD, key=pkey("pick_add", proj.id), disabled=not chosen):
            _act(svc.schedule, user, proj.id, chosen, ok=f"{len(chosen)} story(ies) added to the sprint.")


def _sprint_row(proj, svc, user, x, s) -> None:
    with st.container(border=True):
        c0, c1, c2 = st.columns([0.6, 6, 2.4], vertical_alignment="center")
        can_tick = proj.can("review") and x["state"] in (B.ACTIVE, B.REVIEW)
        done = s["status"] == B.DONE
        ticked = c0.checkbox("Done", value=done, key=pkey("tick", proj.id, s["id"]), disabled=not can_tick,
                             label_visibility="collapsed",
                             help="Delivered. Only the sprint's audit marks a story verified.")
        if can_tick and ticked != done:
            _act(svc.tick, user, proj.id, s["id"], ticked)
        crit = B.ethical_criteria(s)
        meta = [B.ORIGIN_LABELS.get(s.get("origin"), ""),
                ("implements " + ", ".join(s["evr_ids"])) if s.get("evr_ids") else "",
                f"{len(crit)} ethical criteria" if crit else (s.get("no_impact_reason") and "no ethical impact") or
                ("not refined yet" if s.get("origin") == B.PRODUCT else ""),
                f"{s['estimate']} pt" if s.get("estimate") else ""]
        c1.markdown(f"**{esc(s['id'])}** · {esc(_title(s))}")
        c1.caption(" · ".join(m for m in meta if m))
        if s.get("needs_review_reason"):
            c1.caption(f"{I.WARN} {s['needs_review_reason']}")
        with c1:
            from .jira_panel import disagreement

            disagreement(proj, user, svc, s)
        with c2:
            st.badge(B.STATUS_LABELS[s["status"]], color=STATUS_COLOR.get(s["status"], "gray"))
            jira = s.get("jira") or {}
            if jira.get("key"):
                st.markdown(f"[{esc(jira['key'])}]({jira.get('url', '')})" if jira.get("url") else jira["key"])
            if proj.can("run") and x["state"] in (B.PLANNING, B.ACTIVE):
                if st.button("Remove", key=pkey("unsched", proj.id, s["id"]), type="tertiary",
                             icon=":material/remove_circle_outline:"):
                    _act(svc.schedule, user, proj.id, [s["id"]], add=False, ok=f"{s['id']} is back in the backlog.")


def _past_sprints(sp) -> None:
    closed = B.closed_sprints(sp)
    if not closed:
        return
    st.markdown("**Closed sprints**")
    st.dataframe([{
        "Sprint": x["name"], "Closed": str(x.get("closed_at", ""))[:10],
        "Opinion": str(x.get("opinion") or "").replace("_", " "),
        "Trend": TREND_LABEL.get(x.get("trend"), x.get("trend") or ""),
        "Verified": len((x.get("result") or {}).get("verified") or []),
        "Carried over": len((x.get("result") or {}).get("carried_over") or []),
    } for x in reversed(closed)], hide_index=True, width="stretch")


# ---------------------------------------------------------------------------
# Backlog
# ---------------------------------------------------------------------------


def _backlog_view(proj, user, svc, data) -> None:
    bl = data["backlog"]
    can_run = proj.can("run")
    uncovered = data["uncovered"]
    row = st.container(horizontal=True)
    if can_run and uncovered and row.button(f"Generate stories ({len(uncovered)} requirements without one)",
                                            icon=look_icon("story_refiner"), key=pkey("gen", proj.id)):
        routes.go(routes.STAGE, project=proj.id, agent="story_generate")
    if can_run:
        _add_story_forms(proj, svc, user)

    stories = bl["stories"]
    if not stories:
        empty_state("The backlog is empty", "Generate RAI stories from the requirements, or add product stories.")
        return
    f1, f2, f3 = st.columns([1, 2, 2])
    origin = f1.selectbox("Origin", ["All", "RAI", "Product"], key=pkey("bl_origin", proj.id))
    statuses = f2.multiselect("Status", list(B.STATUSES), default=[s for s in B.STATUSES if s != B.OBSOLETE],
                              format_func=B.STATUS_LABELS.get, key=pkey("bl_status", proj.id))
    query = f3.text_input("Search", key=pkey("bl_q", proj.id), placeholder="Id, title or requirement")
    shown = [s for s in stories
             if (origin == "All" or B.ORIGIN_LABELS.get(s["origin"]) == origin)
             and (not statuses or s["status"] in statuses)
             and (not query or query.lower() in " ".join([s["id"], _title(s), *s.get("evr_ids", [])]).lower())]
    shown.sort(key=lambda s: (list(B.STATUSES).index(s["status"]) if s["status"] in B.STATUSES else 9,
                              0 if s.get("origin") == B.RAI else 1, s.get("created_at") or ""))
    visible = _short_list(shown, pkey("bl_all", proj.id))
    event = st.dataframe([{
        "ID": s["id"], "Origin": B.ORIGIN_LABELS.get(s["origin"], ""), "Title": _title(s),
        "Requirements": ", ".join(s.get("evr_ids") or []), "Status": B.STATUS_LABELS[s["status"]],
        "Sprint": s.get("sprint") or s.get("verified_in") or "",
        "Ethical criteria": len(B.ethical_criteria(s)), "Jira": (s.get("jira") or {}).get("key", ""),
    } for s in visible], hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
        key=pkey("bl_table", proj.id))
    picked = (getattr(event, "selection", None) or {}).get("rows") if event is not None else None
    if picked:
        _story_detail(proj, svc, user, visible[picked[0]])
    else:
        st.caption("Select a row to see the story, its criteria and its history.")


def _add_story_forms(proj, svc, user) -> None:
    with st.expander("Add a product story", icon=I.ADD):
        with st.form(pkey("add_story", proj.id), clear_on_submit=True, border=False):
            title = st.text_input("Title")
            description = st.text_area("Story", height=80, placeholder="As a …, I want …, so that …")
            criteria = st.text_area("Acceptance criteria (one per line, optional)", height=80)
            c1, c2 = st.columns([3, 1])
            touches = c1.multiselect("What it touches", list(CAP_LABELS), format_func=CAP_LABELS.get)
            estimate = c2.number_input("Points (optional)", min_value=0, value=0)
            if st.form_submit_button("Add to the backlog", type="primary", icon=I.ADD):
                _act(svc.add_story, user, proj.id, {"title": title, "description": description,
                                                    "acceptance_criteria": criteria, "touches": touches,
                                                    "estimate": int(estimate) or None},
                     ok="Story added to the backlog.")
    with st.expander("Paste several stories", icon=I.EXAMPLE):
        text = st.text_area("Stories", height=140, key=pkey("paste_bl", proj.id), label_visibility="collapsed",
                            placeholder="As a recruiter, I want …\nAcceptance criteria:\n- …\n\nAs a manager, I want …")
        if st.button("Add them", key=pkey("paste_bl_btn", proj.id), disabled=not text.strip()):
            parsed = parse_backlog(text)
            for p in parsed:
                try:
                    svc.add_story(user, proj.id, {"title": p.get("title", ""), "description": p.get("description", ""),
                                                  "acceptance_criteria": p.get("acceptance_criteria", "")})
                except (ValueError, AccessDenied) as exc:
                    st.error(str(exc))
                    return
            flash(f"{len(parsed)} story(ies) added to the backlog.")
            st.rerun()


def _story_detail(proj, svc, user, s) -> None:
    with st.container(border=True):
        st.markdown(f"#### {esc(s['id'])} · {esc(_title(s))}")
        st.caption(" · ".join(x for x in (B.ORIGIN_LABELS.get(s["origin"], "") + " story",
                                          B.STATUS_LABELS[s["status"]],
                                          ("implements " + ", ".join(s["evr_ids"])) if s.get("evr_ids") else "",
                                          f"carried over {s['carried_over']}x" if s.get("carried_over") else "",
                                          f"verified in {s['verified_in']}" if s.get("verified_in") else "") if x))
        if s.get("description"):
            st.markdown(s["description"])
        if s.get("criteria"):
            st.markdown("**Acceptance criteria**")
            for c in s["criteria"]:
                if c.get("kind") == "ethical":
                    st.markdown(f"- **{esc(c['id'])}** (ethical) {esc(c.get('text', ''))}"
                                + (f" _Evidence: {esc(c['evidence_artifact'])}_" if c.get("evidence_artifact") else ""))
                else:
                    st.markdown(f"- {esc(c['id'])}: {esc(c.get('text', ''))}")
        elif s.get("no_impact_reason"):
            st.caption(f"No ethical impact: {s['no_impact_reason']}")
        if s.get("needs_review_reason"):
            st.warning(s["needs_review_reason"] + (" It is proposed obsolete." if s.get("obsolete_proposed") else ""),
                       icon=I.WARN)
            if proj.can("run"):
                r = st.container(horizontal=True)
                if r.button("Keep it", key=pkey("keep", proj.id, s["id"]), icon=I.CONFIRM):
                    _act(svc.resolve_story_review, user, proj.id, s["id"], "keep", ok=f"{s['id']} kept.")
                if r.button("Mark obsolete", key=pkey("obs", proj.id, s["id"]), icon=I.DISCARD):
                    _act(svc.resolve_story_review, user, proj.id, s["id"], "obsolete", ok=f"{s['id']} is obsolete.")
        if proj.can("run") and s["status"] not in (B.VERIFIED, B.OBSOLETE):
            with st.expander("Edit", icon=I.REVISE):
                with st.form(pkey("edit", proj.id, s["id"]), border=False):
                    title = st.text_input("Title", value=s.get("title", ""))
                    description = st.text_area("Story", value=s.get("description", ""), height=80)
                    c1, c2 = st.columns(2)
                    estimate = c1.number_input("Points", min_value=0, value=int(s.get("estimate") or 0))
                    deps = c2.text_input("Depends on (ids)", value=", ".join(s.get("depends_on") or []))
                    st.caption("Criteria and requirement links change through the User Story Refiner's gate.")
                    if st.form_submit_button("Save", icon=I.SAVE):
                        _act(svc.update_story, user, proj.id, s["id"],
                             {"title": title, "description": description, "estimate": int(estimate) or None,
                              "depends_on": [d.strip().upper() for d in deps.split(",") if d.strip()]},
                             ok=f"{s['id']} saved.")
        hist = (s.get("history") or [])[-5:]
        if hist:
            st.caption("History: " + " · ".join(f"{h['at'][:10]} {h['what']} ({h['by']})" for h in reversed(hist)))


# ---------------------------------------------------------------------------
# Roadmap
# ---------------------------------------------------------------------------


def _roadmap_view(proj, data) -> None:
    rm = data["roadmap"]
    if not rm:
        empty_state("No roadmap yet", "It is computed from the approved requirements.")
        return
    counts, rows = rm["counts"], rm["requirements"]
    left = rm.get("sprints_left")
    stat_tiles([
        ("Requirements verified", f"{counts.get('verified', 0)} / {len(rows)}", "", False),
        ("Stories open", rm["open_stories"], f"{rm['open_rai']} RAI", False),
        ("Sprints closed", rm["closed_sprints"], TREND_LABEL.get(rm["trend"]["direction"], ""),
         rm["trend"]["direction"] == "declining"),
        ("Sprints left", "—" if left is None else left, "estimate at the pace so far" if left else "", False),
    ])
    series = rm["series"]
    if series:
        st.markdown("**Requirements verified, by sprint**")
        st.line_chart({"Sprint": [x.get("name") or x.get("sprint") for x in series],
                       "Requirements verified": [x.get("verified_requirements", 0) for x in series]},
                      x="Sprint", y="Requirements verified", height=220)
        st.caption(rm["trend"]["reason"])
    else:
        st.caption("The line starts when the first sprint closes on its audit.")
    st.markdown("**Every requirement, highest priority first**")
    visible = _short_list(rows, pkey("rm_all", proj.id))
    table = [{"Requirement": r["id"], "State": R.REQ_STATE_LABELS[r["state"]],
              "Stories": ", ".join(r["stories"]), "Legal obligation": r["obligation"],
              "Priority": r["priority"], "Verified in": r["verified_in"],
              "Statement": r["statement"][:120]} for r in visible]
    st.dataframe(table, hide_index=True, width="stretch")
    import csv
    import io

    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["Requirement", "State", "Stories", "Legal obligation", "Priority",
                                        "Verified in", "Statement"])
    w.writeheader()
    for r in rows:
        w.writerow({"Requirement": r["id"], "State": R.REQ_STATE_LABELS[r["state"]], "Stories": " ".join(r["stories"]),
                    "Legal obligation": r["obligation"], "Priority": r["priority"], "Verified in": r["verified_in"],
                    "Statement": r["statement"]})
    st.download_button("Roadmap (CSV)", buf.getvalue(), file_name="roadmap.csv", mime="text/csv",
                       icon=I.DOWNLOAD, key=pkey("rm_csv", proj.id))
