#!/usr/bin/env python3
"""
ingest.py — Build (or rebuild) the Chroma normative index.

Usage:
    python ingest.py

Reads every Markdown file in ``corpus/`` and indexes it into the persistent
Chroma collection used by the agents for retrieval-augmented generation.
Run this once after cloning the repo, and again whenever you edit or add
corpus documents (e.g. replacing a curated summary with a full legal text).

The corpus is extensible: drop any additional ``.md`` file into ``corpus/``.
If the filename is not one of the known sources (see raia/config.py), it is
indexed with authority level "advisory" by default; add an entry to
``AUTHORITY_LEVELS`` / ``SOURCE_NAMES`` for proper citation labels.
"""

from raia.rag import ingest_corpus

if __name__ == "__main__":
    print("Building the RAIA normative index (Chroma)...")
    print("Note: the first run downloads a small embedding model (~80 MB).")
    n = ingest_corpus(verbose=True)
    print(f"Done. {n} chunks indexed.")
