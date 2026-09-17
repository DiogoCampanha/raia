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
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from raia.agents import AGENTS
from raia.contract import vocab as V
from raia.contract.schema import record_model
from raia.deploy import friendly_llm_error
from raia.examples import EXAMPLES
from raia.fields import InputField
from raia.projects import AccessDenied, Project, UsageLimitReached

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
        if value not in (None, "", []):
            out[f.key] = value
    return out


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
    for f in missing:
        value = saved.get(f.key)
        if value in (None, "", []):
            continue
        if f.options and not f.is_multi and value not in [o.value for o in f.options]:
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
    elif st.button("Load example (resume-screening scenario)", key=pkey("ex", spec.key),
                   icon=I.EXAMPLE, type="secondary"):
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
        with st.container(border=True):
            st.markdown(f"**{group}**")
            for f in visible:
                _render_field(spec.key, f, disabled=not can_run)

    if can_run:
        _autosave_intake(project, spec)
        st.caption("Answers are saved to this project as you type.")

    current = _current_inputs(spec.key, spec.input_fields)
    return {f.key: current[f.key] for f in spec.input_fields if f.visible(current)}


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
    rec["summary"] = st.text_area("Summary", original.get("summary", ""), height=110, key=k("summary"))
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

    if not errors and not original.get("schema_errors"):
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


def _preview(agent_key: str, payload: Dict[str, Any], edited: Dict[str, Any]) -> str:
    from raia.pipeline import _rationale_stub
    from raia.sanitize import sanitization_notice

    agent = AGENTS[agent_key]
    stub = _rationale_stub(payload)
    record = agent.finalize_record(edited, stub, payload.get("evidence") or [], payload.get("attempt", 1))
    text = agent.render_record(record, stub)
    if payload.get("sanitization"):
        text = sanitization_notice(payload["sanitization"]) + text
    return text


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
            st.caption("Showing your edits, re-computed and re-rendered. Nothing is saved until you approve.")
            try:
                st.markdown(_preview(agent_key, payload, edited_record))
            except Exception as exc:  # noqa: BLE001 - shown to the reviewer
                st.error(f"The edited record could not be rendered: {exc}")
        else:
            st.markdown(payload["draft"])
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
