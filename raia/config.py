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

#: The model each provider uses when ``RAIA_LLM_MODEL`` is not set. Claude is
#: the reference model; the OpenAI default is that provider's model with the
#: same balance of capability and cost. Provider model ids change: check the
#: provider's model list before relying on a default.
DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-5-5",
    "openai": "gpt-6.2-sol",
    "mock": "mock",
}

#: Model name for the chosen provider.
LLM_MODEL: str = os.getenv("RAIA_LLM_MODEL", "").strip() or DEFAULT_MODELS.get(LLM_PROVIDER, "")


#: Sampling temperature. Not sent by default: current Claude models (Sonnet 5.5
#: among them) and current OpenAI reasoning models refuse any temperature, so
#: the provider's own sampling applies. Set ``RAIA_LLM_TEMPERATURE`` to a number
#: for a model that accepts one (a low value aids reproducibility). If a model
#: rejects the value anyway, :func:`raia.llm.invoke_chat` retries once without
#: it and the provenance records ``temperature: null`` from then on, so every
#: record states what was actually sent. Reproducibility rests on the prompt
#: hash and, with ``RAIA_TRANSCRIPT_KEY``, the sealed transcript of each run.
def _optional_float(raw: str):
    raw = (raw or "").strip().lower()
    if raw in ("", "none", "null", "default", "omit"):
        return None
    return float(raw)


LLM_TEMPERATURE = _optional_float(os.getenv("RAIA_LLM_TEMPERATURE", ""))

#: Maximum tokens per agent response. Agents now carry a computed rationale
#: block and a machine-readable summary in addition to their analysis, and a
#: response truncated at the limit is a reliability defect, so the ceiling is
#: generous and truncation is detected rather than tolerated.
LLM_MAX_TOKENS: int = int(os.getenv("RAIA_LLM_MAX_TOKENS", "16384"))

#: The ceiling a retry may raise the budget to after a reply was cut off at the
#: limit. A standard record for a high-risk system carries a note per obligation
#: and several findings, so the first budget can be too small on a real project;
#: one retry with more room is cheaper than a wasted stage.
LLM_MAX_TOKENS_CEILING: int = int(os.getenv("RAIA_LLM_MAX_TOKENS_CEILING", "32000"))

#: Retries for transient provider failures (overload / rate limit / timeout).
#: Applied with exponential backoff; non-transient errors are never retried.
LLM_RETRIES: int = int(os.getenv("RAIA_LLM_RETRIES", "2"))
LLM_RETRY_BASE_DELAY: float = float(os.getenv("RAIA_LLM_RETRY_BASE_DELAY", "2.0"))

#: How many times a reply that cannot be read as a RAIA record is sent back to
#: the model — with its validation errors, or, when it was cut off at the token
#: limit, with a larger budget and an instruction to be compact — before the
#: stage shows a fallback record. Each repair is one more model call.
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
#: Log, for every page run, how long it took and how many database round trips
#: it made (``1`` to enable). For diagnosing a slow deployment; off by default.
PROFILE: bool = os.getenv("RAIA_PROFILE", "0") == "1"

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
LEGAL_EFFECTIVE: str = "2026-11-11T00:00:00+00:00"

#: Model calls (runs and regenerations) one person may trigger per UTC day.
#: Protects the deployment's API key from a runaway session. 0 disables it.
MAX_RUNS_PER_DAY: int = int(os.getenv("RAIA_MAX_RUNS_PER_DAY", "60"))

#: Secret used to derive stable pseudonyms in research exports. Without it the
#: pseudonyms are still one-way, but a fixed secret keeps them stable across
#: exports and prevents anyone re-deriving them from a known email address.
PSEUDONYM_KEY: str = os.getenv("RAIA_PSEUDONYM_KEY", "")

#: Key that encrypts the exact prompt and raw reply of every run, so a draft can
#: be reproduced and audited later (comma-separated: the first encrypts, all
#: decrypt, for rotation). Without it the text is not stored at all; a run keeps
#: only its prompt hash and token counts.
TRANSCRIPT_KEY: str = os.getenv("RAIA_TRANSCRIPT_KEY", "")

# Optional Jira integration. A person's Jira API token is stored encrypted with
# this key; without it the token lives only in the browser session and is asked
# for again next time. Jira is never required: the board works without it.
JIRA_KEY: str = os.getenv("RAIA_JIRA_KEY", "")

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
#: Every file in ``corpus/`` is such a summary today, the two legal texts
#: included; remove a key only when its file holds the official wording.
DERIVED_SOURCES = {"eu_ai_act", "pl_2338_2023", "ieee_7000", "ms_rai_v2", "nist_ai_rmf", "eccola"}

#: Legal sources that are not law yet. PL 2338/2023 is a bill: the Senate
#: approved it and the Chamber of Deputies has not voted. RAIA screens against
#: it because a team building today will ship under it, and says so wherever a
#: tier or an obligation of such a source is shown, so nobody reads a proposal
#: as a duty already in force. Remove a source from this set when it is enacted
#: (and check its corpus file against the enacted text).
PROPOSED_SOURCES = {"pl_2338_2023"}
#: What follows the name of a proposed source on screen and in documents.
PROPOSED_NOTE = "bill, not in force"


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


_BUILD_ID: str = ""


def build_id() -> str:
    """Which build of RAIA is running: package version plus the git commit.

    Stamped into every draft's provenance and every submitted assessment, so
    evaluations of different builds can be told apart. ``RAIA_BUILD`` overrides
    it on hosts where the source is not a git checkout.
    """
    global _BUILD_ID
    if _BUILD_ID:
        return _BUILD_ID
    from . import __version__

    sha = os.getenv("RAIA_BUILD", "").strip()
    if not sha:
        try:
            import subprocess

            out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=Path(__file__).resolve().parent,
                                 capture_output=True, text=True, timeout=3)
            sha = out.stdout.strip() if out.returncode == 0 else ""
        except (OSError, subprocess.SubprocessError):
            sha = ""
    _BUILD_ID = f"{__version__}+{sha or 'unknown'}"
    return _BUILD_ID
