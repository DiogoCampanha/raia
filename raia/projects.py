"""
raia.projects
=============

People, projects and who may do what — the layer every screen goes through.

A RAIA **project** owns its blackboard: its approved artifacts, the drafts
waiting at a human gate, the answers typed into each intake form, its open
issues and its evaluation events. A person reaches a project only through a
**membership**, and every operation on a project passes through one
authorization check, :meth:`ProjectService.authorize`, *below* the user
interface. The UI hides buttons a person may not use, but hiding is a courtesy;
the refusal happens here.

Roles
-----
``owner``     everything, including inviting people, changing roles, project
              settings and deleting the project.
``editor``    fills in intake forms, runs agents, approves or rejects drafts,
              arbitrates open issues.
``reviewer``  reads everything, approves or rejects drafts and arbitrates open
              issues, but does not run agents or change inputs.

Approvals carry identity
------------------------
The approver recorded at a gate is the authenticated person, taken from the
session — never a name typed into a box. A project may additionally require a
**second approver**: the person who ran a stage cannot approve that stage's
draft, which is separation of duties enforced by code rather than by habit.

Stage is derived, never stored
------------------------------
A project's progress is computed from its blackboard every time it is asked
for. A stored "current stage" field would be a second source of truth, and the
stage gates already compute the only one that matters.
"""

from __future__ import annotations

import contextlib
import contextvars
import datetime as _dt
import functools
import hashlib
import hmac
import io
import json
import re
import uuid
import zipfile
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional

from . import config
from .db import Database, get_database, utcnow
from . import lineage
from .storage import open_repository

OWNER = "owner"
EDITOR = "editor"
REVIEWER = "reviewer"
ROLES = (OWNER, EDITOR, REVIEWER)
ROLE_LABELS = {
    OWNER: "Owner — full control, manages people and settings",
    EDITOR: "Editor — fills in inputs, runs agents, approves",
    REVIEWER: "Reviewer — reviews and approves drafts, does not run agents",
}

#: action -> roles allowed to perform it.
PERMISSIONS: Dict[str, frozenset] = {
    "view": frozenset({OWNER, EDITOR, REVIEWER}),
    "run": frozenset({OWNER, EDITOR}),
    "review": frozenset({OWNER, EDITOR, REVIEWER}),
    "manage": frozenset({OWNER}),
}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AccessDenied(PermissionError):
    """The person is not allowed to do this on this project."""


class UsageLimitReached(RuntimeError):
    """The person reached the daily model-call allowance."""


@dataclass(frozen=True)
class User:
    id: str
    email: str
    name: str
    consented_at: Optional[str] = None

    @property
    def label(self) -> str:
        return f"{self.name} <{self.email}>" if self.name else self.email

    @property
    def is_admin(self) -> bool:
        return self.email.lower() in config.ADMIN_EMAILS


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    description: str
    created_by: str
    created_at: str
    updated_at: str
    archived_at: Optional[str]
    require_second_approver: bool
    role: str = ""

    def can(self, action: str) -> bool:
        return self.role in PERMISSIONS[action]


def _user(row: Dict[str, Any]) -> User:
    return User(row["id"], row["email"], row.get("name") or "", row.get("consented_at"))


def _project(row: Dict[str, Any]) -> Project:
    return Project(
        id=row["id"], name=row["name"], description=row.get("description") or "",
        created_by=row["created_by"], created_at=row["created_at"], updated_at=row["updated_at"],
        archived_at=row.get("archived_at"),
        require_second_approver=bool(row.get("require_second_approver")),
        role=row.get("role") or "",
    )


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def pseudonym(user_id: str) -> str:
    """Stable, one-way participant code for research exports."""
    if not user_id:
        return ""
    key = (config.PSEUDONYM_KEY or "raia-default-pseudonym-key").encode("utf-8")
    return "P-" + hmac.new(key, user_id.encode("utf-8"), hashlib.sha256).hexdigest()[:10]


#: Membership answers already looked up during the current page run. Set by
#: :meth:`ProjectService.request_scope`; ``None`` outside one, which means no
#: memo at all (every call queries).
_ACCESS_MEMO: "contextvars.ContextVar[Optional[Dict[Any, Any]]]" = contextvars.ContextVar(
    "raia_access_memo", default=None
)


def _changes_access(fn):
    """Mark a method that changes projects or memberships.

    It runs without the per-run membership memo (so it reads what it just
    wrote), and the memo is dropped afterwards for the rest of the run.
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        memo = _ACCESS_MEMO.get()
        token = _ACCESS_MEMO.set(None)
        try:
            return fn(*args, **kwargs)
        finally:
            _ACCESS_MEMO.reset(token)
            if memo is not None:
                memo.clear()

    return wrapper


class ProjectService:
    """All project operations, each one authorized."""

    def __init__(self, runner: Any = None, db: Optional[Database] = None) -> None:
        self.db = db or get_database()
        self._runner = runner

    @property
    def runner(self):
        if self._runner is None:
            from .pipeline import StageRunner

            self._runner = StageRunner()
        return self._runner

    # -- One page run -------------------------------------------------------------

    @staticmethod
    @contextlib.contextmanager
    def request_scope() -> Iterator[None]:
        """Look up each membership once per page run instead of once per call.

        A page asks for the same project's membership several times (the
        project, its repository, its stage summary...). Inside this scope the
        first answer is reused for the rest of the run; the next run — the next
        click — asks the database again, so a person removed from a project
        still loses access on their next click. Any change to projects or
        memberships made during the run drops the memo.
        """
        token = _ACCESS_MEMO.set({})
        try:
            yield
        finally:
            _ACCESS_MEMO.reset(token)

    # -- People -------------------------------------------------------------------

    def sign_in(self, email: str, name: str = "") -> User:
        """Create or refresh the account for an authenticated identity."""
        email = normalize_email(email)
        if not EMAIL_RE.match(email):
            raise ValueError("A signed-in identity must carry a valid email address.")
        now = utcnow()
        with self.db.tx() as t:
            row = t.one("SELECT * FROM users WHERE email = ?", (email,))
            if row is None:
                t.execute(
                    "INSERT INTO users (id, email, name, created_at, last_login_at) VALUES (?, ?, ?, ?, ?)",
                    (uuid.uuid4().hex, email, name or "", now, now),
                )
            else:
                t.execute(
                    "UPDATE users SET last_login_at = ?, name = ? WHERE id = ?",
                    (now, name or row.get("name") or "", row["id"]),
                )
            row = t.one("SELECT * FROM users WHERE email = ?", (email,))
        return _user(row)

    def get_user(self, user_id: str) -> Optional[User]:
        row = self.db.one("SELECT * FROM users WHERE id = ?", (user_id,))
        return _user(row) if row else None

    def record_consent(self, user: User) -> User:
        self.db.execute("UPDATE users SET consented_at = ? WHERE id = ?", (utcnow(), user.id))
        return self.get_user(user.id)  # type: ignore[return-value]

    @_changes_access
    def delete_account(self, user: User) -> None:
        """Remove a person and everything that exists only because of them.

        Projects they alone own are deleted with all their data. Projects that
        have another owner keep their audit trail (approvals already recorded
        stay attributed — that is what an audit trail is for), but the person's
        membership, invitations, ratings and account are removed.
        """
        for p in self.list_projects(user, include_archived=True):
            owners = [m for m in self.members(user, p.id) if m["role"] == OWNER]
            if p.role == OWNER and len(owners) == 1:
                self._delete_project_data(p.id)
        with self.db.tx() as t:
            t.execute("DELETE FROM project_members WHERE user_id = ?", (user.id,))
            t.execute("DELETE FROM invitations WHERE email = ? OR invited_by = ?", (user.email, user.id))
            t.execute("DELETE FROM experience_ratings WHERE user_id = ?", (user.id,))
            t.execute("DELETE FROM usage_counters WHERE user_id = ?", (user.id,))
            t.execute("DELETE FROM users WHERE id = ?", (user.id,))

    # -- Projects ---------------------------------------------------------------------

    def list_projects(self, user: User, include_archived: bool = False) -> List[Project]:
        rows = self.db.query(
            "SELECT p.*, m.role FROM projects p JOIN project_members m ON m.project_id = p.id "
            "WHERE m.user_id = ? ORDER BY p.updated_at DESC",
            (user.id,),
        )
        projects = [_project(r) for r in rows]
        return projects if include_archived else [p for p in projects if not p.archived_at]

    @_changes_access
    def create_project(self, user: User, name: str, description: str = "") -> Project:
        name = (name or "").strip()
        if not name:
            raise ValueError("A project needs a name.")
        pid = uuid.uuid4().hex
        now = utcnow()
        with self.db.tx() as t:
            t.execute(
                "INSERT INTO projects (id, name, description, created_by, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (pid, name[:120], (description or "").strip()[:2000], user.id, now, now),
            )
            t.execute(
                "INSERT INTO project_members (project_id, user_id, role, added_at, added_by) "
                "VALUES (?, ?, ?, ?, ?)",
                (pid, user.id, OWNER, now, user.id),
            )
        open_repository(pid).record_event("project_created", {"user": user.id})
        return self.get_project(user, pid)

    def get_project(self, user: User, project_id: str) -> Project:
        memo = _ACCESS_MEMO.get()
        key = (user.id, project_id)
        if memo is not None and key in memo:
            row = memo[key]
        else:
            row = self.db.one(
                "SELECT p.*, m.role FROM projects p JOIN project_members m ON m.project_id = p.id "
                "WHERE p.id = ? AND m.user_id = ?",
                (project_id, user.id),
            )
            if memo is not None:
                memo[key] = row
        if row is None:
            # Same answer whether the project does not exist or is someone
            # else's: an id must not be usable to probe for projects.
            raise AccessDenied("Project not found, or you are not a member of it.")
        return _project(row)

    def authorize(self, user: User, project_id: str, action: str) -> Project:
        if action not in PERMISSIONS:
            raise ValueError(f"Unknown action '{action}'.")
        project = self.get_project(user, project_id)
        if not project.can(action):
            raise AccessDenied(
                f"Your role on this project ({project.role}) does not allow this ({action})."
            )
        return project

    def repository(self, user: User, project_id: str, action: str = "view"):
        self.authorize(user, project_id, action)
        return open_repository(project_id)

    def touch(self, project_id: str) -> None:
        self.db.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (utcnow(), project_id))

    @_changes_access
    def update_project(self, user: User, project_id: str, *, name: Optional[str] = None,
                       description: Optional[str] = None,
                       require_second_approver: Optional[bool] = None) -> Project:
        self.authorize(user, project_id, "manage")
        if name is not None and not name.strip():
            raise ValueError("A project needs a name.")
        with self.db.tx() as t:
            if name is not None:
                t.execute("UPDATE projects SET name = ? WHERE id = ?", (name.strip()[:120], project_id))
            if description is not None:
                t.execute("UPDATE projects SET description = ? WHERE id = ?",
                          (description.strip()[:2000], project_id))
            if require_second_approver is not None:
                t.execute("UPDATE projects SET require_second_approver = ? WHERE id = ?",
                          (1 if require_second_approver else 0, project_id))
            t.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (utcnow(), project_id))
        return self.get_project(user, project_id)

    @_changes_access
    def set_archived(self, user: User, project_id: str, archived: bool) -> Project:
        self.authorize(user, project_id, "manage")
        self.db.execute("UPDATE projects SET archived_at = ? WHERE id = ?",
                        (utcnow() if archived else None, project_id))
        return self.get_project(user, project_id)

    def delete_project(self, user: User, project_id: str) -> None:
        self.authorize(user, project_id, "manage")
        self._delete_project_data(project_id)

    @_changes_access
    def _delete_project_data(self, project_id: str) -> None:
        open_repository(project_id).reset()
        with self.db.tx() as t:
            t.execute("DELETE FROM invitations WHERE project_id = ?", (project_id,))
            t.execute("DELETE FROM project_members WHERE project_id = ?", (project_id,))
            t.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    # -- Members and invitations ------------------------------------------------------

    def members(self, user: User, project_id: str) -> List[Dict[str, Any]]:
        self.authorize(user, project_id, "view")
        return self.db.query(
            "SELECT u.id AS user_id, u.email, u.name, m.role, m.added_at FROM project_members m "
            "JOIN users u ON u.id = m.user_id WHERE m.project_id = ? ORDER BY m.added_at",
            (project_id,),
        )

    def invite(self, user: User, project_id: str, email: str, role: str) -> Dict[str, Any]:
        """Invite a person by the email address they sign in with.

        No message is sent. The invitation waits on the invitee's *My projects*
        page and is matched against the address their identity provider has
        verified, so only the owner of that address can accept it.
        """
        self.authorize(user, project_id, "manage")
        email = normalize_email(email)
        if not EMAIL_RE.match(email):
            raise ValueError("Enter a valid email address.")
        if role not in ROLES:
            raise ValueError(f"Unknown role '{role}'.")
        with self.db.tx() as t:
            member = t.one(
                "SELECT m.role FROM project_members m JOIN users u ON u.id = m.user_id "
                "WHERE m.project_id = ? AND u.email = ?",
                (project_id, email),
            )
            if member:
                raise ValueError(f"{email} is already a member of this project ({member['role']}).")
            t.execute(
                "UPDATE invitations SET status = 'revoked', responded_at = ? "
                "WHERE project_id = ? AND email = ? AND status = 'pending'",
                (utcnow(), project_id, email),
            )
            inv_id = uuid.uuid4().hex
            t.execute(
                "INSERT INTO invitations (id, project_id, email, role, invited_by, created_at, status) "
                "VALUES (?, ?, ?, ?, ?, ?, 'pending')",
                (inv_id, project_id, email, role, user.id, utcnow()),
            )
        open_repository(project_id).record_event("member_invited", {"user": user.id, "role": role})
        return {"id": inv_id, "email": email, "role": role}

    def project_invitations(self, user: User, project_id: str) -> List[Dict[str, Any]]:
        self.authorize(user, project_id, "manage")
        return self.db.query(
            "SELECT id, email, role, created_at FROM invitations "
            "WHERE project_id = ? AND status = 'pending' ORDER BY created_at",
            (project_id,),
        )

    def revoke_invitation(self, user: User, project_id: str, invitation_id: str) -> None:
        self.authorize(user, project_id, "manage")
        self.db.execute(
            "UPDATE invitations SET status = 'revoked', responded_at = ? "
            "WHERE id = ? AND project_id = ? AND status = 'pending'",
            (utcnow(), invitation_id, project_id),
        )

    def my_invitations(self, user: User) -> List[Dict[str, Any]]:
        return self.db.query(
            "SELECT i.id, i.role, i.created_at, p.name AS project_name, p.description, "
            "u.name AS invited_by_name, u.email AS invited_by_email FROM invitations i "
            "JOIN projects p ON p.id = i.project_id LEFT JOIN users u ON u.id = i.invited_by "
            "WHERE i.email = ? AND i.status = 'pending' ORDER BY i.created_at",
            (normalize_email(user.email),),
        )

    @_changes_access
    def respond_to_invitation(self, user: User, invitation_id: str, accept: bool) -> Optional[Project]:
        with self.db.tx() as t:
            inv = t.one(
                "SELECT * FROM invitations WHERE id = ? AND status = 'pending'", (invitation_id,)
            )
            if inv is None or normalize_email(inv["email"]) != normalize_email(user.email):
                raise AccessDenied("This invitation is not addressed to you, or it is no longer open.")
            t.execute(
                "UPDATE invitations SET status = ?, responded_at = ? WHERE id = ?",
                ("accepted" if accept else "declined", utcnow(), invitation_id),
            )
            if accept:
                t.execute(
                    "INSERT INTO project_members (project_id, user_id, role, added_at, added_by) "
                    "VALUES (?, ?, ?, ?, ?) ON CONFLICT (project_id, user_id) DO NOTHING",
                    (inv["project_id"], user.id, inv["role"], utcnow(), inv["invited_by"]),
                )
        if not accept:
            return None
        open_repository(inv["project_id"]).record_event(
            "member_joined", {"user": user.id, "role": inv["role"]}
        )
        return self.get_project(user, inv["project_id"])

    @_changes_access
    def change_role(self, user: User, project_id: str, member_id: str, role: str) -> None:
        self.authorize(user, project_id, "manage")
        if role not in ROLES:
            raise ValueError(f"Unknown role '{role}'.")
        with self.db.tx() as t:
            self._guard_last_owner(t, project_id, member_id, new_role=role)
            t.execute("UPDATE project_members SET role = ? WHERE project_id = ? AND user_id = ?",
                      (role, project_id, member_id))

    @_changes_access
    def remove_member(self, user: User, project_id: str, member_id: str) -> None:
        if member_id == user.id:
            self.authorize(user, project_id, "view")  # anyone may leave
        else:
            self.authorize(user, project_id, "manage")
        with self.db.tx() as t:
            self._guard_last_owner(t, project_id, member_id, new_role=None)
            t.execute("DELETE FROM project_members WHERE project_id = ? AND user_id = ?",
                      (project_id, member_id))

    @staticmethod
    def _guard_last_owner(t, project_id: str, member_id: str, new_role: Optional[str]) -> None:
        current = t.one("SELECT role FROM project_members WHERE project_id = ? AND user_id = ?",
                        (project_id, member_id))
        if current is None:
            raise ValueError("That person is not a member of this project.")
        if current["role"] == OWNER and new_role != OWNER:
            owners = t.query("SELECT user_id FROM project_members WHERE project_id = ? AND role = ?",
                             (project_id, OWNER))
            if len(owners) <= 1:
                raise ValueError("A project must keep at least one owner. Make someone else owner first.")

    # -- Progress (derived) --------------------------------------------------------------

    def stage_summary(self, user: User, project_id: str) -> Dict[str, Any]:
        """Where a project stands, derived from its blackboard and event log."""
        from .agents import AGENTS

        repo = self.repository(user, project_id, "view")
        stages = lineage.stage_states(repo, AGENTS)
        names = {k: a.spec.name for k, a in AGENTS.items()}
        for s in stages:
            s["stale_because_names"] = [names[k] for k in s["stale_because"]]
        open_issues = sum(1 for i in repo.open_issues() if i.get("status") == "open")
        approved = sum(1 for s in stages if s["approved"])
        next_stage = next((s for s in stages if s["status"] == lineage.READY), None)
        return {
            "stages": stages,
            "approved": approved,
            "total": len(stages),
            "in_review": [s["name"] for s in stages if s["status"] == lineage.IN_REVIEW],
            "stale": [s["name"] for s in stages if s["status"] == lineage.STALE],
            "next": next_stage["name"] if next_stage else None,
            "next_agent": next_stage["agent"] if next_stage else None,
            "open_issues": open_issues,
            "risk": risk_summary(repo),
        }

    def revision_impact(self, user: User, project_id: str, agent_key: str) -> List[str]:
        """Names of approved stages that re-approving ``agent_key`` would flag for review."""
        from .agents import AGENTS

        repo = self.repository(user, project_id, "view")
        return [AGENTS[k].spec.name for k in lineage.revision_impact(repo, agent_key, AGENTS)]

    def reconfirm_stage(self, user: User, project_id: str, agent_key: str, note: str = "") -> None:
        """Record a person's decision that a flagged stage still holds as approved.

        The artifact is not touched: nothing new is persisted, and the decision
        is an event attributed to the signed-in person, like any arbitration.
        """
        from .agents import AGENTS

        repo = self.repository(user, project_id, "review")
        state = next((s for s in lineage.stage_states(repo, AGENTS) if s["agent"] == agent_key), None)
        if state is None:
            raise ValueError(f"Unknown stage '{agent_key}'.")
        if state["status"] != lineage.STALE:
            raise ValueError("Only a stage flagged for review can be confirmed as still valid.")
        repo.record_event("stage_reconfirmed", {
            "agent": agent_key, "user": user.id, "upstream": state["stale_because"],
            "note": (note or "").strip()[:1000],
        })
        self.touch(project_id)

    # -- The pipeline, authorized ---------------------------------------------------------

    @staticmethod
    def _actor(user: User) -> Dict[str, str]:
        return {"id": user.id, "name": user.label}

    def _count_model_call(self, user: User) -> None:
        if config.MAX_RUNS_PER_DAY <= 0:
            return
        day = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
        with self.db.tx() as t:
            row = t.one("SELECT runs FROM usage_counters WHERE user_id = ? AND day = ?", (user.id, day))
            runs = row["runs"] if row else 0
            if runs >= config.MAX_RUNS_PER_DAY:
                raise UsageLimitReached(
                    f"You have reached today's limit of {config.MAX_RUNS_PER_DAY} agent runs. "
                    "It resets at midnight UTC."
                )
            t.execute(
                "INSERT INTO usage_counters (user_id, day, runs) VALUES (?, ?, 1) "
                "ON CONFLICT (user_id, day) DO UPDATE SET runs = usage_counters.runs + 1",
                (user.id, day),
            )

    def save_intake(self, user: User, project_id: str, agent_key: str, values: Dict[str, Any]) -> None:
        repo = self.repository(user, project_id, "run")
        repo.save_intake(agent_key, values, by=user.id)

    def load_intake(self, user: User, project_id: str, agent_key: str) -> Dict[str, Any]:
        return self.repository(user, project_id, "view").load_intake(agent_key)

    # -- Suggestions and recommendations (nothing counts until a person adopts it) --

    def suggest_intake(self, user: User, project_id: str, agent_key: str) -> Dict[str, Any]:
        """Answers to an agent's context questions, proposed from approved upstream work.

        Rule-based: no model is called and no usage is counted. The proposal is
        returned to the form, which fills only empty fields; the event records
        what was offered.
        """
        from .agents import AGENTS

        agent = AGENTS[agent_key]
        repo = self.repository(user, project_id, "run")
        if agent.spec.suggest is None:
            return {"fields": {}, "basis": "", "control_hints": []}
        result = agent.spec.suggest(repo.upstream_bundle(agent.spec.upstream_keys))
        repo.record_event("intake_suggested", {
            "agent": agent_key, "user": user.id,
            "fields": {k: v.get("values", []) for k, v in (result.get("fields") or {}).items()},
        })
        return result

    def recommend_requirements(self, user: User, project_id: str, agent_key: str,
                               inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Candidate requirements from the model, checked in code, for a person to adopt or reject."""
        from .agents import AGENTS

        agent = AGENTS[agent_key]
        if not hasattr(agent, "recommend"):
            raise ValueError("This agent does not recommend requirements.")
        repo = self.repository(user, project_id, "run")
        self._count_model_call(user)
        result = agent.recommend(repo, inputs)
        repo.record_event("requirements_recommended", {
            "agent": agent_key, "user": user.id,
            "offered": [c["addresses"] for c in result.get("candidates") or []],
            "dropped": [d.get("reason", "") for d in result.get("dropped") or []],
            "prompt_sha256_16": (result.get("provenance") or {}).get("prompt_sha256_16", ""),
        })
        return result

    def record_recommendation_decision(self, user: User, project_id: str, agent_key: str,
                                       candidate: Dict[str, Any], decision: str,
                                       requirement_id: str = "", edited: bool = False) -> None:
        """Log one person's decision on one candidate: adopted, or rejected."""
        if decision not in ("adopted", "rejected"):
            raise ValueError("A recommendation is adopted or rejected.")
        repo = self.repository(user, project_id, "run")
        repo.record_event(f"recommendation_{decision}", {
            "agent": agent_key, "user": user.id, "candidate": candidate.get("id", ""),
            "addresses": candidate.get("addresses", ""), "requirement_id": requirement_id,
            "edited": bool(edited),
        })

    def start_run(self, user: User, project_id: str, agent_key: str, inputs: Dict[str, Any]) -> dict:
        repo = self.repository(user, project_id, "run")
        repo.save_intake(agent_key, inputs, by=user.id)
        self._count_model_call(user)
        from .agents import AGENTS

        if agent_key in AGENTS and repo.read_artifact(AGENTS[agent_key].spec.output_key) is not None:
            repo.record_event("revision_started", {"agent": agent_key, "user": user.id})
        result = self.runner.start(project_id, agent_key, inputs, actor=self._actor(user))
        self.touch(project_id)
        return result

    def second_approver_blocks(self, user: User, project_id: str, payload: Dict[str, Any]) -> bool:
        project = self.get_project(user, project_id)
        return bool(project.require_second_approver and payload.get("run_by") == user.id)

    def resume(self, user: User, project_id: str, agent_key: str, decision: Dict[str, Any]) -> dict:
        """Deliver a human decision to a paused gate, as the signed-in person."""
        self.authorize(user, project_id, "review")
        action = decision.get("action")
        if action not in ("approve", "reject"):
            raise ValueError("A decision is either approve or reject.")
        repo = open_repository(project_id)
        pending = repo.load_pending(agent_key) or {}
        if action == "approve" and self.second_approver_blocks(user, project_id, pending):
            raise AccessDenied(
                "This project requires a second approver: the person who ran a stage cannot "
                "approve its draft. Ask another editor, reviewer or owner to review it."
            )
        clean = dict(decision)
        # Identity comes from the session, never from the caller's payload.
        clean["approver"] = user.label
        clean["approver_id"] = user.id
        if action == "reject":
            self._count_model_call(user)
        result = self.runner.resume(project_id, agent_key, clean)
        self.touch(project_id)
        return result

    def restore(self, user: User, project_id: str, agent_key: str) -> dict:
        repo = self.repository(user, project_id, "review")
        payload = repo.load_pending(agent_key)
        if not payload:
            raise ValueError("There is no saved draft to restore for this stage.")
        result = self.runner.restore(project_id, agent_key, payload)
        repo.record_event("restore", {"agent": agent_key, "user": user.id})
        return result

    def discard_pending(self, user: User, project_id: str, agent_key: str) -> None:
        self.repository(user, project_id, "run").clear_pending(agent_key)

    def has_thread(self, user: User, project_id: str, agent_key: str) -> bool:
        self.authorize(user, project_id, "view")
        return self.runner.has_thread(project_id, agent_key)

    def set_issue_status(self, user: User, project_id: str, issue_id: str, status: str,
                         note: str = "") -> bool:
        repo = self.repository(user, project_id, "review")
        ok = repo.set_issue_status(issue_id, status, note, user.label)
        if ok:
            repo.record_event("issue_arbitrated", {"user": user.id, "issue": issue_id, "status": status})
        return ok

    # -- Tester assessment -------------------------------------------------------------------

    def submit_rating(self, user: User, payload: Dict[str, Any]) -> None:
        """Store one tester assessment (final submission). A pending draft is discarded."""
        body = dict(payload)
        body["status"] = "submitted"
        with self.db.tx() as t:
            self._delete_drafts(t, user)
            t.execute(
                "INSERT INTO experience_ratings (id, user_id, submitted_at, payload) VALUES (?, ?, ?, ?)",
                (uuid.uuid4().hex, user.id, utcnow(), json.dumps(body, ensure_ascii=False, default=str)),
            )

    @staticmethod
    def _delete_drafts(t, user: User) -> None:
        for r in t.query("SELECT id, payload FROM experience_ratings WHERE user_id = ?", (user.id,)):
            if json.loads(r["payload"]).get("status") == "draft":
                t.execute("DELETE FROM experience_ratings WHERE id = ?", (r["id"],))

    def save_assessment_draft(self, user: User, payload: Dict[str, Any]) -> None:
        """Keep a half-finished assessment. Drafts never reach research exports."""
        body = dict(payload)
        body["status"] = "draft"
        with self.db.tx() as t:
            self._delete_drafts(t, user)
            t.execute(
                "INSERT INTO experience_ratings (id, user_id, submitted_at, payload) VALUES (?, ?, ?, ?)",
                (uuid.uuid4().hex, user.id, utcnow(), json.dumps(body, ensure_ascii=False, default=str)),
            )

    def _ratings(self, user: User) -> List[Dict[str, Any]]:
        rows = self.db.query(
            "SELECT submitted_at, payload FROM experience_ratings WHERE user_id = ? "
            "ORDER BY submitted_at DESC",
            (user.id,),
        )
        return [{"submitted_at": r["submitted_at"], **json.loads(r["payload"])} for r in rows]

    def my_latest_rating(self, user: User) -> Optional[Dict[str, Any]]:
        """The latest *submitted* assessment, or ``None``."""
        return next((r for r in self._ratings(user) if r.get("status", "submitted") != "draft"), None)

    def my_assessment_draft(self, user: User) -> Optional[Dict[str, Any]]:
        """The saved draft, if any. Submitting discards it, so a draft is always the newest."""
        return next((r for r in self._ratings(user) if r.get("status") == "draft"), None)

    def my_data_export(self, user: User) -> bytes:
        """Everything RAIA holds that is about this person, as JSON (right of access)."""
        account = self.db.one(
            "SELECT email, name, created_at, consented_at, last_login_at FROM users WHERE id = ?",
            (user.id,),
        ) or {}
        memberships = self.db.query(
            "SELECT p.name AS project, m.role, m.added_at FROM project_members m "
            "JOIN projects p ON p.id = m.project_id WHERE m.user_id = ? ORDER BY m.added_at",
            (user.id,),
        )
        invitations = self.db.query(
            "SELECT i.email, i.role, i.status, i.created_at, p.name AS project FROM invitations i "
            "LEFT JOIN projects p ON p.id = i.project_id WHERE i.email = ? OR i.invited_by = ?",
            (user.email, user.id),
        )
        document = {
            "exported_at": utcnow(),
            "account": dict(account),
            "project_memberships": [dict(m) for m in memberships],
            "invitations": [dict(i) for i in invitations],
            "assessments": self._ratings(user),
            "note": "Project content (answers, drafts, artifacts) is exported per project from "
                    "the project page, since it belongs to every member of that project.",
        }
        return json.dumps(document, indent=2, ensure_ascii=False, default=str).encode("utf-8")

    # -- Research data (pseudonymized) --------------------------------------------------------

    def research_export(self, user: User) -> bytes:
        """Every project's evaluation events and every rating, pseudonymized.

        Emails, names and free-text identities never leave: user ids become
        stable participant codes, approver labels are dropped, and project
        names are replaced by project codes. Free-text comments are kept, since
        they are the point of asking, and are the one field a researcher must
        read before publishing.
        """
        if not user.is_admin:
            raise AccessDenied("Only the study coordinators can export research data.")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
            projects = self.db.query("SELECT id, created_at, archived_at FROM projects ORDER BY created_at")
            codes = {p["id"]: f"PRJ-{i + 1:03d}" for i, p in enumerate(projects)}
            events: List[str] = []
            for p in projects:
                for e in open_repository(p["id"]).events():
                    events.append(json.dumps(pseudonymize_event(e, codes[p["id"]]), ensure_ascii=False))
            z.writestr("evaluation_events.jsonl", "\n".join(events))
            ratings = self.db.query(
                "SELECT user_id, submitted_at, payload FROM experience_ratings ORDER BY submitted_at"
            )
            submitted = [r for r in ratings
                         if json.loads(r["payload"]).get("status", "submitted") != "draft"]
            z.writestr("experience_ratings.jsonl", "\n".join(
                json.dumps({"participant": pseudonym(r["user_id"]), "submitted_at": r["submitted_at"],
                            **json.loads(r["payload"])}, ensure_ascii=False)
                for r in submitted
            ))
            members = self.db.query("SELECT project_id, user_id, role FROM project_members")
            z.writestr("memberships.jsonl", "\n".join(
                json.dumps({"project": codes.get(m["project_id"], "?"),
                            "participant": pseudonym(m["user_id"]), "role": m["role"]})
                for m in members
            ))
            z.writestr("README.txt", RESEARCH_README.format(created=utcnow()))
        buffer.seek(0)
        return buffer.read()


_IDENTITY_FIELDS = {"user", "by", "approver", "approver_id", "run_by", "run_by_name", "resolved_by"}


def pseudonymize_event(event: Dict[str, Any], project_code: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"project": project_code}
    for k, v in event.items():
        if k in ("user", "approver_id", "run_by"):
            out["participant" if k == "user" else k] = pseudonym(str(v)) if v else ""
        elif k in _IDENTITY_FIELDS:
            continue
        else:
            out[k] = v
    return out


RESEARCH_README = """RAIA — research data export (pseudonymized)
Created: {created}

evaluation_events.jsonl   One line per event in any project: runs rejected with
                          a reason code, approvals (attempt, edited or not,
                          checks), restores, arbitrations, membership changes,
                          and Requirements Reviewer recommendations: what was
                          suggested or recommended, and each candidate adopted
                          (edited or not) or rejected.
experience_ratings.jsonl  Each submitted tester assessment (instrument id in
                          "instrument"): optional broad profile, the five Likert
                          dimensions, optional per-stage items and open answers.
                          Drafts are excluded. A participant may submit more
                          than once; keep the latest per participant unless the
                          analysis says otherwise.
memberships.jsonl         Which participant held which role on which project.

Participants appear as P-xxxxxxxxxx codes (keyed HMAC of an internal id) and
projects as PRJ-nnn. No email address, name or project name is included.
Free-text comments are included verbatim: read them before publishing.
"""


#: EU tier text (from the risk screen) -> short label and severity for the UI.
RISK_LEVELS = [
    ("unacceptable", "Prohibited", "critical"),
    ("prohibited unless", "Restricted", "critical"),
    ("high-risk unless", "High risk (exemption claimed)", "high"),
    ("high-risk", "High risk", "high"),
    ("limited", "Limited risk", "medium"),
    ("minimal", "Minimal risk", "low"),
]


def risk_summary(repo) -> Dict[str, Any]:
    """The approved risk classification of a project, reduced to what a dashboard shows."""
    data = repo.read_data("risk_classification") or {}
    structured = data.get("structured") or {}
    verdict = structured.get("computed_verdict") or {}
    eu = str(verdict.get("eu_tier") or "")
    if not eu:
        return {"label": "Not assessed", "level": "none", "eu_tier": "", "br_tier": ""}
    label, level = eu, "medium"
    for needle, short, sev in RISK_LEVELS:
        if eu.startswith(needle):
            label, level = short, sev
            break
    return {"label": label, "level": level, "eu_tier": eu, "br_tier": str(verdict.get("br_tier") or "")}
