"""
raia.export
===========

Session export: everything a tester saw, in one file.

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
    from .repository import ArtifactRepository

MANIFEST = """RAIA — evaluation session export
================================

Created: {created}
Session workspace: {project}

artifacts/            The approved artifacts. Each .md is what a human read and
                      approved; its provenance header records the model, the
                      corpus version, which attempt was approved, whether the
                      draft was edited, and the result of the automated checks.
                      Each .json is the structured record the next agent read.

git_history.txt       One line per approval. Every approval is a commit.

evaluation_events.jsonl
                      What happened during the session: every rejection with
                      its reason code, every approval, every rating. This is
                      the research data — it is about the session, not part of
                      the project's audit trail.

Nothing in this archive is sent anywhere. It is produced in your browser
session and downloaded by you.
"""


def session_bundle(repo: "ArtifactRepository") -> bytes:
    """Zip the whole session: artifacts, sidecars, history and events."""
    buffer = io.BytesIO()
    created = _dt.datetime.now().isoformat(timespec="seconds")

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("MANIFEST.txt", MANIFEST.format(created=created, project=repo.project))

        if repo.artifacts_dir.exists():
            for path in sorted(repo.artifacts_dir.iterdir()):
                if path.is_file():
                    z.write(path, f"artifacts/{path.name}")

        history = repo.history(limit=500)
        z.writestr(
            "git_history.txt",
            "\n".join(f"{h['commit']}  {h['date']}  {h['message']}" for h in history)
            or "(no commits)",
        )

        events = repo.events()
        z.writestr(
            "evaluation_events.jsonl",
            "\n".join(json.dumps(e, ensure_ascii=False, default=str) for e in events)
            or "",
        )

    buffer.seek(0)
    return buffer.read()


def bundle_name(project: str) -> str:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M")
    return f"raia-session-{project}-{stamp}.zip"
