"""
raia.export
===========

Project export: the whole blackboard of one project, in one file.

The hosted deployment's storage is disposable — workspaces are discarded when
the app restarts — and testers were being told to download artifacts one at a
time before that happened. That is a poor way to treat the only record of an
evaluation session, and it is the evidence the study depends on.

This builds a single archive with the approved artifacts (Markdown and their
structured sidecars), the Open Issues register, the Git history, the
evaluation events (rejections, ratings, approvals) and a plain-text manifest
explaining what each file is.
"""

import datetime as _dt
import io
import json
import zipfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .repository import BaseRepository

MANIFEST = """RAIA — project export
=====================

Created: {created}
Project: {project}
History integrity at export: {integrity}

artifacts/            The approved artifacts. Each .md is what a human read and
                      approved; its provenance header records the model, the
                      corpus version, which attempt was approved, whether the
                      draft was edited, and the result of the automated checks.
                      Each .json is the structured record the next agent read.

action_plan.csv       Every action from every approved RAIA record, sorted by
action_plan.json      computed priority, with owner, lifecycle stage, review
                      cadence, verification method and evidence artifact.

git_history.txt       One line per recorded version. Every approval is one.

history_chain.json    (database-backed projects) the full hash chain, so the
                      history can be re-verified offline.

evaluation_events.jsonl
                      What happened during the session: every rejection with
                      its reason code, every approval, every rating. This is
                      the research data — it is about the session, not part of
                      the project's audit trail. People appear as participant
                      codes, not names.

Nothing in this archive is sent anywhere. It is produced on request and
downloaded by you.
"""


def session_bundle(repo: "BaseRepository", project_label: str = "") -> bytes:
    """Zip one project: artifacts, sidecars, history and pseudonymized events."""
    from .projects import pseudonymize_event

    buffer = io.BytesIO()
    created = _dt.datetime.now().isoformat(timespec="seconds")
    integrity = repo.verify_history()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("MANIFEST.txt", MANIFEST.format(
            created=created, project=project_label or repo.project,
            integrity=("OK — " if integrity["ok"] else "FAILED — ") + integrity["detail"],
        ))

        for name, content in repo.current_files().items():
            z.writestr(f"artifacts/{name}", content)

        from .contract import actions as action_plan

        rows = action_plan.project_actions(repo)
        z.writestr("action_plan.csv", action_plan.to_csv(rows))
        z.writestr("action_plan.json", action_plan.to_json(rows))

        history = repo.history(limit=500)
        z.writestr(
            "git_history.txt",
            "\n".join(f"{h['commit']}  {h['date']}  {h['message']}" for h in history)
            or "(no commits)",
        )
        if hasattr(repo, "chain"):
            z.writestr("history_chain.json", json.dumps(repo.chain(), indent=2, default=str))

        events = [pseudonymize_event(e, "this-project") for e in repo.events()]
        z.writestr(
            "evaluation_events.jsonl",
            "\n".join(json.dumps(e, ensure_ascii=False, default=str) for e in events)
            or "",
        )

    buffer.seek(0)
    return buffer.read()


def bundle_name(project: str) -> str:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M")
    slug = "".join(c if c.isalnum() else "-" for c in project.lower()).strip("-")[:40] or "project"
    return f"raia-{slug}-{stamp}.zip"
