"""
pytest entry point for the RAIA test-suite.

Each suite is a script with its own isolated workspace, database and
configuration (they set environment variables before importing RAIA, and RAIA
reads its configuration once at import). Running them in one process would
let one suite's settings leak into the next, so each runs in its own process
and is reported here as one test, with its failed checks in the message.

    pytest                      # every suite
    pytest -k projects          # one suite
    RAIA_COVERAGE=1 pytest      # with coverage; then: coverage combine && coverage report

The browser checks (``browser_check.py``, ``guide_screenshots.py``) need a
Chromium and are run separately.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

SUITES = [
    "test_engines",
    "test_contract",
    "smoke_test",
    "test_projects",
    "test_backlog",
    "test_jira",
    "test_skill",
    "test_ui",
]

#: Suites that exercise storage run again on the hash-chained database store
#: (SQLite here), and — when RAIA_TEST_DATABASE_URL names a disposable
#: PostgreSQL database — on PostgreSQL with the durable graph checkpointer.
STORAGE_SUITES = ["test_projects", "test_backlog", "test_jira"]
VARIANTS = ([(s, {}) for s in SUITES]
            + [(s, {"RAIA_STORE": "database"}) for s in STORAGE_SUITES]
            + ([(s, {"RAIA_DATABASE_URL": os.environ["RAIA_TEST_DATABASE_URL"]}) for s in STORAGE_SUITES]
               if os.environ.get("RAIA_TEST_DATABASE_URL") else []))


def _id(v) -> str:
    suite, extra = v
    if "RAIA_DATABASE_URL" in extra:
        return f"{suite}[postgres]"
    return f"{suite}[database]" if extra else suite


@pytest.mark.parametrize("suite,extra", VARIANTS, ids=[_id(v) for v in VARIANTS])
def test_suite(suite: str, extra: dict) -> None:
    if "RAIA_DATABASE_URL" in extra:
        _reset_postgres(extra["RAIA_DATABASE_URL"])
    env = {**os.environ, "RAIA_LLM_PROVIDER": "mock", "RAIA_FAKE_EMBED": "1",
           "RAIA_AUTH": os.environ.get("RAIA_AUTH", "dev"), **extra}
    cmd = [sys.executable]
    if os.environ.get("RAIA_COVERAGE") == "1":
        cmd += ["-m", "coverage", "run", "--parallel-mode", f"--rcfile={ROOT / '.coveragerc'}"]
    cmd.append(str(ROOT / "tests" / f"{suite}.py"))
    proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=1800)
    out = proc.stdout + proc.stderr
    failed = [line.strip() for line in out.splitlines() if line.strip().startswith("FAIL")]
    passed = sum(1 for line in out.splitlines() if line.strip().startswith("PASS"))
    assert proc.returncode == 0, (
        f"{suite}: {len(failed)} check(s) failed, {passed} passed\n" + "\n".join(failed[:40])
        + ("" if failed else "\n" + out[-4000:])
    )


def _reset_postgres(url: str) -> None:
    """Start each PostgreSQL run from an empty schema (the URL must be a throwaway database)."""
    import psycopg

    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
