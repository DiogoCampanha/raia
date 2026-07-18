"""
RAIA -- Responsible AI Assistant
================================

Reference implementation of the multi-agent architecture described in
"RAIA: A Multi-Agent Architecture to Operationalize Responsible AI across
the Software Development Life Cycle".

Package layout
--------------
* :mod:`raia.config`      -- environment-driven configuration.
* :mod:`raia.llm`         -- provider-agnostic LLM factory (Claude by default).
* :mod:`raia.rag`         -- Chroma RAG over the normative corpus.
* :mod:`raia.repository`  -- Git-versioned shared artifact repository (blackboard).
* :mod:`raia.agents`      -- the five specialized agents.
* :mod:`raia.pipeline`    -- LangGraph orchestration with human checkpoints.
"""

# --- Hosted-platform compatibility shim -------------------------------------
# Chroma requires sqlite3 >= 3.35, but some hosting platforms (notably
# Streamlit Community Cloud) ship an older system sqlite3. When the
# `pysqlite3-binary` package is available (installed on Linux via
# requirements.txt), transparently swap it in BEFORE chromadb is imported
# anywhere. Harmless no-op on machines with a modern sqlite3.
try:  # pragma: no cover - only takes effect on hosted Linux platforms
    __import__("pysqlite3")
    import sys as _sys

    _sys.modules["sqlite3"] = _sys.modules.pop("pysqlite3")
except ImportError:
    pass

__version__ = "0.1.0"
