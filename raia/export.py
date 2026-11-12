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

The AI Skill download (:func:`skill_bundle`) is the same project outputs for a
different reader: an AI assistant the team is allowed to use. It has two parts.
The fixed part is the skill (:mod:`raia.skill.build`): identical for every
project and every download of a version. The project part is this project's
outputs, written here, and it is the only thing that differs between two
downloads. It leaves out what belongs to the research and to RAIA's own
integrity checks: the evaluation events, the version history and the hash
chain. The download comes in four formats (:data:`raia.skill.build.FORMATS`):
three zips laid out for Cursor, ChatGPT and Claude, and one Markdown file for
any assistant.
"""

import datetime as _dt
import io
import json
import zipfile
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:  # pragma: no cover
    from .repository import BaseRepository

MANIFEST = """RAIA — project export
=====================

Created: {created}
Project: {project}
History integrity at export: {integrity}

BRIEF.md              One page to hand to someone else: what the product does
                      with AI, where it sits, the most pressing risks, the
                      requirements that answer them, the decisions needed and
                      what has been verified. Written by code from the approved
                      records.

artifacts/            The approved artifacts. Each .md is what a human read and
                      approved; its provenance header records the model, the
                      corpus version, which attempt was approved, whether the
                      draft was edited, and the result of the automated checks.
                      Each .json is the structured record the next agent read.

action_plan.csv       Every action from every approved RAIA record, sorted by
action_plan.json      computed priority, with owner, lifecycle stage, review
                      cadence, verification method and evidence artifact.

backlog.csv           The backlog: every story, its origin (RAI or product), the
backlog.json          requirements it implements, its status and sprint, its
                      ethical acceptance criteria and its Jira key if it has one.
sprints.json          Every sprint with its state, scope, audit opinion, trend and
                      the numbers recorded when it closed.
roadmap.csv           Where each approved requirement stands: its stories, its
                      state and the sprint it was verified in.

git_history.txt       One line per recorded version. Every approval is one.

history_chain.json    (database-backed projects) the full hash chain, so the
                      history can be re-verified offline.

runs.json             Every model run: stage, draft id, model, prompt hash and the
                      tokens it used. transcripts/ holds the exact prompt and raw
                      replies of each run, when this deployment keeps them
                      (RAIA_TRANSCRIPT_KEY); the prompt hash in an artifact's
                      provenance is computed from that prompt.

people.json           Who each user:<id> reference in the files is, at export
                      time. The record names people only by reference, so a
                      person who deletes their account is no longer named
                      anywhere, and the history still verifies.

evaluation_events.jsonl
                      What happened during the session: every rejection with
                      its reason code, every approval, every rating. This is
                      the research data — it is about the session, not part of
                      the project's audit trail. People appear as participant
                      codes, not names.

Nothing in this archive is sent anywhere. It is produced on request and
downloaded by you.
"""


def session_bundle(repo: "BaseRepository", project_label: str = "",
                   people: Optional[Dict[str, str]] = None) -> bytes:
    """Zip one project: artifacts, sidecars, history and pseudonymized events.

    ``people`` maps each ``user:<id>`` reference found in the files to the
    person's name at export time. It is written beside the files, not into
    them, so the files still verify against the hash chain.
    """
    from .projects import pseudonymize_event

    buffer = io.BytesIO()
    created = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    integrity = repo.verify_history()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("MANIFEST.txt", MANIFEST.format(
            created=created, project=project_label or repo.project,
            integrity=("OK — " if integrity["ok"] else "FAILED — ") + integrity["detail"],
        ))

        from .brief import project_brief

        z.writestr("BRIEF.md", project_brief(repo, project_label or repo.project, created[:10]))
        _outputs(z, repo)

        history = repo.history(limit=500)
        z.writestr(
            "git_history.txt",
            "\n".join(f"{h['commit']}  {h['date']}  {h['message']}" for h in history)
            or "(no commits)",
        )
        if hasattr(repo, "chain"):
            z.writestr("history_chain.json", json.dumps(repo.chain(), indent=2, default=str))
        if people:
            z.writestr("people.json", json.dumps(people, indent=2, ensure_ascii=False, sort_keys=True))
        if hasattr(repo, "transcripts"):
            runs = repo.transcripts(unseal=True)
            z.writestr("runs.json", json.dumps([{k: v for k, v in r.items() if k != "transcript"} for r in runs],
                                               indent=2, ensure_ascii=False))
            for r in runs:
                if r.get("transcript"):
                    z.writestr(f"transcripts/{r['draft_id']}.json",
                               json.dumps(r["transcript"], indent=2, ensure_ascii=False))

        events = [pseudonymize_event(e, "this-project") for e in repo.events()]
        z.writestr(
            "evaluation_events.jsonl",
            "\n".join(json.dumps(e, ensure_ascii=False, default=str) for e in events)
            or "",
        )

    buffer.seek(0)
    return buffer.read()


def _outputs(z: zipfile.ZipFile, repo: "BaseRepository", root: str = "") -> None:
    """The approved artifacts, the action plan and the board, under ``root``."""
    from .contract import actions as action_plan

    for name, content in repo.current_files().items():
        z.writestr(f"{root}artifacts/{name}", content)
    rows = action_plan.project_actions(repo)
    z.writestr(f"{root}action_plan.csv", action_plan.to_csv(rows))
    z.writestr(f"{root}action_plan.json", action_plan.to_json(rows))
    _board_files(z, repo, root)


def _board_files(z: zipfile.ZipFile, repo: "BaseRepository", root: str = "") -> None:
    """The backlog, the sprints and the roadmap, as tables (no Jira token is ever in them)."""
    import csv

    from . import backlog as B
    from . import roadmap as R

    bl, sp = B.load(repo)
    if not bl["stories"] and not sp["sprints"]:
        return
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["id", "origin", "title", "requirements", "status", "sprint", "verified_in", "carried_over",
                "ethical_criteria", "jira_key"])
    for s in bl["stories"]:
        w.writerow([s["id"], s.get("origin"), s.get("title"), " ".join(s.get("evr_ids") or []), s.get("status"),
                    s.get("sprint"), s.get("verified_in"), s.get("carried_over"),
                    " ".join(c["id"] for c in B.ethical_criteria(s)), (s.get("jira") or {}).get("key", "")])
    z.writestr(f"{root}backlog.csv", buf.getvalue())
    z.writestr(f"{root}backlog.json", json.dumps(bl, indent=2, ensure_ascii=False, default=str))
    z.writestr(f"{root}sprints.json", json.dumps(sp, indent=2, ensure_ascii=False, default=str))
    review = (repo.read_data("requirements_review") or {}).get("structured") or {}
    if review:
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(["requirement", "state", "stories", "legal_obligation", "priority", "verified_in", "statement"])
        for r in R.requirement_states(review, bl):
            w.writerow([r["id"], r["state"], " ".join(r["stories"]), r["obligation"], r["priority"],
                        r["verified_in"], r["statement"]])
        z.writestr(f"{root}roadmap.csv", buf.getvalue())


def _slug(project: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in project.lower()).strip("-")[:40] or "project"


def bundle_name(project: str) -> str:
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d-%H%M")
    return f"raia-{_slug(project)}-{stamp}.zip"


# ---------------------------------------------------------------------------
# The AI Skill download
# ---------------------------------------------------------------------------

SKILL_MANIFEST = """RAIA — project outputs for the AI Skill (the project part)
=============================================================

Created: {created}
Project: {project}

README.md             What this folder is, and when it was taken.

BRIEF.md              One page for a person: what the product does with AI, where
                      it sits, the most pressing risks, the requirements that
                      answer them, the decisions needed and what has been verified.

PROJECT_CONTEXT.md    This project's facts, generated by code from the approved
                      records: stages, what RAIA was told, risk tiers and
                      obligations, requirements and where they stand, open
                      decisions, backlog and sprints, latest audit, actions to
                      do now. Start here.

artifacts/            The approved artifacts. Each .md is what a human read and
                      approved; its provenance header records who approved it,
                      when, the model and the result of the automated checks.
                      Each .json is the same record, structured. A file named
                      <name>.SPR-n.md is the copy approved for sprint SPR-n.

action_plan.csv       Every action from every approved RAIA record, sorted by
action_plan.json      computed priority, with owner, lifecycle stage, review
                      cadence, verification method and evidence artifact.

backlog.csv           The backlog: every story, its origin (RAI or product), the
backlog.json          requirements it implements, its status and sprint, its
                      ethical acceptance criteria and its Jira key if it has one.
sprints.json          Every sprint with its state, scope, audit opinion and trend.
roadmap.csv           Where each approved requirement stands.

Not included: the research data (evaluation events), the version history and
the hash chain. They are in the full project download (Download project).
Nothing in this archive is sent anywhere. It is produced on request and
downloaded by you.
"""


def _project_part(z: zipfile.ZipFile, repo: "BaseRepository", label: str, created: str, root: str) -> None:
    """One project's outputs under ``root``: the only part of a download that depends on the project."""
    from .skill import build
    from .skill.context import project_context

    from .brief import project_brief

    z.writestr(root + "README.md", build.project_readme(label, created))
    z.writestr(root + "BRIEF.md", project_brief(repo, label, created[:10]))
    z.writestr(root + "PROJECT_CONTEXT.md", project_context(repo, label, created))
    z.writestr(root + "MANIFEST.txt", SKILL_MANIFEST.format(created=created, project=label))
    _outputs(z, repo, root)


def skill_bundle(repo: "BaseRepository", project_label: str = "", fmt: str = "cursor") -> bytes:
    """The AI Skill for one assistant: the fixed part, laid out for it, and this project's part.

    ``cursor``: the skill folder under ``.cursor/skills/``, ``raia-project/``
    beside it and an optional ``AGENTS.md``. ``chatgpt`` and ``claude``: the
    skill as a zip to upload (the same bytes for everyone) and ``raia-project/``
    to attach. ``generic``: one Markdown file, the fixed part first and the
    project's context after a marker. Every format opens with how to install it.
    """
    from .skill import build
    from .skill.context import project_context

    if fmt not in build.FORMATS:
        raise ValueError(f"unknown AI Skill format: {fmt}")
    label = project_label or repo.project
    created = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
    if fmt == "generic":
        part = (build.project_readme(label, created).split("\n```", 1)[0].rstrip() + "\n\n"
                + project_context(repo, label, created))
        return build.generic_markdown(part).encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README_FIRST.md", build.install_readme(fmt))
        if fmt == "cursor":
            for name, text in build.fixed_files().items():
                z.writestr(f".cursor/skills/{build.SKILL_DIR}/{name}", text)
            z.writestr("AGENTS.md", build.agents_md())
        else:
            z.writestr(f"{build.SKILL_DIR}.zip", build.fixed_zip())
        _project_part(z, repo, label, created, f"{build.PROJECT_DIR}/")
    buffer.seek(0)
    return buffer.read()


def skill_bundle_name(project: str, fmt: str = "cursor") -> str:
    from .skill import build

    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d-%H%M")
    return f"raia-{_slug(project)}-ai-skill-{fmt}-{stamp}.{build.FORMATS[fmt][1]}"


def skill_bundle_mime(fmt: str = "cursor") -> str:
    return "text/markdown" if fmt == "generic" else "application/zip"
