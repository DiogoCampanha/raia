"""
raia.repository
===============

The **shared artifact repository** — RAIA's blackboard.

Agents never talk to each other; they read from and, after human approval,
write to this repository. Every write is a recorded version, so the full
history of recommendations, approvals and revisions is preserved and auditable.

Two additions carry the weight of everything else in the system:

**A JSON sidecar for every artifact.** The blackboard used to hold prose, so
nothing downstream could operate on a *value* — a risk tier, an obligation, a
requirement identifier, a threshold. Every artifact is now written twice in the
same commit: the Markdown a person reads, and a structured record the next
agent's decision procedure consumes. This is what makes coverage matrices,
traceability and threshold checks possible at all.

**A real Open Issues register.** Same-level normative conflicts were supposed
to be recorded as explicit open issues and escalated for human arbitration.
The register now exists as a first-class artifact with its own file, its own
structure and its own page in the UI, populated automatically from the rule
engines and from each approved draft.

One blackboard belongs to one **project**. Everything that is not the storage
mechanism itself — sanitization, provenance headers, sidecars, the register,
deduplication — lives in :class:`BaseRepository`, so the two storage backends
cannot drift apart in behaviour:

* :class:`ArtifactRepository` — a Git repository per project on local disk;
* :class:`raia.storage.DatabaseRepository` — append-only, hash-chained tables
  in PostgreSQL, for hosted deployments whose disk does not survive a restart.
"""

import datetime as _dt
import json
import re
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import config, provenance
from .sanitize import sanitize_artifact

# Canonical artifact file names, in pipeline order. The two-digit prefix makes
# the SDLC ordering visible in any file browser.
ARTIFACT_FILES: Dict[str, str] = {
    "product_brief": "01_product_brief.md",
    "risk_classification": "02_risk_classification.md",
    "requirements_review": "03_requirements_review.md",
    "refined_stories": "04_refined_stories.md",
    "rai_backlog": "04a_rai_backlog.md",
    "audit_report": "05_audit_report.md",
    # Retired: the Drift Monitor is no longer part of the build. Kept so a
    # project that approved one still lists it under its documents.
    "drift_report": "06_drift_report.md",
    "open_issues": "07_open_issues.md",
    "backlog": "08_backlog.md",
    "sprints": "09_sprints.md",
}

#: Artifacts of stages no longer in the build, with how they are labelled.
RETIRED_ARTIFACTS: Dict[str, str] = {"drift_report": "Retired stage (Drift Monitor)"}

#: Registers maintained by code (not agent outputs): written through the same
#: commit path, but never listed as a stage's approved artifact.
REGISTERS = ("open_issues", "backlog", "sprints")

OPEN = "open"
RESOLVED = "resolved"
ACCEPTED = "accepted"
#: A person chose one of the issue's options (or wrote their own), with a reason.
DECIDED = "decided"
ISSUE_STATUSES = (OPEN, DECIDED, RESOLVED, ACCEPTED)


#: How many times a read-modify-write of a register is recomputed when another
#: writer committed in between (see :meth:`BaseRepository.atomic`).
ATOMIC_ATTEMPTS = 5


class ConcurrentEdit(RuntimeError):
    """Another write reached the project between this write's read and its commit."""

    def __init__(self, project: str = "") -> None:
        super().__init__(
            "Someone else changed this project at the same moment. Nothing was lost: "
            "reload and try again."
        )
        self.project = project


def _apply_decision(issue: Dict[str, Any], decision: Dict[str, Any]) -> None:
    """Record a person's decision on a register entry."""
    issue["status"] = DECIDED
    issue["decision"] = str(decision.get("choice") or "").strip()[:300]
    issue["rationale"] = str(decision.get("rationale") or "").strip()[:1000]
    issue["decided_by"] = decision.get("by") or "human"
    issue["decided_at"] = decision.get("at") or _now()


def _sidecar(filename: str) -> str:
    return filename.rsplit(".", 1)[0] + ".json"


def sprint_file(key: str, sprint_id: str) -> str:
    """The per-sprint copy of an artifact: ``04_refined_stories.SPR-2.md``.

    A flat name rather than a folder, so both storage backends and every export
    treat it as one more file of the blackboard.
    """
    stem, ext = ARTIFACT_FILES[key].rsplit(".", 1)
    return f"{stem}.{sprint_id}.{ext}"


def _git_available() -> bool:
    return shutil.which("git") is not None


def _now() -> str:
    """UTC, like every other timestamp in the audit trail."""
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


class BaseRepository:
    """Storage-independent blackboard behaviour for a single project.

    A backend implements the primitives at the bottom of this class: read a
    file, write a set of files as one recorded version, list history, and keep
    the non-audited working state (pending drafts, intake drafts, events).
    """

    backend = "abstract"

    def __init__(self, project: str) -> None:
        if not project or not str(project).strip():
            raise ValueError("Project id must not be empty.")
        self.project = str(project)

    # -- Backend primitives ----------------------------------------------------

    def _read_file(self, name: str) -> Optional[str]:
        raise NotImplementedError

    def _commit_files(self, files: Dict[str, str], message: str,
                      expected_head: Optional[str] = None) -> str:
        """Record ``files`` as one version.

        With ``expected_head``, refuse with :class:`ConcurrentEdit` unless the
        project's latest version is still that one: the write was computed
        from what was read at that version.
        """
        raise NotImplementedError

    def head(self) -> str:
        """An identifier of the project's latest recorded version."""
        raise NotImplementedError

    def refresh(self) -> None:
        """Forget any read cache, so the next read sees other writers' versions."""

    def history(self, limit: int = 50) -> List[Dict[str, str]]:
        raise NotImplementedError

    def current_files(self) -> Dict[str, str]:
        """Every current artifact file, name -> content (used by exports)."""
        raise NotImplementedError

    def verify_history(self) -> Dict[str, Any]:
        """Integrity of the version history: ``{"ok": bool, "detail": str}``."""
        raise NotImplementedError

    def _pending_write(self, agent_key: str, text: str) -> None:
        raise NotImplementedError

    def _pending_read(self, agent_key: str) -> Optional[str]:
        raise NotImplementedError

    def _pending_all(self) -> Dict[str, str]:
        raise NotImplementedError

    def _pending_delete(self, agent_key: str) -> None:
        raise NotImplementedError

    def save_intake(self, agent_key: str, values: Dict[str, Any], by: str = "") -> None:
        raise NotImplementedError

    def load_intake(self, agent_key: str) -> Dict[str, Any]:
        raise NotImplementedError

    def record_event(self, kind: str, payload: Dict[str, Any]) -> None:
        raise NotImplementedError

    def events(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def reset(self) -> None:
        raise NotImplementedError

    # -- Read side (what downstream agents consume) ---------------------------

    def read_artifact(self, key: str) -> Optional[str]:
        return self._read_file(ARTIFACT_FILES[key])

    def read_data(self, key: str) -> Dict[str, Any]:
        """The structured sidecar for an artifact, or ``{}`` if there is none."""
        text = self._read_file(_sidecar(ARTIFACT_FILES[key]))
        if not text:
            return {}
        try:
            return json.loads(text)
        except ValueError:
            return {}

    def existing_artifacts(self) -> List[str]:
        return [k for k in ARTIFACT_FILES if self.read_artifact(k) is not None]

    def read_sprint_artifact(self, key: str, sprint_id: str) -> Optional[str]:
        """The copy of an artifact approved for one sprint, if there is one."""
        return self._read_file(sprint_file(key, sprint_id))

    def read_sprint_data(self, key: str, sprint_id: str) -> Dict[str, Any]:
        text = self._read_file(_sidecar(sprint_file(key, sprint_id)))
        if not text:
            return {}
        try:
            return json.loads(text)
        except ValueError:
            return {}

    # -- Registers maintained by code (backlog, sprints) ------------------------

    def read_register(self, key: str) -> Dict[str, Any]:
        """The structured body of a code-maintained register, or ``{}``."""
        return dict((self.read_data(key) or {}).get("structured") or {})

    @staticmethod
    def register_files(key: str, structured: Dict[str, Any], markdown: str) -> Dict[str, str]:
        """The two files of a register, ready to go into one commit."""
        filename = ARTIFACT_FILES[key]
        return {
            filename: markdown,
            _sidecar(filename): json.dumps({"artifact": key, "structured": structured},
                                           indent=2, ensure_ascii=False, default=str),
        }

    def commit_files(self, files: Dict[str, str], message: str,
                     expected_head: Optional[str] = None) -> str:
        """Record several files as one version (used for register updates)."""
        return self._commit_files(files, message, expected_head=expected_head)

    def atomic(self, build: Callable[[], Tuple[Dict[str, str], str, Any]]) -> Tuple[Any, str]:
        """Run a read-modify-write of the registers without losing anyone's change.

        ``build`` reads what it needs from this repository, computes the new
        content and returns ``(files, message, result)``. The files are
        committed only if no other version was recorded since the read began;
        otherwise ``build`` runs again on the fresh state. Two people ticking
        two stories at the same moment therefore both see their tick kept.
        Returns ``(result, commit)``; ``commit`` is empty when nothing changed.
        """
        for attempt in range(ATOMIC_ATTEMPTS):
            self.refresh()
            base = self.head()
            files, message, result = build()
            if not files:
                return result, ""
            try:
                return result, self._commit_files(files, message, expected_head=base)
            except ConcurrentEdit:
                if attempt == ATOMIC_ATTEMPTS - 1:
                    raise
        raise RuntimeError("unreachable")

    def upstream_context(self, keys: List[str]) -> str:
        """Approved upstream artifacts, concatenated as prompt context."""
        parts = []
        for key in keys:
            content = self.read_artifact(key)
            if content:
                parts.append(f"===== UPSTREAM ARTIFACT: {key} =====\n{content.strip()}")
        return "\n\n".join(parts) if parts else "(no upstream artifacts yet)"

    def upstream_bundle(self, keys: List[str]) -> Dict[str, Dict[str, Any]]:
        """Text *and* structured payload for each upstream artifact.

        This is what a decision procedure reads. Text alone was never enough to
        compute a coverage matrix or a traceability register over.
        """
        bundle: Dict[str, Dict[str, Any]] = {}
        for key in keys:
            text = self.read_artifact(key)
            if text is None:
                continue
            payload = self.read_data(key)
            bundle[key] = {
                "text": text,
                "data": payload.get("structured", payload),
                "provenance": payload.get("provenance", {}),
            }
        return bundle

    # -- Write side (only ever called AFTER human approval) -------------------

    def save_artifact(
        self,
        key: str,
        content: str,
        approved_by: str = "human",
        structured: Optional[Dict[str, Any]] = None,
        run_provenance: Optional[Dict[str, Any]] = None,
        extra_files: Optional[Dict[str, str]] = None,
        sprint_id: str = "",
        expected_head: Optional[str] = None,
    ) -> str:
        """Persist an approved artifact — Markdown and sidecar, one commit.

        The content is sanitized on the way in, not only on the way in from the
        form: a human-edited draft is the largest free-text surface in the
        system, it is committed, and it is injected into every downstream
        prompt. Findings are recorded, never silently removed.
        """
        filename = ARTIFACT_FILES[key]
        cleaned = sanitize_artifact(content or "")
        record = dict(run_provenance or {})
        if cleaned.findings:
            record.setdefault("artifact_sanitization", []).extend(cleaned.findings)

        header = provenance.header_comment(key, record)
        payload = {
            "artifact": key,
            "file": filename,
            "structured": structured or {},
            "provenance": record,
        }
        files = {
            filename: header + cleaned.text,
            _sidecar(filename): json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        }
        if sprint_id:
            # The same approval, kept per sprint so the series survives the next one.
            copy = sprint_file(key, sprint_id)
            files[copy] = files[filename]
            files[_sidecar(copy)] = files[_sidecar(filename)]
        # Registers the approval changes (the backlog, the sprints) travel in the
        # same commit: one approval, one recorded version.
        files.update(extra_files or {})
        commit = self._commit_files(
            files,
            f"raia({key}): human-approved update by {approved_by}"
            + (f" ({sprint_id})" if sprint_id else ""),
            expected_head=expected_head,
        )
        self.clear_pending_for(key)
        return commit

    # -- Open issues register --------------------------------------------------

    def open_issues(self) -> List[Dict[str, Any]]:
        text = self._read_file(_sidecar(ARTIFACT_FILES["open_issues"]))
        if not text:
            return []
        try:
            return json.loads(text).get("structured", {}).get("issues", [])
        except ValueError:
            return []

    def append_open_issues(
        self, issues: List[Any], raised_by: str, artifact: str = "", commit: str = ""
    ) -> int:
        """Record normative conflicts as explicit, tracked open issues.

        Same-level conflicts and rule-engine/model disagreements are escalated
        for human arbitration rather than resolved silently — which means they
        need somewhere to live, a status, and a way to be seen. Each issue is a
        RAIA record issue (type, deciding role, blocking flag, options, links);
        a plain string is accepted and typed conservatively. Duplicates of an
        already-recorded issue are skipped so a rejected-and-regenerated draft
        does not multiply the register.

        An issue may arrive already decided — a person took the decision on the
        draft before approving it — as ``issue["decision"] = {"choice",
        "rationale", "by", "at"}``. It is recorded decided; if the same issue is
        already in the register and still open, the decision is applied to it.

        The register is read and written in one :meth:`atomic` step, so an
        issue raised at the same moment by another approval is never lost and
        no identifier is handed out twice.
        """

        def build():
            existing = self.open_issues()
            known = {_fingerprint(i.get("text", "")) for i in existing}
            stamp = _now()
            added = decided_existing = 0
            for item in issues:
                meta = item if isinstance(item, dict) else {"description": item}
                text = str(meta.get("description") or meta.get("text") or "").strip()
                decision = meta.get("decision") if isinstance(meta.get("decision"), dict) else None
                if not text:
                    continue
                if _fingerprint(text) in known:
                    if decision and decision.get("choice"):
                        for old in existing:
                            if _fingerprint(old.get("text", "")) == _fingerprint(text) and old.get("status") == OPEN:
                                _apply_decision(old, decision)
                                decided_existing += 1
                    continue
                known.add(_fingerprint(text))
                existing.append(
                    {
                        "id": _next_issue_id(existing),
                        "text": text,
                        "type": meta.get("type") or "missing_information",
                        "decision_owner": meta.get("decision_owner") or "product",
                        "blocking": bool(meta.get("blocking")),
                        "options": list(meta.get("options") or []),
                        "links": list(meta.get("links") or []),
                        "record_id": meta.get("id", ""),
                        "origin": meta.get("origin") or "agent",
                        "raised_by": raised_by,
                        "artifact": artifact,
                        "commit": commit,
                        "raised_at": stamp,
                        "status": OPEN,
                    }
                )
                if decision and decision.get("choice"):
                    _apply_decision(existing[-1], decision)
                added += 1
            if not (added or decided_existing):
                return {}, "", 0
            message = (f"raia(open_issues): {added} raised by {raised_by}"
                       + (f", {decided_existing} decided" if decided_existing else ""))
            return self._issue_files(existing), message, added

        added, _ = self.atomic(build)
        return added

    def set_issue_status(self, issue_id: str, status: str, note: str = "", by: str = "human",
                         decision: str = "") -> bool:
        """Settle (or reopen) one register entry. ``decision`` is the option chosen, for DECIDED."""
        if status not in ISSUE_STATUSES:
            raise ValueError(f"Unknown status '{status}'. Use one of {ISSUE_STATUSES}.")

        def build():
            issues = self.open_issues()
            issue = next((i for i in issues if i.get("id") == issue_id), None)
            if issue is None:
                return {}, "", False
            if status == OPEN:
                for k in ("decision", "rationale", "decided_by", "decided_at",
                          "resolution_note", "resolved_by", "resolved_at"):
                    issue.pop(k, None)
                issue["status"] = OPEN
                issue["reopened_by"], issue["reopened_at"] = by, _now()
                message = f"raia(open_issues): {issue_id} reopened by {by}"
            elif status == DECIDED:
                _apply_decision(issue, {"choice": decision, "rationale": note, "by": by, "at": _now()})
                message = f"raia(open_issues): {issue_id} decided by {by}"
            else:
                issue["status"] = status
                issue["resolution_note"] = note
                issue["resolved_by"] = by
                issue["resolved_at"] = _now()
                message = f"raia(open_issues): {issue_id} marked {status} by {by}"
            return self._issue_files(issues), message, True

        ok, _ = self.atomic(build)
        return ok

    def _issue_files(self, issues: List[Dict[str, Any]]) -> Dict[str, str]:
        """The register's two files (Markdown and sidecar) for one commit."""
        filename = ARTIFACT_FILES["open_issues"]
        lines = [
            "<!--  RAIA artifact: open_issues | maintained automatically from agent runs  -->",
            "",
            "# Open Issues (human arbitration required)",
            "",
            "Conflicts the system refused to resolve on its own: same-level normative",
            "conflicts, disagreements between a rule engine and an agent, and gaps a",
            "human has to close. Nothing here is settled by the software.",
            "",
        ]
        for status, title in (
            (OPEN, "Open"),
            (DECIDED, "Decided"),
            (ACCEPTED, "Accepted risk"),
            (RESOLVED, "Resolved"),
        ):
            group = [i for i in issues if i.get("status") == status]
            if not group:
                continue
            lines.append(f"## {title} ({len(group)})")
            lines.append("")
            for i in group:
                lines.append(
                    f"- **{i['id']}** — {i['text']}  \n"
                    f"  _{str(i.get('type', 'missing_information')).replace('_', ' ')} · decided by "
                    f"{str(i.get('decision_owner', 'product')).replace('_', ' ')}"
                    f"{' · blocking' if i.get('blocking') else ''}_  \n"
                    f"  _raised by {i.get('raised_by', '?')} on {i.get('raised_at', '?')}_"
                    + (f" · _{i.get('resolution_note')}_" if i.get("resolution_note") else "")
                    + (f"  \n  **Decided:** {i.get('decision')} — {i.get('rationale') or 'no reason given'} "
                       f"_({i.get('decided_by', '?')}, {i.get('decided_at', '?')})_" if i.get("status") == DECIDED else "")
                )
            lines.append("")

        return {
            filename: "\n".join(lines),
            _sidecar(filename): json.dumps(
                {"artifact": "open_issues", "structured": {"issues": issues}},
                indent=2, ensure_ascii=False,
            ),
        }

    # -- Run transcripts (reproducibility) ---------------------------------------

    def save_transcript(self, agent_key: str, draft_id: str, transcript: Dict[str, Any],
                        meta: Dict[str, Any]) -> None:
        """Keep a run's exact prompt and raw replies, sealed, with its token use.

        The provenance of an approved artifact carries a hash of the prompt;
        the transcript is what that hash was computed from, so a past draft
        can be reproduced and audited. The text is stored only encrypted
        (``RAIA_TRANSCRIPT_KEY``); without a key only the metadata is kept.
        It is working data, not part of the hash chain, and is deleted with
        the project.
        """
        from . import sealed

        row = {
            "draft_id": draft_id, "agent_key": agent_key, "created_at": _now(),
            "prompt_sha256_16": meta.get("prompt_sha256_16", ""), "model": meta.get("model", ""),
            "input_tokens": int(meta.get("input_tokens") or 0), "output_tokens": int(meta.get("output_tokens") or 0),
            "calls": int(meta.get("calls") or 0),
            "sealed": sealed.seal(json.dumps(transcript, ensure_ascii=False, default=str)),
        }
        self._transcript_write(row)

    def transcripts(self, unseal: bool = False) -> List[Dict[str, Any]]:
        """Every kept run, oldest first; with ``unseal``, the decrypted transcript too."""
        from . import sealed

        out = []
        for row in self._transcript_rows():
            item = {k: v for k, v in row.items() if k != "sealed"}
            item["stored"] = bool(row.get("sealed"))
            if unseal and row.get("sealed"):
                text = sealed.unseal(row["sealed"])
                item["transcript"] = json.loads(text) if text else None
            out.append(item)
        return out

    def _transcript_write(self, row: Dict[str, Any]) -> None:
        raise NotImplementedError

    def _transcript_rows(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    # -- Pending drafts (restart resilience) -----------------------------------

    def save_pending(self, agent_key: str, payload: Dict[str, Any]) -> None:
        """Keep an in-review draft outside the server process.

        The graph checkpointer may live in the server process. When a hosted
        deployment restarts mid-review, the paused thread is gone while the
        browser still shows the draft — the tester presses Approve and the app
        fails. The draft is therefore also stored here, so the review can be
        restored into a fresh graph run without re-calling the model.
        """
        self._pending_write(agent_key, json.dumps(payload, indent=2, ensure_ascii=False, default=str))

    def load_pending(self, agent_key: str) -> Optional[Dict[str, Any]]:
        text = self._pending_read(agent_key)
        if not text:
            return None
        try:
            return json.loads(text)
        except ValueError:
            return None

    def pending_agents(self) -> List[str]:
        """Agents with a draft currently awaiting human review."""
        return sorted(self._pending_all())

    def clear_pending_for(self, artifact_key: str) -> None:
        for agent_key, text in self._pending_all().items():
            try:
                if json.loads(text).get("artifact_key") == artifact_key:
                    self._pending_delete(agent_key)
            except ValueError:
                continue

    def clear_pending(self, agent_key: str) -> None:
        self._pending_delete(agent_key)


#: One lock per project folder, so two sessions in this process never interleave
#: a check-and-commit on the same Git repository.
_PATH_LOCKS: Dict[str, threading.RLock] = {}
_PATH_LOCKS_GUARD = threading.Lock()


class ArtifactRepository(BaseRepository):
    """Git-versioned blackboard for a single project, on local disk."""

    backend = "git"

    def __init__(self, project: str) -> None:
        slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in str(project).strip())
        if not slug:
            raise ValueError("Project name must contain letters or digits.")
        super().__init__(project)
        self.path: Path = config.WORKSPACE_DIR / slug
        self.artifacts_dir: Path = self.path / "artifacts"
        self.pending_dir: Path = self.path / ".pending"
        self.intake_dir: Path = self.path / ".intake"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self._use_git = _git_available()
        if self._use_git:
            self._init_git()

    # -- Git plumbing --------------------------------------------------------

    def _run_git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args], cwd=self.path, capture_output=True, text=True, check=False
        )

    def _init_git(self) -> None:
        if not (self.path / ".git").exists():
            self._run_git("init", "-q")
            self._run_git("config", "user.name", "RAIA")
            self._run_git("config", "user.email", "raia@localhost")

    def _read_file(self, name: str) -> Optional[str]:
        f = self.artifacts_dir / name
        return f.read_text(encoding="utf-8") if f.exists() else None

    def _lock(self) -> threading.RLock:
        with _PATH_LOCKS_GUARD:
            return _PATH_LOCKS.setdefault(str(self.path.resolve()), threading.RLock())

    def head(self) -> str:
        if self._use_git:
            rev = self._run_git("rev-parse", "HEAD")
            return rev.stdout.strip() if rev.returncode == 0 else "0"
        log = self.path / "history.json"
        return str(len(json.loads(log.read_text())) if log.exists() else 0)

    def _commit_files(self, files: Dict[str, str], message: str,
                      expected_head: Optional[str] = None) -> str:
        with self._lock():
            if expected_head is not None and self.head() != str(expected_head):
                raise ConcurrentEdit(self.project)
            for name, content in files.items():
                (self.artifacts_dir / name).write_text(content, encoding="utf-8")
            stamp = _now()
            if not self._use_git:
                log = self.path / "history.json"
                entries = json.loads(log.read_text()) if log.exists() else []
                entries.append({"files": list(files), "message": message, "at": stamp})
                log.write_text(json.dumps(entries, indent=2))
                return stamp
            for name in files:
                self._run_git("add", str(Path("artifacts") / name))
            self._run_git("commit", "-q", "-m", message)
            rev = self._run_git("rev-parse", "--short", "HEAD")
            return rev.stdout.strip() or stamp

    def current_files(self) -> Dict[str, str]:
        if not self.artifacts_dir.exists():
            return {}
        return {
            p.name: p.read_text(encoding="utf-8")
            for p in sorted(self.artifacts_dir.iterdir()) if p.is_file()
        }

    def verify_history(self) -> Dict[str, Any]:
        from .storage import verify_events

        with self._lock():
            events = verify_events(self._event_rows(chain_legacy=True))
        if not events["ok"]:
            return events
        if not self._use_git:
            return {"ok": True, "detail": f"plain history log (git not installed); {events['detail']}"}
        res = self._run_git("fsck", "--no-dangling")
        if res.returncode != 0:
            return {"ok": False, "detail": res.stderr.strip() or "git fsck failed"}
        return {"ok": True, "detail": f"git object store verified; {events['detail']}"}

    # -- Working state ---------------------------------------------------------

    def _pending_write(self, agent_key: str, text: str) -> None:
        self.pending_dir.mkdir(parents=True, exist_ok=True)
        (self.pending_dir / f"{agent_key}.json").write_text(text, encoding="utf-8")

    def _pending_read(self, agent_key: str) -> Optional[str]:
        f = self.pending_dir / f"{agent_key}.json"
        return f.read_text(encoding="utf-8") if f.exists() else None

    def _pending_all(self) -> Dict[str, str]:
        if not self.pending_dir.exists():
            return {}
        return {f.stem: f.read_text(encoding="utf-8") for f in self.pending_dir.glob("*.json")}

    def _pending_delete(self, agent_key: str) -> None:
        f = self.pending_dir / f"{agent_key}.json"
        if f.exists():
            f.unlink()

    def save_intake(self, agent_key: str, values: Dict[str, Any], by: str = "") -> None:
        self.intake_dir.mkdir(parents=True, exist_ok=True)
        (self.intake_dir / f"{agent_key}.json").write_text(
            json.dumps({"values": values, "by": by, "at": _now()}, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    def load_intake(self, agent_key: str) -> Dict[str, Any]:
        f = self.intake_dir / f"{agent_key}.json"
        if not f.exists():
            return {}
        try:
            return json.loads(f.read_text(encoding="utf-8")).get("values", {})
        except (ValueError, OSError):
            return {}

    def _transcript_write(self, row: Dict[str, Any]) -> None:
        folder = self.path / ".transcripts"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{row['draft_id']}.json").write_text(json.dumps(row, ensure_ascii=False), encoding="utf-8")

    def _transcript_rows(self) -> List[Dict[str, Any]]:
        folder = self.path / ".transcripts"
        if not folder.exists():
            return []
        rows = []
        for f in folder.glob("*.json"):
            try:
                rows.append(json.loads(f.read_text(encoding="utf-8")))
            except ValueError:
                continue
        return sorted(rows, key=lambda r: r.get("created_at", ""))

    # -- Evaluation instrumentation -------------------------------------------

    def record_event(self, kind: str, payload: Dict[str, Any]) -> None:
        """Append one evaluation event (rejection, approval, restore).

        The panel's interaction with the approval gate is the project's
        evidence for the human-oversight claim, so it is captured as data
        rather than reconstructed from memory afterwards. Stored outside the
        artifact tree: it is research data about the work, not part of the
        project's audit trail.
        """
        from .storage import GENESIS, event_digest

        self.path.mkdir(parents=True, exist_ok=True)
        with self._lock():
            rows = self._event_rows(chain_legacy=True)
            seq = len(rows) + 1
            parent = rows[-1]["digest"] if rows else GENESIS
            at = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="microseconds")
            body = json.dumps(payload, ensure_ascii=False, default=str)
            line = {"seq": seq, "at": at, "kind": kind, "payload": body, "parent_digest": parent,
                    "digest": event_digest(parent, seq, at, kind, body)}
            with (self.path / "evaluation_events.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(line, ensure_ascii=False) + "\n")

    def _event_rows(self, chain_legacy: bool = False) -> List[Dict[str, Any]]:
        """The stored event lines. Lines written before events were chained are
        chained once, in order, the first time a new event is recorded."""
        from .storage import GENESIS, event_digest

        log = self.path / "evaluation_events.jsonl"
        if not log.exists():
            return []
        rows = []
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
        if chain_legacy and any("digest" not in r for r in rows):
            parent, chained = GENESIS, []
            for i, r in enumerate(rows, 1):
                if "digest" in r:
                    body, at, kind = r["payload"], r["at"], r["kind"]
                else:
                    at, kind = r.pop("at", ""), r.pop("kind", "")
                    body = json.dumps(r, ensure_ascii=False, default=str)
                digest = event_digest(parent, i, at, kind, body)
                chained.append({"seq": i, "at": at, "kind": kind, "payload": body,
                                "parent_digest": parent, "digest": digest})
                parent = digest
            log.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in chained), encoding="utf-8")
            rows = chained
        return rows

    def events(self) -> List[Dict[str, Any]]:
        out = []
        for r in self._event_rows():
            if "digest" not in r:          # a line from before events were chained
                out.append(r)
                continue
            try:
                body = json.loads(r["payload"])
            except ValueError:
                body = {}
            out.append({"at": r["at"], "kind": r["kind"], **body})
        return out

    # -- Audit trail -----------------------------------------------------------

    def history(self, limit: int = 50) -> List[Dict[str, str]]:
        if self._use_git:
            res = self._run_git(
                "log", f"-{limit}", "--pretty=format:%h|%ad|%s", "--date=format:%Y-%m-%d %H:%M"
            )
            out = []
            for line in res.stdout.splitlines():
                try:
                    h, date, msg = line.split("|", 2)
                    out.append({"commit": h, "date": date, "message": msg})
                except ValueError:
                    continue
            return out
        log = self.path / "history.json"
        if log.exists():
            entries = json.loads(log.read_text())
            return [
                {"commit": "-", "date": e["at"], "message": e["message"]}
                for e in reversed(entries)
            ][:limit]
        return []

    def reset(self) -> None:
        """Delete this project's repository entirely."""
        root = config.WORKSPACE_DIR.resolve()
        target = self.path.resolve()
        if target != root and root in target.parents:
            shutil.rmtree(target, ignore_errors=True)

    @staticmethod
    def list_projects() -> List[str]:
        if not config.WORKSPACE_DIR.exists():
            return []
        return sorted(p.name for p in config.WORKSPACE_DIR.iterdir() if p.is_dir())


def _next_issue_id(issues: List[Dict[str, Any]]) -> str:
    """One more than the highest ISSUE-n in the register (never reused)."""
    numbers = [int(m.group(1)) for i in issues
               for m in [re.fullmatch(r"ISSUE-(\d+)", str(i.get("id") or ""))] if m]
    return f"ISSUE-{max(numbers, default=0) + 1}"


def _fingerprint(text: str) -> str:
    return " ".join((text or "").lower().split())[:160]
