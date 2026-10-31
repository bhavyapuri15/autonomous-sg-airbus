"""Organiser citation format (31 Oct update): record_id + Federal Register citation and page + section.

`enrich(c)` fills record_ids / docket_number / federal_register_citation / section / source_url on a CitationRef from the
SQLite index. `enrich_model(obj)` walks any response model and enriches every CitationRef (and DirectiveInfo) in it,
so enrichment happens centrally at response assembly instead of ad hoc at every producer.

Rules: values already present on the CitationRef are never overwritten; nothing is invented (missing -> None / []).
Final-rule-lookup documents are not organiser records, so their record_ids stay empty. DB access is read-only and
defensive (the organiser tables may not exist yet). Lookups are cached per DB file version (mtime+size), so an atomic
rebuild invalidates the cache automatically.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from functools import lru_cache
from typing import Any

from pydantic import BaseModel

from backend import config
from backend.api.schemas import CitationRef, DirectiveInfo, RegulatoryStage

STAGE_BY_CLASS = {"NPRM": RegulatoryStage.PROPOSED_RULE, "SNPRM": RegulatoryStage.SUPPLEMENTAL_PROPOSAL,
                  "WITHDRAWAL": RegulatoryStage.WITHDRAWAL_NOTICE, "CORRECTION": RegulatoryStage.CORRECTION,
                  "FINAL_RULE": RegulatoryStage.FINAL_RULE}


def fr_permalink(fr_docnum: str) -> str:
    """federalregister.gov short permalink; used only when the DB has no html_url (final-rule lookup docs)."""
    return f"https://www.federalregister.gov/d/{fr_docnum}"


def stage_for(doc_class: str | None) -> RegulatoryStage:
    return STAGE_BY_CLASS.get(doc_class or "", RegulatoryStage.OTHER)


_LOCK = threading.Lock()
_STATE: dict[str, Any] = {"key": None, "docs": None, "rec_doc": {}, "rec_row": {}, "sec": {}}


def _has(conn, table: str) -> bool:
    return conn.execute("select 1 from sqlite_master where name=?", (table,)).fetchone() is not None


def _cols(conn, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"pragma table_info({table})")}


def record_ids_for(conn, fr_docnum: str | None = None, sheet_row: int | None = None) -> list[str]:
    """All organiser record_ids for an FR document (via organiser_index.fr_docnum and records.record_id) or a sheet row."""
    out: set[str] = set()
    try:
        if _has(conn, "organiser_index"):
            oc = _cols(conn, "organiser_index")
            if fr_docnum and "fr_docnum" in oc:
                out.update(r[0] for r in conn.execute("select record_id from organiser_index where fr_docnum=?", (fr_docnum,)))
            if sheet_row is not None and "sheet_row" in oc:
                out.update(r[0] for r in conn.execute("select record_id from organiser_index where sheet_row=?", (sheet_row,)))
        if _has(conn, "records") and "record_id" in _cols(conn, "records"):
            if fr_docnum:
                out.update(r[0] for r in conn.execute("select record_id from records where fr_docnum=?", (fr_docnum,)))
            if sheet_row is not None:
                out.update(r[0] for r in conn.execute("select record_id from records where row=?", (sheet_row,)))
    except sqlite3.Error:
        return []
    return sorted(x for x in out if x)


def _load(conn) -> dict[str, dict]:
    docs: dict[str, dict] = {}
    for r in conn.execute("select fr_docnum,volume,start_page,html_url,source,doc_class,docket_ids_json from documents"):
        try:
            dk = json.loads(r[6] or "[]")
        except ValueError:
            dk = []
        docs[r[0]] = dict(volume=r[1], start_page=r[2], html_url=r[3], source=r[4], doc_class=r[5],
                          docket=_norm_docket(dk[0]) if dk else None)
    return docs


def _norm_docket(d: str) -> str:
    d = (d or "").strip()
    return d[len("Docket No. "):].strip() if d.lower().startswith("docket no. ") else d


def _ro_default() -> sqlite3.Connection:
    return sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True, check_same_thread=False)


def _state():
    """Default-DB caches; reset when the DB file changes (atomic rebuild)."""
    try:
        st = os.stat(config.DB_PATH)
        key = (str(config.DB_PATH), st.st_mtime_ns, st.st_size)
    except OSError:
        return None
    with _LOCK:
        if _STATE["key"] != key:
            _STATE.update(key=key, docs=None, rec_doc={}, rec_row={}, sec={})
        return _STATE


def clear_cache() -> None:
    with _LOCK:
        _STATE.update(key=None)


def _doc(conn, dn: str, use_cache: bool) -> dict | None:
    if not use_cache:
        return _load(conn).get(dn)
    s = _state()
    if s is None:
        return None
    if s["docs"] is None:
        s["docs"] = _load(conn)
    return s["docs"].get(dn)


def _records(conn, dn, row, use_cache: bool) -> list[str]:
    if not use_cache:
        return record_ids_for(conn, dn, row)
    s = _state()
    cache, k = (s["rec_doc"], dn) if dn else (s["rec_row"], row)
    if k not in cache:
        cache[k] = record_ids_for(conn, dn, row)
    return cache[k]


def _section(conn, dn: str, start, end, use_cache: bool) -> str | None:
    """'(c) Applicability' from label + heading of the smallest section containing [start, end]."""
    if start is None or end is None:
        return None
    key = (dn, start, end)
    s = _state() if use_cache else None
    if s is not None and key in s["sec"]:
        return s["sec"][key]
    r = conn.execute("select label,heading,section_path from sections where fr_docnum=? and start_char<=? and end_char>=? "
                     "order by (end_char-start_char) limit 1", (dn, start, end)).fetchone()
    val = _section_str(*r) if r else None
    if s is not None:
        s["sec"][key] = val
    return val


def _section_str(label, heading, path) -> str | None:
    t = " ".join(x.strip() for x in (label, heading) if x and x.strip())
    if t:
        return t
    return path.rsplit("/", 1)[-1] if path else None


def enrich(c: CitationRef, conn=None) -> CitationRef:
    """Return a copy of `c` with the organiser citation fields filled (existing values are kept)."""
    use_cache = conn is None
    own = None
    if conn is None:
        try:
            own = conn = _ro_default()
        except sqlite3.Error:
            return c
    try:
        upd: dict[str, Any] = {}
        if c.fr_docnum:
            d = _doc(conn, c.fr_docnum, use_cache)
            if d is None:
                return c
            if not c.record_ids and d["source"] != "fr_final_rule_lookup":
                rid = _records(conn, c.fr_docnum, None, use_cache)
                if rid:
                    upd["record_ids"] = rid
            if not c.docket_number and d["docket"]:
                upd["docket_number"] = d["docket"]
            if not c.federal_register_citation:
                page = c.fr_page or d["start_page"]
                if d["volume"] and page:
                    upd["federal_register_citation"] = f"{d['volume']} FR {page}"
            if not c.section:
                sec = _section(conn, c.fr_docnum, c.start, c.end, use_cache)
                if sec is None and (c.label or c.section_path):
                    sec = _section_str(c.label, None, c.section_path)
                if sec:
                    upd["section"] = sec
            if not c.source_url:
                upd["source_url"] = d["html_url"] or fr_permalink(c.fr_docnum)
        elif c.sheet_row is not None and not c.record_ids:     # SHEET_* citation: only the record id is knowable
            rid = _records(conn, None, c.sheet_row, use_cache)
            if rid:
                upd["record_ids"] = rid
        return c.model_copy(update=upd) if upd else c
    except sqlite3.Error:
        return c
    finally:
        if own is not None:
            own.close()


def enrich_directive(d: DirectiveInfo, conn=None) -> DirectiveInfo:
    use_cache = conn is None
    own = None
    if conn is None:
        try:
            own = conn = _ro_default()
        except sqlite3.Error:
            return d
    try:
        upd: dict[str, Any] = {}
        doc = _doc(conn, d.fr_docnum, use_cache) if d.fr_docnum else None
        if d.fr_docnum:
            if not d.record_ids and doc and doc["source"] != "fr_final_rule_lookup":
                upd["record_ids"] = _records(conn, d.fr_docnum, None, use_cache)
            if not d.regulatory_stage and doc:
                upd["regulatory_stage"] = stage_for(doc["doc_class"]).value
            if not d.source_url and doc:
                upd["source_url"] = doc["html_url"] or fr_permalink(d.fr_docnum)
        elif d.sheet_rows and not d.record_ids:
            ids = sorted({r for row in d.sheet_rows for r in _records(conn, None, row, use_cache)})
            if ids:
                upd["record_ids"] = ids
        return d.model_copy(update=upd) if upd else d
    except sqlite3.Error:
        return d
    finally:
        if own is not None:
            own.close()


def enrich_model(obj: Any, conn=None) -> Any:
    """Recursively enrich every CitationRef / DirectiveInfo inside a pydantic model, list or dict (in place; returns obj)."""
    if isinstance(obj, CitationRef):
        return enrich(obj, conn)
    if isinstance(obj, DirectiveInfo):
        return enrich_directive(obj, conn)
    if isinstance(obj, BaseModel):
        for name in type(obj).model_fields:
            v = getattr(obj, name, None)
            if v is None or isinstance(v, (str, int, float, bool)):
                continue
            nv = enrich_model(v, conn)
            if nv is not v:
                setattr(obj, name, nv)
        return obj
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            nv = enrich_model(v, conn)
            if nv is not v:
                obj[i] = nv
        return obj
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            nv = enrich_model(v, conn)
            if nv is not v:
                obj[k] = nv
        return obj
    return obj
