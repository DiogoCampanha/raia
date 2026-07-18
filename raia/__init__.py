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

__version__ = "0.1.0"
