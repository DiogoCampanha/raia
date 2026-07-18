"""
raia.config
===========

Central configuration for the RAIA system.

Everything that can vary between deployments (LLM provider, model name,
paths, RAG parameters) is read from environment variables so that switching
providers or storage locations is a configuration change, not a code change
-- as stated in the paper (Section 3.3): "the LangChain abstraction keeps
the system provider-agnostic".

A `.env` file at the project root is loaded automatically (via python-dotenv)
so users only need to copy `.env.example` -> `.env` and fill in their key.
"""

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
LLM_MODEL: str = os.getenv("RAIA_LLM_MODEL", "claude-sonnet-4-5")

#: Sampling temperature. Kept low: agents produce normative analyses,
#: not creative text, so determinism aids reproducibility and auditability.
LLM_TEMPERATURE: float = float(os.getenv("RAIA_LLM_TEMPERATURE", "0.2"))

#: Maximum tokens per agent response.
LLM_MAX_TOKENS: int = int(os.getenv("RAIA_LLM_MAX_TOKENS", "4096"))

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
RAG_TOP_K: int = int(os.getenv("RAIA_RAG_TOP_K", "6"))

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
# Normative authority levels (paper Section 3.4, mechanism (c))
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
