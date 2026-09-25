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


def _lab(hex_: str):
    rgb = [int(hex_.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in rgb]
    xyz = ((0.4124 * c[0] + 0.3576 * c[1] + 0.1805 * c[2]) / 0.95047,
           0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2],
           (0.0193 * c[0] + 0.1192 * c[1] + 0.9505 * c[2]) / 1.08883)
    f = [t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116 for t in xyz]
    return 116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])


def _delta_e(a: str, b: str) -> float:
    return sum((x - y) ** 2 for x, y in zip(_lab(a), _lab(b))) ** .5


def _contrast(a: str, b: str) -> float:
    def lum(h):
        rgb = [int(h.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in rgb]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def agent_identity() -> None:
    """Every agent is recognisable, and its colour never borrows a meaning."""
    from itertools import combinations

    from raia.agents import AGENTS
    from raia.ui.theme import AGENT_LOOK, TONES

    from raia.ui import theme

    check("<" not in theme._css() + theme._agent_css(),
          "the CSS layer has no '<' anywhere, not even in a comment: the HTML sanitizer drops the "
          "whole style block if it finds one")
    check(set(AGENT_LOOK) == set(AGENTS), "every agent has its own look, and no look is orphaned")
    check(len({lk.icon for lk in AGENT_LOOK.values()}) == len(AGENT_LOOK) and
          all(lk.question and lk.motif for lk in AGENT_LOOK.values()),
          "…each with its own icon, question and header pattern")
    worst = min((_delta_e(c, t), k, n) for k, lk in AGENT_LOOK.items() for c in (lk.ink, lk.glow)
                for n, t in TONES.items())
    check(worst[0] >= 20, f"no agent colour can be mistaken for a tone that carries meaning "
                          f"(closest: {worst[1]} vs {worst[2]}, ΔE {worst[0]:.0f})")
    pair = min((_delta_e(a.ink, b.ink), x, y) for (x, a), (y, b) in combinations(AGENT_LOOK.items(), 2))
    check(pair[0] >= 25, f"agents are told apart by colour (closest: {pair[1]} vs {pair[2]}, ΔE {pair[0]:.0f})")
    check(all(_contrast(lk.ink, "#ffffff") >= 4.5 and _contrast(lk.glow, "#0b1120") >= 4.5
              for lk in AGENT_LOOK.values()),
          "agent colours pass WCAG AA: as text on the light theme and under white text, and on the dark theme")


def main() -> None:
    print("== Agent identity ==")
    agent_identity()

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
    check("New to RAIA?" in text(at) and has_button(at, "home_guide"),
          "a newcomer is pointed to the Guide")
    button(at, "home_guide_hide").click()
    ok(at.run(), "the pointer can be hidden")
    check(not has_button(at, "home_guide"), "…and stays hidden")
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
        if agent == "risk_classifier":
            check("How the AI works" in text(at)
                  and any(t.label.startswith("What does the AI produce or decide?") for t in at.text_area)
                  and any(m.label.startswith("What kind of AI does it use?") for m in at.multiselect),
                  "the Risk Classifier asks what the AI produces and how it works")
        button(at, f"{pid1}::run::{agent}").click()
        ok(at.run(), "the run pauses at the gate")
        check("Human review required" in text(at), "the gate is shown")
        check("Recorded in the audit trail as" in text(at), "…naming the signed-in approver")
        check(any("Edit the record" in t.label for t in at.tabs), "…with the record editor, not a text box")
        check("Risks identified" in text(at) and "What to do" in text(at) and "Do now" in text(at),
              "…and the draft reads summary first, then what to do")
        check(any(t.label == "Traceability" for t in at.tabs) and "Deep dive" in str(at._tree),
              "…with the deep dive, section by section, behind a dropdown")
        check(f'data-agent="{agent}"' in text(at) and "agent-hero" in text(at),
              "the stage page wears its agent's own header")
        check(has_button(at, "foot_next") and (has_button(at, "foot_prev") or has_button(at, "foot_project_l")),
              "…and ends with the previous and next stage, even before anything is approved")
        button(at, f"{pid1}::approve::{agent}").click()
        ok(at.run(), "the draft is approved")
        check("Approved and committed" in text(at), "approval is confirmed")
        following = {"risk_classifier": "requirements_reviewer", "requirements_reviewer": "story_refiner"}[agent]
        check('class="next-label"' in text(at) and has_button(at, f"next_{following}")
              and button(at, f"next_{following}").label.startswith("Continue to"),
              "…with a button that continues to the next agent")
        check(button(at, "foot_next").proto.type == "primary", "…and the footer's Next leads on")
    button(at, "next_story_refiner").click()
    ok(at.run(), "the continue button navigates without an error")
    goto(at, "stage", project=pid1, agent="story_refiner")
    ok(at.run(), "the next stage opens")
    check("rail-current" in str(at._tree) or 'data-agent="story_refiner"' in text(at),
          "…in its own identity, with the stage rail marking where the person is")
    goto(at, "stage", project=pid1, agent="requirements_reviewer")
    ok(at.run(), "an approved stage reopens")
    check('class="next-head"' not in text(at) and not has_button(at, "next_story_refiner"),
          "the what's-next card belongs to the approval: it is gone once another stage was opened")
    no_emoji(at, "stage page")
    from raia.storage import open_repository

    brief = open_repository(pid1).read_artifact("product_brief") or ""
    check("## What does the AI produce or decide?" in brief and "## How the AI works" in brief
          and "Machine learning" in brief,
          "the approved product brief carries the new answers for later stages")
    goto(at, "project", id=pid1)
    ok(at.run(), "the project page renders after approvals")
    check(any("Action plan" in t.label for t in at.tabs), "the project has an action plan tab")
    check("Action plan (CSV)" in [d.proto.label for d in at.get("download_button")] or
          any("Action plan (CSV)" in str(d.proto) for d in at.get("download_button")),
          "…with a CSV export")

    print("== 3b. A redraw stays within a database budget ==")
    # Each statement is a network round trip on a hosted database. A stage page
    # once made 26 statements in 24 transactions (about 100 round trips) every
    # time a field changed; this keeps it from growing back.
    from raia import config as _config
    from raia.db import get_database

    stats = get_database().stats
    budgets = {"stage": 10, "project": 16, "home": 10} if _config.STORE_BACKEND == "database" \
        else {"stage": 6, "project": 6, "home": 6}
    goto(at, "stage", project=pid1, agent="story_refiner")
    ok(at.run(), "the next stage opens")
    check(any(t.value == "Ranked shortlist" for t in at.text_input if t.key and "::story::story_refiner::" in t.key),
          "the demo project's stories open as one card each")
    check(any(m.label.startswith("What does this story touch?") for m in at.multiselect),
          "…each asking what that story touches")
    cards = len([t for t in at.text_input if t.label == "Title"])
    button(at, f"{pid1}::story_add::story_refiner").click()
    ok(at.run(), "a story card can be added")
    check(len([t for t in at.text_input if t.label == "Title"]) == cards + 1, "…and appears as a new card")
    last_delete = [b for b in at.button if b.key and b.key.endswith("::del")][-1]
    last_delete.click()
    ok(at.run(), "a story card can be removed")
    check(len([t for t in at.text_input if t.label == "Title"]) == cards, "…and disappears")
    field = next(t for t in at.text_area if t.key and "::in::story_refiner::" in t.key)
    field.input("A changed answer")
    stats.reset()
    ok(at.run(), "a changed answer redraws the page")
    check(stats.transactions == 0 and stats.round_trips <= budgets["stage"],
          f"a stage redraw makes at most {budgets['stage']} round trips "
          f"({stats.statements} statements, {stats.transactions} explicit transactions)")
    for view, params in (("project", {"id": pid1}), ("home", {})):
        goto(at, view, **params)
        stats.reset()
        ok(at.run(), f"the {view} page redraws")
        check(stats.round_trips <= budgets[view],
              f"a {view} page redraw makes at most {budgets[view]} round trips "
              f"({stats.statements} statements, {stats.transactions} explicit transactions)")

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
    check(has_button(at, "next_requirements_reviewer")
          and button(at, "next_requirements_reviewer").label == "Re-check Requirements Reviewer",
          "…and the next step is to re-check the flagged stage, before moving on")

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

    print("== 5b. Recommend ethical requirements: proposed, never assumed ==")
    goto(at, "stage", project=pid2, agent="risk_classifier")
    ok(at.run(), "the second project's Risk Classifier opens")
    button(at, f"{pid2}::ex::risk_classifier").click()
    ok(at.run(), "its answers are filled")
    button(at, f"{pid2}::run::risk_classifier").click()
    ok(at.run(), "it runs")
    button(at, f"{pid2}::approve::risk_classifier").click()
    ok(at.run(), "and is approved")

    rr = "requirements_reviewer"
    goto(at, "stage", project=pid2, agent=rr)
    ok(at.run(), "the Requirements Reviewer opens")
    check(has_button(at, f"{pid2}::recommend::{rr}"), "it offers to recommend ethical requirements")
    at.text_area(key=f"{pid2}::in::{rr}::requirements").input(
        "R1. Score each credit application.\nR2. Respond within 2 seconds.")
    at.multiselect(key=f"{pid2}::in::{rr}::existing_controls").set_value(["logging"])
    at.multiselect(key=f"{pid2}::in::{rr}::stakeholders").set_value(["users"])
    ok(at.run(), "the team answers what only it knows")
    button(at, f"{pid2}::recommend::{rr}").click()
    ok(at.run(), "the recommendation runs")
    state = at.session_state
    check(state[f"{pid2}::in::{rr}::stakeholders"] == ["users"], "an answer the team gave is left alone")
    check(bool(state[f"{pid2}::in::{rr}::values_at_stake"]), "an empty context question is pre-filled")
    check(state[f"{pid2}::in::{rr}::existing_controls"] == ["logging"], "the controls in place are never guessed")
    body = text(at)
    check("Suggested from the approved risk classification" in body, "the pre-filled field says so")
    check("this field is never pre-filled" in body, "the controls question is annotated, not answered")
    check("Recommended requirements" in body and has_button(at, f"{pid2}::cand_adopt::{rr}::C1"),
          "candidate requirements are offered one by one")
    check("R3" not in state[f"{pid2}::in::{rr}::requirements"], "nothing is added before a person adopts it")

    button(at, f"{pid2}::cand_adopt::{rr}::C1").click()
    ok(at.run(), "a candidate is adopted")
    reqs = state[f"{pid2}::in::{rr}::requirements"]
    check("R3." in reqs and "Fit criterion:" in reqs, "…and added to the requirements with the next id")
    check("adopted as **R3**" in text(at), "…and marked as adopted")
    if has_button(at, f"{pid2}::cand_reject::{rr}::C2"):
        button(at, f"{pid2}::cand_reject::{rr}::C2").click()
        ok(at.run(), "another is rejected")
        check("rejected" in text(at), "…and marked as rejected")

    ack = f"{pid2}::suggest_ack::{rr}"
    check(any(c.key == ack for c in at.checkbox), "running asks the person to confirm the pre-filled answers")
    button(at, f"{pid2}::run::{rr}").click()
    ok(at.run(), "running without that confirmation")
    check("have not been reviewed" in text(at), "…is refused")
    at.checkbox(key=ack).check()
    button(at, f"{pid2}::run::{rr}").click()
    ok(at.run(), "running after the confirmation")
    check("Human review required" in text(at), "…reaches the gate")
    check("Where the inputs came from" in text(at), "the draft says which inputs RAIA proposed")
    button(at, f"{pid2}::approve::{rr}").click()
    ok(at.run(), "the draft is approved")
    from raia.storage import open_repository as _open_repo

    repo2 = _open_repo(pid2)
    check("R3 were recommended by RAIA and adopted by the team" in (repo2.read_artifact("requirements_review") or ""),
          "the approved record keeps the adopted requirement apart from the team's own")
    kinds = [e.get("kind") for e in repo2.events()]
    check({"intake_suggested", "requirements_recommended", "recommendation_adopted"} <= set(kinds),
          "each suggestion, recommendation and adoption is in the activity log")
    prov = (repo2.read_data("requirements_review").get("provenance") or {})
    check(bool((prov.get("intake_origin") or {}).get("adopted")), "…and in the draft's provenance")

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

    print("== 7b. Guide page ==")
    goto(at, "guide")
    ok(at.run(), "the Guide opens")
    body = text(at)
    check("Step by step" in body and "Answer the Risk Classifier's questions" in body,
          "…with the step-by-step walkthrough")
    check(all(a.spec.name in body for a in __import__("raia.agents", fromlist=["AGENTS"]).AGENTS.values()),
          "…and every agent in the at-a-glance table")
    no_emoji(at, "guide page")
    from raia.ui import guide as _guide

    check(_guide.DOCUMENT.read_text(encoding="utf-8") == _guide.markdown(),
          "docs/TESTERS.md is generated from the guide and up to date (python -m raia.ui.guide)")

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
    check(not has_button(at, "logout"), "Settings carries no sign-out button of its own")
    from raia.ui import routes as _routes

    check(_routes.SIGN_OUT not in _routes._PAGES,
          "local developer mode lists no Sign out (there is no sign-in to end)")

    print("== 11. Sign out from the Account menu ==")
    from raia import auth

    saved = (auth.mode, auth.current_identity, auth.configuration_problem, auth.logout)
    logouts = []
    auth.mode = lambda: "google"
    auth.configuration_problem = lambda: None
    auth.current_identity = lambda: auth.Identity(config.DEV_USER_EMAIL, config.DEV_USER_NAME)
    auth.logout = lambda: logouts.append(True)
    try:
        g = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
        ok(g.run(), "the app runs for a person signed in with Google")
        check(_routes.SIGN_OUT in _routes._PAGES, "the Account menu lists Sign out")
        goto(g, "signout")
        ok(g.run(), "Sign out opens")
        check(logouts == [True], "…hands over to the identity provider's logout")
        check("_user" not in g.session_state, "…and clears the session")
    finally:
        auth.mode, auth.current_identity, auth.configuration_problem, auth.logout = saved


if __name__ == "__main__":
    main()
    print("\nAll UI checks passed.")
