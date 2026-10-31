"""Build data/indexes/search.sqlite + embeddings from the core DB (read-only). Idempotent and deterministic.

Usage: .venv/bin/python scripts/build_index.py [--force-embed]
"""
from __future__ import annotations

import hashlib
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import DB_PATH  # noqa: E402
from backend.retrieval import embeddings as emb  # noqa: E402
from backend.retrieval.bm25 import SEARCH_DB, write_index  # noqa: E402
from backend.retrieval.chunker import build_chunks  # noqa: E402


def build(force_embed: bool = False, log=print) -> dict:
    t0 = time.time()
    chunks, meta = build_chunks()
    t_chunk = time.time() - t0
    ids = [c["chunk_id"] for c in chunks]
    assert len(set(ids)) == len(ids)
    inputs = [c["embed_text"] for c in chunks]
    fp = hashlib.sha256("\n".join(f"{c['chunk_id']}\t{c['start_char']}\t{c['end_char']}" for c in chunks).encode()).hexdigest()
    t1 = time.time()
    vecs, einfo = emb.build_or_load(ids, inputs, force=force_embed, log=log)
    t_emb = time.time() - t1
    pages = set()
    for c in chunks:
        if c["pdf_page_start"] is not None and c["pdf_page_end"] is not None:
            pages.update((c["fr_docnum"], p) for p in range(c["pdf_page_start"], c["pdf_page_end"] + 1))
    info = dict(n_chunks=len(chunks), n_docs=len(meta), n_applicability_chunks=sum(c["is_applicability"] for c in chunks),
                chunk_fingerprint=fp, pdf_pages_covered=len(pages), kinds=dict(Counter(c["kind"] for c in chunks)),
                sources=dict(Counter(m["source"] for m in meta.values())), model=einfo["model"], model_revision=einfo["revision"],
                core_db=str(DB_PATH))
    t2 = time.time()
    write_index(SEARCH_DB, chunks, meta, info)
    info.update(t_chunk_s=round(t_chunk, 2), t_embed_s=round(t_emb, 2), t_write_s=round(time.time() - t2, 2),
                t_total_s=round(time.time() - t0, 2), embedded_this_run=einfo["n_embedded_this_run"])
    return info


if __name__ == "__main__":
    out = build(force_embed="--force-embed" in sys.argv)
    for k, v in out.items():
        print(f"{k}: {v}")
