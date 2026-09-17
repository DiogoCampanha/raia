#!/usr/bin/env python3
"""
Headless walkthrough of the Streamlit UI.

    python tests/test_ui.py

Uses Streamlit's app-test harness with the mock model and the ``dev`` sign-in,
and walks what a panelist does across the page map: accept the agreement, land
on Home, create the demo project, open it, run and approve stages, revise an
approved stage and see downstream stages flagged (never re-run), confirm a
flagged stage, keep a second project isolated, invite a reviewer, read the
Agents page, submit the assessment, and use Settings. The public legal page is
checked without signing in.

AppTest keeps the page it was last switched to; after an in-app navigation the
test mirrors what the browser URL would do with :func:`goto`.
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

EMOJI = set("🛡️✅⚠️❌🔒📌🟦🟩🟧🧑‍⚖️▶️⭐🗂️👤📊🏠⚖️📜👥📄⬇📋💾🧪📨➕👑✏️🔍↩️🗑️📚🧮📖")


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
    found = next((b for b in at.button if b.key == key), None)
    if found is None:
        print(text(at))
        print([b.key for b in at.button])
        raise KeyError(key)
    return found


def has_button(at: AppTest, key: str) -> bool:
    return any(b.key == key for b in at.button)


def text(at: AppTest) -> str:
    parts = [m.value for m in at.markdown] + [m.value for m in at.info] + [m.value for m in at.success]
    parts += [t.value for t in at.title] + [c.value for c in at.caption] + [w.value for w in at.warning]
    parts += [e.value for e in at.error] + [s.value for s in at.subheader]
    parts += [b.label for b in at.button] + [str(h.proto.body) for h in at.get("html")]
    return "\n".join(str(p) for p in parts)


def goto(at: AppTest, view: str, **params: str) -> AppTest:
    at.query_params.clear()
    for k, v in params.items():
        at.query_params[k] = v
    return at.switch_page(f"views/{view}.py")


def no_emoji(at: AppTest, where: str) -> None:
    found = sorted({ch for ch in text(at) if ch in EMOJI and not ch.isascii() and ch.strip()})
    check(not found, f"no emoji in the {where} ({''.join(found) or 'none'})")


def main() -> None:
    print("== 0. The legal page is public ==")
    anon = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    from raia import config

    config.AUTH_MODE = "google"  # no [auth] block configured: nobody can be signed in
    ok(anon.run(), "the app starts for an anonymous visitor")
    check("Sign-in is not configured" in text(anon) or "Sign in with Google" in text(anon),
          "an anonymous visitor lands on the sign-in page")
    goto(anon, "legal")
    ok(anon.run(), "the privacy page opens without signing in")
    check("Privacy Policy and User Agreement" in text(anon), "…and shows the agreement")
    config.AUTH_MODE = "dev"

    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)

    print("== 1. First visit asks for acceptance ==")
    ok(at.run(), "the app starts")
    check("Before you start" in text(at), "a new person sees the agreement first")
    at.checkbox(key="consent_agree").check()
    ok(at.run(), "the agreement can be accepted")
    button(at, "consent_continue").click()
    ok(at.run(), "acceptance is recorded")
    check("Projects" in text(at), "then lands on Home")
    no_emoji(at, "home page")

    print("== 2. The demo project ==")
    button(at, "demo_project").click()
    ok(at.run(), "the demo project is created and opened")
    pid1 = at.query_params["id"][0]
    goto(at, "project", id=pid1)
    ok(at.run(), "the project page renders")
    check("Demo — resume screening" in text(at), "…with its name")
    check("Continue with Risk Classifier" in text(at), "the primary action is the next stage")
    no_emoji(at, "project page")

    print("== 3. Run and approve the first two stages ==")
    for agent in ("risk_classifier", "requirements_reviewer"):
        goto(at, "stage", project=pid1, agent=agent)
        ok(at.run(), f"the {agent} stage opens")
        check(at.session_state[f"{pid1}::in::{agent}::" + ("product_brief" if agent == "risk_classifier"
              else next(k.split("::")[-1] for k in at.session_state.filtered_state
                        if k.startswith(f"{pid1}::in::{agent}::")))],
              "the demo project's saved answers fill the form")
        button(at, f"{pid1}::run::{agent}").click()
        ok(at.run(), "the run pauses at the gate")
        check("Human review required" in text(at), "the gate is shown")
        check("Recorded in the audit trail as" in text(at), "…naming the signed-in approver")
        check(any("Edit the record" in t.label for t in at.tabs), "…with the record editor, not a text box")
        check("Status:" in text(at) and "Action Plan" in text(at), "…and the draft in the standard layout")
        button(at, f"{pid1}::approve::{agent}").click()
        ok(at.run(), "the draft is approved")
        check("Approved and committed" in text(at), "approval is confirmed")
    no_emoji(at, "stage page")
    goto(at, "project", id=pid1)
    ok(at.run(), "the project page renders after approvals")
    check(any("Action plan" in t.label for t in at.tabs), "the project has an action plan tab")
    check("Action plan (CSV)" in [d.proto.label for d in at.get("download_button")] or
          any("Action plan (CSV)" in str(d.proto) for d in at.get("download_button")),
          "…with a CSV export")

    print("== 4. Revise an approved stage: downstream is flagged, not re-run ==")
    goto(at, "stage", project=pid1, agent="risk_classifier")
    ok(at.run(), "the approved stage opens in read mode")
    check("Approved version" in text(at), "the approved version is shown")
    check("Requirements Reviewer" in text(at) and "flag these approved stages" in text(at),
          "the impact of revising is shown before starting")
    button(at, f"{pid1}::revise::risk_classifier").click()
    ok(at.run(), "revision starts")
    check("You are revising an approved stage" in text(at), "…with the old version still in force")
    button(at, f"{pid1}::run::risk_classifier").click()
    ok(at.run(), "the revision pauses at the gate")
    button(at, f"{pid1}::approve::risk_classifier").click()
    ok(at.run(), "the revision is approved")
    check("now flagged for review" in text(at), "the approval says which stages were flagged")

    goto(at, "home")
    ok(at.run(), "Home opens")
    check("Needs your attention" in text(at), "Home lists what needs attention")
    check("Upstream changed: Risk Classifier" in text(at), "…with the reason")

    goto(at, "stage", project=pid1, agent="requirements_reviewer")
    ok(at.run(), "the flagged stage opens")
    check("This stage needs review" in text(at), "the flagged stage explains why")
    check(not has_button(at, f"{pid1}::approve::requirements_reviewer"),
          "nothing was re-run: there is no draft at its gate")
    button(at, f"{pid1}::reconfirm::requirements_reviewer").click()
    ok(at.run(), "it can be confirmed as still valid")
    check("confirmed as still valid" in text(at), "the confirmation is acknowledged")
    check("This stage needs review" not in text(at), "…and the flag is cleared")

    print("== 5. A second project stays isolated ==")
    goto(at, "home")
    ok(at.run(), "Home opens")
    check(any("2/5 approved" in str(p.proto) for p in at.get("progress")),
          "the project list shows derived progress")
    at.text_input[0].input("Credit-limit recommender")
    next(b for b in at.button if b.label == "Create project").click()
    ok(at.run(), "a second project is created")
    pid2 = at.query_params["id"][0]
    check(pid2 != pid1, "…and opened")
    goto(at, "stage", project=pid2, agent="risk_classifier")
    ok(at.run(), "its Risk Classifier opens")
    brief_key = f"{pid2}::in::risk_classifier::product_brief"
    check(not (at.session_state[brief_key] if brief_key in at.session_state else ""),
          "the new project's form is empty: nothing bled across")
    goto(at, "stage", project=pid2, agent="requirements_reviewer")
    ok(at.run(), "its second stage opens")
    check("Waiting on upstream work" in text(at), "…and is gated by its own progress")

    print("== 6. Invite a reviewer ==")
    goto(at, "project", id=pid1)
    ok(at.run(), "the first project opens")
    email_box = next(t for t in at.text_input if t.label == "Email address")
    email_box.input("reviewer@example.org")
    next(b for b in at.button if b.label == "Send invitation").click()
    ok(at.run(), "an invitation is created")
    check("reviewer@example.org" in text(at), "the pending invitation is listed")
    check("History integrity verified" in text(at), "history integrity is shown in Activity")

    print("== 7. An unknown project id is refused ==")
    goto(at, "project", id="not-a-project")
    ok(at.run(), "the page handles it")
    check("Project not available" in text(at) and has_button(at, "notfound_home"),
          "a clear dead end, not an error")

    print("== 8. Agents page ==")
    goto(at, "agents")
    ok(at.run(), "the Agents page opens")
    check("How RAIA works" in text(at) and "Agent documentation" in text(at), "architecture and docs")
    no_emoji(at, "agents page")

    print("== 9. Assessment ==")
    goto(at, "assessment")
    ok(at.run(), "the assessment opens")
    radios = {r.key: r for r in at.radio if r.key}
    dims = [k for k in radios if k.startswith("a_dim_")]
    check(len(dims) == 5, "the five evaluation dimensions are asked")
    button(at, "assess_submit").click()
    ok(at.run(), "an incomplete submission is refused")
    check("Please give your consent" in text(at), "…consent comes first")
    at.checkbox(key="a_consent").check()
    radios = {r.key: r for r in at.radio if r.key}
    radios["a_dim_utility"].set_value(4)
    button(at, "assess_draft").click()
    ok(at.run(), "a draft can be saved")
    check("Draft saved" in text(at), "…and is acknowledged")
    radios = {r.key: r for r in at.radio if r.key}
    for k in ("a_dim_completeness", "a_dim_usability", "a_dim_rigor", "a_dim_generalizability"):
        radios[k].set_value(4)
    radios["a_stage_risk_classifier"].set_value(5)
    next(s for s in at.selectbox if s.key == "a_profile_context").set_value("Industry")
    button(at, "assess_submit").click()
    ok(at.run(), "the assessment is submitted")
    check("your assessment was recorded" in text(at).lower(), "…and confirmed")
    no_emoji(at, "assessment page")

    print("== 10. Settings ==")
    goto(at, "settings")
    ok(at.run(), "Settings opens")
    check("Download my data" in "\n".join(str(d.proto.label) for d in at.get("download_button")),
          "personal data can be downloaded")
    check("Delete my account" in text(at), "the account can be deleted")


if __name__ == "__main__":
    main()
    print("\nAll UI checks passed.")
