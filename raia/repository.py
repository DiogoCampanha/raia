"""
raia.repository
===============

The **shared artifact repository** -- RAIA's blackboard.

From the paper (Section 3.3): "The agents form a linear pipeline coordinated
through a blackboard-style shared state: a repository of Markdown/JSON
artifacts versioned in Git. [...] With the blackboard design, the audit
trail is structural: every recommendation, decision, and revision is a
versioned, human- and machine-readable document."

Key properties implemented here:

* Agents **never** talk to each other directly; they only read from and
  (after human approval) write to this repository.
* Every write is a Git commit, so the full history of recommendations,
  approvals, and revisions is preserved and auditable.
* If Git is not installed, the repository degrades gracefully to plain
  files and records history in a JSON log instead (with a warning), so
  the tool remains usable everywhere.
"""

import datetime as _dt
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from . import config

# Canonical artifact file names, in pipeline order. The two-digit prefix
# makes the SDLC ordering visible in any file browser.
ARTIFACT_FILES: Dict[str, str] = {
    "product_brief": "01_product_brief.md",
    "risk_classification": "02_risk_classification.md",
    "requirements_review": "03_requirements_review.md",
    "refined_stories": "04_refined_stories.md",
    "audit_report": "05_audit_report.md",
    "drift_report": "06_drift_report.md",
    "open_issues": "07_open_issues.md",
}


def _git_available() -> bool:
    """True if a `git` executable is on PATH."""
    return shutil.which("git") is not None


class ArtifactRepository:
    """Git-versioned blackboard for a single project.

    One instance == one project folder under ``workspace/``. All methods
    are synchronous and cheap; commits are local only (nothing is pushed),
    keeping project data in organization-controlled storage as required by
    governance mechanism (d) of the paper.
    """

    def __init__(self, project: str) -> None:
        # Sanitize the project name into a safe folder slug.
        slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in project.strip())
        if not slug:
            raise ValueError("Project name must contain letters or digits.")
        self.project = project
        self.path: Path = config.WORKSPACE_DIR / slug
        self.artifacts_dir: Path = self.path / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self._use_git = _git_available()
        if self._use_git:
            self._init_git()

    # -- Git plumbing --------------------------------------------------------

    def _run_git(self, *args: str) -> subprocess.CompletedProcess:
        """Run a git command inside the project repository."""
        return subprocess.run(
            ["git", *args],
            cwd=self.path,
            capture_output=True,
            text=True,
            check=False,
        )

    def _init_git(self) -> None:
        """Initialise a local Git repo for the project if needed."""
        if not (self.path / ".git").exists():
            self._run_git("init", "-q")
            # A local identity so commits work on machines without global config.
            self._run_git("config", "user.name", "RAIA")
            self._run_git("config", "user.email", "raia@localhost")

    # -- Read side (what downstream agents consume) ---------------------------

    def read_artifact(self, key: str) -> Optional[str]:
        """Return the current approved content of an artifact, or None."""
        f = self.artifacts_dir / ARTIFACT_FILES[key]
        return f.read_text(encoding="utf-8") if f.exists() else None

    def existing_artifacts(self) -> List[str]:
        """List the artifact keys that already have approved content."""
        return [k for k in ARTIFACT_FILES if (self.artifacts_dir / ARTIFACT_FILES[k]).exists()]

    def upstream_context(self, keys: List[str]) -> str:
        """Concatenate a set of upstream artifacts as prompt context.

        This is how "downstream agents inherit the full context of upstream
        classifications and requirements" (paper, Section 3.2).
        """
        parts = []
        for key in keys:
            content = self.read_artifact(key)
            if content:
                parts.append(f"===== UPSTREAM ARTIFACT: {key} =====\n{content.strip()}")
        return "\n\n".join(parts) if parts else "(no upstream artifacts yet)"

    # -- Write side (only ever called AFTER human approval) -------------------

    def save_artifact(self, key: str, content: str, approved_by: str = "human") -> str:
        """Persist an approved artifact and commit it to Git.

        Returns the commit hash (or a timestamp id in the no-git fallback).
        The metadata header stamped at the top of the file records approval
        provenance -- part of the structural audit trail.
        """
        filename = ARTIFACT_FILES[key]
        timestamp = _dt.datetime.now().isoformat(timespec="seconds")
        header = (
            f"<!-- RAIA artifact: {key} | approved by: {approved_by} "
            f"| approved at: {timestamp} -->\n\n"
        )
        (self.artifacts_dir / filename).write_text(header + content, encoding="utf-8")

        if self._use_git:
            self._run_git("add", str(Path("artifacts") / filename))
            msg = f"raia({key}): human-approved update by {approved_by}"
            self._run_git("commit", "-q", "-m", msg)
            rev = self._run_git("rev-parse", "--short", "HEAD")
            return rev.stdout.strip() or timestamp

        # Fallback: append to a JSON history log when git is unavailable.
        log = self.path / "history.json"
        entries = json.loads(log.read_text()) if log.exists() else []
        entries.append({"artifact": key, "approved_by": approved_by, "at": timestamp})
        log.write_text(json.dumps(entries, indent=2))
        return timestamp

    def append_open_issue(self, issue: str, raised_by: str) -> None:
        """Record a normative conflict as an explicit open issue.

        Implements governance mechanism (c): same-level conflicts "are
        recorded as explicit open issues in the shared repository and
        escalated for human arbitration".
        """
        f = self.artifacts_dir / ARTIFACT_FILES["open_issues"]
        stamp = _dt.datetime.now().isoformat(timespec="seconds")
        entry = f"\n- **[{stamp}]** (raised by *{raised_by}*): {issue.strip()}\n"
        if f.exists():
            f.write_text(f.read_text(encoding="utf-8") + entry, encoding="utf-8")
        else:
            f.write_text("# Open Issues (human arbitration required)\n" + entry, encoding="utf-8")
        if self._use_git:
            self._run_git("add", str(Path("artifacts") / ARTIFACT_FILES["open_issues"]))
            self._run_git("commit", "-q", "-m", f"raia(open_issues): conflict raised by {raised_by}")

    # -- Audit trail -----------------------------------------------------------

    def history(self, limit: int = 50) -> List[Dict[str, str]]:
        """Return the commit history (newest first) for the audit trail view."""
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
                {"commit": "-", "date": e["at"], "message": f"raia({e['artifact']}) approved"}
                for e in reversed(entries)
            ]
        return []

    @staticmethod
    def list_projects() -> List[str]:
        """List project slugs that already exist in the workspace."""
        if not config.WORKSPACE_DIR.exists():
            return []
        return sorted(p.name for p in config.WORKSPACE_DIR.iterdir() if p.is_dir())
