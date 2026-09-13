"""
raia.rag
========

Retrieval-Augmented Generation layer over the normative corpus.

Implements RAIA's grounding mechanism: agents answer through retrieval over
the normative corpora, and each recommendation must link to the specific norm
excerpt that grounds it, making hallucinated obligations detectable at review
time — a property that is now *checked* (see ``raia.validators``) rather than
requested in a prompt.

Two design choices are worth stating plainly.

**Pinned excerpts.** The corpus is small and curated. Similarity search over a
filtered pool of a couple of dozen chunks can silently omit the passage that
decides a classification, and the resulting answer looks exactly as confident
as a grounded one. Each agent's decision procedure therefore declares the
sections it depends on, and those are fetched by exact metadata match and
merged ahead of the similarity results. Retrieval selects *additional*
context; it can no longer remove the decisive text.

**Excerpt identity.** Every chunk carries a stable id that is recorded in the
artifact's provenance, so an approved recommendation can be traced back to the
exact excerpts the agent was shown.
"""

import hashlib
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

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
    chunk_id: str = ""   # stable id, recorded in provenance
    pinned: bool = False  # required by the agent's decision procedure
    pin_reason: str = ""

    def citation(self) -> str:
        """Formatted citation tag agents must attach to recommendations."""
        return f"[Source: {self.source_name} — {self.section} | authority: {self.authority}]"

    @property
    def derived(self) -> bool:
        """True when the corpus text is a summary prepared for this project."""
        return self.source in config.DERIVED_SOURCES


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------


from chromadb.api.types import EmbeddingFunction  # noqa: E402  (after chromadb import)


class _FakeEmbeddingFunction(EmbeddingFunction):
    """Deterministic hash-based embeddings for offline tests (RAIA_FAKE_EMBED=1).

    NOT semantically meaningful -- only guarantees the pipeline runs without
    downloading the ONNX embedding model. Never use in production.
    """

    DIM = 64

    def __call__(self, input: Sequence[str]) -> List[List[float]]:  # noqa: A002
        out = []
        for text in input:
            h = hashlib.sha256(text.encode("utf-8")).digest()
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
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

    return DefaultEmbeddingFunction()


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------


def _split_markdown(text: str, chunk_size: int, overlap: int) -> List[dict]:
    """Split a Markdown document into heading-aware chunks.

    We track the nearest heading so each chunk's metadata records *where* in
    the norm the excerpt comes from -- this is what makes agent citations
    verifiable at human review time, and what lets a decision procedure pin a
    section by name.
    """
    chunks: List[dict] = []
    current_section = "Preamble"
    buffer: List[str] = []

    def flush():
        joined = "\n".join(buffer).strip()
        if not joined:
            return
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
    """(Re)build the Chroma collection from the ``corpus/`` directory."""
    client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))

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


def index_exists() -> bool:
    """True if the normative Chroma collection has already been built."""
    try:
        client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
        client.get_collection(config.CHROMA_COLLECTION)
        return True
    except Exception:
        return False


def corpus_sections() -> Dict[str, List[str]]:
    """Map corpus source -> section headings, read straight from the files.

    Used by the test-suite to verify that every section a decision procedure
    pins actually exists: a pin that silently matches nothing would reopen the
    exact failure mode pinning was introduced to close.
    """
    out: Dict[str, List[str]] = {}
    for md_file in sorted(config.CORPUS_DIR.glob("*.md")):
        headings = [
            m.group(2).strip()
            for m in (re.match(r"^(#{1,4})\s+(.*)", line) for line in md_file.read_text(
                encoding="utf-8").splitlines())
            if m
        ]
        out[md_file.stem] = headings
    return out


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


class NormativeRetriever:
    """Thin retrieval wrapper used by every agent."""

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

    # -- exact fetch (pins) -------------------------------------------------

    def fetch_section(self, source: str, section: str) -> List[NormChunk]:
        """Every chunk of one named section of one source, by exact match."""
        try:
            res = self._collection.get(
                where={"$and": [{"source": {"$eq": source}}, {"section": {"$eq": section}}]},
                include=["documents", "metadatas"],
            )
        except Exception:
            return []
        out: List[NormChunk] = []
        for cid, doc, meta in zip(
            res.get("ids", []), res.get("documents", []), res.get("metadatas", [])
        ):
            out.append(_chunk(cid, doc, meta))
        return out

    # -- similarity ---------------------------------------------------------

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        sources: Optional[List[str]] = None,
        pins: Optional[Iterable[Tuple[str, str, str]]] = None,
    ) -> List[NormChunk]:
        """Pinned sections first, then the top-k most similar excerpts.

        ``pins`` is an iterable of ``(source, section, reason)``. Pinned chunks
        are always present; similarity results are appended, de-duplicated by
        chunk id. The result is what the agent sees and what the citation
        validator will accept.
        """
        chunks: List[NormChunk] = []
        seen: set = set()

        for source, section, reason in pins or []:
            for c in self.fetch_section(source, section):
                if c.chunk_id in seen:
                    continue
                c.pinned = True
                c.pin_reason = reason
                seen.add(c.chunk_id)
                chunks.append(c)

        where = {"source": {"$in": sources}} if sources else None
        try:
            res = self._collection.query(
                query_texts=[query or ""],
                n_results=top_k or config.RAG_TOP_K,
                where=where,
            )
        except Exception:
            return chunks

        ids = (res.get("ids") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        for cid, doc, meta in zip(ids, docs, metas):
            if cid in seen:
                continue
            seen.add(cid)
            chunks.append(_chunk(cid, doc, meta))
        return chunks

    # -- prompt rendering ---------------------------------------------------

    @staticmethod
    def format_context(chunks: List[NormChunk]) -> str:
        """Render retrieved chunks as a prompt context block.

        Ordered pinned-first, then by authority (legal first), so the
        precedence rule is visually reinforced in the prompt and the excerpts
        the decision procedure depends on are never buried.
        """
        rank = {"legal": 0, "standard": 1, "advisory": 2}
        ordered = sorted(
            chunks, key=lambda c: (0 if c.pinned else 1, rank.get(c.authority, 3), c.source)
        )
        blocks = []
        for i, c in enumerate(ordered, 1):
            marks = []
            if c.pinned:
                marks.append(f"REQUIRED: {c.pin_reason}" if c.pin_reason else "REQUIRED")
            if c.derived:
                marks.append("curated summary, not the official text")
            tail = f"  [{'; '.join(marks)}]" if marks else ""
            blocks.append(f"--- Excerpt {i} {c.citation()}{tail} ---\n{c.text.strip()}")
        return "\n\n".join(blocks) if blocks else "(no excerpts retrieved)"

    @staticmethod
    def citation_index(chunks: List[NormChunk]) -> List[str]:
        """The citation tags a validator will accept for this run."""
        seen, out = set(), []
        for c in chunks:
            tag = c.citation()
            if tag not in seen:
                seen.add(tag)
                out.append(tag)
        return out


def _chunk(cid: str, doc: str, meta: dict) -> NormChunk:
    meta = meta or {}
    source = str(meta.get("source", "unknown"))
    return NormChunk(
        text=doc or "",
        source=source,
        source_name=str(meta.get("source_name", config.SOURCE_NAMES.get(source, source))),
        authority=str(meta.get("authority", config.AUTHORITY_LEVELS.get(source, "advisory"))),
        section=str(meta.get("section", "Preamble")),
        chunk_id=str(cid),
    )
