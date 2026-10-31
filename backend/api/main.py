"""FastAPI app: search, query, applicability check, directive/document browsing."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from backend.answer import llm as llm_mod
from backend.answer import pipeline
from backend.api import deps
from backend.api import schemas as S
from backend import citation_meta
from backend.config import ROOT

log = logging.getLogger("api")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="AD NPRM traceable search", version="0.1")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
                   allow_methods=["*"], allow_headers=["*"])


def _err(status: int, error: str, detail: str | None = None) -> JSONResponse:
    return JSONResponse(status_code=status, content=S.ErrorResponse(error=error, detail=detail).model_dump())


@app.middleware("http")
async def _log(request: Request, call_next):
    t = time.perf_counter()
    try:
        resp = await call_next(request)
    except Exception:
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        return _err(500, "internal_error", "Unexpected server error.")
    log.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, resp.status_code, (time.perf_counter() - t) * 1000)
    return resp


@app.exception_handler(RequestValidationError)
async def _validation(request: Request, exc: RequestValidationError):
    errs = [f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors()]
    return _err(422, "validation_error", "; ".join(errs)[:500])


@app.exception_handler(HTTPException)
async def _http(request: Request, exc: HTTPException):
    return _err(exc.status_code, "http_error", str(exc.detail))


# --------------------------------------------------------------------------------------------
@app.get("/health", response_model=S.HealthResponse)
def health():
    db = {}
    try:
        c = deps.db()
        try:
            for t in ("records", "documents", "doc_text", "sections", "pages", "relations"):
                if deps.has_table(c, t):
                    db[t] = c.execute(f"select count(*) from {t}").fetchone()[0]
            db["documents_by_source"] = {r[0]: r[1] for r in c.execute("select source,count(*) from documents group by 1")}
        finally:
            c.close()
        ok = "ok"
    except Exception as e:
        ok, db = "degraded", {"error": type(e).__name__}
    return S.HealthResponse(status=ok, db=db, modules=deps.module_status(), llm_configured=llm_mod.configured())


@app.post("/query", response_model=S.QueryResponse)
def query(req: S.QueryRequest):
    log.info("query use_llm=%s directive_id=%s qlen=%d", req.use_llm, req.directive_id, len(req.question))
    return citation_meta.enrich_model(pipeline.answer(req))   # idempotent; pipeline._finish already enriches


@app.post("/search", response_model=S.SearchResponse)
def search(req: S.SearchRequest):
    hs = deps.module("hybrid_search")
    if hs is None:
        return _err(503, "retrieval_unavailable", "Retrieval module or index is not available.")
    t = time.perf_counter()
    try:
        out = hs.search_ex(req.query, top_k=req.top_k, filters=req.filters or None)
        hits = [hs.to_search_hit(h) for h in out["hits"]]
    except Exception as e:
        log.exception("search failed")
        return _err(503, "retrieval_unavailable", f"{type(e).__name__}")
    for h in hits:
        h.citation = citation_meta.enrich(h.citation)
    return S.SearchResponse(hits=hits, timings_ms=S.Timings(retrieval=round((time.perf_counter() - t) * 1000, 2),
                                                          total=round((time.perf_counter() - t) * 1000, 2)))


@app.post("/applicability/check", response_model=S.ApplicabilityCheckResponse)
def applicability_check(req: S.ApplicabilityCheckRequest):
    res = deps.resolve_ids(req.directive_id, explicit=True)
    cat = deps.catalog()
    if not res.docnums:
        return _err(404, "directive_not_found", "Not in indexed dataset." + (
            " Closest different IDs: " + ", ".join(i.fr_docnum for i in res.near_miss) if res.near_miss else ""))
    if len(res.docnums) > 1:
        return _err(409, "directive_ambiguous", "Several documents match: " + ", ".join(res.docnums[:10]))
    docnum = res.docnums[0]
    warnings: list[str] = []
    if deps.module("applicability") is None:
        return _err(503, "applicability_unavailable", "Applicability engine not available.")
    qreq = S.QueryRequest(question="applicability", directive_id=docnum, aircraft=req.aircraft, use_llm=False)
    app_res, rev = pipeline._run_engines(docnum, qreq, warnings)
    fapp, fdoc = pipeline.evaluate_final_rule(docnum, qreq, rev, app_res, warnings)
    resp = S.ApplicabilityCheckResponse(directive=cat.info(docnum), applicability=app_res, revision=rev, warnings=warnings,
                                        final_rule_applicability=fapp, final_rule_docnum=fdoc)
    citation_meta.enrich_model(resp)
    for w in pipeline.stage_warnings(resp):    # same stage warning as /query
        if w not in resp.warnings:
            resp.warnings.append(w)
    return resp


# --------------------------------------------------------------------------------------------
@app.get("/directives", response_model=S.DirectiveListResponse)
def list_directives(q: str = Query("", max_length=200), make: str = Query("", max_length=100),
                    doc_class: str = Query("", max_length=30), source: str = Query("", max_length=40),
                    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    cat = deps.catalog()
    ql, ml = q.strip().lower(), make.strip().lower()
    items = []
    by_doc: dict[str, list[dict]] = {}
    for r in cat.recs:
        if r["fr_docnum"]:
            by_doc.setdefault(r["fr_docnum"], []).append(r)
    for dn, m in cat.meta.items():
        if doc_class and (m["doc_class"] or "").lower() != doc_class.lower():
            continue
        if source and m["source"] != source:
            continue
        if ml and not any(ml in x.lower() for x in m["make_norm"]):
            continue
        rows = by_doc.get(dn, [])
        rids = sorted(r["record_id"] for r in rows if r.get("record_id"))
        hay = " ".join([dn, m["title"] or "", " ".join(m["dockets"]), " ".join(m["models"]), " ".join(m["ad_numbers"]), " ".join(rids)]).lower()
        if ql and ql not in hay:
            continue
        items.append(S.DirectiveListItem(fr_docnum=dn, docket=(m["dockets"][0] if m["dockets"] else None), doc_class=m["doc_class"],
                                         title=m["title"], publication_date=m["publication_date"], source=m["source"],
                                         make=m["make_norm"], models=m["models"], ad_number=(m["ad_numbers"] or [None])[0],
                                         sheet_rows=[r["row"] for r in rows], record_ids=rids))
    items.sort(key=lambda i: (i.publication_date or "", i.fr_docnum or ""), reverse=True)
    if not source or source == "organiser_sheet":
        import json as _j
        for r in cat.meta_only:
            if doc_class or (ml and ml not in (r["make_norm"] or "").lower()):
                continue
            if ql and ql not in " ".join([r["docket_norm"] or "", r["subject"] or "", r["make_raw"] or "", r.get("record_id") or ""]).lower():
                continue
            items.append(S.DirectiveListItem(fr_docnum=None, docket=r["docket_norm"], title=r["subject"],
                                             publication_date=r["publish_date"], source="organiser_sheet",
                                             make=[r["make_norm"]] if r["make_norm"] else [], models=_j.loads(r["models_json"] or "[]"),
                                             sheet_rows=[r["row"]], record_ids=[r["record_id"]] if r.get("record_id") else []))
    return S.DirectiveListResponse(total=len(items), limit=limit, offset=offset, items=items[offset:offset + limit])


def _doc_meta(c, dn: str) -> S.DocumentMeta | None:
    d = c.execute("select * from documents where fr_docnum=?", (dn,)).fetchone()
    if not d:
        return None
    cat = deps.catalog()
    pages = c.execute("select count(*) from pages where fr_docnum=?", (dn,)).fetchone()[0]
    return S.DocumentMeta(fr_docnum=dn, title=d["title"], fr_type=d["fr_type"], doc_class=d["doc_class"],
                          publication_date=d["publication_date"], volume=d["volume"], start_page=d["start_page"],
                          end_page=d["end_page"], dockets=cat.meta.get(dn, {}).get("dockets", []), pdf_url=d["pdf_url"],
                          xml_url=d["xml_url"], html_url=d["html_url"], source=d["source"],
                          extraction_status=d["extraction_status"], pdf_cached=deps.pdf_path(dn) is not None, page_count=pages)


def _sheet_row(r: dict) -> S.SheetRow:
    return S.SheetRow(row=r["row"], docket=r["docket_norm"], fr_docnum=r["fr_docnum"] or None, subject=r["subject"],
                      status_raw=r["status_raw"], publish_date=r["publish_date"], make=r["make_norm"] or r["make_raw"],
                      models=json.loads(r["models_json"] or "[]"), ad_number=r["ad_number"] or None,
                      citation=r["citation"] or None, summary=r["summary"])


@app.get("/directives/{directive_id}", response_model=S.DirectiveDetail)
def directive_detail(directive_id: str):
    if len(directive_id) > 100:
        raise HTTPException(422, "id too long")
    cat = deps.catalog()
    res = deps.resolve_ids(directive_id, explicit=True)
    if not res.docnums and not res.meta_only:
        return JSONResponse(status_code=404, content=S.ErrorResponse(
            error="directive_not_found", detail="Not in indexed dataset." + (
                " Closest different IDs: " + ", ".join(i.fr_docnum for i in res.near_miss) if res.near_miss else "")).model_dump())
    docnums = list(res.docnums)
    if len(docnums) == 1:
        docnums = cat.group_for(docnums[0]) if directive_id.upper() != docnums[0].upper() else docnums
    c = deps.db()
    try:
        docs = [m for m in (_doc_meta(c, d) for d in docnums) if m]
        rows = [r for r in cat.recs if (r["fr_docnum"] in docnums) or r in res.meta_only]
        relations = []
        if deps.has_table(c, "relations"):
            q = ",".join("?" * len(docnums))
            relations = [dict(r) for r in c.execute(f"select * from relations where src in ({q}) or dst in ({q})", docnums * 2)]
            for r in relations:   # evidence is stored as JSON text; return it parsed
                for k, v in list(r.items()):
                    if isinstance(v, str) and v[:1] in "[{" and k.endswith(("evidence", "json")):
                        try:
                            r[k] = json.loads(v)
                        except ValueError:
                            pass
    finally:
        c.close()
    warnings: list[str] = []
    revision = None
    primary = res.docnums[0] if res.docnums else None
    rm = deps.module("revisions")
    if primary and rm is not None:
        try:
            revision = rm.revision_status(primary)
        except Exception as e:
            warnings.append(f"Revision engine failed ({type(e).__name__}).")
    elif primary:
        warnings.append("Revision engine unavailable.")
    c = deps.db()
    try:
        for m in docs:
            m.record_ids = citation_meta.record_ids_for(c, m.fr_docnum) if m.source != "fr_final_rule_lookup" else []
        sheet = [_sheet_row(r) for r in rows]
        for sr in sheet:
            ids = citation_meta.record_ids_for(c, None, sr.row)
            sr.record_id = ids[0] if ids else None
    finally:
        c.close()
    rids = sorted({i for m in docs for i in m.record_ids} | {sr.record_id for sr in sheet if sr.record_id})
    detail = S.DirectiveDetail(query_id=directive_id, documents=docs, sheet_rows=sheet, revision=revision,
                               relations=relations, applicability_text=deps.applicability_quote(primary) if primary else None,
                               warnings=warnings, candidates=[], record_ids=rids)
    return citation_meta.enrich_model(detail)


def _valid_doc(docnum: str) -> bool:
    c = deps.db()
    try:
        return c.execute("select 1 from documents where fr_docnum=?", (docnum,)).fetchone() is not None
    finally:
        c.close()


@app.get("/documents/{docnum}", response_model=S.DocumentMeta)
def document_meta(docnum: str):
    c = deps.db()
    try:
        m = _doc_meta(c, docnum)
    finally:
        c.close()
    if m is None:
        raise HTTPException(404, "Document not in indexed dataset.")
    return m


@app.get("/documents/{docnum}/pdf")
def document_pdf(docnum: str):
    if not _valid_doc(docnum):          # DB membership check = path-traversal guard
        raise HTTPException(404, "Document not in indexed dataset.")
    p = deps.pdf_path(docnum)
    if p is None:
        raise HTTPException(404, "PDF not cached locally; use the pdf_url in document metadata.")
    return FileResponse(p, media_type="application/pdf", filename=f"{docnum}.pdf")


@app.get("/documents/{docnum}/pages/{pdf_page}", response_model=S.PageResponse)
def document_page(docnum: str, pdf_page: int):
    c = deps.db()
    try:
        r = c.execute("select * from pages where fr_docnum=? and pdf_page=?", (docnum, pdf_page)).fetchone()
    finally:
        c.close()
    if r is None:
        raise HTTPException(404, "Page not found.")
    return S.PageResponse(fr_docnum=docnum, pdf_page=pdf_page, fr_page=r["fr_page"], text=r["text"] or "",
                          is_image_only=bool(r["is_image_only"]))


@app.get("/evaluation/summary")
def evaluation_summary():
    files = sorted((ROOT / "evaluation" / "results").glob("*.json"), key=lambda p: p.stat().st_mtime) \
        if (ROOT / "evaluation" / "results").is_dir() else []
    if not files:
        return {}
    try:
        return json.loads(Path(files[-1]).read_text())
    except ValueError:
        return _err(500, "evaluation_results_unreadable", files[-1].name)
