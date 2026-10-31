"""Deterministic retrieval benchmark harness (no LLM). Writes data/processed/retrieval_benchmark.json."""
from __future__ import annotations

import json
import random
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import PROCESSED  # noqa: E402
from backend.retrieval import hybrid_search as hs  # noqa: E402


def generate_queries(ix, n_each: int = 10, seed: int = 7) -> list[dict]:
    rnd = random.Random(seed)
    docs = sorted(ix.docs.values(), key=lambda d: d["fr_docnum"])
    qs = []
    dk = [d for d in docs if d["dockets"]]
    for d in rnd.sample(dk, min(n_each, len(dk))):
        k = d["dockets"][0]
        qs.append(dict(kind="docket", query=k, expect=d["fr_docnum"]))
        qs.append(dict(kind="docket_lower_space", query=k.lower().replace("-", " ", 1), expect=d["fr_docnum"]))
    for d in rnd.sample(docs, n_each):
        qs.append(dict(kind="docnum", query=d["fr_docnum"], expect=d["fr_docnum"]))
        if d["volume"] and d["start_page"]:
            qs.append(dict(kind="fr_citation", query=f"{d['volume']} FR {d['start_page']}", expect=d["fr_docnum"]))
    md = [d for d in docs if d["models"]]
    for d in rnd.sample(md, min(n_each, len(md))):
        qs.append(dict(kind="model", query=f"{d['models'][0]} applicability", expect=d["fr_docnum"]))
    for d in rnd.sample(docs, n_each):
        words = [w for w in d["title"].replace("Airworthiness Directives;", "").split() if len(w) > 3][:6]
        qs.append(dict(kind="title", query=" ".join(words), expect=d["fr_docnum"]))
    return qs


def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(round(p * (len(v) - 1))))]


def run(top_k: int = 10) -> dict:
    hs.reset()
    t0 = time.perf_counter()
    ix = hs.get_index()
    qs = generate_queries(ix)
    lat = []
    hit1 = hit10 = 0
    per_kind: dict = {}
    for i, q in enumerate(qs):
        t = time.perf_counter()
        hits = hs.search(q["query"], top_k=top_k)
        ms = (time.perf_counter() - t) * 1000
        if i == 0:
            ms += (t - t0) * 1000  # cold: includes index load
        lat.append(ms)
        docs = [h["fr_docnum"] for h in hits]
        r1, r10 = bool(docs[:1] == [q["expect"]]), q["expect"] in docs
        hit1 += r1
        hit10 += r10
        pk = per_kind.setdefault(q["kind"], [0, 0, 0])
        pk[0] += 1; pk[1] += r1; pk[2] += r10
    warm = lat[1:]
    conn = sqlite3.connect(f"file:{hs.SEARCH_DB}?mode=ro", uri=True)
    out = dict(n_queries=len(qs), cold_ms=round(lat[0], 1),
               warm_ms=dict(p50=round(pct(warm, .5), 1), p95=round(pct(warm, .95), 1), max=round(max(warm), 1)),
               hit_at_1=f"{hit1}/{len(qs)}", hit_at_10=f"{hit10}/{len(qs)}",
               per_kind={k: dict(n=v[0], at1=v[1], at10=v[2]) for k, v in per_kind.items()},
               n_chunks=ix.n, pdf_pages_covered=ix.info.get("pdf_pages_covered"), n_docs=len(ix.docs), index_info=ix.info)
    conn.close()
    PROCESSED.mkdir(parents=True, exist_ok=True)
    (PROCESSED / "retrieval_benchmark.json").write_text(json.dumps(out, indent=1, default=str))
    return out


if __name__ == "__main__":
    r = run()
    print(json.dumps({k: v for k, v in r.items() if k != "index_info"}, indent=1))
