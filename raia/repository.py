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
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config, provenance
from .sanitize import sanitize_artifact

# Canonical artifact file names, in pipeline order. The two-digit prefix makes
# the SDLC ordering visible in any file browser.
ARTIFACT_FILES: Dict[str, str] = {
    "product_brief": "01_product_brief.md",
    "risk_classification": "02_risk_classification.md",
    "requirements_review": "03_requirements_review.md",
    "refined_stories": "04_refined_stories.md",
    "audit_report": "05_audit_report.md",
    "drift_report": "06_drift_report.md",
    "open_issues": "07_open_issues.md",
}

OPEN = "open"
RESOLVED = "resolved"
ACCEPTED = "accepted"
ISSUE_STATUSES = (OPEN, RESOLVED, ACCEPTED)


def _sidecar(filename: str) -> str:
    return filename.rsplit(".", 1)[0] + ".json"


def _git_available() -> bool:
    return shutil.which("git") is not None


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


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

    def _commit_files(self, files: Dict[str, str], message: str) -> str:
        raise NotImplementedError

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
        commit = self._commit_files(
            {
                filename: header + cleaned.text,
                _sidecar(filename): json.dumps(payload, indent=2, ensure_ascii=False, default=str),
            },
            f"raia({key}): human-approved update by {approved_by}",
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
        self, issues: List[str], raised_by: str, artifact: str = "", commit: str = ""
    ) -> int:
        """Record normative conflicts as explicit, tracked open issues.

        Same-level conflicts and rule-engine/model disagreements are escalated
        for human arbitration rather than resolved silently — which means they
        need somewhere to live, a status, and a way to be seen. Duplicates of an
        already-recorded issue are skipped so a rejected-and-regenerated draft
        does not multiply the register.
        """
        existing = self.open_issues()
        known = {_fingerprint(i.get("text", "")) for i in existing}
        stamp = _now()
        added = 0

        for text in issues:
            text = (text or "").strip()
            if not text or _fingerprint(text) in known:
                continue
            known.add(_fingerprint(text))
            existing.append(
                {
                    "id": f"ISSUE-{len(existing) + 1}",
                    "text": text,
                    "raised_by": raised_by,
                    "artifact": artifact,
                    "commit": commit,
                    "raised_at": stamp,
                    "status": OPEN,
                }
            )
            added += 1

        if added:
            self._write_open_issues(existing, f"raia(open_issues): {added} raised by {raised_by}")
        return added

    def set_issue_status(self, issue_id: str, status: str, note: str = "", by: str = "human") -> bool:
        if status not in ISSUE_STATUSES:
            raise ValueError(f"Unknown status '{status}'. Use one of {ISSUE_STATUSES}.")
        issues = self.open_issues()
        for issue in issues:
            if issue.get("id") == issue_id:
                issue["status"] = status
                issue["resolution_note"] = note
                issue["resolved_by"] = by
                issue["resolved_at"] = _now()
                self._write_open_issues(
                    issues, f"raia(open_issues): {issue_id} marked {status} by {by}"
                )
                return True
        return False

    def _write_open_issues(self, issues: List[Dict[str, Any]], message: str) -> None:
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
                    f"  _raised by {i.get('raised_by', '?')} on {i.get('raised_at', '?')}_"
                    + (f" · _{i.get('resolution_note')}_" if i.get("resolution_note") else "")
                )
            lines.append("")

        self._commit_files(
            {
                filename: "\n".join(lines),
                _sidecar(filename): json.dumps(
                    {"artifact": "open_issues", "structured": {"issues": issues}},
                    indent=2, ensure_ascii=False,
                ),
            },
            message,
        )

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

    def _commit_files(self, files: Dict[str, str], message: str) -> str:
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
        if not self._use_git:
            return {"ok": True, "detail": "plain history log (git not installed)"}
        res = self._run_git("fsck", "--no-dangling")
        return {"ok": res.returncode == 0, "detail": "git object store verified"
                if res.returncode == 0 else (res.stderr.strip() or "git fsck failed")}

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

    # -- Evaluation instrumentation -------------------------------------------

    def record_event(self, kind: str, payload: Dict[str, Any]) -> None:
        """Append one evaluation event (rejection, approval, restore).

        The panel's interaction with the approval gate is the project's
        evidence for the human-oversight claim, so it is captured as data
        rather than reconstructed from memory afterwards. Stored outside the
        artifact tree: it is research data about the work, not part of the
        project's audit trail.
        """
        self.path.mkdir(parents=True, exist_ok=True)
        log = self.path / "evaluation_events.jsonl"
        entry = {"at": _now(), "kind": kind, **payload}
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

    def events(self) -> List[Dict[str, Any]]:
        log = self.path / "evaluation_events.jsonl"
        if not log.exists():
            return []
        out = []
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
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


def _fingerprint(text: str) -> str:
    return " ".join((text or "").lower().split())[:160]
