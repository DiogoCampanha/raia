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
    EDITOR, OWNER, REVIEWER, AccessDenied, ProjectService, UsageLimitReached, pseudonym,
)
from raia.rag import ingest_corpus                               # noqa: E402
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
               {"action": "approve", "content": out2["payload"]["draft"], "approver": "Mallory"})
    check(repo2.read_artifact("risk_classification") is not None, "approving in one project persists there")
    check(repo1.read_artifact("risk_classification") is None and svc.has_thread(ana, p1.id, "risk_classifier"),
          "…and leaves the other project's review untouched")
    s1, s2 = svc.stage_summary(ana, p1.id), svc.stage_summary(ana, p2.id)
    check(s1["in_review"] == ["Risk Classifier"] and s1["approved"] == 0, "progress is derived per project (1)")
    check(s2["approved"] == 1 and s2["next"] == "Requirements Reviewer", "progress is derived per project (2)")

    print("== 5. Approvals carry the signed-in identity ==")
    data = repo2.read_data("risk_classification")
    approval = data["provenance"]["approval"]
    check(approval["approved_by"] == ana.label and approval["approver_id"] == ana.id,
          "the approver is the authenticated person, not the name passed by the caller")
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
    check(denied(svc.resume, ana, p1.id, "risk_classifier", {"action": "approve", "content": pending["draft"]}),
          "with a second approver required, the runner cannot approve their own stage")
    check(repo1.read_artifact("risk_classification") is None, "INVARIANT: the refused approval persisted nothing")
    out = svc.resume(bruno, p1.id, "risk_classifier",
                     {"action": "reject", "feedback": "Name the oversight measures.", "reason": "too_vague"})
    check(out["payload"]["run_by"] == ana.id, "a regeneration keeps the original runner")
    done = svc.resume(bruno, p1.id, "risk_classifier", {"action": "approve", "content": out["payload"]["draft"]})
    check(bool(done["commit"]), "a different member approves")
    prov = repo1.read_data("risk_classification")["provenance"]["approval"]
    check(prov["approver_id"] == bruno.id and prov["run_by"] == ana.id,
          "the record shows both the runner and the approver")

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
                             {"action": "approve", "content": repo1.load_pending("requirements_reviewer")["draft"]})
    else:
        restored = svc.restore(bruno, p1.id, "requirements_reviewer")
        check(restored["status"] == "awaiting_review",
              "INVARIANT: a restored review stops at the human checkpoint again")
        check(repo1.read_artifact("requirements_review") is None, "INVARIANT: recovery persists nothing on its own")
        check(restored["payload"]["run_by"] == ana.id, "the restored draft still knows who ran it")
        check(denied(svc.resume, ana, p1.id, "requirements_reviewer",
                     {"action": "approve", "content": restored["payload"]["draft"]}),
              "separation of duties still applies after a restore")
        resumed = svc.resume(bruno, p1.id, "requirements_reviewer",
                             {"action": "approve", "content": restored["payload"]["draft"]})
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

    print("== 10. Usage allowance ==")
    original = config.MAX_RUNS_PER_DAY
    config.MAX_RUNS_PER_DAY = 1
    try:
        carla_p = svc.create_project(carla, "Allowance")
        svc.start_run(carla, carla_p.id, "risk_classifier", EXAMPLES["risk_classifier"])
        try:
            svc.resume(carla, carla_p.id, "risk_classifier", {"action": "reject", "feedback": "again"})
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
    check(lineage.ancestors("drift_monitor") == ["risk_classifier", "requirements_reviewer", "story_refiner"],
          "dependencies are derived from what each agent reads, transitively")
    check(lineage.descendants("risk_classifier") == ["requirements_reviewer", "story_refiner", "auditor",
                                                     "drift_monitor"], "…and so are dependents")
    svc.update_project(ana, p1.id, require_second_approver=False)
    run = svc.start_run(ana, p1.id, "requirements_reviewer", EXAMPLES["requirements_reviewer"])
    svc.resume(ana, p1.id, "requirements_reviewer", {"action": "approve", "content": run["payload"]["draft"]})
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
    svc.resume(ana, p1.id, "risk_classifier", {"action": "approve", "content": run["payload"]["draft"]})
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
    svc.delete_project(ana, p2.id)
    check(denied(svc.get_project, ana, p2.id) and open_repository(p2.id).read_artifact("risk_classification") is None,
          "deleting a project removes it and its blackboard")
    svc.delete_account(carla)
    check(svc.get_user(carla.id) is None and denied(svc.get_project, carla, carla_p.id),
          "deleting an account removes the person and the projects only they owned")

    print("== 13. Sign-in configuration fails closed ==")
    saved_url, saved_mode = config.DATABASE_URL, config.AUTH_MODE
    config.DATABASE_URL, config.AUTH_MODE = "postgresql://u:p@host/db", ""
    check(auth.mode() == "dev" and auth.configuration_problem() is not None,
          "a database-backed deployment without sign-in refuses to open")
    config.AUTH_MODE = "google"
    check(auth.configuration_problem() is not None, "Google sign-in without an [auth] block refuses to open")
    config.DATABASE_URL, config.AUTH_MODE = saved_url, saved_mode


if __name__ == "__main__":
    main()
    print("\nAll project and access checks passed.")
