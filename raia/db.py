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
import time
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
    # -- optional integrations (per person; never on a project's blackboard) --
    """CREATE TABLE IF NOT EXISTS jira_connections (
        user_id TEXT PRIMARY KEY,
        site TEXT NOT NULL,
        email TEXT NOT NULL,
        token_enc TEXT NOT NULL,
        project_key TEXT,
        issue_type TEXT,
        updated_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS ix_members_user ON project_members (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_invites_email ON invitations (email, status)",
    "CREATE INDEX IF NOT EXISTS ix_events_project ON project_events (project_id, at)",
]


#: Changes to the baseline schema above, applied once each and recorded in
#: ``schema_migrations``. The baseline stays exactly as first released, so an
#: existing database and a new one end in the same shape. Append only: never
#: edit or reorder an entry that has shipped.
def _add_columns(t: "Tx", table: str, columns: Sequence[str]) -> None:
    have = t.columns(table)
    for col in columns:
        name = col.split()[0]
        if name not in have:
            t.execute(f"ALTER TABLE {table} ADD COLUMN {col}")


def _m001_chain_events(t: "Tx") -> None:
    """Hash-chain the project event log (decisions live there, not only metrics)."""
    _add_columns(t, "project_events", ["seq INTEGER", "parent_digest TEXT", "digest TEXT"])
    from .storage import GENESIS, event_digest

    rows = t.query("SELECT id, project_id, at, kind, payload FROM project_events "
                   "WHERE seq IS NULL ORDER BY project_id, at, id")
    state: Dict[str, Any] = {}
    for r in rows:
        if r["project_id"] not in state:
            last = t.one("SELECT seq, digest FROM project_events WHERE project_id = ? AND seq IS NOT NULL "
                         "ORDER BY seq DESC LIMIT 1", (r["project_id"],))
            state[r["project_id"]] = (last["seq"], last["digest"]) if last else (0, GENESIS)
        seq, parent = state[r["project_id"]]
        seq += 1
        digest = event_digest(parent, seq, r["at"], r["kind"], r["payload"])
        t.execute("UPDATE project_events SET seq = ?, parent_digest = ?, digest = ? WHERE id = ?",
                  (seq, parent, digest, r["id"]))
        state[r["project_id"]] = (seq, digest)
    t.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_events_seq ON project_events (project_id, seq)")


def _m002_assessments(t: "Tx") -> None:
    """Assessments become findable: status, project, instrument and build as columns, items as rows."""
    _add_columns(t, "experience_ratings", ["status TEXT", "project_id TEXT", "instrument TEXT",
                                           "build TEXT", "updated_at TEXT"])
    import json as _json

    for r in t.query("SELECT id, submitted_at, payload FROM experience_ratings WHERE status IS NULL"):
        try:
            body = _json.loads(r["payload"])
        except ValueError:
            body = {}
        t.execute("UPDATE experience_ratings SET status = ?, instrument = ?, build = ?, updated_at = ? "
                  "WHERE id = ?",
                  (body.get("status") or "submitted", body.get("instrument") or "", body.get("build") or "",
                   r["submitted_at"], r["id"]))
    t.execute("""CREATE TABLE IF NOT EXISTS assessment_items (
        rating_id TEXT NOT NULL,
        kind TEXT NOT NULL,
        item_key TEXT NOT NULL,
        score INTEGER,
        value TEXT,
        comment TEXT,
        project_id TEXT,
        commit_ref TEXT,
        PRIMARY KEY (rating_id, kind, item_key)
    )""")
    t.execute("CREATE INDEX IF NOT EXISTS ix_ratings_user ON experience_ratings (user_id, status)")
    t.execute("CREATE INDEX IF NOT EXISTS ix_ratings_project ON experience_ratings (project_id)")
    t.execute("CREATE INDEX IF NOT EXISTS ix_items_project ON assessment_items (project_id, kind, item_key)")


def _m003_admin_audit(t: "Tx") -> None:
    """Who did what with administrative or account-wide reach (exports, deletions, sign-ins)."""
    t.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id TEXT PRIMARY KEY,
        at TEXT NOT NULL,
        actor_id TEXT,
        action TEXT NOT NULL,
        target TEXT,
        detail TEXT
    )""")
    t.execute("CREATE INDEX IF NOT EXISTS ix_audit_at ON audit_log (at)")


MIGRATIONS = [
    ("001_chain_events", _m001_chain_events),
    ("002_assessments", _m002_assessments),
    ("003_admin_audit", _m003_admin_audit),
]


def is_unique_violation(exc: BaseException) -> bool:
    """A primary-key or unique-index conflict, on either engine."""
    names = {c.__name__ for c in type(exc).__mro__}
    return "IntegrityError" in names or "UniqueViolation" in names


def utcnow() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def is_postgres_url(url: str) -> bool:
    return url.startswith(("postgres://", "postgresql://"))


#: A pooled connection used within this many seconds is handed out without a
#: liveness probe. Probing on every checkout cost one network round trip per
#: query — on a hosted database, most of the time a page took to redraw.
#: Connections idle for longer are still probed, which is what survives a
#: managed database that scaled to zero and dropped them.
FRESH_SECONDS = 30.0

#: Idle pooled connections are closed after this long, below the ~5 minutes
#: after which managed providers such as Neon suspend an idle database.
POOL_MAX_IDLE = 240.0


class Stats:
    """Round trips issued by this process, for profiling and query budgets.

    ``statements`` counts SQL statements sent; ``transactions`` counts explicit
    BEGIN/COMMIT pairs (two extra round trips each on PostgreSQL). A test holds
    the pages to a budget so a redraw cannot quietly grow back to dozens of
    database calls.
    """

    def __init__(self) -> None:
        self.statements = 0
        self.transactions = 0

    def reset(self) -> None:
        self.statements = 0
        self.transactions = 0

    @property
    def round_trips(self) -> int:
        return self.statements + 2 * self.transactions


def _check_if_stale(conn: Any) -> None:
    """Pool check: probe only a connection that sat idle, not every checkout."""
    last = getattr(conn, "_raia_last_used", None)
    if last is not None and time.monotonic() - last < FRESH_SECONDS:
        return
    from psycopg_pool import ConnectionPool

    ConnectionPool.check_connection(conn)


class Tx:
    """One unit of work. ``?`` placeholders on every engine."""

    def __init__(self, conn: Any, postgres: bool, stats: Optional["Stats"] = None) -> None:
        self._conn = conn
        self._pg = postgres
        self._stats = stats

    def _sql(self, sql: str) -> str:
        return sql.replace("?", "%s") if self._pg else sql

    def _count(self) -> None:
        if self._stats is not None:
            self._stats.statements += 1

    def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        self._count()
        cur = self._conn.cursor()
        try:
            cur.execute(self._sql(sql), tuple(params))
        finally:
            cur.close()

    def query(self, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        self._count()
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

    def columns(self, table: str) -> set:
        """The column names a table has now."""
        if self._pg:
            rows = self.query("SELECT column_name AS name FROM information_schema.columns "
                              "WHERE table_name = ? AND table_schema = current_schema()", (table,))
        else:
            rows = self.query(f"PRAGMA table_info({table})")
        return {r["name"] for r in rows}


class Database:
    """SQLite file locally, PostgreSQL (e.g. Neon) when hosted."""

    def __init__(self, url: str) -> None:
        self.url = url
        self.postgres = is_postgres_url(url)
        self._lock = threading.RLock()
        self.stats = Stats()
        if self.postgres:
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool

            # prepare_threshold=None keeps the pool compatible with the
            # transaction-mode connection poolers managed providers put in
            # front of Postgres. A connection that sat idle is probed before
            # use (a database that scaled to zero drops them); one used a
            # moment ago is not, because that probe is a full round trip.
            self.pool = ConnectionPool(
                url,
                min_size=1,
                max_size=6,
                kwargs={"autocommit": True, "prepare_threshold": None, "row_factory": dict_row},
                check=_check_if_stale,
                max_idle=POOL_MAX_IDLE,
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
    def _pg_connection(self) -> Iterator[Any]:
        with self.pool.connection() as conn:
            try:
                yield conn
            finally:
                try:
                    conn._raia_last_used = time.monotonic()
                except Exception:  # noqa: BLE001 - only an optimisation hint
                    pass

    @contextlib.contextmanager
    def _sqlite_tx(self) -> Iterator[Tx]:
        with self._lock:
            conn = self._sqlite
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield Tx(conn, False, self.stats)
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            else:
                conn.execute("COMMIT")

    @contextlib.contextmanager
    def tx(self) -> Iterator[Tx]:
        """An explicit transaction, for work of more than one statement."""
        self.stats.transactions += 1
        if self.postgres:
            with self._pg_connection() as conn:
                with conn.transaction():
                    yield Tx(conn, True, self.stats)
            return
        with self._sqlite_tx() as t:
            yield t

    @contextlib.contextmanager
    def _single(self) -> Iterator[Tx]:
        """One statement, atomic on its own.

        On PostgreSQL the pooled connections are in autocommit mode, so a lone
        statement already runs as its own transaction; wrapping it in
        BEGIN/COMMIT only added two network round trips to every read. SQLite
        is local and keeps its explicit transaction under the process lock.
        """
        if self.postgres:
            with self._pg_connection() as conn:
                yield Tx(conn, True, self.stats)
            return
        with self._sqlite_tx() as t:
            yield t

    def migrate(self) -> None:
        with self.tx() as t:
            for stmt in SCHEMA:
                t.execute(stmt)
            t.execute("CREATE TABLE IF NOT EXISTS schema_migrations "
                      "(id TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
        applied = {r["id"] for r in self.query("SELECT id FROM schema_migrations")}
        for mid, step in MIGRATIONS:
            if mid in applied:
                continue
            with self.tx() as t:
                step(t)
                t.execute("INSERT INTO schema_migrations (id, applied_at) VALUES (?, ?)", (mid, utcnow()))
        self.stats.reset()

    # Convenience wrappers for single statements.
    def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        with self._single() as t:
            t.execute(sql, params)

    def query(self, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        with self._single() as t:
            return t.query(sql, params)

    def one(self, sql: str, params: Sequence[Any] = ()) -> Optional[Dict[str, Any]]:
        with self._single() as t:
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
