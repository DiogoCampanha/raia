"""
raia.rag
========

Retrieval-Augmented Generation layer over the normative corpus.

Implements mechanism (b) of the paper's governance section: "agents answer
through RAG over the normative corpora, and each recommendation must link
to the specific norm excerpt that grounds it, making hallucinated
obligations detectable at review time."

Design choices
--------------
* **Chroma** persistent client (as specified in the paper, Section 3.3).
* **Default embedding function** (all-MiniLM-L6-v2 via ONNX) shipped with
  Chroma -- no extra API key needed for retrieval, which keeps setup light.
* Every chunk carries metadata: ``source`` (corpus file id), ``source_name``
  (human-readable), ``authority`` (legal / standard / advisory) and
  ``section`` (the nearest Markdown heading), so agents can cite precisely
  and the conflict-precedence rule (legal > standard > advisory) can be
  applied at prompt level.
"""

import hashlib
import re
from dataclasses import dataclass
from typing import List, Optional, Sequence

import chromadb

from . import config

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class NormChunk:
    """One retrieved excerpt of a normative document."""

    text: str
    source: str          # corpus file id, e.g. "eu_ai_act"
    source_name: str     # human-readable name for citations
    authority: str       # "legal" | "standard" | "advisory"
    section: str         # nearest Markdown heading at ingestion time

    def citation(self) -> str:
        """Formatted citation tag agents must attach to recommendations."""
        return f"[Source: {self.source_name} — {self.section} | authority: {self.authority}]"


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------


from chromadb.api.types import EmbeddingFunction  # noqa: E402  (after chromadb import)


class _FakeEmbeddingFunction(EmbeddingFunction):
    """Deterministic hash-based embeddings for offline tests (RAIA_FAKE_EMBED=1).

    NOT semantically meaningful -- only guarantees the pipeline runs without
    downloading the ONNX embedding model. Never use in production.
    Subclasses Chroma's EmbeddingFunction so query-time helpers
    (embed_query, etc.) are inherited.
    """

    DIM = 64

    def __call__(self, input: Sequence[str]) -> List[List[float]]:  # noqa: A002
        out = []
        for text in input:
            h = hashlib.sha256(text.encode("utf-8")).digest()
            # Repeat the 32-byte digest to fill DIM floats in [0, 1).
            vals = [(h[i % 32] + i) % 251 / 251.0 for i in range(self.DIM)]
            out.append(vals)
        return out

    @staticmethod
    def name() -> str:  # chromadb identifies embedding functions by name
        return "raia-fake-embed"

    def get_config(self) -> dict:  # required by newer chromadb persistence
        return {}

    @staticmethod
    def build_from_config(config: dict) -> "_FakeEmbeddingFunction":
        return _FakeEmbeddingFunction()


def _embedding_function():
    """Return the embedding function according to configuration."""
    if config.FAKE_EMBEDDINGS:
        return _FakeEmbeddingFunction()
    # Chroma's default: all-MiniLM-L6-v2 (ONNX), downloaded on first use.
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

    return DefaultEmbeddingFunction()


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------


def _split_markdown(text: str, chunk_size: int, overlap: int) -> List[dict]:
    """Split a Markdown document into heading-aware chunks.

    We track the nearest heading so each chunk's metadata records *where*
    in the norm the excerpt comes from -- this is what makes agent
    citations verifiable at human review time.
    """
    chunks: List[dict] = []
    current_section = "Preamble"
    buffer: List[str] = []

    def flush():
        joined = "\n".join(buffer).strip()
        if not joined:
            return
        # Window the section content into overlapping chunks.
        start = 0
        while start < len(joined):
            piece = joined[start : start + chunk_size]
            chunks.append({"text": piece, "section": current_section})
            if start + chunk_size >= len(joined):
                break
            start += chunk_size - overlap

    for line in text.splitlines():
        heading = re.match(r"^(#{1,4})\s+(.*)", line)
        if heading:
            flush()
            buffer = []
            current_section = heading.group(2).strip()
        else:
            buffer.append(line)
    flush()
    return chunks


def ingest_corpus(verbose: bool = True) -> int:
    """(Re)build the Chroma collection from the ``corpus/`` directory.

    Returns the number of chunks indexed. Idempotent: the collection is
    recreated from scratch on every call so the index always mirrors the
    corpus folder exactly.
    """
    client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))

    # Drop any stale collection to keep index == corpus.
    try:
        client.delete_collection(config.CHROMA_COLLECTION)
    except Exception:
        pass  # collection did not exist yet

    collection = client.create_collection(
        name=config.CHROMA_COLLECTION,
        embedding_function=_embedding_function(),
        metadata={"hnsw:space": "cosine"},
    )

    n = 0
    for md_file in sorted(config.CORPUS_DIR.glob("*.md")):
        source = md_file.stem
        authority = config.AUTHORITY_LEVELS.get(source, "advisory")
        source_name = config.SOURCE_NAMES.get(source, source)
        text = md_file.read_text(encoding="utf-8")

        for i, chunk in enumerate(
            _split_markdown(text, config.RAG_CHUNK_SIZE, config.RAG_CHUNK_OVERLAP)
        ):
            collection.add(
                ids=[f"{source}-{i}"],
                documents=[chunk["text"]],
                metadatas=[
                    {
                        "source": source,
                        "source_name": source_name,
                        "authority": authority,
                        "section": chunk["section"],
                    }
                ],
            )
            n += 1
        if verbose:
            print(f"  indexed {source} ({source_name})")

    if verbose:
        print(f"Ingested {n} chunks into '{config.CHROMA_COLLECTION}' at {config.CHROMA_DIR}")
    return n


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


class NormativeRetriever:
    """Thin retrieval wrapper used by every agent.

    Agents may restrict retrieval to the sources that ground them (their
    "normative grounding" column in Table 2 of the paper) via ``sources``.
    """

    def __init__(self) -> None:
        client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
        try:
            self._collection = client.get_collection(
                name=config.CHROMA_COLLECTION,
                embedding_function=_embedding_function(),
            )
        except Exception as exc:
            raise RuntimeError(
                "Chroma collection not found. Run `python ingest.py` first "
                "to build the normative index."
            ) from exc

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        sources: Optional[List[str]] = None,
    ) -> List[NormChunk]:
        """Return the top-k norm excerpts most relevant to *query*."""
        where = {"source": {"$in": sources}} if sources else None
        res = self._collection.query(
            query_texts=[query],
            n_results=top_k or config.RAG_TOP_K,
            where=where,
        )
        chunks: List[NormChunk] = []
        for doc, meta in zip(res["documents"][0], res["metadatas"][0]):
            chunks.append(
                NormChunk(
                    text=doc,
                    source=meta["source"],
                    source_name=meta["source_name"],
                    authority=meta["authority"],
                    section=meta["section"],
                )
            )
        return chunks

    @staticmethod
    def format_context(chunks: List[NormChunk]) -> str:
        """Render retrieved chunks as a prompt context block.

        Chunks are ordered by authority (legal first) so the precedence
        rule is visually reinforced in the prompt.
        """
        rank = {"legal": 0, "standard": 1, "advisory": 2}
        ordered = sorted(chunks, key=lambda c: rank.get(c.authority, 3))
        blocks = []
        for i, c in enumerate(ordered, 1):
            blocks.append(
                f"--- Excerpt {i} {c.citation()} ---\n{c.text.strip()}"
            )
        return "\n\n".join(blocks) if blocks else "(no excerpts retrieved)"
