"""
raia.storage
============

Chooses where a project's blackboard lives, and provides the database-backed
implementation used by hosted deployments.

Why a second backend exists at all: a hosted Streamlit process has a
disposable disk. A Git repository per project on that disk is erased on every
redeploy, which is incompatible with people returning to their projects over
days. :class:`DatabaseRepository` keeps the same semantics in PostgreSQL:

* **Append-only.** An approved artifact is never updated in place; a new
  version row is added, exactly as a commit would add one.
* **Hash-chained.** Every recorded version has a digest over its parent's
  digest, its message and the SHA-256 of every file it wrote. Altering or
  removing any past version breaks the chain, and :meth:`verify_history`
  says where. This is what keeps the audit trail tamper-evident without Git.

The behaviour above the storage primitives — sanitization, provenance, sidecars,
the open-issues register — is inherited unchanged from
:class:`raia.repository.BaseRepository`, so both backends are exercised by the
same tests.
"""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from typing import Any, Dict, List, Optional

from . import config
from .db import Database, get_database, is_unique_violation, utcnow
from .repository import ArtifactRepository, BaseRepository, ConcurrentEdit

#: How many times a write is re-tried when another writer took the next
#: version number first. Only plain writes are re-tried here; a write that was
#: computed from what it read raises ConcurrentEdit so the caller can recompute.
WRITE_ATTEMPTS = 5

GENESIS = "0" * 64

#: Per project, a counter bumped by every write made in this process. A
#: repository object's read snapshot is valid only while the counter is where
#: it was when the snapshot was taken, so a write made through any other
#: repository object for the same project is seen by the next read — at no
#: database cost.
_generation: Dict[str, int] = {}
_generation_lock = threading.Lock()


def _bump(project: str) -> None:
    with _generation_lock:
        _generation[project] = _generation.get(project, 0) + 1


def _gen(project: str) -> int:
    return _generation.get(project, 0)


def _event_time() -> str:
    """Microsecond UTC timestamp for events.

    Events are read back ``ORDER BY at``; two events in the same second (an
    approval and a re-confirmation, say) must not be ordered by a random id.
    ISO strings with and without microseconds still sort correctly together.
    """
    import datetime as _dt

    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="microseconds")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def event_digest(parent: str, seq: int, at: str, kind: str, payload_json: str) -> str:
    """Digest of one event, chained to the one before it in the same project."""
    material = json.dumps({"parent": parent, "seq": int(seq), "at": at, "kind": kind,
                           "payload": payload_json}, sort_keys=True, ensure_ascii=False)
    return _sha(material)


def verify_events(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Recompute an event chain: rows carry seq, at, kind, payload, parent_digest, digest."""
    parent, expected = GENESIS, 1
    for r in rows:
        if r.get("seq") != expected:
            return {"ok": False, "detail": f"event {expected} is missing from the event chain"}
        if r.get("parent_digest") != parent:
            return {"ok": False, "detail": f"event {expected} does not follow its parent"}
        if event_digest(parent, r["seq"], r["at"], r["kind"], r["payload"]) != r.get("digest"):
            return {"ok": False, "detail": f"event {expected} was altered"}
        parent, expected = r["digest"], expected + 1
    return {"ok": True, "detail": f"event chain intact ({len(rows)} events)"}


def commit_digest(parent: str, message: str, file_hashes: Dict[str, str], at: str) -> str:
    material = json.dumps(
        {"parent": parent, "message": message, "files": dict(sorted(file_hashes.items())), "at": at},
        sort_keys=True, ensure_ascii=False,
    )
    return _sha(material)


class DatabaseRepository(BaseRepository):
    """Append-only, hash-chained blackboard in the RAIA database."""

    backend = "database"

    def __init__(self, project: str, db: Optional[Database] = None) -> None:
        super().__init__(project)
        self.db = db or get_database()
        # Read-through snapshots, one per repository object. A repository is
        # opened for one service call or one page run, and a page run reads
        # the same handful of files many times over (every stage's status
        # checks its prerequisites). One query for the current version of every
        # file replaces a round trip per read. Any write to the project made in
        # this process invalidates the snapshot (see ``_generation``); the
        # recorded history itself is never cached.
        self._files: Optional[Dict[str, str]] = None
        self._pending: Optional[Dict[str, str]] = None
        self._seen = -1

    def _fresh(self) -> None:
        """Drop the snapshots if the project was written since they were taken."""
        gen = _gen(self.project)
        if gen != self._seen:
            self._files = None
            self._pending = None
            self._seen = gen

    # -- Versioned files --------------------------------------------------------

    def _current(self) -> Dict[str, str]:
        self._fresh()
        if self._files is None:
            rows = self.db.query(
                "SELECT f.name, f.content FROM project_files f "
                "JOIN (SELECT name, MAX(seq) AS seq FROM project_files WHERE project_id = ? "
                "GROUP BY name) m ON f.name = m.name AND f.seq = m.seq "
                "WHERE f.project_id = ? ORDER BY f.name",
                (self.project, self.project),
            )
            self._files = {r["name"]: r["content"] for r in rows}
        return self._files

    def _read_file(self, name: str) -> Optional[str]:
        return self._current().get(name)

    def head(self) -> str:
        row = self.db.one("SELECT MAX(seq) AS seq FROM project_commits WHERE project_id = ?", (self.project,))
        return str((row or {}).get("seq") or 0)

    def refresh(self) -> None:
        self._files = None
        self._pending = None
        self._seen = -1

    def _commit_files(self, files: Dict[str, str], message: str,
                      expected_head: Optional[str] = None) -> str:
        hashes = {name: _sha(content) for name, content in files.items()}
        for attempt in range(WRITE_ATTEMPTS):
            at = utcnow()
            try:
                with self.db.tx() as t:
                    last = t.one(
                        "SELECT seq, digest FROM project_commits WHERE project_id = ? "
                        "ORDER BY seq DESC LIMIT 1",
                        (self.project,),
                    )
                    if expected_head is not None and str(last["seq"] if last else 0) != str(expected_head):
                        raise ConcurrentEdit(self.project)
                    seq = (last["seq"] + 1) if last else 1
                    parent = last["digest"] if last else GENESIS
                    digest = commit_digest(parent, message, hashes, at)
                    for name, content in files.items():
                        t.execute(
                            "INSERT INTO project_files (project_id, name, seq, content, sha256) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (self.project, name, seq, content, hashes[name]),
                        )
                    t.execute(
                        "INSERT INTO project_commits (project_id, seq, at, message, files, parent_digest, digest) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (self.project, seq, at, message, json.dumps(sorted(files)), parent, digest),
                    )
            except Exception as exc:  # noqa: BLE001 - only a version-number race is retried
                if not is_unique_violation(exc):
                    raise
                # Another writer took this version number between our read and
                # our insert. A write computed from what it read must be
                # recomputed by its caller; a plain write simply goes again.
                if expected_head is not None:
                    raise ConcurrentEdit(self.project) from exc
                if attempt == WRITE_ATTEMPTS - 1:
                    raise
                continue
            _bump(self.project)
            return digest[:8]
        raise RuntimeError("unreachable")

    def history(self, limit: int = 50) -> List[Dict[str, str]]:
        rows = self.db.query(
            "SELECT seq, at, message, digest FROM project_commits WHERE project_id = ? "
            "ORDER BY seq DESC LIMIT ?",
            (self.project, int(limit)),
        )
        return [
            {"commit": r["digest"][:8], "date": r["at"][:16].replace("T", " "), "message": r["message"]}
            for r in rows
        ]

    def current_files(self) -> Dict[str, str]:
        return dict(self._current())

    def chain(self) -> List[Dict[str, Any]]:
        """The full commit chain, oldest first (exported for offline verification)."""
        commits = self.db.query(
            "SELECT seq, at, message, files, parent_digest, digest FROM project_commits "
            "WHERE project_id = ? ORDER BY seq",
            (self.project,),
        )
        files = self.db.query(
            "SELECT name, seq, sha256 FROM project_files WHERE project_id = ?", (self.project,)
        )
        by_seq: Dict[int, Dict[str, str]] = {}
        for f in files:
            by_seq.setdefault(f["seq"], {})[f["name"]] = f["sha256"]
        return [{**c, "file_hashes": by_seq.get(c["seq"], {})} for c in commits]

    def verify_history(self) -> Dict[str, Any]:
        """Recompute every digest and every file hash, then the event chain."""
        files = self._verify_files()
        if not files["ok"]:
            return files
        events = verify_events(self._event_rows())
        if not events["ok"]:
            return events
        return {"ok": True, "detail": f"{files['detail']}; {events['detail']}"}

    def _event_rows(self) -> List[Dict[str, Any]]:
        return self.db.query(
            "SELECT seq, at, kind, payload, parent_digest, digest FROM project_events "
            "WHERE project_id = ? ORDER BY seq", (self.project,))

    def _verify_files(self) -> Dict[str, Any]:
        parent = GENESIS
        commits = self.chain()
        contents = self.db.query(
            "SELECT name, seq, content, sha256 FROM project_files WHERE project_id = ?",
            (self.project,),
        )
        for row in contents:
            if _sha(row["content"]) != row["sha256"]:
                return {"ok": False, "detail": f"file {row['name']} (version {row['seq']}) was altered"}
        expected_seq = 1
        for c in commits:
            if c["seq"] != expected_seq:
                return {"ok": False, "detail": f"version {expected_seq} is missing from the chain"}
            if c["parent_digest"] != parent:
                return {"ok": False, "detail": f"version {c['seq']} does not follow its parent"}
            recomputed = commit_digest(parent, c["message"], c["file_hashes"], c["at"])
            if recomputed != c["digest"]:
                return {"ok": False, "detail": f"version {c['seq']} was altered"}
            parent = c["digest"]
            expected_seq += 1
        return {"ok": True, "detail": f"hash chain intact ({len(commits)} versions)"}

    # -- Working state ---------------------------------------------------------

    def _pending_map(self) -> Dict[str, str]:
        self._fresh()
        if self._pending is None:
            rows = self.db.query(
                "SELECT agent_key, payload FROM pending_reviews WHERE project_id = ?", (self.project,)
            )
            self._pending = {r["agent_key"]: r["payload"] for r in rows}
        return self._pending

    def _pending_write(self, agent_key: str, text: str) -> None:
        self.db.execute(
            "INSERT INTO pending_reviews (project_id, agent_key, payload, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (project_id, agent_key) DO UPDATE SET payload = excluded.payload, "
            "updated_at = excluded.updated_at",
            (self.project, agent_key, text, utcnow()),
        )
        _bump(self.project)

    def _pending_read(self, agent_key: str) -> Optional[str]:
        return self._pending_map().get(agent_key)

    def _pending_all(self) -> Dict[str, str]:
        return dict(self._pending_map())

    def _pending_delete(self, agent_key: str) -> None:
        self.db.execute(
            "DELETE FROM pending_reviews WHERE project_id = ? AND agent_key = ?",
            (self.project, agent_key),
        )
        _bump(self.project)

    def save_intake(self, agent_key: str, values: Dict[str, Any], by: str = "") -> None:
        self.db.execute(
            "INSERT INTO intake_drafts (project_id, agent_key, values_json, updated_at, updated_by) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT (project_id, agent_key) DO UPDATE SET "
            "values_json = excluded.values_json, updated_at = excluded.updated_at, "
            "updated_by = excluded.updated_by",
            (self.project, agent_key, json.dumps(values, ensure_ascii=False, default=str), utcnow(), by),
        )

    def load_intake(self, agent_key: str) -> Dict[str, Any]:
        row = self.db.one(
            "SELECT values_json FROM intake_drafts WHERE project_id = ? AND agent_key = ?",
            (self.project, agent_key),
        )
        if not row:
            return {}
        try:
            return json.loads(row["values_json"])
        except ValueError:
            return {}

    def record_event(self, kind: str, payload: Dict[str, Any]) -> None:
        """Append one event to the project's hash-chained event log.

        Events carry decisions that are not artifacts — a stage re-confirmed,
        a card accepted or rejected, a draft rejected with its reason — and the
        "needs review" status of every stage is computed from them, so they are
        chained like the versions are: editing one breaks ``verify_history``.
        """
        body = json.dumps(payload, ensure_ascii=False, default=str)
        for attempt in range(WRITE_ATTEMPTS):
            at = _event_time()
            try:
                with self.db.tx() as t:
                    last = t.one(
                        "SELECT seq, digest FROM project_events WHERE project_id = ? AND seq IS NOT NULL "
                        "ORDER BY seq DESC LIMIT 1", (self.project,))
                    seq = (last["seq"] + 1) if last else 1
                    parent = last["digest"] if last else GENESIS
                    t.execute(
                        "INSERT INTO project_events (id, project_id, at, kind, payload, seq, parent_digest, digest) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (uuid.uuid4().hex, self.project, at, kind, body, seq, parent,
                         event_digest(parent, seq, at, kind, body)),
                    )
                return
            except Exception as exc:  # noqa: BLE001 - only a sequence race is retried
                if not is_unique_violation(exc) or attempt == WRITE_ATTEMPTS - 1:
                    raise

    def events(self) -> List[Dict[str, Any]]:
        rows = self.db.query(
            "SELECT at, kind, payload FROM project_events WHERE project_id = ? ORDER BY seq, at, id",
            (self.project,),
        )
        out = []
        for r in rows:
            try:
                body = json.loads(r["payload"])
            except ValueError:
                body = {}
            out.append({"at": r["at"], "kind": r["kind"], **body})
        return out

    def _transcript_write(self, row: Dict[str, Any]) -> None:
        self.db.execute(
            "INSERT INTO run_transcripts (project_id, draft_id, agent_key, created_at, prompt_sha256_16, model, "
            "input_tokens, output_tokens, calls, sealed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (project_id, draft_id) DO NOTHING",
            (self.project, row["draft_id"], row["agent_key"], row["created_at"], row["prompt_sha256_16"],
             row["model"], row["input_tokens"], row["output_tokens"], row["calls"], row["sealed"]),
        )

    def _transcript_rows(self) -> List[Dict[str, Any]]:
        return self.db.query(
            "SELECT draft_id, agent_key, created_at, prompt_sha256_16, model, input_tokens, output_tokens, "
            "calls, sealed FROM run_transcripts WHERE project_id = ? ORDER BY created_at", (self.project,))

    def reset(self) -> None:
        """Erase every trace of this project (used when a project is deleted)."""
        with self.db.tx() as t:
            for table in ("project_files", "project_commits", "pending_reviews",
                          "intake_drafts", "project_events", "run_transcripts"):
                t.execute(f"DELETE FROM {table} WHERE project_id = ?", (self.project,))
        _bump(self.project)


def open_repository(project_id: str) -> BaseRepository:
    """The blackboard for one project, on the configured backend."""
    if config.STORE_BACKEND == "database":
        return DatabaseRepository(project_id)
    return ArtifactRepository(project_id)


def build_checkpointer():
    """Graph checkpointer: durable in PostgreSQL, in memory otherwise.

    With a PostgreSQL checkpointer a review paused at the human gate survives a
    server restart as a real graph thread, so the reviewer simply continues.
    The on-disk restore path remains as a second line of defence.
    """
    from . import db as _db

    if config.STORE_BACKEND == "database" and _db.is_postgres_url(config.DATABASE_URL):
        from langgraph.checkpoint.postgres import PostgresSaver

        saver = PostgresSaver(get_database().pool)
        saver.setup()
        return saver
    from langgraph.checkpoint.memory import MemorySaver

    return MemorySaver()
