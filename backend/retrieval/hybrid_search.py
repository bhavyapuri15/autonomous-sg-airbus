"""Hybrid retrieval: exact-ID router (pinned first) + BM25 (FTS5) + dense (bge-small, numpy) fused by RRF."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading

import numpy as np

from backend.api.schemas import CitationRef, SearchHit, SourceTier
from backend.config import INDEXES
from backend.retrieval import embeddings as emb
from backend.retrieval.bm25 import SEARCH_DB, bm25_search
from backend.retrieval.chunker import canon_docket, extract_dockets
from backend.retrieval.id_router import IDRouter

RRF_K = 60
TOP_N = 50
PIN_BONUS = 1.0  # pinned (exact-ID) hits: score = bonus + rrf, so they always sort first

_INDEX = None
_LOCK = threading.RLock()


def _norm_tok(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", s.upper())


class Index:
    def __init__(self, path=SEARCH_DB):
        self.conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.rows = [dict(r) for r in self.conn.execute("select * from chunks order by idx")]
        for r in self.rows:
            r["dockets"] = json.loads(r.pop("dockets_json"))
            r["make"] = json.loads(r.pop("make_json"))
            r["models"] = json.loads(r.pop("models_json"))
            r["_models_n"] = {_norm_tok(m) for m in r["models"]}
            r["_make_l"] = [m.casefold() for m in r["make"]]
        self.n = len(self.rows)
        self.docs = {}
        for d in self.conn.execute("select * from docs"):
            d = dict(d)
            d["dockets"] = json.loads(d.pop("dockets_json"))
            d["models"] = json.loads(d.pop("models_json"))
            d["make"] = json.loads(d.pop("make_json"))
            self.docs[d["fr_docnum"]] = d
        self.info = {r["k"]: json.loads(r["v"]) for r in self.conn.execute("select * from info")}
        self.by_doc: dict[str, list[int]] = {}
        for r in self.rows:
            self.by_doc.setdefault(r["fr_docnum"], []).append(r["idx"])
        self.vecs, meta = emb.load_cache()
        if self.vecs is None or meta["chunk_ids"] != [r["chunk_id"] for r in self.rows]:
            raise RuntimeError("embeddings cache missing/out of sync with search.sqlite; run scripts/build_index.py")
        known = [r[0] for r in self.conn.execute("select distinct ad_number from ad_mentions")]
        self.router = IDRouter(list(self.docs.values()), self._ad_lookup, known)
        self.dates = np.array([r["publication_date"] or "" for r in self.rows])

    def docs_models(self, dn):
        return set(self.rows[self.by_doc[dn][0]]["models"])

    def _ad_lookup(self, ad):
        return [(self.rows[r[0]]["fr_docnum"], r[0]) for r in
                self.conn.execute("select chunk_idx from ad_mentions where ad_number=? order by chunk_idx", (ad,))]

    def mask(self, f: dict | None):
        if not f:
            return None
        f = {k: v for k, v in f.items() if v not in (None, "")}
        if not f:
            return None
        m = np.ones(self.n, bool)
        mk = f.get("make"); mod = _norm_tok(f["model"]) if f.get("model") else None
        dc = f["doc_class"].casefold() if f.get("doc_class") else None
        src = f.get("source")
        dk = None
        if f.get("docket"):
            dk = set(extract_dockets(f["docket"])) | {canon_docket(f["docket"])}
            dk |= {re.sub(r"-AD$", "", x) for x in dk}
        for i, r in enumerate(self.rows):
            ok = True
            if mk and not any(mk.casefold() == x or mk.casefold() in x for x in r["_make_l"]):
                ok = False
            elif mod and mod not in r["_models_n"]:
                ok = False
            elif dc and (r["doc_class"] or "").casefold() != dc:
                ok = False
            elif src and r["source"] != src:
                ok = False
            elif dk and not (dk & {x for d in r["dockets"] for x in (d, re.sub(r"-AD$", "", d))}):
                ok = False
            elif f.get("date_from") and (r["publication_date"] or "") < f["date_from"]:
                ok = False
            elif f.get("date_to") and (r["publication_date"] or "") > f["date_to"]:
                ok = False
            m[i] = ok
        return m


def get_index(reload: bool = False) -> Index:
    global _INDEX
    with _LOCK:
        if _INDEX is None or reload:
            _INDEX = Index()
        return _INDEX


def reset():
    global _INDEX
    with _LOCK:
        _INDEX = None


def citation_id(fr_docnum, start, end) -> str:
    return hashlib.sha256(f"{fr_docnum}|{start}|{end}".encode()).hexdigest()[:12]


def _hit(ix: Index, idx: int, score: float, **kw) -> dict:
    r = ix.rows[idx]
    d = ix.docs.get(r["fr_docnum"], {})
    cid = citation_id(r["fr_docnum"], r["start_char"], r["end_char"])
    h = dict(
        chunk_id=r["chunk_id"], fr_docnum=r["fr_docnum"], docket=(r["dockets"][0] if r["dockets"] else None),
        dockets=r["dockets"], title=r["title"], doc_class=r["doc_class"], source=r["source"],
        section_path=r["section_path"], label=r["label"], heading=r["heading"], text=r["text"],
        start=r["start_char"], end=r["end_char"], fr_page=r["fr_page_start"], pdf_page=r["pdf_page_start"],
        fr_page_end=r["fr_page_end"], pdf_page_end=r["pdf_page_end"], publication_date=r["publication_date"],
        is_applicability=bool(r["is_applicability"]), citation_id=cid, pdf_url=d.get("pdf_url"), xml_url=d.get("xml_url"),
        score=score, bm25_rank=None, bm25_score=None, dense_rank=None, dense_cosine=None,
        match_sources=[], exact_label=None, _idx=idx,
    )
    h.update(kw)
    return h


def to_search_hit(h: dict) -> SearchHit:
    cit = CitationRef(citation_id=h["citation_id"], fr_docnum=h["fr_docnum"], section_path=h["section_path"],
                      label=h["label"], fr_page=h["fr_page"], pdf_page=h["pdf_page"], quote=h["text"],
                      start=h["start"], end=h["end"], source_tier=SourceTier.FR_FULL_TEXT,
                      pdf_url=h["pdf_url"], xml_url=h["xml_url"])
    return SearchHit(chunk_id=h["chunk_id"], fr_docnum=h["fr_docnum"], docket=h["docket"], title=h["title"],
                     doc_class=h["doc_class"], section_path=h["section_path"], text=h["text"], score=h["score"],
                     match_sources=h["match_sources"], citation=cit)


def search_ex(query: str, top_k: int = 10, filters: dict | None = None, doc_level: bool = False) -> dict:
    """Returns {hits, near_miss, detected_ids}. Near-miss suggestions are never merged into hits."""
    ix = get_index()
    with _LOCK:
        route = ix.router.route(query)
        mask = ix.mask(filters)
        allowed = None
        if mask is not None:
            ix.conn.execute("create temp table if not exists allowed(id integer primary key)")
            ix.conn.execute("delete from allowed")
            ix.conn.executemany("insert into allowed values(?)", [(int(i),) for i in np.nonzero(mask)[0]])
            allowed = True
        bm = bm25_search(ix.conn, query, TOP_N, allowed_temp=bool(allowed)) if (mask is None or mask.any()) else []
        qv = emb.embed_query(query)
        cos = ix.vecs @ qv
        cand = cos if mask is None else np.where(mask, cos, -np.inf)
        k = min(TOP_N, int(np.isfinite(cand).sum()))
        top = np.argsort(-cand, kind="stable")[:k] if k else np.array([], int)
    bm_rank = {i: (r + 1, s) for r, (i, s) in enumerate(bm)}
    de_rank = {int(i): r + 1 for r, i in enumerate(top)}
    fused: dict[int, float] = {}
    for i, (r, _) in bm_rank.items():
        fused[i] = fused.get(i, 0) + 1 / (RRF_K + r)
    for i, r in de_rank.items():
        fused[i] = fused.get(i, 0) + 1 / (RRF_K + r)
    order = sorted(fused, key=lambda i: (-fused[i], i))

    def mk(i, score, extra_src=()):
        src = list(extra_src)
        if i in bm_rank:
            src.append("bm25")
        if i in de_rank:
            src.append("dense")
        return _hit(ix, i, score, bm25_rank=bm_rank.get(i, (None, None))[0], bm25_score=bm_rank.get(i, (None, None))[1],
                    dense_rank=de_rank.get(i), dense_cosine=float(cos[i]), match_sources=src)

    hits: list[dict] = []
    seen_chunks: set[int] = set()
    pinned_docs: set[str] = set()
    for e in route.exact:
        dn = e["fr_docnum"]
        if dn in pinned_docs:
            continue
        idxs = ix.by_doc.get(dn, [])
        if mask is not None:
            idxs = [i for i in idxs if mask[i]]
        if not idxs:
            continue
        if e["chunk_idx"] is not None and e["chunk_idx"] in idxs:
            pick = e["chunk_idx"]
        else:
            in_doc = [i for i in order if i in set(idxs)] if route.remaining else []
            if in_doc:
                pick = in_doc[0]
            else:
                summ = [i for i in idxs if ix.rows[i]["section_path"] == "preamble/SUMMARY"]
                pick = (summ or idxs)[0]
        pinned_docs.add(dn)
        seen_chunks.add(pick)
        h = mk(pick, PIN_BONUS + fused.get(pick, 0.0), ["exact_id"])
        h["exact_label"] = e["label"]
        hits.append(h)
    seen_docs = set(pinned_docs)
    for i in order:
        if i in seen_chunks:
            continue
        dn = ix.rows[i]["fr_docnum"]
        if doc_level and dn in seen_docs:
            continue
        seen_docs.add(dn)
        seen_chunks.add(i)
        hits.append(mk(i, fused[i]))
    hits = hits[:top_k]
    for h in hits:
        h.pop("_idx", None)
    return dict(hits=hits, near_miss=route.near_miss, detected_ids=route.detected)


def search(query: str, top_k: int = 10, filters: dict | None = None, doc_level: bool = False) -> list[dict]:
    return search_ex(query, top_k, filters, doc_level)["hits"]
