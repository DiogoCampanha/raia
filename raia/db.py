"""
raia.db
=======

A deliberately small database layer shared by the project registry and the
database-backed artifact repository.

RAIA runs in two places. On a laptop, and in the test-suite, everything must
work with nothing installed beyond Python, so the database is a SQLite file.
On a hosted deployment the process's disk is disposable, so the same tables
live in a managed PostgreSQL instance. The SQL here is written once, in the
subset both engines accept, and the only dialect difference that leaks —
the parameter placeholder — is translated in one place.

No ORM: the schema is a handful of tables, and every query that touches
access control should be readable at a glance.
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence

SCHEMA: List[str] = [
    # -- identity and access -------------------------------------------------
    """CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT NOT NULL UNIQUE,
        name TEXT,
        created_at TEXT NOT NULL,
        consented_at TEXT,
        last_login_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        archived_at TEXT,
        require_second_approver INTEGER NOT NULL DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS project_members (
        project_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        role TEXT NOT NULL,
        added_at TEXT NOT NULL,
        added_by TEXT,
        PRIMARY KEY (project_id, user_id)
    )""",
    """CREATE TABLE IF NOT EXISTS invitations (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        email TEXT NOT NULL,
        role TEXT NOT NULL,
        invited_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        status TEXT NOT NULL,
        responded_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS experience_ratings (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        submitted_at TEXT NOT NULL,
        payload TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS usage_counters (
        user_id TEXT NOT NULL,
        day TEXT NOT NULL,
        runs INTEGER NOT NULL,
        PRIMARY KEY (user_id, day)
    )""",
    # -- the database-backed blackboard ---------------------------------------
    """CREATE TABLE IF NOT EXISTS project_files (
        project_id TEXT NOT NULL,
        name TEXT NOT NULL,
        seq INTEGER NOT NULL,
        content TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        PRIMARY KEY (project_id, name, seq)
    )""",
    """CREATE TABLE IF NOT EXISTS project_commits (
        project_id TEXT NOT NULL,
        seq INTEGER NOT NULL,
        at TEXT NOT NULL,
        message TEXT NOT NULL,
        files TEXT NOT NULL,
        parent_digest TEXT NOT NULL,
        digest TEXT NOT NULL,
        PRIMARY KEY (project_id, seq)
    )""",
    """CREATE TABLE IF NOT EXISTS pending_reviews (
        project_id TEXT NOT NULL,
        agent_key TEXT NOT NULL,
        payload TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (project_id, agent_key)
    )""",
    """CREATE TABLE IF NOT EXISTS intake_drafts (
        project_id TEXT NOT NULL,
        agent_key TEXT NOT NULL,
        values_json TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        updated_by TEXT,
        PRIMARY KEY (project_id, agent_key)
    )""",
    """CREATE TABLE IF NOT EXISTS project_events (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        at TEXT NOT NULL,
        kind TEXT NOT NULL,
        payload TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS ix_members_user ON project_members (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_invites_email ON invitations (email, status)",
    "CREATE INDEX IF NOT EXISTS ix_events_project ON project_events (project_id, at)",
]


def utcnow() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def is_postgres_url(url: str) -> bool:
    return url.startswith(("postgres://", "postgresql://"))


class Tx:
    """One unit of work. ``?`` placeholders on every engine."""

    def __init__(self, conn: Any, postgres: bool) -> None:
        self._conn = conn
        self._pg = postgres

    def _sql(self, sql: str) -> str:
        return sql.replace("?", "%s") if self._pg else sql

    def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        cur = self._conn.cursor()
        try:
            cur.execute(self._sql(sql), tuple(params))
        finally:
            cur.close()

    def query(self, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        cur = self._conn.cursor()
        try:
            cur.execute(self._sql(sql), tuple(params))
            rows = cur.fetchall()
            if self._pg:
                return [dict(r) for r in rows]
            cols = [c[0] for c in cur.description or []]
            return [dict(zip(cols, r)) for r in rows]
        finally:
            cur.close()

    def one(self, sql: str, params: Sequence[Any] = ()) -> Optional[Dict[str, Any]]:
        rows = self.query(sql, params)
        return rows[0] if rows else None


class Database:
    """SQLite file locally, PostgreSQL (e.g. Neon) when hosted."""

    def __init__(self, url: str) -> None:
        self.url = url
        self.postgres = is_postgres_url(url)
        self._lock = threading.RLock()
        if self.postgres:
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool

            # prepare_threshold=None keeps the pool compatible with the
            # transaction-mode connection poolers managed providers put in
            # front of Postgres; check_connection survives a database that
            # scaled to zero and dropped idle connections.
            self.pool = ConnectionPool(
                url,
                min_size=1,
                max_size=6,
                kwargs={"autocommit": True, "prepare_threshold": None, "row_factory": dict_row},
                check=ConnectionPool.check_connection,
                open=True,
            )
            self._sqlite = None
        else:
            path = url[len("sqlite:///"):] if url.startswith("sqlite:///") else url
            if path != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
            self._sqlite = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
            self._sqlite.execute("PRAGMA foreign_keys=ON")
            if path != ":memory:":
                self._sqlite.execute("PRAGMA journal_mode=WAL")
            self.pool = None
        self.migrate()

    @contextlib.contextmanager
    def tx(self) -> Iterator[Tx]:
        if self.postgres:
            with self.pool.connection() as conn:
                with conn.transaction():
                    yield Tx(conn, True)
            return
        with self._lock:
            conn = self._sqlite
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield Tx(conn, False)
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            else:
                conn.execute("COMMIT")

    def migrate(self) -> None:
        with self.tx() as t:
            for stmt in SCHEMA:
                t.execute(stmt)

    # Convenience wrappers for single statements.
    def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        with self.tx() as t:
            t.execute(sql, params)

    def query(self, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        with self.tx() as t:
            return t.query(sql, params)

    def one(self, sql: str, params: Sequence[Any] = ()) -> Optional[Dict[str, Any]]:
        with self.tx() as t:
            return t.one(sql, params)

    def close(self) -> None:
        if self.pool is not None:
            self.pool.close()
        if self._sqlite is not None:
            self._sqlite.close()


_instances: Dict[str, Database] = {}
_instances_lock = threading.Lock()


def get_database(url: Optional[str] = None) -> Database:
    """One Database per URL per process."""
    from . import config

    url = url or config.DATABASE_URL
    with _instances_lock:
        if url not in _instances:
            _instances[url] = Database(url)
        return _instances[url]


def reset_instances() -> None:
    """Close every cached connection (tests use this to simulate a restart)."""
    with _instances_lock:
        for db in _instances.values():
            try:
                db.close()
            except Exception:  # noqa: BLE001
                pass
        _instances.clear()
