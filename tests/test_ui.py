#!/usr/bin/env python3
"""
Headless walkthrough of the Streamlit UI, organized around projects.

    python tests/test_ui.py

Uses Streamlit's app-test harness with the mock model and the ``dev`` sign-in,
and walks what a panelist does: consent, create the demo project, run and
approve a stage, open a second project at a different stage and switch between
them without anything bleeding across, invite a reviewer, and rate the whole
experience in one form.
"""

import os
import sys
import tempfile
from pathlib import Path

os.environ["RAIA_LLM_PROVIDER"] = "mock"
os.environ["RAIA_FAKE_EMBED"] = "1"
os.environ["RAIA_AUTH"] = "dev"
_tmp = tempfile.mkdtemp(prefix="raia_ui_")
os.environ["RAIA_WORKSPACE_DIR"] = str(Path(_tmp) / "workspace")
os.environ["RAIA_CHROMA_DIR"] = str(Path(_tmp) / "chroma")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from streamlit.testing.v1 import AppTest  # noqa: E402


def check(cond: bool, label: str) -> None:
    print(("  PASS  " if cond else "  FAIL  ") + label)
    if not cond:
        sys.exit(1)


def ok(at: AppTest, label: str) -> AppTest:
    warnings = [w.value for w in at.warning if "Session State API" in str(w.value)]
    check(not warnings, f"no widget/session-state conflicts ({warnings or 'none'})")
    if at.exception:
        for e in at.exception:
            print(e.value)
            print("\n".join(e.stack_trace))
    check(not at.exception, label)
    return at


def button(at: AppTest, key: str):
    return next(b for b in at.button if b.key == key)


def text(at: AppTest) -> str:
    parts = [m.value for m in at.markdown] + [m.value for m in at.info] + [m.value for m in at.success]
    parts += [t.value for t in at.title] + [c.value for c in at.caption] + [w.value for w in at.warning]
    parts += [e.value for e in at.error]
    return "\n".join(str(p) for p in parts)


def main() -> None:
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)

    print("== 1. First visit asks for consent ==")
    ok(at.run(), "the app starts")
    check("Before you start" in text(at), "a new person sees the privacy notice first")
    at.checkbox[0].check()
    ok(at.run(), "consent can be given")
    next(b for b in at.button if b.label == "Continue").click()
    ok(at.run(), "consent is recorded")
    check("My projects" in text(at), "then lands on My projects")

    print("== 2. The demo project ==")
    button(at, "demo_project").click()
    ok(at.run(), "the demo project is created")
    pid1 = at.session_state["project_id"]
    check("Demo — resume screening" in text(at), "…and opened on its overview")
    rate_btn = button(at, "nav_rate")
    check(rate_btn.proto.type == "primary", "the rating entry is highlighted in the sidebar")

    print("== 3. Run and approve a stage ==")
    at.sidebar.radio[0].set_value("risk_classifier")
    ok(at.run(), "the Risk Classifier page opens")
    check(at.session_state[f"{pid1}::in::risk_classifier::product_brief"],
          "the demo project's saved answers fill the form")
    check(not any("Rate this stage" in str(e.label) for e in at.expander),
          "the per-stage rating widget is gone")
    button(at, f"{pid1}::run::risk_classifier").click()
    ok(at.run(), "the run pauses at the gate")
    check("Human review required" in "\n".join(s.value for s in at.subheader), "the gate is shown")
    check(not any(t.label.startswith("Your name") for t in at.text_input),
          "the gate no longer asks for a typed name")
    check("Recorded in the audit trail as" in text(at), "…it names the signed-in approver instead")
    button(at, f"{pid1}::approve::risk_classifier").click()
    ok(at.run(), "the draft is approved")
    check("Approved and committed" in text(at), "approval is confirmed")
    check(at.sidebar.radio[0].value == "risk_classifier", "approving no longer resets the navigation")

    print("== 4. A second project at a different stage ==")
    button(at, "nav_projects").click()
    ok(at.run(), "back to My projects")
    check("1/5 approved" in text(at), "the project card shows derived progress")
    at.text_input[0].input("Credit-limit recommender")
    next(b for b in at.button if b.label == "Create project").click()
    ok(at.run(), "a second project is created")
    pid2 = at.session_state["project_id"]
    check(pid2 != pid1, "…and opened")
    at.sidebar.radio[0].set_value("risk_classifier")
    ok(at.run(), "its Risk Classifier opens")
    brief_key = f"{pid2}::in::risk_classifier::product_brief"
    check(not (at.session_state[brief_key] if brief_key in at.session_state else ""),
          "the new project's form is empty — nothing bled across")
    check("Human review required" not in "\n".join(s.value for s in at.subheader),
          "and it is at its own stage")
    at.sidebar.selectbox[0].set_value(pid1)
    ok(at.run(), "switching back to the first project works")
    check(at.session_state["project_id"] == pid1, "the first project is open again")
    at.sidebar.radio[0].set_value("requirements_reviewer")
    ok(at.run(), "its next stage is available")
    check("Stage gate" not in text(at), "the first project's next stage is unlocked by its own approval")

    print("== 5. Invite a reviewer ==")
    at.sidebar.radio[0].set_value("people")
    ok(at.run(), "People & settings opens")
    email_box = next(t for t in at.text_input if t.label == "Email address")
    email_box.input("reviewer@example.org")
    next(b for b in at.button if b.label == "Send invitation").click()
    ok(at.run(), "an invitation is created")
    check("reviewer@example.org" in text(at), "the pending invitation is listed")

    print("== 6. Rate the whole experience in one go ==")
    button(at, "nav_rate").click()
    ok(at.run(), "the rating page opens")
    check("Rate your experience" in text(at), "one page for the whole experience")
    radios = {r.key: r for r in at.radio if r.key and r.key.startswith("rate_")}
    stage_keys = {k.split("_")[1] for k in radios if not k.startswith("rate_overall")}
    check(len([k for k in radios if k.endswith("_usefulness")]) == 5, "every stage can be rated on the same form")
    radios["rate_risk_classifier_usefulness"].set_value(4)
    radios["rate_overall_overall_satisfaction"].set_value(5)
    next(b for b in at.button if b.label == "Submit rating").click()
    ok(at.run(), "the rating is submitted")
    check("your rating was recorded" in text(at), "…and confirmed")
    check(button(at, "nav_rate").label == "⭐ Update your rating", "the sidebar reflects it")
    del stage_keys

    print("== 7. Audit trail ==")
    at.sidebar.selectbox[0].set_value(pid1)
    ok(at.run(), "project reopened")
    at.sidebar.radio[0].set_value("audit")
    ok(at.run(), "the audit trail opens")
    check("History integrity verified" in text(at), "history integrity is shown")
    check("Local developer" in text(at), "approvals are attributed to the signed-in person")


if __name__ == "__main__":
    main()
    print("\nAll UI checks passed.")
