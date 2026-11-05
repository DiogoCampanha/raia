#!/usr/bin/env python3
"""
Projects, people and access: the invariants of the multi-user layer.

Runs offline against whichever storage the environment selects, so the same
assertions cover every backend:

    # Git repositories per project + SQLite registry (local default)
    python tests/test_projects.py

    # Database-backed blackboard on SQLite
    RAIA_STORE=database python tests/test_projects.py

    # Database-backed blackboard and checkpointer on PostgreSQL
    RAIA_DATABASE_URL=postgresql://... python tests/test_projects.py

What is asserted, and why it matters:

* **Isolation** — a person who is not a member cannot read, run, approve,
  export or even confirm the existence of someone else's project, and the
  refusal happens in the service layer, not only in the UI.
* **Independence** — two projects at different stages never share a draft,
  an answer or an approval.
* **The persistence invariant, now with identity** — nothing persists without
  an approval, and the approval is recorded under the signed-in person, whatever
  name the caller tries to pass.
* **Separation of duties** — with a second approver required, the person who
  ran a stage cannot approve it.
* **Durability** — projects, answers and paused reviews survive a restart,
  and a recovered review still stops at the gate.
* **Tamper evidence** — altering a recorded version breaks the history check.
* **Pseudonymization** — research exports carry participant codes, never
  names or email addresses.
"""

import io
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

os.environ["RAIA_LLM_PROVIDER"] = "mock"
os.environ["RAIA_FAKE_EMBED"] = "1"
os.environ.setdefault("RAIA_AUTH", "dev")
_tmp = tempfile.mkdtemp(prefix="raia_projects_")
os.environ["RAIA_WORKSPACE_DIR"] = str(Path(_tmp) / "workspace")
os.environ["RAIA_CHROMA_DIR"] = str(Path(_tmp) / "chroma")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from raia import auth, config, db                                # noqa: E402
from raia.examples import EXAMPLES                               # noqa: E402
from raia.export import session_bundle                           # noqa: E402
from raia.pipeline import StageRunner                            # noqa: E402
from raia.projects import (                                      # noqa: E402
    EDITOR, OWNER, REVIEWER, AccessDenied, ProjectService, StaleDraft, UsageLimitReached, pseudonym,
)
from raia.rag import ingest_corpus                               # noqa: E402
from raia.repository import ConcurrentEdit                       # noqa: E402
from raia.storage import open_repository                         # noqa: E402

FAILURES = []


def check(cond: bool, label: str) -> None:
    print(("  PASS  " if cond else "  FAIL  ") + label)
    if not cond:
        FAILURES.append(label)
        sys.exit(1)


def denied(fn, *args, **kwargs) -> bool:
    try:
        fn(*args, **kwargs)
    except AccessDenied:
        return True
    return False


def fresh_database() -> None:
    """Start from empty tables (a shared PostgreSQL test database is reused)."""
    if not db.is_postgres_url(config.DATABASE_URL):
        return
    d = db.get_database()
    with d.tx() as t:
        for table in ("users", "projects", "project_members", "invitations", "experience_ratings",
                      "usage_counters", "project_files", "project_commits", "pending_reviews",
                      "intake_drafts", "project_events"):
            t.execute(f"DELETE FROM {table}")
        for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
            try:
                t.execute(f"DELETE FROM {table}")
            except Exception:  # noqa: BLE001 - tables appear after the first setup()
                pass


def main() -> None:
    backend = f"store={config.STORE_BACKEND}, database={'postgres' if db.is_postgres_url(config.DATABASE_URL) else 'sqlite'}"
    print(f"== 0. Configuration ({backend}) ==")
    ingest_corpus(verbose=False)
    fresh_database()
    svc = ProjectService(runner=StageRunner())

    print("== 1. Accounts ==")
    ana = svc.sign_in("Ana@Example.org", "Ana Souza")
    bruno = svc.sign_in("bruno@example.org", "Bruno Lima")
    carla = svc.sign_in("carla@example.org", "Carla Reis")
    check(svc.sign_in("ana@example.org", "Ana Souza").id == ana.id,
          "signing in again maps to the same account (email is case-insensitive)")
    try:
        svc.sign_in("not-an-email", "x")
        check(False, "an identity without a valid email is refused")
    except ValueError:
        check(True, "an identity without a valid email is refused")
    check(ana.consented_at is None and svc.record_consent(ana).consented_at,
          "consent is recorded explicitly")

    print("== 2. Projects belong to people ==")
    p1 = svc.create_project(ana, "Hiring assistant", "ranks applicants")
    p2 = svc.create_project(ana, "Credit limits")
    check(p1.role == OWNER, "the creator owns the project")
    check({p.id for p in svc.list_projects(ana)} == {p1.id, p2.id}, "the owner sees both projects")
    check(svc.list_projects(bruno) == [], "another person sees none of them")

    print("== 3. Isolation is enforced below the UI ==")
    probes = {
        "open": (svc.get_project, (bruno, p1.id)),
        "read the blackboard": (svc.repository, (bruno, p1.id)),
        "see progress": (svc.stage_summary, (bruno, p1.id)),
        "save answers": (svc.save_intake, (bruno, p1.id, "risk_classifier", {"x": 1})),
        "read answers": (svc.load_intake, (bruno, p1.id, "risk_classifier")),
        "run an agent": (svc.start_run, (bruno, p1.id, "risk_classifier", EXAMPLES["risk_classifier"])),
        "approve": (svc.resume, (bruno, p1.id, "risk_classifier", {"action": "approve"})),
        "list members": (svc.members, (bruno, p1.id)),
        "invite": (svc.invite, (bruno, p1.id, "x@example.org", EDITOR)),
        "arbitrate": (svc.set_issue_status, (bruno, p1.id, "ISSUE-1", "resolved")),
        "delete": (svc.delete_project, (bruno, p1.id)),
    }
    for what, (fn, args) in probes.items():
        check(denied(fn, *args), f"a non-member cannot {what}")
    try:
        svc.get_project(bruno, "0" * 32)
    except AccessDenied as exc:
        missing_msg = str(exc)
    try:
        svc.get_project(bruno, p1.id)
    except AccessDenied as exc:
        foreign_msg = str(exc)
    check(missing_msg == foreign_msg, "a foreign project is indistinguishable from a missing one")

    print("== 4. Independence between projects ==")
    svc.save_intake(ana, p1.id, "risk_classifier", EXAMPLES["risk_classifier"])
    svc.save_intake(ana, p2.id, "risk_classifier", {"product_brief": "a different product"})
    check(svc.load_intake(ana, p1.id, "risk_classifier") != svc.load_intake(ana, p2.id, "risk_classifier"),
          "each project keeps its own answers")
    out1 = svc.start_run(ana, p1.id, "risk_classifier", EXAMPLES["risk_classifier"])
    out2 = svc.start_run(ana, p2.id, "risk_classifier", EXAMPLES["risk_classifier"])
    check(out1["status"] == out2["status"] == "awaiting_review", "both projects pause at their own gate")
    repo1, repo2 = open_repository(p1.id), open_repository(p2.id)
    check(repo1.read_artifact("risk_classification") is None,
          "INVARIANT: nothing is persisted while a draft is under review")
    svc.resume(ana, p2.id, "risk_classifier",
               {"action": "approve", "draft_id": out2["payload"]["draft_id"], "content": out2["payload"]["draft"],
                "approver": "Mallory"})
    check(repo2.read_artifact("risk_classification") is not None, "approving in one project persists there")
    check(repo1.read_artifact("risk_classification") is None and svc.has_thread(ana, p1.id, "risk_classifier"),
          "…and leaves the other project's review untouched")
    s1, s2 = svc.stage_summary(ana, p1.id), svc.stage_summary(ana, p2.id)
    check(s1["in_review"] == ["Risk Classifier"] and s1["approved"] == 0, "progress is derived per project (1)")
    check(s2["approved"] == 1 and s2["next"] == "Requirements Reviewer", "progress is derived per project (2)")

    print("== 5. Approvals carry the signed-in identity ==")
    data = repo2.read_data("risk_classification")
    approval = data["provenance"]["approval"]
    check(approval["approved_by"] == ana.ref and approval["approver_id"] == ana.id,
          "the approver is the authenticated person, not the name passed by the caller")
    recorded = "\n".join(repo2.current_files().values()) + "\n".join(h["message"] for h in repo2.history())
    check("ana@example.org" not in recorded and "Ana Souza" not in recorded and ana.ref in recorded,
          "the record names the approver by reference only: no name or email enters the chain")
    shown = svc.reader(ana, p2.id).read_data("risk_classification")["provenance"]["approval"]["approved_by"]
    check(shown == ana.label, "…and a page shows the person's name")
    check(svc.people_map(ana, p2.id) == {ana.ref: ana.label}, "…and an export says who each reference is")
    check(svc.humanize("approved by user:" + "0" * 32) == "approved by a former member",
          "a person whose account is gone is shown as a former member, and named nowhere")
    try:
        svc.reader(ana, p2.id).commit_files({"x.md": "x"}, "through a display view")
        check(False, "a display view of the blackboard cannot write")
    except AttributeError:
        check(True, "a display view of the blackboard cannot write")
    check("Mallory" not in (repo2.read_artifact("risk_classification") or ""),
          "a forged approver name never reaches the artifact")
    brief = repo2.read_data("product_brief")
    check(bool(brief) and brief["provenance"]["approval"]["approver_id"] == ana.id,
          "the human-authored brief is committed inside the same approval")

    print("== 6. Invitations and roles ==")
    inv = svc.invite(ana, p1.id, "Bruno@Example.org", REVIEWER)
    check(denied(svc.respond_to_invitation, carla, inv["id"], True),
          "an invitation cannot be accepted by anyone but its addressee")
    check([i["id"] for i in svc.my_invitations(bruno)] == [inv["id"]], "the invitee sees it waiting")
    joined = svc.respond_to_invitation(bruno, inv["id"], True)
    check(joined.role == REVIEWER, "accepting grants the invited role")
    check(denied(svc.respond_to_invitation, bruno, inv["id"], True), "an invitation is single-use")
    check(denied(svc.start_run, bruno, p1.id, "requirements_reviewer", {}),
          "a reviewer cannot run agents")
    check(denied(svc.save_intake, bruno, p1.id, "risk_classifier", {}), "a reviewer cannot change answers")
    check(denied(svc.invite, bruno, p1.id, "x@example.org", EDITOR), "a reviewer cannot invite")
    try:
        svc.invite(ana, p1.id, "bruno@example.org", EDITOR)
        check(False, "inviting an existing member is refused")
    except ValueError:
        check(True, "inviting an existing member is refused")
    try:
        svc.change_role(ana, p1.id, ana.id, EDITOR)
        check(False, "the last owner cannot demote themselves")
    except ValueError:
        check(True, "the last owner cannot demote themselves")

    print("== 7. Separation of duties ==")
    svc.update_project(ana, p1.id, require_second_approver=True)
    pending = open_repository(p1.id).load_pending("risk_classifier")
    check(pending["run_by"] == ana.id, "the draft records who ran the stage")
    check(denied(svc.resume, ana, p1.id, "risk_classifier", {"action": "approve", "draft_id": pending["draft_id"],
                                                                   "content": pending["draft"]}),
          "with a second approver required, the runner cannot approve their own stage")
    check(repo1.read_artifact("risk_classification") is None, "INVARIANT: the refused approval persisted nothing")
    out = svc.resume(bruno, p1.id, "risk_classifier",
                     {"action": "reject", "draft_id": pending["draft_id"],
                      "feedback": "Name the oversight measures.", "reason": "too_vague"})
    check(out["payload"]["run_by"] == ana.id, "a regeneration keeps the original runner")
    done = svc.resume(bruno, p1.id, "risk_classifier", {"action": "approve", "draft_id": out["payload"]["draft_id"],
                                                         "content": out["payload"]["draft"]})
    check(bool(done["commit"]), "a different member approves")
    prov = repo1.read_data("risk_classification")["provenance"]["approval"]
    check(prov["approver_id"] == bruno.id and prov["run_by"] == ana.id,
          "the record shows both the runner and the approver")

    print("== 7b. A decision is bound to the draft it was taken on ==")
    seen = svc.start_run(ana, p1.id, "risk_classifier", EXAMPLES["risk_classifier"])["payload"]
    newer = svc.start_run(ana, p1.id, "risk_classifier", EXAMPLES["risk_classifier"])["payload"]
    check(seen["draft_id"] != newer["draft_id"], "every draft has its own id")

    def stale(decision) -> bool:
        try:
            svc.resume(bruno, p1.id, "risk_classifier", decision)
        except StaleDraft:
            return True
        return False

    approved_before = repo1.read_data("risk_classification")["provenance"]["approval"]
    check(stale({"action": "approve", "draft_id": seen["draft_id"], "content": seen["draft"]}),
          "approving a draft another run has replaced is refused")
    check(stale({"action": "approve", "content": newer["draft"]}), "a decision that names no draft is refused")
    check(stale({"action": "reject", "draft_id": seen["draft_id"], "feedback": "x"}),
          "…and so is rejecting a replaced draft")
    check(repo1.read_data("risk_classification")["provenance"]["approval"] == approved_before,
          "INVARIANT: a refused decision persisted nothing")
    svc.resume(bruno, p1.id, "risk_classifier",
               {"action": "approve", "draft_id": newer["draft_id"], "content": newer["draft"]})
    check(repo1.read_data("risk_classification")["provenance"]["approval"]["approver_id"] == bruno.id,
          "the current draft is approved normally")

    print("== 8. Durability across a restart ==")
    svc.save_intake(ana, p1.id, "requirements_reviewer", EXAMPLES["requirements_reviewer"])
    started = svc.start_run(ana, p1.id, "requirements_reviewer", EXAMPLES["requirements_reviewer"])
    check(started["status"] == "awaiting_review", "a second stage is left waiting at the gate")
    db.reset_instances()                 # the process dies: pools and caches are gone
    svc = ProjectService(runner=StageRunner())
    ana = svc.get_user(ana.id)
    bruno = svc.get_user(bruno.id)
    check(ana is not None and {p.id for p in svc.list_projects(ana)} == {p1.id, p2.id},
          "accounts and projects survive")
    check(svc.load_intake(ana, p1.id, "requirements_reviewer") == EXAMPLES["requirements_reviewer"],
          "answers survive")
    repo1 = open_repository(p1.id)
    check(repo1.load_pending("requirements_reviewer") is not None, "the paused draft survives")
    if svc.has_thread(bruno, p1.id, "requirements_reviewer"):
        check(True, "the paused graph thread itself survived (durable checkpointer)")
        resumed = svc.resume(bruno, p1.id, "requirements_reviewer",
                             {"action": "approve", "draft_id": svc.runner.draft_at_gate(p1.id, "requirements_reviewer")["draft_id"],
                              "content": repo1.load_pending("requirements_reviewer")["draft"]})
    else:
        restored = svc.restore(bruno, p1.id, "requirements_reviewer")
        check(restored["status"] == "awaiting_review",
              "INVARIANT: a restored review stops at the human checkpoint again")
        check(repo1.read_artifact("requirements_review") is None, "INVARIANT: recovery persists nothing on its own")
        check(restored["payload"]["run_by"] == ana.id, "the restored draft still knows who ran it")
        check(denied(svc.resume, ana, p1.id, "requirements_reviewer",
                     {"action": "approve", "draft_id": restored["payload"]["draft_id"],
                      "content": restored["payload"]["draft"]}),
              "separation of duties still applies after a restore")
        resumed = svc.resume(bruno, p1.id, "requirements_reviewer",
                             {"action": "approve", "draft_id": restored["payload"]["draft_id"],
                      "content": restored["payload"]["draft"]})
    check(bool(resumed["commit"]) and repo1.read_artifact("requirements_review") is not None,
          "the review completes after the restart")

    print("== 9. Version history is tamper-evident ==")
    check(repo1.verify_history()["ok"], f"history verifies ({repo1.verify_history()['detail']})")
    if repo1.backend == "database":
        d = db.get_database()
        row = d.one("SELECT name, seq, content FROM project_files WHERE project_id = ? "
                    "AND name = '02_risk_classification.md' ORDER BY seq LIMIT 1", (p1.id,))
        d.execute("UPDATE project_files SET content = ? WHERE project_id = ? AND name = ? AND seq = ?",
                  (row["content"] + "\nHigh risk? No, minimal.", p1.id, row["name"], row["seq"]))
        check(not repo1.verify_history()["ok"], "an edited past version is detected")
        d.execute("UPDATE project_files SET content = ? WHERE project_id = ? AND name = ? AND seq = ?",
                  (row["content"], p1.id, row["name"], row["seq"]))
        last = d.one("SELECT seq, message FROM project_commits WHERE project_id = ? ORDER BY seq LIMIT 1", (p1.id,))
        d.execute("UPDATE project_commits SET message = ? WHERE project_id = ? AND seq = ?",
                  ("raia(risk_classification): human-approved update by someone else", p1.id, last["seq"]))
        check(not repo1.verify_history()["ok"], "a rewritten approval message is detected")
        d.execute("UPDATE project_commits SET message = ? WHERE project_id = ? AND seq = ?",
                  (last["message"], p1.id, last["seq"]))
        check(repo1.verify_history()["ok"], "restoring the original content restores integrity")
        ev = d.one("SELECT id, payload FROM project_events WHERE project_id = ? AND kind = 'stage_reconfirmed' "
                   "OR (project_id = ? AND kind = 'approval') ORDER BY seq LIMIT 1", (p1.id, p1.id))
        d.execute("UPDATE project_events SET payload = ? WHERE id = ?", ('{"agent": "auditor"}', ev["id"]))
        check(not repo1.verify_history()["ok"], "an edited decision in the event log is detected")
        d.execute("UPDATE project_events SET payload = ? WHERE id = ?", (ev["payload"], ev["id"]))
    else:
        log = repo1.path / "evaluation_events.jsonl"
        original_log = log.read_text(encoding="utf-8")
        lines = original_log.splitlines()
        first = json.loads(lines[0])
        first["kind"] = "something_else"
        log.write_text("\n".join([json.dumps(first)] + lines[1:]) + "\n", encoding="utf-8")
        check(not repo1.verify_history()["ok"], "an edited decision in the event log is detected")
        log.write_text(original_log, encoding="utf-8")
    check(repo1.verify_history()["ok"] and "event chain intact" in repo1.verify_history()["detail"],
          "the event log is part of the verified history")

    print("== 9b. Concurrent writes keep everyone's change ==")
    from raia import backlog as B
    from raia.repository import _next_issue_id

    race = f"race-{p1.id}"
    seed_repo = open_repository(race)
    bl, sp = B.load(seed_repo)
    B.add_story(bl, origin=B.PRODUCT, title="Story one", by="setup")
    B.add_story(bl, origin=B.PRODUCT, title="Story two", by="setup")
    seed_repo.commit_files(B.register_files(seed_repo, bl, sp), "seed")
    repo_a, repo_b, interleaved = open_repository(race), open_repository(race), []

    def bruno_edits():
        b, s2 = B.load(repo_b)
        B.update_story(b, "US-2", {"title": "Edited by Bruno"}, "bruno")
        return B.register_files(repo_b, b, s2), "bruno", None

    def ana_edits():
        a, s1 = B.load(repo_a)
        if not interleaved:            # Bruno saves between Ana's read and Ana's write
            interleaved.append(True)
            repo_b.atomic(bruno_edits)
        B.update_story(a, "US-1", {"title": "Edited by Ana"}, "ana")
        return B.register_files(repo_a, a, s1), "ana", None

    repo_a.atomic(ana_edits)
    titles = {s["id"]: s["title"] for s in B.load(open_repository(race))[0]["stories"]}
    check(titles == {"US-1": "Edited by Ana", "US-2": "Edited by Bruno"},
          f"two people editing the board at the same moment both keep their edit ({titles})")
    stale_head = repo_a.head()
    repo_b.commit_files({"x.md": "x"}, "someone else")
    try:
        repo_a.commit_files({"y.md": "y"}, "computed from an old read", expected_head=stale_head)
        check(False, "a write computed from an old read is refused")
    except ConcurrentEdit:
        check(True, "a write computed from an old read is refused")

    raised = []
    original_issues = repo_a.open_issues

    def issues_with_a_race():
        if not raised:
            raised.append(True)
            repo_b.append_open_issues(["Raised by another approval"], raised_by="B")
        return original_issues()

    repo_a.open_issues = issues_with_a_race
    repo_a.append_open_issues(["Raised by this approval"], raised_by="A")
    repo_a.open_issues = original_issues
    ids = [i["id"] for i in open_repository(race).open_issues()]
    check(sorted(ids) == ["ISSUE-1", "ISSUE-2"], f"issues raised at the same moment get distinct ids ({ids})")
    check(_next_issue_id([{"id": "ISSUE-1"}, {"id": "ISSUE-3"}]) == "ISSUE-4", "an issue id is never reused")
    open_repository(race).reset()

    print("== 10. Usage allowance ==")
    original = config.MAX_RUNS_PER_DAY
    config.MAX_RUNS_PER_DAY = 1
    try:
        carla_p = svc.create_project(carla, "Allowance")
        first = svc.start_run(carla, carla_p.id, "risk_classifier", EXAMPLES["risk_classifier"])
        try:
            svc.resume(carla, carla_p.id, "risk_classifier",
                       {"action": "reject", "draft_id": first["payload"]["draft_id"], "feedback": "again"})
            check(False, "a regeneration beyond the daily allowance is refused")
        except UsageLimitReached:
            check(True, "a regeneration beyond the daily allowance is refused")
    finally:
        config.MAX_RUNS_PER_DAY = original

    print("== 11. Ratings and pseudonymized research data ==")
    svc.submit_rating(bruno, {"stages": {"risk_classifier": {"usefulness": 4, "ease": 5, "trust": 4,
                                                              "comment": "clear"}},
                              "overall": {"overall_satisfaction": 4}})
    check(svc.my_latest_rating(bruno)["overall"]["overall_satisfaction"] == 4, "a whole-experience rating is stored")
    check(denied(svc.research_export, bruno), "only coordinators can export research data")
    config.ADMIN_EMAILS = {"ana@example.org"}
    ana = svc.get_user(ana.id)
    raw = svc.research_export(ana)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        blob = "\n".join(z.read(n).decode("utf-8") for n in z.namelist())
    leaked = [s for s in ("ana@example.org", "bruno@example.org", "Ana Souza", "Bruno Lima",
                          "Hiring assistant", ana.id, bruno.id) if s in blob]
    check(not leaked, f"no email, name, project name or internal id leaks ({leaked or 'none'})")
    check(pseudonym(bruno.id) in blob and "PRJ-001" in blob, "participants and projects appear as codes")
    events = [json.loads(l) for l in zipfile.ZipFile(io.BytesIO(raw)).read("evaluation_events.jsonl")
              .decode().splitlines() if l]
    check(any(e["kind"] == "rejection" and e.get("reason_code") == "too_vague" for e in events),
          "the research data keeps what was decided and why")
    bundle = session_bundle(open_repository(p1.id), p1.name)
    with zipfile.ZipFile(io.BytesIO(bundle)) as z:
        manifest = z.read("MANIFEST.txt").decode()
        ev = z.read("evaluation_events.jsonl").decode()
    check("History integrity at export: OK" in manifest, "the project export states its integrity")
    check("bruno@example.org" not in ev and bruno.id not in ev, "the project export's events are pseudonymized")

    print("== 11b. Revising a stage flags what depends on it, and re-runs nothing ==")
    from raia import lineage
    check(lineage.ancestors("auditor") == ["risk_classifier", "requirements_reviewer", "story_refiner"],
          "dependencies are derived from what each agent reads, transitively")
    check(lineage.descendants("risk_classifier") == ["requirements_reviewer", "story_refiner", "auditor"],
          "…and so are dependents")
    svc.update_project(ana, p1.id, require_second_approver=False)
    run = svc.start_run(ana, p1.id, "requirements_reviewer", EXAMPLES["requirements_reviewer"])
    svc.resume(ana, p1.id, "requirements_reviewer", {"action": "approve", "draft_id": run["payload"]["draft_id"],
                                                        "content": run["payload"]["draft"]})
    states = {x["agent"]: x for x in svc.stage_summary(ana, p1.id)["stages"]}
    check(states["requirements_reviewer"]["status"] == "approved", "a normal approval is not flagged")
    check(svc.revision_impact(ana, p1.id, "risk_classifier") == ["Requirements Reviewer"],
          "the impact of a revision lists exactly the approved dependents")
    try:
        svc.reconfirm_stage(ana, p1.id, "requirements_reviewer")
        check(False, "a stage that is not flagged cannot be re-confirmed")
    except ValueError:
        check(True, "a stage that is not flagged cannot be re-confirmed")
    run = svc.start_run(ana, p1.id, "risk_classifier", EXAMPLES["risk_classifier"])
    states = {x["agent"]: x for x in svc.stage_summary(ana, p1.id)["stages"]}
    check(states["risk_classifier"]["status"] == "in_review" and
          states["requirements_reviewer"]["status"] == "approved",
          "a revision waiting at its gate flags nothing: the approved version is still in force")
    svc.resume(ana, p1.id, "risk_classifier", {"action": "approve", "draft_id": run["payload"]["draft_id"],
                                                        "content": run["payload"]["draft"]})
    summary = svc.stage_summary(ana, p1.id)
    states = {x["agent"]: x for x in summary["stages"]}
    check(states["requirements_reviewer"]["status"] == "stale" and
          states["requirements_reviewer"]["stale_because"] == ["risk_classifier"],
          "approving the revision flags the dependent stage, naming the cause")
    check(states["story_refiner"]["status"] != "stale", "a stage that was never approved is not flagged")
    check("requirements_reviewer" not in open_repository(p1.id).pending_agents(),
          "INVARIANT: no downstream agent was re-run")
    check(any(e["kind"] == "revision_started" for e in open_repository(p1.id).events()),
          "the revision is in the project log")
    check(denied(svc.reconfirm_stage, carla, p1.id, "requirements_reviewer"),
          "a non-member cannot re-confirm a stage")
    svc.reconfirm_stage(bruno, p1.id, "requirements_reviewer", "Tier unchanged")
    states = {x["agent"]: x for x in svc.stage_summary(ana, p1.id)["stages"]}
    check(states["requirements_reviewer"]["status"] == "approved", "a reviewer's re-confirmation clears the flag")
    ev = [e for e in open_repository(p1.id).events() if e["kind"] == "stage_reconfirmed"][-1]
    check(ev["user"] == bruno.id and ev["upstream"] == ["risk_classifier"], "…and is attributed and explained")
    check(summary["risk"]["label"] != "Not assessed", "the dashboard risk label comes from the approved classification")

    print("== 11d. Where to go next after a stage ==")
    keys = ["risk_classifier", "requirements_reviewer", "story_refiner", "auditor"]

    def stages(*statuses):
        return [{"agent": k, "status": st_} for k, st_ in zip(keys, statuses)]

    def nxt(statuses, after=None):
        return [s["agent"] for s in lineage.next_steps(stages(*statuses), after)]

    check(nxt(("approved", "ready", "blocked", "blocked"), "risk_classifier") == ["requirements_reviewer"],
          "after the first stage: the next stage in order")
    check(nxt(("approved", "approved", "ready", "ready"), "requirements_reviewer")
          == ["story_refiner", "auditor"],
          "the Story Refiner and the Auditor open together, and both are offered")
    check(nxt(("approved", "stale", "stale", "ready"), "risk_classifier")
          == ["requirements_reviewer", "story_refiner", "auditor"],
          "stages flagged by a revision come first, before moving on")
    check(nxt(("ready", "approved", "in_review", "approved"), "auditor")
          == ["risk_classifier", "story_refiner"] and
          nxt(("approved", "approved", "in_review", "approved"), "auditor") == ["story_refiner"],
          "with nothing later open, earlier open stages are offered")
    check(nxt(("approved",) * 4, "auditor") == [] and nxt(("approved",) * 4) == [],
          "an empty answer means every stage is approved")
    check(nxt(("approved", "stale", "ready", "in_review")) == ["auditor", "requirements_reviewer",
                                                                "story_refiner"],
          "a project page offers drafts first, then flagged stages, then stages ready to run")
    check("blocked" not in {s["status"] for s in lineage.next_steps(stages("approved", "blocked", "blocked",
                                                                             "blocked", "ready"), "risk_classifier")},
          "a blocked stage is never offered")

    print("== 11c. Assessment drafts and personal data ==")
    svc.save_assessment_draft(bruno, {"instrument": "test", "dimensions": {"utility": {"score": 2}}})
    check(svc.my_assessment_draft(bruno) is not None, "a draft is kept")
    check(svc.my_latest_rating(bruno).get("status") == "submitted", "…without replacing the submission")
    raw = svc.research_export(ana)
    ratings = [json.loads(l) for l in zipfile.ZipFile(io.BytesIO(raw)).read("experience_ratings.jsonl")
               .decode().splitlines() if l]
    check(ratings and all(r.get("status") != "draft" for r in ratings), "drafts never reach the research export")
    mine = json.loads(svc.my_data_export(bruno))
    check(mine["account"]["email"] == "bruno@example.org" and mine["assessments"],
          "a person can download what RAIA holds about them")

    print("== 12. Leaving, deleting ==")
    svc.remove_member(bruno, p1.id, bruno.id)
    check(denied(svc.get_project, bruno, p1.id), "a member who leaves loses access immediately")
    svc.start_run(ana, p2.id, "risk_classifier", EXAMPLES["risk_classifier"])
    thread = {"configurable": {"thread_id": f"{p2.id}::risk_classifier"}}
    check(svc.runner._checkpointer.get_tuple(thread) is not None, "a project's runs are kept as graph threads")
    svc.delete_project(ana, p2.id)
    check(svc.runner._checkpointer.get_tuple(thread) is None,
          "deleting a project deletes its graph threads (answers, drafts, feedback, names)")
    check(denied(svc.get_project, ana, p2.id) and open_repository(p2.id).read_artifact("risk_classification") is None,
          "deleting a project removes it and its blackboard")
    svc.delete_account(carla)
    check(svc.get_user(carla.id) is None and denied(svc.get_project, carla, carla_p.id),
          "deleting an account removes the person and the projects only they owned")

    print("== 12b. An existing database is upgraded in place ==")
    import sqlite3 as _sqlite3
    legacy = Path(tempfile.mkdtemp()) / "legacy.db"
    con = _sqlite3.connect(legacy)
    for stmt in db.SCHEMA:
        con.execute(stmt)
    for i, kind in enumerate(("approval", "stage_reconfirmed", "rejection")):
        con.execute("INSERT INTO project_events (id, project_id, at, kind, payload) VALUES (?, ?, ?, ?, ?)",
                    (f"e{i}", "old-project", f"2026-09-0{i + 1}T10:00:00+00:00", kind, '{"agent": "auditor"}'))
    con.execute("INSERT INTO experience_ratings (id, user_id, submitted_at, payload) VALUES (?, ?, ?, ?)",
                ("r1", "u1", "2026-10-01T10:00:00+00:00", '{"status": "draft", "instrument": "raia-panel-v1"}'))
    con.commit()
    con.close()
    upgraded = db.Database(f"sqlite:///{legacy}")
    rows = upgraded.query("SELECT seq, at, kind, payload, parent_digest, digest FROM project_events "
                          "WHERE project_id = 'old-project' ORDER BY seq")
    from raia.storage import verify_events
    check([r["seq"] for r in rows] == [1, 2, 3] and verify_events(rows)["ok"],
          "events recorded before the upgrade are chained, in order, and verify")
    rating = upgraded.one("SELECT status, instrument FROM experience_ratings WHERE id = 'r1'")
    check(rating == {"status": "draft", "instrument": "raia-panel-v1"},
          "assessments recorded before the upgrade get their status and instrument as columns")
    applied = {r["id"] for r in upgraded.query("SELECT id FROM schema_migrations")}
    check({m for m, _ in db.MIGRATIONS} <= applied, "every migration is recorded as applied")
    upgraded.migrate()
    check(len(upgraded.query("SELECT id FROM schema_migrations")) == len(applied), "…and runs only once")
    upgraded.close()

    print("== 13. Sign-in configuration fails closed ==")
    saved_url, saved_mode = config.DATABASE_URL, config.AUTH_MODE
    config.DATABASE_URL, config.AUTH_MODE = "postgresql://u:p@host/db", ""
    check(auth.mode() == "dev" and auth.configuration_problem() is not None,
          "a database-backed deployment without sign-in refuses to open")
    config.DATABASE_URL = "sqlite:///somewhere.db"
    check(auth.mode() == "dev" and auth.configuration_problem() is not None,
          "a SQLite deployment without sign-in refuses to open too: dev mode is never a fallback")
    config.AUTH_MODE = "dev"
    check(auth.configuration_problem() is None, "…and opens when dev mode is chosen explicitly")
    config.AUTH_MODE = "google"
    check(auth.configuration_problem() is not None, "Google sign-in without an [auth] block refuses to open")
    config.DATABASE_URL, config.AUTH_MODE = saved_url, saved_mode


if __name__ == "__main__":
    main()
    print("\nAll project and access checks passed.")
