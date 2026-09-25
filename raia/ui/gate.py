"""
raia.ui.gate
============

The two halves of a stage page: the structured intake form, and the human
approval gate.

**The questions are asked, not inferred.** Each agent declares typed fields —
selects, multi-selects, yes/no, uploads — and a rule engine reads them. A field
exists because something in the code consumes it.

**Edits are made to the record, not to prose.** Every draft is a RAIA record
rendered into the one layout every stage follows. A reviewer changes its fields
— the summary, a finding's placement on the scales, an action's owner — and
the software re-computes priorities and re-renders the document, so the
approved artifact still follows the standard after a person has touched it.

**The gate shows its evidence.** A reviewer is never asked to approve a claim
with the grounds hidden: the draft arrives alongside the excerpts that were
retrieved, the facts the rule engine computed, and the result of every
automated check. Nothing is persisted until a signed-in person approves it,
and the approval is recorded under that person's verified identity.
"""

from __future__ import annotations

import copy
import json
import uuid
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from raia.agents import AGENTS
from raia.contract import vocab as V
from raia.contract.schema import record_model
from raia.deploy import friendly_llm_error
from raia.examples import EXAMPLES
from raia.fields import InputField
from raia.rationale.coverage import ORIGIN_KEY, next_requirement
from raia.projects import AccessDenied, Project, UsageLimitReached

from .record_view import record_view
from .state import current_user, flash, get_service, pkey
from .theme import CHECK, I

#: Structured reasons a reviewer can give when rejecting a draft. Free text
#: alone cannot be counted; these can.
REJECTION_REASONS = [
    ("wrong_verdict", "The classification or verdict is wrong"),
    ("missing", "Something important is missing"),
    ("unsupported", "A claim is unsupported or wrongly cited"),
    ("too_vague", "Too vague to act on"),
    ("wrong_context", "Does not fit how we actually work"),
    ("too_long", "Too long to review properly"),
    ("other", "Something else"),
]


# ---------------------------------------------------------------------------
# Structured intake form
# ---------------------------------------------------------------------------


def _state_key(agent_key: str, field_key: str) -> str:
    return pkey("in", agent_key, field_key)


def _current_inputs(agent_key: str, fields: List[InputField]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for f in fields:
        value = st.session_state.get(_state_key(agent_key, f.key))
        if value is None:
            value = [] if f.is_list else (f.default or "")
        if f.kind == "stories" and isinstance(value, list):
            value = [{k: v for k, v in s.items() if k != "uid"} for s in value if isinstance(s, dict)]
        out[f.key] = value
    return out


# ---------------------------------------------------------------------------
# Stories, one card each
# ---------------------------------------------------------------------------
#
# A story is entered with its own description, acceptance criteria and what it
# touches, so the engine can select themes per story and the agent can tell a
# story's existing criteria from the story itself. The list lives in session
# state under the field's key; each card's widgets are keyed by a stable uid, so
# removing one story never shifts another's answers.

STORY_PARTS = (("id", ""), ("title", ""), ("description", ""), ("acceptance_criteria", ""), ("capabilities", []))


def _new_story(**values: Any) -> Dict[str, Any]:
    story = {part: copy.deepcopy(default) for part, default in STORY_PARTS}
    story.update(values)
    story["uid"] = uuid.uuid4().hex[:10]
    return story


def _story_key(agent_key: str, uid: str, part: str) -> str:
    return pkey("story", agent_key, uid, part)


def _stories(agent_key: str, f: InputField) -> List[Dict[str, Any]]:
    """The field's stories as a list of dicts with uids (reading older shapes too)."""
    key = _state_key(agent_key, f.key)
    value = st.session_state.get(key)
    if isinstance(value, str):
        value = f.parse(value) if f.parse and value.strip() else []
    if not isinstance(value, list):
        value = []
    stories = [s if isinstance(s, dict) and s.get("uid") else _new_story(**(s if isinstance(s, dict) else {}))
               for s in value]
    if not stories:
        stories = [_new_story()]
    st.session_state[key] = stories
    return stories


def _sync_story(agent_key: str, story: Dict[str, Any]) -> None:
    for part, _ in STORY_PARTS:
        k = _story_key(agent_key, story["uid"], part)
        if k in st.session_state:
            story[part] = copy.deepcopy(st.session_state[k])


def _add_story(agent_key: str, field_key: str, after: Optional[str] = None, copy_of: Optional[str] = None) -> None:
    stories = st.session_state.get(_state_key(agent_key, field_key)) or []
    for s in stories:
        _sync_story(agent_key, s)
    source = next((s for s in stories if s.get("uid") == copy_of), None)
    new = _new_story(**{p: copy.deepcopy(source.get(p, d)) for p, d in STORY_PARTS if p != "id"}) if source else _new_story()
    at = next((i + 1 for i, s in enumerate(stories) if s.get("uid") == after), len(stories))
    stories.insert(at, new)
    st.session_state[_state_key(agent_key, field_key)] = stories


def _remove_story(agent_key: str, field_key: str, uid: str) -> None:
    stories = [s for s in st.session_state.get(_state_key(agent_key, field_key)) or [] if s.get("uid") != uid]
    for part, _ in STORY_PARTS:
        st.session_state.pop(_story_key(agent_key, uid, part), None)
    st.session_state[_state_key(agent_key, field_key)] = stories or [_new_story()]


def _paste_stories(agent_key: str, f: InputField) -> None:
    paste_key = pkey("story_paste", agent_key)
    text = st.session_state.get(paste_key) or ""
    parsed = f.parse(text) if f.parse else []
    stories = [s for s in st.session_state.get(_state_key(agent_key, f.key)) or []]
    for s in stories:
        _sync_story(agent_key, s)
    # A lone empty card is replaced, not kept above the pasted ones.
    stories = [s for s in stories if any(str(s.get(p) or "").strip() for p in ("title", "description", "acceptance_criteria"))]
    stories += [_new_story(**{k: v for k, v in p.items() if k in dict(STORY_PARTS)}) for p in parsed]
    st.session_state[_state_key(agent_key, f.key)] = stories or [_new_story()]
    st.session_state[paste_key] = ""
    st.session_state[pkey("story_paste_note", agent_key)] = (
        f"Added {len(parsed)} story card(s). Check each one, and answer what it touches." if parsed
        else "No story was found in the pasted text.")


def _stories_field(agent_key: str, f: InputField, disabled: bool) -> List[Dict[str, Any]]:
    stories = _stories(agent_key, f)
    st.markdown(f"**{f.label}**" + (" \\*" if f.required else ""), help=f.help or None)
    for i, story in enumerate(stories, 1):
        uid = story["uid"]
        k = lambda part: _story_key(agent_key, uid, part)  # noqa: E731
        for part, default in STORY_PARTS:
            if k(part) not in st.session_state:
                st.session_state[k(part)] = copy.deepcopy(story.get(part, default))
        with st.container(border=True):
            top = st.columns([1.2, 5, 0.45, 0.45], vertical_alignment="bottom")
            top[0].text_input("ID", key=k("id"), placeholder=f"S{i}", disabled=disabled,
                              help="The id in your tracker (S1, PROJ-42). Left empty, one is assigned.")
            top[1].text_input("Title", key=k("title"), placeholder="A short name for the story", disabled=disabled)
            top[2].button(":material/content_copy:", key=k("dup"), help="Duplicate this story",
                          on_click=_add_story, args=(agent_key, f.key, uid, uid), disabled=disabled)
            top[3].button(":material/delete:", key=k("del"), help="Remove this story",
                          on_click=_remove_story, args=(agent_key, f.key, uid), disabled=disabled)
            st.text_area("Story *", key=k("description"), height=76, disabled=disabled,
                         placeholder="As a …, I want … so that …")
            st.text_area("Acceptance criteria", key=k("acceptance_criteria"), height=88, disabled=disabled,
                         placeholder="One per line. They stay yours: RAIA adds ethical criteria and flags "
                                     "any of these that conflicts.")
            st.multiselect("What does this story touch? *", [o.value for o in f.options], key=k("capabilities"),
                           format_func=f.label_for, placeholder="Choose all that apply", disabled=disabled,
                           help="This answer selects the ethical themes for this story. Choose \"None of "
                                "these\" if it touches none.")
        _sync_story(agent_key, story)
    if not disabled:
        row = st.container(horizontal=True)
        row.button("Add a story", icon=I.ADD, key=pkey("story_add", agent_key),
                   on_click=_add_story, args=(agent_key, f.key))
        with row.popover("Paste several at once", icon=I.EXAMPLE):
            st.text_area("Paste stories", key=pkey("story_paste", agent_key), height=180,
                         placeholder="S1. As a recruiter, I want …\nAcceptance criteria:\n- …\n\n"
                                     "S2. As an HR manager, I want …",
                         help="Ids like S1 or PROJ-42, or one story per paragraph. Lines under "
                              "\"Acceptance criteria\", bullets and \"Given …\" lines become that "
                              "story's criteria.")
            st.button("Add as story cards", key=pkey("story_paste_go", agent_key), type="primary",
                      on_click=_paste_stories, args=(agent_key, f))
        note = st.session_state.pop(pkey("story_paste_note", agent_key), None)
        if note:
            st.caption(note)
    return stories


def _render_field(agent_key: str, f: InputField, disabled: bool) -> Any:
    key = _state_key(agent_key, f.key)
    label = f.label + (" *" if f.required else "")

    if f.kind == "stories":
        return _stories_field(agent_key, f, disabled)
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
                            index=None, placeholder="Choose one", disabled=disabled)
    if f.kind == "multiselect":
        return st.multiselect(label, [o.value for o in f.options], key=key, help=f.help,
                              format_func=f.label_for, placeholder="Choose all that apply",
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
                except Exception:  # noqa: BLE001 - surfaced to the person
                    st.error("That file could not be read as text. Export it as CSV or plain text.")
        if f.kind == "csv":
            return st.text_area("Or paste the rows" if not disabled else label, key=key,
                                height=f.height, placeholder=f.placeholder, disabled=disabled)
        return st.session_state.get(key, "")
    return st.text_area(label, key=key, help=f.help, height=f.height, disabled=disabled)


def _snapshot(spec) -> Dict[str, Any]:
    out = {}
    for f in spec.input_fields:
        value = st.session_state.get(_state_key(spec.key, f.key))
        if value not in (None, "", []) and not (f.kind == "stories" and f.is_empty(value)):
            # A copy: the stories list is edited in place, and the last saved
            # snapshot must not change with it or no change would ever be saved.
            out[f.key] = copy.deepcopy(value)
    origin = st.session_state.get(_origin_key(spec.key))
    if origin:
        out[ORIGIN_KEY] = origin
    recs = st.session_state.get(_recs_key(spec.key))
    if recs:
        out[RECS_KEY] = recs
    return out


# ---------------------------------------------------------------------------
# Where answers came from: suggestions and adopted recommendations
# ---------------------------------------------------------------------------
#
# A suggestion fills only an empty field and is remembered as one, so the
# engine can tell a pre-filled answer from one the team gave, and the form can
# say so beside the field. A recommended requirement enters the requirements
# only when a person adopts it, one at a time, and is remembered with the id it
# was given. Nothing here reaches an artifact without the usual approval.

RECS_KEY = "_recommendations"


def _origin_key(agent_key: str) -> str:
    return pkey("origin", agent_key)


def _recs_key(agent_key: str) -> str:
    return pkey("recs", agent_key)


def _origin(agent_key: str) -> Dict[str, Any]:
    return st.session_state.setdefault(_origin_key(agent_key), {"fields": {}, "adopted": []})


def pending_suggestions(agent_key: str) -> List[str]:
    """Labels of pre-filled fields still holding exactly what was suggested."""
    agent = AGENTS[agent_key]
    out = []
    for key, meta in (st.session_state.get(_origin_key(agent_key)) or {}).get("fields", {}).items():
        current = st.session_state.get(_state_key(agent_key, key)) or []
        if sorted(current) == sorted(meta.get("values") or []):
            f = agent.spec.field_by_key(key)
            out.append(f.label if f else key)
    return out


def origin_for_run(agent_key: str) -> Dict[str, Any]:
    """What the engine needs to know about where the answers came from."""
    origin = st.session_state.get(_origin_key(agent_key)) or {}
    return {"fields": origin.get("fields") or {}, "adopted": origin.get("adopted") or []}


def _apply_suggestions(project: Project, agent) -> Tuple[List[str], List[str]]:
    """Fill empty context fields from the approved classification. Returns (filled, kept)."""
    spec = agent.spec
    result = get_service().suggest_intake(current_user(), project.id, spec.key)
    origin = _origin(spec.key)
    origin["control_hints"] = result.get("control_hints") or []
    origin["basis"] = result.get("basis", "")
    filled, kept = [], []
    for key, meta in (result.get("fields") or {}).items():
        f = spec.field_by_key(key)
        if f is None:
            continue
        current = st.session_state.get(_state_key(spec.key, key))
        if current not in (None, "", []):
            kept.append(f.label)
            continue
        allowed = {o.value for o in f.options}
        values = [v for v in meta.get("values") or [] if v in allowed]
        if not values:
            continue
        st.session_state[_state_key(spec.key, key)] = values
        origin["fields"][key] = {"values": values, "reasons": meta.get("reasons") or {}}
        filled.append(f.label)
    return filled, kept


def _recommend(project: Project, agent) -> None:
    """The one button: suggest context answers, then ask for candidate requirements."""
    spec = agent.spec
    filled, kept = _apply_suggestions(project, agent)
    msgs = []
    if filled:
        msgs.append("Pre-filled from the approved risk classification: **" + "**, **".join(filled)
                    + "**. Review them before running.")
    if kept:
        msgs.append("Your answers to **" + "**, **".join(kept) + "** were left as they were.")
    if hasattr(agent, "recommend"):
        inputs = _current_inputs(spec.key, spec.input_fields)
        with st.spinner("Reading the approved classification and the norms for candidate requirements"):
            try:
                result = get_service().recommend_requirements(current_user(), project.id, spec.key, inputs)
            except (AccessDenied, UsageLimitReached) as exc:
                flash(" ".join(msgs + [str(exc)]))
                return
            except Exception as exc:  # noqa: BLE001 - surfaced to the person
                flash(" ".join(msgs + [friendly_llm_error(exc)]))
                return
        st.session_state[_recs_key(spec.key)] = {
            "candidates": result.get("candidates") or [],
            "dropped": result.get("dropped") or [],
            "note": result.get("note", ""),
            "evidence": {e["citation"]: e for e in result.get("evidence") or []},
        }
        n = len(result.get("candidates") or [])
        msgs.append(f"{n} candidate requirement(s) to review below." if n
                    else (result.get("note") or "No candidate passed the checks."))
    flash(" ".join(msgs) or "Nothing to suggest: the risk classification has no structured data.")


def _adopt(project_id: str, agent_key: str, cid: str) -> None:
    """Callback: add one candidate to the requirements, in the team's format, and remember it."""
    recs = st.session_state.get(_recs_key(agent_key)) or {}
    cand = next((c for c in recs.get("candidates") or [] if c["id"] == cid), None)
    if not cand or cand.get("status") != "open":
        return
    statement = " ".join((st.session_state.get(pkey("cand", agent_key, cid, "statement")) or "").split())
    fit = " ".join((st.session_state.get(pkey("cand", agent_key, cid, "fit")) or "").split())
    if not statement or not fit:
        st.session_state[pkey("cand_err", agent_key, cid)] = "A requirement needs a statement and a fit criterion."
        return
    edited = statement != cand["statement"] or fit != cand["fit_criterion"]
    req_key = _state_key(agent_key, "requirements")
    fmt = st.session_state.get(_state_key(agent_key, "requirement_format")) or "numbered"
    line = f"{statement.rstrip('.')}. Fit criterion: {fit}"
    added = next_requirement(st.session_state.get(req_key) or "", fmt, line)
    st.session_state[req_key] = added["text"]
    origin = _origin(agent_key)
    origin["adopted"] = [a for a in origin.get("adopted") or [] if a.get("id") != added["id"]] + [{
        "id": added["id"], "text": added["line"], "candidate_id": cid,
        "addresses": cand["addresses"], "edited": edited,
    }]
    cand["status"], cand["requirement_id"] = "adopted", added["id"]
    get_service().record_recommendation_decision(current_user(), project_id, agent_key, cand,
                                                 "adopted", added["id"], edited)


def _reject(project_id: str, agent_key: str, cid: str) -> None:
    recs = st.session_state.get(_recs_key(agent_key)) or {}
    cand = next((c for c in recs.get("candidates") or [] if c["id"] == cid), None)
    if not cand or cand.get("status") != "open":
        return
    cand["status"] = "rejected"
    get_service().record_recommendation_decision(current_user(), project_id, agent_key, cand, "rejected")


def _clear_recs(agent_key: str) -> None:
    st.session_state.pop(_recs_key(agent_key), None)


def _candidate_panel(project: Project, agent, can_run: bool) -> None:
    spec = agent.spec
    recs = st.session_state.get(_recs_key(spec.key)) or {}
    cands = recs.get("candidates") or []
    dropped = recs.get("dropped") or []
    if not cands and not dropped:
        return
    with st.container(border=True):
        st.markdown(f"{I.SUGGEST} **Recommended requirements — adopt, edit or reject each one**")
        st.caption("RAIA proposed these for gaps your current answers leave. None of them counts "
                   "until you adopt it; an adopted one is added to your requirements and is marked in "
                   "the record as a recommendation you adopted, not one the team wrote.")
        evidence = recs.get("evidence") or {}
        for c in cands:
            cid = c["id"]
            if c.get("status") == "adopted":
                st.markdown(f"{I.OK} `{c['addresses']}` — adopted as **{c.get('requirement_id', '')}**.")
                continue
            if c.get("status") == "rejected":
                st.markdown(f"{I.DISCARD} {c['addresses']} — rejected.")
                continue
            with st.container(border=True):
                st.markdown(f"**{cid}** · addresses `{c['addresses']}` — {c.get('gap_subject', '')}")
                sk, fk = pkey("cand", spec.key, cid, "statement"), pkey("cand", spec.key, cid, "fit")
                if sk not in st.session_state:
                    st.session_state[sk] = c["statement"]
                if fk not in st.session_state:
                    st.session_state[fk] = c["fit_criterion"]
                st.text_area("Requirement", key=sk, height=80, disabled=not can_run)
                st.text_input("Fit criterion (how it is verified)", key=fk, disabled=not can_run)
                meta = [f"Verified by {c.get('verification_method', 'inspection')}"]
                if c.get("value"):
                    meta.append(f"protects {c['value'].replace('_', ' ')}")
                st.caption(" · ".join(meta))
                with st.expander("Grounds", icon=I.EVIDENCE):
                    for tag in c.get("citations") or []:
                        st.markdown(f"`{tag}`")
                        ex = evidence.get(tag)
                        if ex:
                            st.caption(ex.get("text", "")[:600])
                err = st.session_state.pop(pkey("cand_err", spec.key, cid), None)
                if err:
                    st.error(err)
                if can_run:
                    row = st.container(horizontal=True)
                    row.button("Adopt", key=pkey("cand_adopt", spec.key, cid), type="primary",
                               icon=I.APPROVE, on_click=_adopt, args=(project.id, spec.key, cid))
                    row.button("Reject", key=pkey("cand_reject", spec.key, cid), icon=I.DISCARD,
                               on_click=_reject, args=(project.id, spec.key, cid))
        if dropped:
            with st.expander(f"{len(dropped)} candidate(s) failed the checks and were not shown",
                             icon=I.WARN):
                for d in dropped:
                    st.markdown(f"- `{d.get('addresses') or '?'}` — {d.get('reason', '')}")
        if can_run:
            st.button("Dismiss recommendations", key=pkey("recs_clear", spec.key),
                      on_click=_clear_recs, args=(spec.key,))


def _field_origin_note(agent_key: str, f: InputField) -> None:
    """Say, under a field, that its answer was suggested — and why — until a person changes it."""
    origin = st.session_state.get(_origin_key(agent_key)) or {}
    if f.key == "existing_controls" and origin.get("control_hints"):
        hints = origin["control_hints"]
        st.caption(f"{I.INFO} The approved classification assigns obligations these controls would "
                   "discharge: " + "; ".join(f"{h['label'].split(',')[0]} ({', '.join(h['obligations'])})"
                                             for h in hints)
                   + ". Tick only those actually in place — this field is never pre-filled.")
        return
    meta = (origin.get("fields") or {}).get(f.key)
    if not meta:
        return
    current = st.session_state.get(_state_key(agent_key, f.key)) or []
    if sorted(current) != sorted(meta.get("values") or []):
        st.caption(f"{I.REVISE} Adjusted from a suggestion.")
        return
    st.caption(f"{I.SUGGEST} Suggested from the approved risk classification — review it.")
    with st.expander("Why each value was suggested"):
        for value, why in (meta.get("reasons") or {}).items():
            st.markdown(f"- **{f.label_for(value)}** — {why}")


def _load_saved_intake(project: Project, spec) -> None:
    """Fill the form from the project's saved answers.

    Streamlit forgets the state of widgets that were not drawn in a run, which
    happens every time a person reads another page and comes back. Answers
    belong to the project, not to the browser, so any field whose state is
    missing is refilled from storage; fields already on screen are left alone.
    """
    missing = [f for f in spec.input_fields
               if _state_key(spec.key, f.key) not in st.session_state]
    if not missing:
        return
    saved = get_service().load_intake(current_user(), project.id, spec.key)
    if isinstance(saved.get(ORIGIN_KEY), dict) and _origin_key(spec.key) not in st.session_state:
        st.session_state[_origin_key(spec.key)] = saved[ORIGIN_KEY]
    if isinstance(saved.get(RECS_KEY), dict) and _recs_key(spec.key) not in st.session_state:
        st.session_state[_recs_key(spec.key)] = saved[RECS_KEY]
    for f in missing:
        value = saved.get(f.key)
        if value in (None, "", []):
            continue
        if f.kind == "stories" and isinstance(value, str) and f.parse:
            # Saved before stories were entered one by one: split the text, and
            # give every story the capabilities once declared for the whole sprint.
            caps = [c for c in saved.get("touched_capabilities") or [] if c]
            value = [{**s, "capabilities": s.get("capabilities") or list(caps)} for s in f.parse(value)]
        if f.kind in ("select", "boolean") and value not in [o.value for o in f.options]:
            continue
        st.session_state[_state_key(spec.key, f.key)] = value
    st.session_state[pkey("saved", spec.key)] = {**saved, **_snapshot(spec)}


def _autosave_intake(project: Project, spec) -> None:
    snap = _snapshot(spec)
    if snap != st.session_state.get(pkey("saved", spec.key)):
        get_service().save_intake(current_user(), project.id, spec.key, snap)
        st.session_state[pkey("saved", spec.key)] = snap


def intake_form(project: Project, agent, can_run: bool) -> Dict[str, Any]:
    """Render the agent's typed fields, grouped, honouring conditional visibility."""
    spec = agent.spec
    _load_saved_intake(project, spec)
    if spec.intro:
        st.info(spec.intro, icon=I.INFO)
    if not can_run:
        st.caption("You are a reviewer on this project: you can read the inputs, but only "
                   "owners and editors change them and run agents.")
    _intake_fields(project, agent, can_run)
    current = _current_inputs(spec.key, spec.input_fields)
    out = {f.key: current[f.key] for f in spec.input_fields if f.visible(current)}
    origin = origin_for_run(spec.key)
    if origin["fields"] or origin["adopted"]:
        out[ORIGIN_KEY] = origin
    return out


@st.fragment
def _intake_fields(project: Project, agent, can_run: bool) -> None:
    """The fields themselves, redrawn on their own.

    Changing an answer re-runs only this fragment — the fields, their
    conditional visibility and the autosave — not the whole stage page with its
    header, status and tracker, each of which reads from the database. The Run
    button sits outside, so pressing it re-runs the page and reads every answer
    from the session.
    """
    spec = agent.spec
    if can_run and st.button("Load example (resume-screening scenario)", key=pkey("ex", spec.key),
                             icon=I.EXAMPLE, type="secondary"):
        for f in spec.input_fields:
            value = EXAMPLES.get(spec.key, {}).get(f.key)
            if value is not None:
                st.session_state[_state_key(spec.key, f.key)] = copy.deepcopy(value)
        st.session_state.pop(_origin_key(spec.key), None)
        st.session_state.pop(_recs_key(spec.key), None)
        st.rerun()

    recommends = hasattr(agent, "recommend")
    if can_run and (spec.suggest is not None or recommends):
        with st.container(border=True):
            st.markdown(f"{I.SUGGEST} **{'Recommend ethical requirements' if recommends else 'Suggest answers'}**")
            st.caption(
                "RAIA reads the approved risk classification, pre-fills the stakeholder and principle "
                "questions you have left empty, and proposes a few candidate requirements for the gaps "
                "your answers leave, each grounded in the norms and checked before you see it. You adopt, "
                "edit or reject every one; the controls you have in place are never guessed. "
                "Answer that question first, so no candidate proposes work you have already done."
                + (" Proposing requirements uses one agent run from today's allowance." if recommends else "")
            )
            if st.button("Recommend ethical requirements" if recommends else "Suggest answers",
                         key=pkey("recommend", spec.key), icon=I.SUGGEST):
                _recommend(project, agent)
                st.rerun()

    target = getattr(agent, "RECOMMEND_TARGET", None)
    target_group = spec.field_by_key(target).group if target and spec.field_by_key(target) else None

    for group in spec.field_groups():
        fields = [f for f in spec.input_fields if f.group == group]
        current = _current_inputs(spec.key, spec.input_fields)
        visible = [f for f in fields if f.visible(current)]
        if not visible:
            continue
        with st.container(border=True):
            st.markdown(f"**{group}**")
            for f in visible:
                _render_field(spec.key, f, disabled=not can_run)
                _field_origin_note(spec.key, f)
        if group == target_group:
            _candidate_panel(project, agent, can_run)

    if can_run:
        _autosave_intake(project, spec)
        st.caption("Answers are saved to this project as you type.")


# ---------------------------------------------------------------------------
# The human approval gate
# ---------------------------------------------------------------------------


def validation_panel(validation: Dict[str, Any]) -> None:
    items = validation.get("items") or []
    if not items:
        return
    level = validation.get("level", "pass")
    headline = validation.get("headline", "")
    box = st.error if level == "fail" else (st.warning if level == "warn" else st.success)
    box(f"**Automated checks — {headline}**", icon=CHECK.get(level, I.INFO))
    with st.expander("What was checked", expanded=level == "fail"):
        for item in items:
            mark = {"pass": ":green[Pass]", "warn": ":orange[Warning]", "fail": ":red[Fail]"}.get(
                item["level"], item["level"])
            st.markdown(f"{mark} **{item['title']}** — {item['detail']}")
            for sub in item.get("items", [])[:12]:
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;• `{sub}`")
        st.caption(
            "Checks inform; they never block. A failed check on an otherwise sound draft "
            "is a reason to look closely, not a reason for the software to overrule you."
        )


def evidence_panel(evidence: List[Dict[str, Any]]) -> None:
    if not evidence:
        st.caption("No excerpts were retrieved for this run.")
        return
    pinned = [e for e in evidence if e.get("pinned")]
    st.caption(
        f"{len(evidence)} excerpt(s) were in the prompt, {len(pinned)} of them required by the "
        "decision procedure. Every citation in the draft is checked against exactly this set."
    )
    for e in evidence:
        tag = "Required · " if e.get("pinned") else ""
        title = f"{tag}{e['source_name'] if 'source_name' in e else e['source']} — {e['section']}"
        with st.expander(f"{title}  ·  _{e['authority']}_"):
            if e.get("pinned") and e.get("pin_reason"):
                st.caption(f"Required by the decision procedure: {e['pin_reason']}")
            if e.get("derived"):
                st.caption(
                    "This text is a curated summary prepared for the project, not the "
                    "official source. Verify anything consequential against the original."
                )
            st.markdown(f"`{e['citation']}`")
            st.text(e["text"])


def _next_step_hint(agent_key: str, impact: List[str]) -> str:
    if impact:
        return ("These stages were approved against the previous version and are now flagged "
                "for review: **" + "**, **".join(impact) + "**.")
    keys = list(AGENTS)
    i = keys.index(agent_key)
    if i + 1 < len(keys):
        return f"Next stage: **{AGENTS[keys[i + 1]].spec.name}**."
    return "Pipeline complete. When you are done, please complete the **Assessment**."


def _options(values) -> Dict[str, Any]:
    return {"options": list(values), "required": True}


def _frame(rows: List[Dict[str, Any]], columns: List[str]) -> pd.DataFrame:
    return pd.DataFrame([{c: r.get(c, "") for c in columns} for r in rows], columns=columns)


def _records(frame: Any) -> List[Dict[str, Any]]:
    rows = frame.to_dict("records") if hasattr(frame, "to_dict") else list(frame or [])
    out = []
    for r in rows:
        clean = {k: ("" if (v is None or (isinstance(v, float) and v != v)) else v) for k, v in r.items()}
        if any(str(v).strip() for v in clean.values()):
            out.append(clean)
    return out


def _csv(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [p.strip() for p in str(value or "").split(",") if p.strip()]


def record_editor(agent_key: str, payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Structured editing of a draft record. Returns (edited record, errors)."""
    original = payload.get("record") or {}
    if not original:
        st.info("This draft predates the standard record and can only be approved as it is, "
                "or rejected to regenerate it in the standard format.", icon=I.INFO)
        return None, []
    k = lambda *parts: pkey("rec", agent_key, str(payload.get("attempt", 1)), *parts)  # noqa: E731
    rec = copy.deepcopy(original)

    st.caption("Change fields, not prose. Risk level, priority, identifiers and the issues the "
               "rule engine raised are recomputed by the software when you approve.")
    rec["headline"] = st.text_input("Headline", original.get("headline", ""), key=k("headline"),
                                    help="The bottom line in one sentence.")
    rec["summary"] = st.text_area("Summary", original.get("summary", ""), height=90, key=k("summary"))
    rec["overall_status"] = st.selectbox(
        "Overall status", list(V.OVERALL_STATUSES), key=k("status"),
        index=V.rank(V.OVERALL_STATUSES, original.get("overall_status", "on_track")),
        format_func=lambda v: v.replace("_", " ").capitalize(),
        help="The software raises this if a finding or issue requires it; it never lowers it.")

    st.markdown("**Findings** — placement on the NIST AI RMF likelihood and magnitude scales")
    f_cols = ["id", "title", "statement", "principle", "nist_category", "magnitude", "likelihood", "placement_rationale"]
    findings = st.data_editor(
        _frame(original.get("findings") or [], f_cols), key=k("findings"), num_rows="fixed",
        hide_index=True, width="stretch",
        column_config={
            "id": st.column_config.TextColumn("ID", disabled=True),
            "title": st.column_config.TextColumn("Finding"),
            "statement": st.column_config.TextColumn("Statement"),
            "placement_rationale": st.column_config.TextColumn("Why this placement"),
            "principle": st.column_config.SelectboxColumn("Principle", **_options(V.PRINCIPLE_KEYS)),
            "nist_category": st.column_config.SelectboxColumn("NIST AI RMF", **_options(V.NIST_CATEGORIES)),
            "magnitude": st.column_config.SelectboxColumn("Magnitude", **_options(V.MAGNITUDE)),
            "likelihood": st.column_config.SelectboxColumn("Likelihood", **_options(V.LIKELIHOOD)),
        })
    by_id = {f["id"]: f for f in original.get("findings") or []}
    rec["findings"] = [{**by_id.get(r["id"], {}), **r} for r in _records(findings)]

    st.markdown("**Action plan** — add a row for a new action; leave its ID empty")
    a_cols = ["id", "action", "finding_ids", "response", "owner_role", "lifecycle_stage",
              "review_cadence", "verification_method", "evidence_artifact"]
    actions_in = [{**a, "finding_ids": ", ".join(a.get("finding_ids") or [])} for a in original.get("actions") or []]
    actions = st.data_editor(
        _frame(actions_in, a_cols), key=k("actions"), num_rows="dynamic", hide_index=True, width="stretch",
        column_config={
            "id": st.column_config.TextColumn("ID", disabled=True),
            "action": st.column_config.TextColumn("Action"),
            "evidence_artifact": st.column_config.TextColumn("Evidence artifact"),
            "finding_ids": st.column_config.TextColumn("Findings (comma-separated ids)"),
            "response": st.column_config.SelectboxColumn("Response", **_options(V.RESPONSES)),
            "owner_role": st.column_config.SelectboxColumn("Owner", **_options(V.OWNER_ROLES)),
            "lifecycle_stage": st.column_config.SelectboxColumn("Lifecycle stage", **_options(V.LIFECYCLE_STAGES)),
            "review_cadence": st.column_config.SelectboxColumn("Review cadence", **_options(V.REVIEW_CADENCES)),
            "verification_method": st.column_config.SelectboxColumn("Verification", **_options(V.VERIFICATION_METHODS)),
        })
    a_by_id = {a["id"]: a for a in original.get("actions") or []}
    rec["actions"] = []
    for i, r in enumerate(_records(actions), 1):
        base = a_by_id.get(r.get("id"), {})
        rec["actions"].append({**base, **r, "id": r.get("id") or f"new-{i}",
                               "finding_ids": _csv(r.get("finding_ids"))})

    st.markdown("**Open issues raised by the agent** — the rule engine's and the software's are kept as they are")
    fixed = [i for i in original.get("open_issues") or [] if i.get("origin") in ("engine", "code")]
    for i in fixed:
        st.caption(f"{i.get('id')} · {V.ISSUE_TYPE_LABELS.get(i.get('type'), i.get('type'))} · {i.get('description')}")
    i_cols = ["id", "type", "description", "decision_owner", "blocking"]
    agent_issues = [i for i in original.get("open_issues") or [] if i.get("origin") not in ("engine", "code")]
    frame = _frame(agent_issues, i_cols)
    frame["blocking"] = frame["blocking"].astype(bool) if len(frame) else frame["blocking"]
    issues = st.data_editor(
        frame, key=k("issues"), num_rows="dynamic", hide_index=True, width="stretch",
        column_config={
            "id": st.column_config.TextColumn("ID", disabled=True),
            "description": st.column_config.TextColumn("Description"),
            "type": st.column_config.SelectboxColumn("Type", **_options(V.ISSUE_TYPES)),
            "decision_owner": st.column_config.SelectboxColumn("Decided by", **_options(V.OWNER_ROLES)),
            "blocking": st.column_config.CheckboxColumn("Blocking", default=False),
        })
    i_by_id = {i["id"]: i for i in agent_issues}
    rec["open_issues"] = fixed + [
        {**i_by_id.get(r.get("id"), {}), **r, "blocking": bool(r.get("blocking")), "origin": "agent"}
        for r in _records(issues)
    ]

    errors: List[str] = []
    with st.expander("Agent-specific sections (JSON)"):
        st.caption("The part of the record shaped by this agent's normative source. It is checked "
                   "against the schema before it can be approved.")
        raw = st.text_area("Extension", json.dumps(original.get("extension") or {}, indent=2, ensure_ascii=False),
                           height=320, key=k("extension"), label_visibility="collapsed")
        try:
            rec["extension"] = json.loads(raw)
        except ValueError as exc:
            errors.append(f"extension: not valid JSON ({exc})")

    # A draft is checked against the schema only once a person has changed it:
    # an untouched draft written under an earlier version of the contract stays
    # approvable exactly as it was generated.
    if not errors and not original.get("schema_errors") and _edited_changes(original, rec):
        try:
            record_model(agent_key).model_validate(rec)
        except Exception as exc:  # noqa: BLE001 - shown to the reviewer
            errors += [f"{'.'.join(str(p) for p in e.get('loc', ()))}: {e.get('msg')}"
                       for e in getattr(exc, "errors", lambda: [])()] or [str(exc)]
    if errors:
        st.error("The edited record does not conform to the standard, so it cannot be approved "
                 "yet:\n\n" + "\n".join(f"- {e}" for e in errors[:10]), icon=I.ERROR)
    return rec, errors


def _edited_changes(original: Dict[str, Any], edited: Optional[Dict[str, Any]]) -> bool:
    if not edited or not original:
        return False
    from raia.pipeline import _core

    return _core(edited) != _core(original)


def _preview(agent_key: str, payload: Dict[str, Any], edited: Dict[str, Any]) -> Dict[str, Any]:
    """The edited record, re-computed exactly as it would be on approval."""
    from raia.pipeline import _rationale_stub

    agent = AGENTS[agent_key]
    stub = _rationale_stub(payload)
    return agent.finalize_record(edited, stub, payload.get("evidence") or [], payload.get("attempt", 1))


def _computed_data(payload: Dict[str, Any]) -> Dict[str, Any]:
    return dict((payload.get("rationale") or {}).get("data") or {})


def draft_view(agent_key: str, payload: Dict[str, Any], record: Optional[Dict[str, Any]] = None) -> None:
    """A draft in the three tiers every record is read in."""
    record = record if record is not None else (payload.get("record") or {})
    record_view(agent_key, record, _computed_data(payload),
                key=pkey("draft", agent_key, str(payload.get("attempt", 1))),
                fallback_markdown=payload.get("draft") or "")
    st.download_button("Download this draft (Markdown)", payload.get("draft") or "",
                       file_name=f"{payload.get('artifact_key', agent_key)}-draft.md", mime="text/markdown",
                       key=pkey("dl_draft", agent_key, str(payload.get("attempt", 1))), icon=I.DOWNLOAD,
                       type="tertiary")


def review_gate(project: Project, agent_key: str, payload: Dict[str, Any]) -> None:
    """The human checkpoint: evidence, checks, edit, approve or reject."""
    user = current_user()
    svc = get_service()

    with st.container(border=True):
        st.subheader("Human review required", anchor=False)
        ran_by = payload.get("run_by_name")
        st.caption(
            f"Draft #{payload.get('attempt', 1)} by **{payload['agent_name']}**"
            + (f", run by {ran_by}" if ran_by else "")
            + ". Nothing is persisted until it is approved. You may edit the record before approving."
        )
    if payload.get("restored"):
        st.info("This review was restored after the app restarted. The draft is exactly as it "
                "was; approving it still goes through the normal gate.", icon=I.RESTORE)
    if payload.get("sanitization"):
        st.warning("**Input sanitization notice** — patterns often used for prompt injection "
                   "were found in the inputs: " + "; ".join(payload["sanitization"]), icon=I.WARN)

    validation_panel(payload.get("validation") or {})

    tab_read, tab_edit, tab_evidence, tab_reason = st.tabs(
        [":material/article: Draft", ":material/edit: Edit the record",
         ":material/menu_book: Evidence", ":material/calculate: What the code computed"]
    )
    with tab_edit:
        edited_record, edit_errors = record_editor(agent_key, payload)
    changed = _edited_changes(payload.get("record") or {}, edited_record) and not edit_errors
    with tab_read:
        if changed:
            st.caption("Showing your edits, re-computed. Nothing is saved until you approve.")
            try:
                draft_view(agent_key, payload, _preview(agent_key, payload, edited_record))
            except Exception as exc:  # noqa: BLE001 - shown to the reviewer
                st.error(f"The edited record could not be rendered: {exc}")
        else:
            draft_view(agent_key, payload)
    with tab_evidence:
        evidence_panel(payload.get("evidence") or [])
    with tab_reason:
        st.caption(
            "Computed before the model was called. These facts, tables and identifiers are "
            "ground truth for the agent: it may argue with a verdict, but it cannot restate one."
        )
        st.markdown(payload.get("rationale_md") or "_No rule engine for this agent._")

    blocked_by_four_eyes = svc.second_approver_blocks(user, project.id, payload)
    impact = svc.revision_impact(user, project.id, agent_key)

    col_a, col_r = st.columns(2, gap="large")
    with col_a, st.container(border=True):
        st.markdown("**Approve**")
        st.caption(f"Recorded in the audit trail as **{user.label}**, your signed-in identity.")
        if impact:
            st.warning("Approving will flag these approved stages for review: **"
                       + "**, **".join(impact) + "**.", icon=I.WARN)
        if blocked_by_four_eyes:
            st.warning("This project requires a **second approver**: you ran this stage, so "
                       "someone else must approve it. Invite a reviewer from the project's "
                       "**People** tab.", icon=I.LOCK)
        if edit_errors:
            st.caption("Fix the edited record before approving, or reject to regenerate.")
        if st.button("Approve and commit", type="primary", key=pkey("approve", agent_key),
                     disabled=blocked_by_four_eyes or bool(edit_errors), icon=I.APPROVE):
            with st.spinner("Committing to the audit trail"):
                try:
                    decision = {"action": "approve"}
                    if changed:
                        decision["record"] = edited_record
                    result = svc.resume(user, project.id, agent_key, decision)
                except AccessDenied as exc:
                    st.error(str(exc))
                    return
                except Exception as exc:  # noqa: BLE001 - surfaced to the person
                    st.error(friendly_llm_error(exc))
                    return
            st.session_state.pop(pkey("pending", agent_key), None)
            st.session_state.pop(pkey("revising", agent_key), None)
            flash(f"Approved and committed (`{result.get('commit', '')}`). "
                  + _next_step_hint(agent_key, impact))
            st.rerun()

    with col_r, st.container(border=True):
        st.markdown("**Reject and regenerate**")
        reason = st.selectbox(
            "Main reason", [c for c, _ in REJECTION_REASONS],
            format_func=lambda c: dict(REJECTION_REASONS)[c],
            key=pkey("reason", agent_key),
        )
        feedback = st.text_area(
            "What should the agent fix?", key=pkey("fb", agent_key), height=90,
            placeholder="Be specific: this goes straight into the next attempt.",
        )
        if st.button("Reject and regenerate", key=pkey("reject", agent_key), icon=I.REJECT):
            with st.spinner("Regenerating with your feedback"):
                try:
                    result = svc.resume(
                        user, project.id, agent_key,
                        {"action": "reject",
                         "feedback": feedback or dict(REJECTION_REASONS)[reason],
                         "reason": reason},
                    )
                except (AccessDenied, UsageLimitReached) as exc:
                    st.error(str(exc))
                    return
                except Exception as exc:  # noqa: BLE001 - surfaced to the person
                    st.error(friendly_llm_error(exc))
                    return
            st.session_state[pkey("pending", agent_key)] = result["payload"]
            st.rerun()
