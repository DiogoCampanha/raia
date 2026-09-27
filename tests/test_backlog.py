#!/usr/bin/env python3
"""
The sprint cycle: backlog, sprints, roadmap and the project-wide audit.

Runs offline with the mock model, against whichever storage the environment
selects (like ``tests/test_projects.py``):

    python tests/test_backlog.py
    RAIA_STORE=database python tests/test_backlog.py

What is asserted, and why it matters:

* **Requirements become backlog work through a gate.** Generated RAI stories
  enter the backlog only when a person approves them, each linked to a
  requirement, as ``RAI-n``; the run covers a short list unless widened.
* **The whole cycle works without Jira.** Planning, ticks, ending a sprint and
  closing it on its audit are all manual actions.
* **Only an approved audit sets verified.** A tick means delivered; the audit
  decides, sprint by sprint, what is verified and what is carried over.
* **The audit is project-wide.** Unscheduled requirements are planned, not
  failures; progress, backlog gaps and the next sprint are computed by code.
* **Requirement changes flag only the stories they touch.**
* **Roles.** Reviewers tick stories but cannot plan or add them.
"""

import os
import sys
import tempfile
from pathlib import Path

os.environ["RAIA_LLM_PROVIDER"] = "mock"
os.environ["RAIA_FAKE_EMBED"] = "1"
os.environ.setdefault("RAIA_AUTH", "dev")
_tmp = tempfile.mkdtemp(prefix="raia_backlog_")
os.environ["RAIA_WORKSPACE_DIR"] = str(Path(_tmp) / "workspace")
os.environ["RAIA_CHROMA_DIR"] = str(Path(_tmp) / "chroma")
if not os.environ.get("RAIA_DATABASE_URL"):
    os.environ["RAIA_DATABASE_URL"] = f"sqlite:///{Path(_tmp) / 'raia.db'}"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from raia import backlog as B                                    # noqa: E402
from raia import roadmap as R                                    # noqa: E402
from raia.examples import EXAMPLES                               # noqa: E402
from raia.pipeline import StageRunner                            # noqa: E402
from raia.projects import AccessDenied, EDITOR, REVIEWER, ProjectService  # noqa: E402
from raia.rag import ingest_corpus                               # noqa: E402

FAILURES = []


def check(cond: bool, label: str) -> None:
    print(("  PASS  " if cond else "  FAIL  ") + label)
    if not cond:
        FAILURES.append(label)


def raises(exc, fn, *a, **k) -> bool:
    try:
        fn(*a, **k)
    except exc:
        return True
    return False


def approve(svc, user, pid, key, inputs):
    out = svc.start_run(user, pid, key, inputs)
    payload = out["payload"]
    failed = [i["code"] for i in payload["validation"]["items"] if i["level"] == "fail"]
    svc.resume(user, pid, key, {"action": "approve", "record": payload["record"]})
    return payload, failed


def main() -> None:
    ingest_corpus(verbose=False)
    svc = ProjectService(runner=StageRunner())
    ana = svc.sign_in("ana@example.org", "Ana Souza")
    rita = svc.sign_in("rita@example.org", "Rita Reviewer")
    eddie = svc.sign_in("eddie@example.org", "Eddie Editor")
    p = svc.create_project(ana, "Hiring assistant")
    for who, role in ((rita, REVIEWER), (eddie, EDITOR)):
        inv = svc.invite(ana, p.id, who.email, role)
        svc.respond_to_invitation(who, inv["id"], True)

    print("== 1. The board opens with the requirements ==")
    check(not svc.board(ana, p.id)["ready"], "no board before the requirements are approved")
    check(raises(ValueError, svc.create_sprint, ana, p.id), "…and no sprint either")
    approve(svc, ana, p.id, "risk_classifier", EXAMPLES["risk_classifier"])
    approve(svc, ana, p.id, "requirements_reviewer", EXAMPLES["requirements_reviewer"])
    board = svc.board(ana, p.id)
    evrs = [r["id"] for r in board["roadmap"]["requirements"]]
    check(board["ready"] and len(evrs) > 0, f"the board opens with {len(evrs)} requirements on the roadmap")
    check(all(r["state"] == R.NO_STORY for r in board["roadmap"]["requirements"]),
          "every requirement starts with no story")

    print("== 2. Generate mode: a short list, through the gate ==")
    payload, failed = approve(svc, ana, p.id, "story_generate", EXAMPLES["story_generate"])
    scope = payload["rationale"]["verdict"]["evr_ids"]
    check(len(scope) == min(len(evrs), R.SHORT_LIST), f"the run covers the short list ({len(scope)})")
    check(not failed, f"the generated record passes its checks ({failed or 'none failed'})")
    board = svc.board(ana, p.id)
    rai = [s for s in board["backlog"]["stories"] if s["origin"] == B.RAI]
    check(len(rai) == len(scope) and all(s["id"].startswith("RAI-") for s in rai),
          "approved stories enter the backlog as RAI-n")
    check(all(s["evr_ids"] and s["status"] == B.BACKLOG for s in rai), "each links a requirement, in the backlog")
    check(all(c["id"].startswith(f"AC-{s['id']}-") for s in rai for c in B.ethical_criteria(s)),
          "criteria are renamed to the backlog id")
    if len(evrs) > R.SHORT_LIST:
        wider = svc.board(ana, p.id)["uncovered"]
        check(len(wider) == len(evrs) - len(scope), "the rest wait for a later run")

    print("== 3. Planning a sprint, by rules and by hand ==")
    check(raises(AccessDenied, svc.create_sprint, rita, p.id), "a reviewer cannot plan a sprint")
    svc.create_sprint(eddie, p.id, name="Sprint 1", goal="Explanations", capacity=3)
    check(raises(ValueError, svc.create_sprint, ana, p.id), "one open sprint at a time")
    sugg = svc.suggest_sprint(ana, p.id)
    check(0 < len(sugg["suggested"]) <= 3 and all(x["reason"] for x in sugg["suggested"]),
          "the suggestion fills the capacity, each with its reason (no model call)")
    us = svc.add_story(eddie, p.id, {"title": "Ranked shortlist", "description": "As a recruiter I want a shortlist.",
                                     "acceptance_criteria": "Shows 20 candidates", "touches": ["scoring"]})
    check(us["id"] == "US-1" and us["criteria"][0]["id"] == "US-1-E1", "a product story added by hand is US-1")
    check(raises(AccessDenied, svc.add_story, rita, p.id, {"title": "x"}), "a reviewer cannot add stories")
    picked = [x["id"] for x in sugg["suggested"]]
    svc.schedule(ana, p.id, picked + [us["id"]])
    check(raises(ValueError, svc.tick, ana, p.id, picked[0], True), "a story cannot be ticked before the sprint starts")
    svc.start_sprint(ana, p.id)
    x = svc.board(ana, p.id)["open_sprint"]
    check(x["state"] == B.ACTIVE and x["id"] == "SPR-1", "the sprint starts")

    print("== 4. Refine mode writes back to the backlog ==")
    refine_inputs = {"user_stories": [{"id": "US-1", "title": "Ranked shortlist",
                                       "description": "As a recruiter I want a shortlist.",
                                       "acceptance_criteria": "Shows 20 candidates", "capabilities": ["scoring"]}],
                     "sprint_goal": "Explanations"}
    payload, failed = approve(svc, ana, p.id, "story_refiner", refine_inputs)
    s1 = B.story(svc.board(ana, p.id)["backlog"], "US-1")
    check(any(c["kind"] == "ethical" for c in s1["criteria"]) and s1["criteria"][0]["kind"] == "existing",
          "the team's criterion is kept and ethical criteria are added")
    repo = svc.repository(ana, p.id)
    check(repo.read_sprint_artifact("refined_stories", "SPR-1") is not None, "the refinement is kept per sprint")

    print("== 5. Ticks are manual, and never verify ==")
    done = picked[:1] + ["US-1"]
    svc.tick(rita, p.id, done[0], True)
    svc.tick(ana, p.id, "US-1", True)
    board = svc.board(ana, p.id)
    check(B.story(board["backlog"], done[0])["status"] == B.DONE, "a reviewer can tick a story done")
    check(not any(s["status"] == B.VERIFIED for s in board["backlog"]["stories"]), "a tick never sets verified")
    svc.end_sprint(ana, p.id)

    print("== 6. The sprint closes on its audit, project-wide ==")
    crit = [c["id"] for c in B.ethical_criteria(B.story(board["backlog"], done[0]))]
    audit_inputs = {"sprint_id": "Sprint 1", "evidence_types": ["test_results"],
                    "sprint_outcomes": "Delivered " + ", ".join(crit) + " with test results attached."}
    out = svc.start_run(ana, p.id, "auditor", audit_inputs)
    payload = out["payload"]
    data = payload["rationale"]["data"]
    check(data.get("project_mode") and data.get("sprint_close") == "SPR-1", "the audit knows it closes SPR-1")
    items = [i["id"] for i in data["audited_items"]]
    check(set(crit) <= set(items), "this sprint's criteria are audited")
    unscheduled = [r["id"] for r in data["project_state"]["requirements"] if r["state"] in (R.PLANNED, R.NO_STORY)]
    check(not set(unscheduled) & set(items), "requirements not scheduled yet are planned, not audited as failures")
    ext = payload["record"]["extension"]
    check(ext.get("progress", {}).get("projected") and ext.get("project_state"),
          "progress and where the project stands are computed")
    check("Where the Project Stands" in payload["draft"] and "Is the Backlog Enough" in payload["draft"],
          "the report carries the project-wide sections")
    # A reviewer marks the evidenced criteria satisfied (downgrades only are allowed from the model).
    record = payload["record"]
    for i in record["extension"]["items"]:
        if i["item_id"] in crit:
            i["verdict"] = "satisfied"
    svc.resume(ana, p.id, "auditor", {"action": "approve", "record": record})
    board = svc.board(ana, p.id)
    sp1 = B.sprint(board["sprints"], "SPR-1")
    check(sp1["state"] == B.CLOSED and sp1["snapshot"], "the approved audit closes the sprint and records its numbers")
    st_done = B.story(board["backlog"], done[0])
    check(st_done["status"] == B.VERIFIED and st_done["verified_in"] == "SPR-1", "only the audit verifies a story")
    carried = [s for s in board["backlog"]["stories"] if s.get("carried_over")]
    check(carried and all(s["status"] == B.BACKLOG for s in carried), "undelivered stories are carried over")
    check(repo.read_sprint_artifact("audit_report", "SPR-1") is not None, "the audit is kept per sprint")

    print("== 7. A second sprint, and the trend ==")
    svc.create_sprint(ana, p.id, capacity=5)
    sugg = svc.suggest_sprint(ana, p.id)
    check(sugg["suggested"] and "carried over" in sugg["suggested"][0]["reason"],
          "carried-over stories come first in the next suggestion")
    svc.schedule(ana, p.id, [x["id"] for x in sugg["suggested"]])
    svc.start_sprint(ana, p.id)
    svc.end_sprint(ana, p.id)
    out = svc.start_run(ana, p.id, "auditor", {"sprint_id": "Sprint 2", "evidence_types": [],
                                                 "sprint_outcomes": "Nothing was delivered."})
    tr = out["payload"]["record"]["extension"]["progress"]["trend"]["direction"]
    check(tr in ("declining", "flat"), f"a sprint that verifies nothing does not read as improving ({tr})")
    svc.resume(ana, p.id, "auditor", {"action": "approve", "record": out["payload"]["record"]})
    rm = svc.board(ana, p.id)["roadmap"]
    check(rm["closed_sprints"] == 2 and len(rm["series"]) == 2, "the roadmap shows both sprints")

    print("== 8. Requirement changes flag only what they touch ==")
    bl = svc.board(ana, p.id)["backlog"]
    before = {s["id"]: s["status"] for s in bl["stories"]}
    target = next(s for s in bl["stories"] if s["origin"] == B.RAI)
    diff = B.compare_requirements([{"id": target["evr_ids"][0], "statement": "old"}],
                                  [{"id": target["evr_ids"][0], "statement": "new"}])
    flagged = B.change_control(bl, diff, "test")
    check(flagged["flagged"] and all(sid in flagged["flagged"] for sid in
                                     [s["id"] for s in bl["stories"] if target["evr_ids"][0] in s["evr_ids"]]),
          "stories linked to a changed requirement are flagged")
    others = [s for s in bl["stories"] if s["id"] not in flagged["flagged"]]
    check(all(s["status"] == before[s["id"]] for s in others), "every other story is untouched")
    diff = B.compare_requirements([{"id": e} for e in target["evr_ids"]], [])
    res = B.change_control(bl, diff, "test")
    check(target["id"] in res["proposed_obsolete"], "an RAI story left with no requirement is proposed obsolete")
    B.resolve_review(bl, target["id"], "obsolete", "test")
    check(B.story(bl, target["id"])["status"] == B.OBSOLETE, "a person confirms it")

    print("== 8b. Requirement recommendations start short and grow on request ==")
    r1 = svc.recommend_requirements(ana, p.id, "requirements_reviewer", EXAMPLES["requirements_reviewer"])
    refs1 = [c["addresses"] for c in r1["candidates"]]
    r2 = svc.recommend_requirements(ana, p.id, "requirements_reviewer", EXAMPLES["requirements_reviewer"],
                                    exclude=refs1)
    refs2 = [c["addresses"] for c in r2["candidates"]]
    check(0 < len(refs1) <= 5, f"the first list is short ({len(refs1)})")
    check(not set(refs1) & set(refs2), "'Recommend more' offers only gaps not offered yet")

    print("== 9. Rules that never bend ==")
    bl2 = B.empty_backlog()
    check(raises(ValueError, B.add_story, bl2, origin=B.RAI, title="x"), "an RAI story must link a requirement")
    check(R.trend([]) ["direction"] == "none" and R.trend([{"verified_requirements": 1}])["direction"] == "first_sprint",
          "no trend before two sprints")
    blocked = {"stories": [{"id": "RAI-1", "origin": "rai", "status": "backlog", "evr_ids": ["EVR-1"],
                            "created_at": "1"}], "counters": {}}
    s = R.suggest(blocked, B.empty_sprints(), {}, [{"status": "open", "blocking": True, "links": ["EVR-1"], "id": "I1"}])
    check(not s["suggested"] and s["blocked"], "a story behind a blocking open issue is never suggested")

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed:")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("All sprint-cycle checks passed.")


if __name__ == "__main__":
    main()
