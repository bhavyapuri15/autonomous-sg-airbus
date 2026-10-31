"""Shared helpers: read-only DB access, directive resolution, optional-module loading."""
from __future__ import annotations

import hashlib
import importlib
import json
import re
import sqlite3
import threading

from backend.api.schemas import CitationRef, DirectiveInfo, SourceTier
from backend.config import DB_PATH, FR_DOCS_DIR, FR_FINAL_RULES_DIR

_MODULES: dict[str, object] = {}
_ERRORS: dict[str, str] = {}
OPTIONAL = {
    "hybrid_search": "backend.retrieval.hybrid_search",
    "id_router": "backend.retrieval.id_router",
    "applicability": "backend.rules.applicability",
    "revisions": "backend.rules.revisions",
    "citations": "backend.verification.citations",
    "grounding": "backend.verification.grounding",
}


def module(name: str):
    """Return the optional module or None (never raises). Reason kept in module_errors()."""
    if name in _MODULES:
        return _MODULES[name]
    try:
        m = importlib.import_module(OPTIONAL[name])
    except Exception as e:  # missing module or import-time failure
        _ERRORS[name] = f"{type(e).__name__}: {e}"
        return None
    _MODULES[name] = m
    _ERRORS.pop(name, None)
    return m


def module_status() -> dict:
    out = {}
    for n in OPTIONAL:
        out[n] = {"loaded": module(n) is not None, "error": _ERRORS.get(n)}
    return out


def db() -> sqlite3.Connection:
    c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def has_table(conn, name: str) -> bool:
    return conn.execute("select 1 from sqlite_master where name=?", (name,)).fetchone() is not None


def pdf_path(docnum: str):
    for base in (FR_DOCS_DIR, FR_FINAL_RULES_DIR):
        p = base / docnum / "document.pdf"
        if p.is_file():
            return p
    return None


def citation_id(docnum, start, end) -> str:
    return hashlib.sha256(f"{docnum}|{start}|{end}".encode()).hexdigest()[:12]


# --- directive resolution ------------------------------------------------------------------
class Catalog:
    """In-memory view of documents+records for ID resolution (small: ~420 docs)."""

    def __init__(self):
        from backend.retrieval.chunker import load_doc_meta
        from backend.retrieval.id_router import IDRouter, load_record_map
        conn = db()
        try:
            self.meta = load_doc_meta(conn)
            self.recs = [dict(r) for r in conn.execute("select * from records")]
            self._ad = {}
            for r in self.recs:
                if r["ad_number"] and r["fr_docnum"]:
                    self._ad.setdefault(r["ad_number"], []).append(r["fr_docnum"])
        finally:
            conn.close()
        self.meta_only = [r for r in self.recs if not r["fr_docnum"]]
        known = sorted(self._ad)
        self.router = IDRouter(list(self.meta.values()), lambda ad: [(d, None) for d in self._ad.get(ad, [])], known,
                               record_ids=load_record_map())
        self.by_docket: dict[str, list[str]] = {}
        for dn, m in self.meta.items():
            for k in m["dockets"]:
                self.by_docket.setdefault(k, []).append(dn)

    def info(self, docnum: str) -> DirectiveInfo | None:
        m = self.meta.get(docnum)
        if not m:
            return None
        rows = [r for r in self.recs if r["fr_docnum"] == docnum]
        cit = next((r["citation"] for r in rows if r["citation"]), None) or (
            f"{m['volume']} FR {m['start_page']}" if m.get("volume") and m.get("start_page") else None)
        return DirectiveInfo(fr_docnum=docnum, docket=(m["dockets"][0] if m["dockets"] else None), doc_class=m["doc_class"],
                             title=m["title"], publication_date=m["publication_date"], citation=cit,
                             sheet_rows=[r["row"] for r in rows], pdf_url=m.get("pdf_url"))

    def meta_only_info(self, rec: dict) -> DirectiveInfo:
        return DirectiveInfo(fr_docnum=None, docket=rec["docket_norm"] or rec["docket_raw"], doc_class=None,
                             title=rec["subject"], publication_date=rec["publish_date"], citation=rec["citation"] or None,
                             sheet_rows=[rec["row"]])

    def group_for(self, docnum: str) -> list[str]:
        """Docnum plus other documents sharing a docket (date ordered)."""
        out = {docnum}
        for k in self.meta[docnum]["dockets"]:
            out.update(self.by_docket.get(k, []))
        return sorted(out, key=lambda d: (self.meta[d]["publication_date"] or "", d))


_CAT: Catalog | None = None
_LOCK = threading.Lock()


def catalog() -> Catalog:
    global _CAT
    with _LOCK:
        if _CAT is None:
            _CAT = Catalog()
        return _CAT


class Resolution:
    def __init__(self):
        self.docnums: list[str] = []      # exact documents (several = ambiguous AD-number mention etc.)
        self.meta_only: list[dict] = []   # sheet rows without FR text
        self.near_miss: list[DirectiveInfo] = []
        self.near_labels: list[str] = []
        self.detected: list[dict] = []


def resolve_ids(text: str, *, explicit: bool) -> Resolution:
    """Resolve identifiers in `text`. explicit=True: whole string is an id the user supplied."""
    cat = catalog()
    res = Resolution()
    r = cat.router.route(text)
    res.detected = r.detected
    seen = []
    for e in r.exact:
        if e["fr_docnum"] not in seen:
            seen.append(e["fr_docnum"])
    # docket given -> single directive (the docket group); keep the doc list as is
    res.docnums = seen
    # metadata-only sheet rows (no FR text) matched by their sheet docket id
    from backend.retrieval.chunker import canon_docket
    ctext = canon_docket(text)
    for rec in cat.meta_only:
        dn = canon_docket(rec["docket_norm"] or "")
        if dn and re.search(rf"(?<![A-Z0-9]){re.escape(dn)}(?![A-Z0-9])", ctext):
            res.meta_only.append(rec)
    for nm in r.near_miss:
        info = cat.info(nm["fr_docnum"]) if nm.get("fr_docnum") else None
        if info and all(i.fr_docnum != info.fr_docnum for i in res.near_miss):
            res.near_miss.append(info)
            res.near_labels.append(f"{nm['id_type']} '{nm['query_id']}' not found; closest different ID: {nm['suggestion']}")
    return res


def applicability_quote(docnum: str) -> CitationRef | None:
    """Verbatim applicability paragraph straight from the sections table (no generation)."""
    conn = db()
    try:
        row = conn.execute(
            "select s.*, d.pdf_url, d.xml_url from sections s join documents d using(fr_docnum) where s.fr_docnum=? and "
            "(lower(coalesce(s.heading,'')) like 'applicab%' or lower(s.section_path) like '%applicab%') "
            "order by s.seq limit 1", (docnum,)).fetchone()
    finally:
        conn.close()
    if not row or not row["text"]:
        return None
    return CitationRef(citation_id=citation_id(docnum, row["start_char"], row["end_char"]), fr_docnum=docnum,
                       section_path=row["section_path"], label=row["label"], fr_page=row["fr_page_start"],
                       pdf_page=row["pdf_page_start"], quote=row["text"], start=row["start_char"], end=row["end_char"],
                       source_tier=SourceTier.FR_FULL_TEXT, pdf_url=row["pdf_url"], xml_url=row["xml_url"])
