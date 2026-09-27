#!/usr/bin/env python3
"""
Optional Jira export and sync, against a mock Jira Cloud (no network).

    python tests/test_jira.py

What is asserted, and why it matters:

* **The CSV works with no setup.** A ``Summary`` header, one ``Labels`` column
  per label, quoted multi-line descriptions carrying the ethical criteria.
* **A push is idempotent.** New stories are created in batches of at most 50;
  a second push creates nothing and updates only what changed.
* **A sync never verifies and never overrides a person.** Jira's Done marks a
  story done; a story done on the board and open in Jira is a disagreement a
  person settles.
* **Tokens stay private.** Stored encrypted, never in the project's files,
  its download or the events; deleted with the account.
"""

import csv
import io
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ["RAIA_LLM_PROVIDER"] = "mock"
os.environ["RAIA_FAKE_EMBED"] = "1"
os.environ.setdefault("RAIA_AUTH", "dev")
os.environ["RAIA_JIRA_KEY"] = "test-key-for-jira-tokens"
_tmp = tempfile.mkdtemp(prefix="raia_jira_")
os.environ["RAIA_WORKSPACE_DIR"] = str(Path(_tmp) / "workspace")
os.environ["RAIA_CHROMA_DIR"] = str(Path(_tmp) / "chroma")
if not os.environ.get("RAIA_DATABASE_URL"):
    os.environ["RAIA_DATABASE_URL"] = f"sqlite:///{Path(_tmp) / 'raia.db'}"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx                                                    # noqa: E402

from raia import backlog as B                                   # noqa: E402
from raia import jira as J                                      # noqa: E402
from raia.examples import EXAMPLES                              # noqa: E402
from raia.export import session_bundle                          # noqa: E402
from raia.pipeline import StageRunner                           # noqa: E402
from raia.projects import ProjectService                        # noqa: E402
from raia.rag import ingest_corpus                              # noqa: E402

FAILURES = []
TOKEN = "atlassian-secret-token-123"


def check(cond: bool, label: str) -> None:
    print(("  PASS  " if cond else "  FAIL  ") + label)
    if not cond:
        FAILURES.append(label)


class FakeJira:
    """Just enough of Jira Cloud: bulk create, update, search/jql, myself, fields, agile sprint."""

    def __init__(self) -> None:
        self.issues = {}
        self.n = 0
        self.calls = []
        self.batches = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.calls.append((request.method, path))
        if request.headers.get("authorization", "").split(" ")[0] != "Basic":
            return httpx.Response(401)
        body = json.loads(request.content or b"{}") if request.content else {}
        if path == "/rest/api/3/myself":
            return httpx.Response(200, json={"displayName": "Ana on Jira"})
        if path == "/rest/api/3/field":
            return httpx.Response(200, json=[{"id": "customfield_10016", "name": "Story point estimate"}])
        if path == "/rest/api/3/issue/bulk":
            ups = body["issueUpdates"]
            self.batches.append(len(ups))
            if len(ups) > 50:
                return httpx.Response(400, json={"errorMessages": ["too many"]})
            out = []
            for u in ups:
                self.n += 1
                key = f"{u['fields']['project']['key']}-{self.n}"
                self.issues[key] = {"fields": u["fields"], "status": ("To Do", "new")}
                out.append({"id": str(self.n), "key": key})
            return httpx.Response(201, json={"issues": out, "errors": []})
        if path.startswith("/rest/api/3/issue/") and request.method == "PUT":
            key = path.rsplit("/", 1)[-1]
            self.issues[key]["fields"].update(body["fields"])
            return httpx.Response(204)
        if path == "/rest/api/3/search/jql":
            jql = body["jql"]
            found = []
            for key, iss in self.issues.items():
                labels = iss["fields"].get("labels") or []
                if key in jql or any(l in jql for l in labels if l.startswith("raia-RAI") or l.startswith("raia-US")):
                    found.append({"key": key, "fields": {"status": {"name": iss["status"][0],
                                                                     "statusCategory": {"key": iss["status"][1]}},
                                                          "labels": labels}})
            return httpx.Response(200, json={"issues": found, "isLast": True})
        if path.startswith("/rest/agile/1.0/sprint/"):
            return httpx.Response(204)
        return httpx.Response(404)


def main() -> None:
    fake = FakeJira()
    J.TRANSPORT = httpx.MockTransport(fake.handler)
    ingest_corpus(verbose=False)
    svc = ProjectService(runner=StageRunner())
    ana = svc.sign_in("ana@example.org", "Ana")
    p = svc.create_project(ana, "Hiring")
    for key in ("risk_classifier", "requirements_reviewer", "story_generate"):
        out = svc.start_run(ana, p.id, key, EXAMPLES[key])
        svc.resume(ana, p.id, key, {"action": "approve", "record": out["payload"]["record"]})
    svc.create_sprint(ana, p.id, capacity=60)
    bl = svc.board(ana, p.id)["backlog"]
    rai = [s["id"] for s in bl["stories"]]
    for i in range(55):
        svc.add_story(ana, p.id, {"title": f"Story {i}", "description": "As a user\nI want \"quotes\", and commas",
                                  "estimate": 2 if i % 2 else None})
    bl = svc.board(ana, p.id)["backlog"]
    svc.schedule(ana, p.id, [s["id"] for s in bl["stories"]])
    svc.start_sprint(ana, p.id)

    print("== 1. CSV for Jira's importer (no setup) ==")
    text = svc.jira_csv(ana, p.id, "sprint")
    rows = list(csv.reader(io.StringIO(text)))
    header = rows[0]
    check(header[:3] == ["Summary", "Issue Type", "Description"] and header.count("Labels") >= 3,
          "Summary first, one Labels column per label")
    check("Story Points" in header, "story points appear when some story has an estimate")
    check(len(rows) - 1 == len(bl["stories"]), "one row per sprint story")
    rai_row = next(r for r in rows[1:] if r[0].startswith(f"[{rai[0]}]"))
    check("Ethical acceptance criteria" in rai_row[2] and "raia-ethics" in rai_row, "RAI rows carry their criteria and label")
    check(any('"quotes"' in r[2] and "\n" in r[2] for r in rows[1:]), "quotes and line breaks survive the round trip")

    print("== 2. Connecting is optional, and the token stays private ==")
    try:
        svc.jira_push(ana, p.id, project_key="RAIA")
        check(False, "pushing without a connection is refused")
    except ValueError:
        check(True, "pushing without a connection is refused, with a pointer to Settings")
    try:
        svc.save_jira_connection(ana, site="http://evil.example.com", email="ana@example.org", token=TOKEN)
        check(False, "only a Jira Cloud site is accepted")
    except ValueError:
        check(True, "only a Jira Cloud site is accepted")
    conn = svc.save_jira_connection(ana, site="your-team.atlassian.net", email="ana@example.org", token=TOKEN,
                                    project_key="raia")
    check(conn["site"] == "https://your-team.atlassian.net" and conn["has_token"] and TOKEN not in json.dumps(conn),
          "the connection is saved; the token is never returned")
    row = svc.db.one("SELECT token_enc FROM jira_connections WHERE user_id = ?", (ana.id,))
    check(TOKEN not in row["token_enc"], "the token is stored encrypted")
    check(svc.jira_test(ana) == "Ana on Jira", "the connection can be tested")

    print("== 3. Push: batches of 50, then idempotent ==")
    result = svc.jira_push(ana, p.id, project_key="RAIA", jira_sprint=7)
    n = len(bl["stories"])
    check(len(result["created"]) == n and not result["errors"], f"{n} stories created")
    check(max(fake.batches) <= 50 and len(fake.batches) >= 2, f"in batches of at most 50 ({fake.batches})")
    check(any(pth == "/rest/agile/1.0/sprint/7/issue" for _, pth in fake.calls), "…and added to the chosen Jira sprint")
    bl = svc.board(ana, p.id)["backlog"]
    check(all((s.get("jira") or {}).get("key") for s in bl["stories"]), "every story keeps its Jira key")
    points = [i["fields"].get("customfield_10016") for i in fake.issues.values()]
    check(2 in points, "estimates go to the site's story-points field")
    before = len(fake.issues)
    again = svc.jira_push(ana, p.id, project_key="RAIA")
    check(not again["created"] and not again["updated"] and len(fake.issues) == before,
          "a second push creates and updates nothing")
    svc.update_story(ana, p.id, bl["stories"][-1]["id"], {"title": "Renamed"})
    third = svc.jira_push(ana, p.id, project_key="RAIA")
    check(third["updated"] == [bl["stories"][-1]["id"]] and not third["created"], "a changed story is updated, only it")

    print("== 4. Sync: done means delivered; a person's change is never overwritten ==")
    bl = svc.board(ana, p.id)["backlog"]
    a, b, c = bl["stories"][0], bl["stories"][1], bl["stories"][2]
    fake.issues[a["jira"]["key"]]["status"] = ("Done", "done")
    svc.tick(ana, p.id, b["id"], True)                      # done on the board, still To Do in Jira
    res = svc.jira_sync(ana, p.id)
    bl = svc.board(ana, p.id)["backlog"]
    check(B.story(bl, a["id"])["status"] == B.DONE and B.story(bl, a["id"])["done"]["source"] == "jira",
          "Done in Jira marks the story done, from Jira")
    check(B.story(bl, b["id"])["status"] == B.DONE and b["id"] in res["disagreements"],
          "a story done on the board but open in Jira stays done, flagged as a disagreement")
    check(not any(s["status"] == B.VERIFIED for s in bl["stories"]), "a sync never verifies")
    check("done" in J.summary_line(res), f"the result is summarized ({J.summary_line(res)})")
    svc.tick(ana, p.id, a["id"], False)                     # a person un-ticks it
    res = svc.jira_sync(ana, p.id)
    check(B.story(svc.board(ana, p.id)["backlog"], a["id"])["status"] == B.IN_SPRINT and a["id"] in res["disagreements"],
          "a person's un-tick survives the next sync, as a disagreement")
    svc.jira_resolve(ana, p.id, a["id"], "jira")
    check(B.story(svc.board(ana, p.id)["backlog"], a["id"])["status"] == B.DONE, "the person settles it (Jira's)")
    svc.jira_resolve(ana, p.id, b["id"], "raia")
    check(not (B.story(svc.board(ana, p.id)["backlog"], b["id"]).get("jira") or {}).get("disagreement"),
          "…or keeps the board's")

    print("== 5. Tokens never leave ==")
    files = svc.repository(ana, p.id).current_files()
    check(not any(TOKEN in v for v in files.values()), "no token in the project's files")
    bundle = session_bundle(svc.repository(ana, p.id), p.name)
    check(TOKEN.encode() not in bundle, "no token in the project download")
    check(TOKEN not in json.dumps(svc.repository(ana, p.id).events()), "no token in the event log")
    check(TOKEN not in svc.my_data_export(ana).decode(), "no token in the person's data export")
    svc.delete_jira_connection(ana)
    check(svc.jira_connection(ana) == {}, "disconnecting deletes the stored token")

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed:")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("All Jira checks passed.")


if __name__ == "__main__":
    main()
