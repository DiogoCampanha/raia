"""
raia.config
===========

Central configuration for the RAIA system.

Everything that can vary between deployments (LLM provider, model name,
paths, RAG parameters) is read from environment variables so that switching
providers or storage locations is a configuration change, not a code change —
a RAIA design requirement: the LangChain abstraction keeps the system
provider-agnostic.

A `.env` file at the project root is loaded automatically (via python-dotenv)
so users only need to copy `.env.example` -> `.env` and fill in their key.
"""

import hashlib
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (two levels up from this file).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# ---------------------------------------------------------------------------
# LLM configuration
# ---------------------------------------------------------------------------

#: Which LLM provider to use: "anthropic" (default), "openai", or "mock".
#: "mock" is used by the test-suite / demo mode -- it produces canned,
#: deterministic outputs without any API call.
LLM_PROVIDER: str = os.getenv("RAIA_LLM_PROVIDER", "anthropic").lower()

#: Model name for the chosen provider.
LLM_MODEL: str = os.getenv("RAIA_LLM_MODEL", "claude-sonnet-5")

#: Sampling temperature. Kept low: agents produce normative analyses,
#: not creative text, so determinism aids reproducibility and auditability.
#: Some newer models no longer accept a temperature at all. Set
#: ``RAIA_LLM_TEMPERATURE = "none"`` (or leave it empty) to omit it; if a model
#: rejects it anyway, :func:`raia.llm.invoke_chat` retries once without it and
#: the provenance records ``temperature: null`` from then on.
def _optional_float(raw: str):
    raw = (raw or "").strip().lower()
    if raw in ("", "none", "null", "default", "omit"):
        return None
    return float(raw)


LLM_TEMPERATURE = _optional_float(os.getenv("RAIA_LLM_TEMPERATURE", "0.2"))

#: Maximum tokens per agent response. Agents now carry a computed rationale
#: block and a machine-readable summary in addition to their analysis, and a
#: response truncated at the limit is a reliability defect, so the ceiling is
#: generous and truncation is detected rather than tolerated.
LLM_MAX_TOKENS: int = int(os.getenv("RAIA_LLM_MAX_TOKENS", "8192"))

#: Retries for transient provider failures (overload / rate limit / timeout).
#: Applied with exponential backoff; non-transient errors are never retried.
LLM_RETRIES: int = int(os.getenv("RAIA_LLM_RETRIES", "2"))
LLM_RETRY_BASE_DELAY: float = float(os.getenv("RAIA_LLM_RETRY_BASE_DELAY", "2.0"))

#: How many times a reply that does not validate against the RAIA record schema
#: is sent back to the model with its validation errors before the stage shows
#: a fallback record. Each repair is one more model call.
CONTRACT_REPAIRS: int = int(os.getenv("RAIA_CONTRACT_REPAIRS", "1"))

# ---------------------------------------------------------------------------
# RAG / Chroma configuration
# ---------------------------------------------------------------------------

#: Directory containing the curated normative corpus (Markdown files).
CORPUS_DIR: Path = Path(os.getenv("RAIA_CORPUS_DIR", PROJECT_ROOT / "corpus"))

#: Directory where the persistent Chroma vector store lives.
CHROMA_DIR: Path = Path(os.getenv("RAIA_CHROMA_DIR", PROJECT_ROOT / ".chroma"))

#: Name of the Chroma collection holding the normative corpus.
CHROMA_COLLECTION: str = os.getenv("RAIA_CHROMA_COLLECTION", "raia_norms")

#: Number of corpus chunks retrieved per agent query.
#:
#: The corpus is deliberately small and curated. Similarity search over a pool
#: of ~20 chunks can silently drop the passage that decides a classification,
#: which produces a confident-looking answer with no ground under it. The
#: retrieval budget is therefore wide, and each agent additionally *pins* the
#: sections its decision procedure depends on (see raia.rationale), so the
#: decisive text is never absent regardless of similarity score.
RAG_TOP_K: int = int(os.getenv("RAIA_RAG_TOP_K", "12"))

#: Approximate chunk size (characters) used at ingestion time.
RAG_CHUNK_SIZE: int = int(os.getenv("RAIA_RAG_CHUNK_SIZE", "1800"))
RAG_CHUNK_OVERLAP: int = int(os.getenv("RAIA_RAG_CHUNK_OVERLAP", "200"))

#: Set RAIA_FAKE_EMBED=1 to replace the default embedding model with a cheap
#: deterministic hash-based embedding. Only meant for CI / offline tests.
FAKE_EMBEDDINGS: bool = os.getenv("RAIA_FAKE_EMBED", "0") == "1"

# ---------------------------------------------------------------------------
# Shared artifact repository (the blackboard)
# ---------------------------------------------------------------------------

#: Root directory where per-project artifact repositories are created.
#: Each project gets its own Git-versioned folder underneath.
WORKSPACE_DIR: Path = Path(os.getenv("RAIA_WORKSPACE_DIR", PROJECT_ROOT / "workspace"))

# ---------------------------------------------------------------------------
# Users, projects and storage
# ---------------------------------------------------------------------------

#: Where users, projects, memberships, invitations and ratings live — and, when
#: ``STORE_BACKEND`` is ``database``, the artifacts themselves. A PostgreSQL URL
#: (e.g. a Neon connection string) on a hosted deployment; a local SQLite file
#: otherwise, so a laptop needs nothing installed.
DATABASE_URL: str = os.getenv("RAIA_DATABASE_URL", "") or f"sqlite:///{WORKSPACE_DIR / 'raia.db'}"

#: Where a project's artifacts, drafts and events are stored:
#:  * ``git``      — one Git repository per project under WORKSPACE_DIR (local default);
#:  * ``database`` — append-only, hash-chained tables in DATABASE_URL (hosted default).
#: A hosted filesystem is wiped on every redeploy, so a PostgreSQL URL selects
#: ``database`` unless told otherwise.
STORE_BACKEND: str = os.getenv(
    "RAIA_STORE", "database" if DATABASE_URL.startswith(("postgres://", "postgresql://")) else "git"
).lower()

#: How people sign in: ``google`` (OpenID Connect via Streamlit's native login)
#: or ``dev`` (a single fixed local user, for laptops and tests only). Empty
#: means: ``google`` when an ``[auth]`` block is configured, ``dev`` otherwise —
#: except that a PostgreSQL-backed deployment never falls back to ``dev``.
AUTH_MODE: str = os.getenv("RAIA_AUTH", "").lower()

#: The identity used in ``dev`` mode.
DEV_USER_EMAIL: str = os.getenv("RAIA_DEV_USER_EMAIL", "developer@raia.local")
DEV_USER_NAME: str = os.getenv("RAIA_DEV_USER_NAME", "Local developer")

#: Accounts allowed to download the pseudonymized research dataset.
ADMIN_EMAILS = {
    e.strip().lower() for e in os.getenv("RAIA_ADMIN_EMAILS", "").split(",") if e.strip()
}

#: Public contact shown on the Privacy Policy and User Agreement page. Google's
#: OAuth consent screen requires a reachable contact for the app.
CONTACT_EMAIL: str = os.getenv("RAIA_CONTACT_EMAIL", "")

#: Effective date of the current Privacy Policy and User Agreement
#: (docs/legal/PRIVACY_AND_TERMS.md). Anyone who accepted an earlier version is
#: asked to accept again on their next visit.
LEGAL_EFFECTIVE: str = "2026-09-17T00:00:00+00:00"

#: Model calls (runs and regenerations) one person may trigger per UTC day.
#: Protects the deployment's API key from a runaway session. 0 disables it.
MAX_RUNS_PER_DAY: int = int(os.getenv("RAIA_MAX_RUNS_PER_DAY", "60"))

#: Secret used to derive stable pseudonyms in research exports. Without it the
#: pseudonyms are still one-way, but a fixed secret keeps them stable across
#: exports and prevents anyone re-deriving them from a known email address.
PSEUDONYM_KEY: str = os.getenv("RAIA_PSEUDONYM_KEY", "")

# ---------------------------------------------------------------------------
# Analysis thresholds
# ---------------------------------------------------------------------------

#: Below this many observations, a per-group fairness figure is reported but
#: explicitly labelled as too small to support a conclusion. A parity gap on
#: twelve rows and one on 120,000 must not render identically.
MIN_GROUP_SAMPLES: int = int(os.getenv("RAIA_MIN_GROUP_SAMPLES", "30"))

#: Default fairness threshold used when no upstream ethical requirement
#: defines one. Deliberately conservative and always reported as a default.
DEFAULT_PARITY_THRESHOLD: float = float(os.getenv("RAIA_DEFAULT_PARITY_THRESHOLD", "0.1"))

# ---------------------------------------------------------------------------
# Normative authority levels (RAIA conflict-precedence rule)
# ---------------------------------------------------------------------------
# Conflicts across levels resolve by precedence: legal > standard > advisory.
# Conflicts within a level are surfaced as open issues for human arbitration.

AUTHORITY_LEVELS = {
    "eu_ai_act": "legal",
    "pl_2338_2023": "legal",
    "ieee_7000": "standard",
    "ms_rai_v2": "standard",
    "nist_ai_rmf": "advisory",
    "eccola": "advisory",
}

#: Human-readable names for corpus sources (used in citations and the UI).
SOURCE_NAMES = {
    "eu_ai_act": "EU AI Act (Regulation (EU) 2024/1689)",
    "pl_2338_2023": "Brazilian AI Bill PL 2338/2023",
    "ieee_7000": "IEEE 7000-2021 (Value-Based Engineering)",
    "ms_rai_v2": "Microsoft Responsible AI Standard v2",
    "nist_ai_rmf": "NIST AI Risk Management Framework 1.0",
    "eccola": "ECCOLA Method (21 cards)",
}

#: Sources whose text is a curated summary prepared for this project rather
#: than a quotable official text. Recorded so the limitation is visible in the
#: audit trail instead of being implied by the citation's authority level.
DERIVED_SOURCES = {"ieee_7000", "ms_rai_v2", "nist_ai_rmf", "eccola"}


def corpus_version() -> str:
    """Short content hash of the corpus directory.

    Stamped into every artifact's provenance so an approved recommendation can
    be tied to the exact normative text the agent was shown. Changing a corpus
    file changes this value, which is what makes a past artifact re-auditable
    against a newer corpus.
    """
    h = hashlib.sha256()
    try:
        for path in sorted(CORPUS_DIR.glob("*.md")):
            h.update(path.name.encode("utf-8"))
            h.update(path.read_bytes())
    except OSError:
        return "unavailable"
    return h.hexdigest()[:12]
