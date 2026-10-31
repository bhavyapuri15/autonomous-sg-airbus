"""Answer pipeline (verification_spec section 2). The LLM is never trusted: every claim goes through verify_answer."""
from __future__ import annotations

import dataclasses
import logging
import re
import time

from backend import config
from backend.answer import abstention as ab
from backend.answer import llm as llm_mod
from backend.answer.query_parse import ParsedQuery, parse
from backend.api import deps
from backend.api.schemas import (AnswerStatus, ApplicabilityResult, ApplicabilityValue, CitationRef, Claim,
                                 DirectiveInfo, QueryRequest, QueryResponse, RevisionResult, RevisionStatus,
                                 Timings, VerificationInfo)

log = logging.getLogger("answer")

_STOP = set("""a an and are as at be been by can do does for from has have how if in into is it its may of on or that the
their there this to was were what when where which who will with would should shall must any all not no than then these those
you your i we our us about per also such other another more most each both either neither whether""".split())
_ENGINE_TOPIC = re.compile(r"applicab|supersed|withdr[ae]w|final rule|finaliz|revis|amend", re.I)


# ---------------------------------------------------------------------------------------------
def _make(cls, **kw):
    """Build a verification dataclass from whichever of these fields it declares."""
    names = {f.name for f in dataclasses.fields(cls)}
    return cls(**{k: v for k, v in kw.items() if k in names})


def _evidence_chunk(cit, hit: dict):
    sp = None
    if hit.get("start") is not None and hit.get("end") is not None:
        sp = [(hit["start"], hit["end"], hit.get("fr_page"), hit.get("pdf_page"))]
    return _make(cit.EvidenceChunk, chunk_id=hit["chunk_id"], fr_docnum=hit["fr_docnum"], text=hit["text"],
                 start_char=hit.get("start") or 0, section_path=hit.get("section_path"), label=hit.get("label"),
                 fr_page_start=hit.get("fr_page"), pdf_page_start=hit.get("pdf_page"), page_spans=sp,
                 pdf_url=hit.get("pdf_url"), xml_url=hit.get("xml_url"), source_tier="FR_FULL_TEXT")


def _draft(cit, text, chunk_id, quote):
    return _make(cit.DraftClaim, text=text, chunk_id=chunk_id, quote=quote, quotes=[(chunk_id, quote)])


def _words(s: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9'/-]*", s)


def _content(s: str) -> set[str]:
    return {w.lower().rstrip("s") for w in _words(s) if w.lower() not in _STOP and len(w) > 2}


_IDF: dict | None = None


def _corpus_idf() -> tuple[dict, float]:
    """Document-frequency of content lemmas over all section texts in ad.sqlite (computed once, cached)."""
    global _IDF
    if _IDF is None:
        import math
        df: dict[str, int] = {}
        conn = deps.db()
        try:
            n = 0
            for (t,) in conn.execute("select text from sections"):
                n += 1
                for w in _content(t or ""):
                    df[w] = df.get(w, 0) + 1
        finally:
            conn.close()
        _IDF = ({w: math.log((n + 1) / (c + 1)) + 1.0 for w, c in df.items()}, math.log(n + 1) + 1.0)
    return _IDF


# question type -> regex over the hit's section path/heading that earns a bonus
_SECTION_BONUS = [
    (re.compile(r"unsafe condition|could happen|what caused|prompted|what (?:wiring |)problem|result in", re.I),
     re.compile(r"unsafe condition|\(e\)|background|summary", re.I)),
    (re.compile(r"compliance|within|how long|how many (?:flight )?(?:hours|cycles|months|days)|when must|before the", re.I),
     re.compile(r"compliance|required actions|\(g\)|\(h\)|proposed ad requirements", re.I)),
    (re.compile(r"part number|p/n|which .{0,30}part", re.I), re.compile(r"parts installation|required actions|\(g\)|\(h\)", re.I)),
    (re.compile(r"affected|which models|which serial|serial number|subject to|applies?\b", re.I),
     re.compile(r"applicab|\(c\)", re.I)),
    (re.compile(r"why .{0,30}(?:withdrawn|pulled|dropped|withdraw)|withdr[ae]w", re.I),
     re.compile(r"discussion|determination|withdraw|summary", re.I)),
]
_SECTION_BONUS_W = 0.35   # fraction of the sentence's own IDF mass added when the section matches


def extractive_claims(question: str, hits: list[dict], max_claims: int = config.EXTRACTIVE_MAX_CLAIMS):
    """Top sentences by IDF-weighted overlap with the question + a section-type bonus.
    Returns [(sentence, chunk_id)]; sentences are exact substrings of their chunk."""
    qset = _content(question)
    idf, default = _corpus_idf()
    bonus_rx = [b for q, b in _SECTION_BONUS if q.search(question)]
    scored = []
    for rank, h in enumerate(hits):
        where = " ".join(str(h.get(k) or "") for k in ("section_path", "heading", "label"))
        sec = bool(bonus_rx) and any(b.search(where) for b in bonus_rx)
        for sent in re.split(r"(?<=[.;])\s+|\n\s*\n", h["text"]):
            sent = " ".join(sent.split()) if "\n" in sent else sent.strip()
            if sent not in h["text"]:           # keep exact-substring property (whitespace-collapse breaks it)
                continue
            n = len(_words(sent))
            table = " | " in sent
            if (n < 6 and not table) or n > 80 or _ENGINE_TOPIC.search(sent):
                continue
            common = qset & _content(sent)
            if len(common) < 2:
                continue
            score = sum(idf.get(w, default) for w in common)
            if sec:
                score *= 1 + _SECTION_BONUS_W
            scored.append((score, -rank, sent, h["chunk_id"]))
    scored.sort(key=lambda t: (-t[0], -t[1]))
    out, seen = [], set()
    for sc, _, sent, cid in scored:
        if sent in seen:
            continue
        seen.add(sent)
        out.append((sent, cid))
        if len(out) >= max_claims:
            break
    return out


# ---------------------------------------------------------------------------------------------
def _search(question: str, group: list[str] | None, docket: str | None, top_k: int):
    hs = deps.module("hybrid_search")
    if hs is None:
        raise RuntimeError("retrieval module unavailable")
    if group:
        filters = {"docket": docket} if docket else None
        hits = hs.search(question, top_k=top_k if filters else 40, filters=filters)
        hits = [h for h in hits if h["fr_docnum"] in group]
        return hits[:top_k]
    return hs.search(question, top_k=top_k)


def _below_threshold(hits: list[dict]) -> bool:
    """Gate on the best dense cosine (BM25 is OR-based and matches stop words, so it is not a usable gate).
    Exact-ID pinned hits always pass. Threshold: config.MIN_TOP_DENSE_COSINE (TO BE CALIBRATED ON DEV SPLIT)."""
    if not hits:
        return True
    if any("exact_id" in (h.get("match_sources") or []) for h in hits[:1]):
        return False
    best = max((h.get("dense_cosine") for h in hits if h.get("dense_cosine") is not None), default=None)
    return best is None or best < config.MIN_TOP_DENSE_COSINE


def _run_engines(docnum: str, req: QueryRequest, warnings: list[str]):
    """Returns (applicability, revision). Engines that are unavailable yield honest NOT_EVALUATED / None + a warning."""
    rev_m, app_m = deps.module("revisions"), deps.module("applicability")
    revision, overlay = None, []
    if rev_m is not None:
        try:
            revision = rev_m.revision_status(docnum)
            overlay = list(rev_m.revision_overlay(docnum) or [])
        except Exception as e:
            log.exception("revision engine failed")
            warnings.append(f"Revision engine failed ({type(e).__name__}); revision status not reported.")
    else:
        warnings.append("Revision engine unavailable; revision status not reported.")
    app = ApplicabilityResult()
    ac = req.aircraft
    if app_m is None:
        warnings.append("Applicability engine unavailable; applicability not evaluated.")
    elif ac and (ac.model or ac.serial or ac.facts):
        try:
            app = app_m.evaluate_document(docnum, ac, overlay)
        except Exception as e:
            log.exception("applicability engine failed")
            warnings.append(f"Applicability engine failed ({type(e).__name__}); not evaluated.")
    if app.applicability_text is None:
        app.applicability_text = deps.applicability_quote(docnum)
    if revision is not None and revision.status == RevisionStatus.WITHDRAWN:
        warnings.extend(o for o in overlay if o not in warnings)
    return app, revision


def _dedupe(cits: list[CitationRef]) -> list[CitationRef]:
    seen, out = set(), []
    for c in cits:
        if c and c.citation_id not in seen:
            seen.add(c.citation_id)
            out.append(c)
    return out


WARN_PROPOSAL = "This is a proposed rule (NPRM), not an enforceable AD; current enforceability not verified."
WARN_WITHDRAWN = ("This is a withdrawn proposed rule (NPRM) or a withdrawal notice, not an enforceable AD; "
                  "the proposal was withdrawn and imposes no requirement.")
_PROPOSAL_STAGES = ("PROPOSED_RULE", "SUPPLEMENTAL_PROPOSAL")


def stage_warnings(resp: QueryResponse) -> list[str]:
    """Regulatory-stage warning for answers about a proposal-stage or withdrawn directive (organiser update)."""
    rev, d = resp.revision, resp.directive
    stage = (rev.regulatory_stage.value if rev else None) or (d.regulatory_stage if d else None)
    if rev is not None:
        if rev.enforceability.value == "PROPOSAL_WITHDRAWN" or rev.regulatory_stage.value == "WITHDRAWAL_NOTICE":
            return [WARN_WITHDRAWN]
        if rev.regulatory_stage.value in _PROPOSAL_STAGES and rev.enforceability.value == "NOT_VERIFIED":
            return [WARN_PROPOSAL]
        return []
    if d is not None and stage in _PROPOSAL_STAGES:
        return [WARN_PROPOSAL]
    if d is not None and stage == "WITHDRAWAL_NOTICE":
        return [WARN_WITHDRAWN]
    return []


def _finish(resp: QueryResponse, t0: float, timings: dict) -> QueryResponse:
    """Single response-assembly point: every CitationRef / DirectiveInfo leaving the pipeline is enriched here
    (record_ids, docket, FR citation, section, source_url) and the regulatory-stage warning is added."""
    from backend import citation_meta
    citation_meta.enrich_model(resp)
    resp.citations = _dedupe(resp.citations)
    for w in stage_warnings(resp):
        if w not in resp.warnings:
            resp.warnings.append(w)
    timings["total"] = (time.perf_counter() - t0) * 1000
    resp.timings_ms = Timings(**{k: round(v, 2) for k, v in timings.items()})
    return resp


# ---------------------------------------------------------------------------------------------
def answer(req: QueryRequest) -> QueryResponse:
    t0 = time.perf_counter()
    tm = dict(retrieval=0.0, engines=0.0, generation=0.0, verification=0.0)
    pq: ParsedQuery = parse(req)
    cat = deps.catalog()
    warnings: list[str] = []

    # --- 2. abstention pre-checks (spec section 5 order) --------------------------------------
    if pq.injection or (deps.module("citations") and _safe_inj(deps.module("citations"), req.question)):
        return _finish(ab.abstain(ab.OUT_OF_SCOPE_INSTRUCTION), t0, tm)

    res = None
    if req.directive_id:
        res = deps.resolve_ids(req.directive_id, explicit=True)
        if not (res.docnums or res.meta_only):
            return _finish(ab.abstain(ab.DIRECTIVE_NOT_FOUND, candidates=res.near_miss, warnings=res.near_labels), t0, tm)
    q_res = deps.resolve_ids(req.question, explicit=False)
    if res is None:
        res = q_res
        unknown = [d for d in q_res.detected if d["id_type"] in ("docket", "fr_docnum", "ad_number")
                   and not re.fullmatch(r"\d{4}-\d{2}", d["normalized"] if isinstance(d["normalized"], str) else "")]
        if unknown and not (q_res.docnums or q_res.meta_only):
            return _finish(ab.abstain(ab.DIRECTIVE_NOT_FOUND, candidates=q_res.near_miss, warnings=q_res.near_labels), t0, tm)

    if res.meta_only and not res.docnums:
        rec = res.meta_only[0]
        return _finish(ab.abstain(ab.SOURCE_TEXT_UNAVAILABLE, citations=ab.sheet_citations(rec),
                                  directive=cat.meta_only_info(rec)), t0, tm)

    if pq.compliance:
        return _finish(ab.abstain(ab.COMPLIANCE_DETERMINATION_OUT_OF_SCOPE), t0, tm)
    if pq.superlative:
        return _finish(ab.abstain(ab.UNSUPPORTED_QUESTION), t0, tm)

    ac = req.aircraft
    docnums = list(res.docnums)
    scoped = bool(docnums)           # directive explicitly resolved (directive_id or exact ID in the question)
    inferred = False
    if not docnums and pq.comparison:
        cands = _candidates(req, tm)
        return _finish(ab.abstain(ab.DIRECTIVE_AMBIGUOUS, status=AnswerStatus.NEEDS_MORE_INFORMATION, candidates=cands,
                                  missing=["directive_id"], warnings=pq.hints), t0, tm)
    if not docnums and pq.intent == "applicability":
        cands = _candidates(req, tm)
        if len(cands) > 1:
            return _finish(ab.abstain(ab.DIRECTIVE_AMBIGUOUS, status=AnswerStatus.NEEDS_MORE_INFORMATION, candidates=cands,
                                      missing=["directive_id"], warnings=pq.hints), t0, tm)
        if len(cands) == 1:
            docnums, inferred = [cands[0].fr_docnum], True
    if len(docnums) > 1 and pq.intent == "applicability":
        proposals = [d for d in docnums if cat.meta[d]["doc_class"] in ("NPRM", "SNPRM")]
        # prefer proposals with an Applicability paragraph; older NPRMs may lack the heading, then use the proposals alone
        narrowed = [d for d in proposals if deps.applicability_quote(d)] or proposals
        if len(narrowed) == 1:
            docnums = narrowed
    if len(docnums) > 1:
        return _finish(ab.abstain(ab.DIRECTIVE_AMBIGUOUS, status=AnswerStatus.NEEDS_MORE_INFORMATION,
                                  candidates=[i for i in (cat.info(d) for d in docnums[:10]) if i],
                                  missing=["directive_id"], warnings=pq.hints), t0, tm)
    if pq.intent == "applicability" and not (ac and ac.model):
        return _finish(ab.abstain(ab.MISSING_MODEL, status=AnswerStatus.NEEDS_MORE_INFORMATION, missing=["aircraft.model"],
                                  warnings=pq.hints, directive=cat.info(docnums[0]) if docnums else None), t0, tm)

    docnum = docnums[0] if docnums else None
    group = cat.group_for(docnum) if docnum else None
    docket = (cat.meta[docnum]["dockets"] or [None])[0] if docnum else None
    if docnum:
        w = _metadata_conflict_warning(docnum)
        if w:
            warnings.append(w)
    if inferred:
        warnings.append(f"Directive {docnum} was inferred from retrieval, not specified; confirm it is the intended one.")

    # --- 3/4. engines + retrieval ---------------------------------------------------------------
    applicability, revision, engines_used = ApplicabilityResult(), None, False
    if docnum:
        t = time.perf_counter()
        applicability, revision = _run_engines(docnum, req, warnings)
        tm["engines"] = (time.perf_counter() - t) * 1000
        engines_used = (revision is not None or applicability.value != ApplicabilityValue.NOT_EVALUATED) and pq.intent != "factual"

    skip_generation = bool(docnum) and pq.intent in ("applicability", "revision") and engines_used
    hits: list[dict] = []
    if not skip_generation or applicability.applicability_text is None:
        t = time.perf_counter()
        try:
            hits = _search(req.question, group, docket, config.ANSWER_TOP_K)
        except Exception as e:
            log.exception("retrieval failed")
            warnings.append(f"Retrieval unavailable ({type(e).__name__}).")
        tm["retrieval"] = (time.perf_counter() - t) * 1000
    if not skip_generation and not engines_used and not scoped and _below_threshold(hits):
        return _finish(ab.abstain(ab.NO_SUPPORTING_EVIDENCE, warnings=warnings, directive=cat.info(docnum) if docnum else None,
                                  revision=revision), t0, tm)
    if not skip_generation and engines_used and not scoped and _below_threshold(hits):
        hits = []   # engines still answer; no passages to cite

    # --- 5/6/7. generation + verification --------------------------------------------------------
    claims: list[Claim] = []
    inferred_candidates: list = []
    vinfo = VerificationInfo()
    cit_m, gr_m = deps.module("citations"), deps.module("grounding")
    if hits and not skip_generation:
        if cit_m is None or gr_m is None:
            return _finish(ab.abstain(ab.VERIFICATION_UNAVAILABLE, warnings=warnings), t0, tm)
        retrieved = {h["chunk_id"]: _evidence_chunk(cit_m, h) for h in hits}
        drafts, mode, insufficient = [], "extractive", False
        t = time.perf_counter()
        if req.use_llm and llm_mod.configured():
            try:
                block = cit_m.wrap_sources(list(retrieved.values()))
                out = llm_mod.generate(req.question, block)
                drafts = [_draft(cit_m, c["text"], c["chunk_id"], c["quote"]) for c in out.claims]
                mode, insufficient = "llm", out.insufficient_evidence
                warnings_missing = out.missing
            except llm_mod.LLMError as e:
                warnings.append(f"LLM generation failed ({e}); fell back to extractive mode.")
        elif req.use_llm:
            warnings.append("LLM not configured (ANTHROPIC_API_KEY unset); used extractive mode.")
        if mode == "extractive":
            if scoped:
                drafts = [_draft(cit_m, s, cid, s) for s, cid in extractive_claims(req.question, hits)]
            else:
                # Corpus-wide question: answer from a single directive (orchestrator review found 14/20 dev answers
                # mixing sentences from different directives) and skip header/closing boilerplate. Directives are
                # tried in retrieval rank order until one yields a usable sentence (at most 3).
                for d in list(dict.fromkeys(h["fr_docnum"] for h in hits))[:3]:
                    ex_hits = [h for h in hits if h["fr_docnum"] == d
                               and (h.get("section_path") or "") not in _BOILERPLATE_SECTIONS]
                    drafts = [_draft(cit_m, s, cid, s) for s, cid in extractive_claims(req.question, ex_hits)]
                    if drafts:
                        break
        tm["generation"] = (time.perf_counter() - t) * 1000
        t = time.perf_counter()
        if drafts:
            claims, vinfo, vwarn = _verify(cit_m, drafts, retrieved, mode)
            warnings.extend(vwarn)
        vinfo.mode = mode
        tm["verification"] = (time.perf_counter() - t) * 1000
        if insufficient and not claims:
            warnings.append("The model reported the sources do not answer the question.")
        if claims and not scoped:
            answer_doc = claims[0].citations[0].fr_docnum
            dropped = [c for c in claims if c.citations[0].fr_docnum != answer_doc]
            claims = [c for c in claims if c.citations[0].fr_docnum == answer_doc]
            others = list(dict.fromkeys([h["fr_docnum"] for h in hits if h["fr_docnum"] != answer_doc]))[:4]
            inferred_candidates = [i for i in (cat.info(d) for d in others) if i]
            warnings.append(f"No directive ID was given: this answer is drawn from the best-matching directive FR {answer_doc}. "
                            f"Confirm it is the intended directive; other possibly relevant directives are listed as candidates.")
            if dropped:
                warnings.append(f"{len(dropped)} verified statement(s) from other directives were withheld so that one answer "
                                f"cites one directive.")
            docnum = answer_doc
            try:
                rev_m = deps.module("revisions")
                if rev_m is not None and revision is None:
                    revision = rev_m.revision_status(answer_doc)
            except Exception:
                log.exception("revision status failed for inferred directive")

    # --- 7/8. assemble ------------------------------------------------------------------------------
    missing = list(pq.hints)
    status = AnswerStatus.ANSWERED
    if applicability.value == ApplicabilityValue.UNKNOWN and applicability.missing and applicability.rule_parse_status != "FAILED":
        status = AnswerStatus.NEEDS_MORE_INFORMATION
        missing = list(applicability.missing) + missing
    if not claims and not engines_used:
        return _finish(ab.abstain(ab.NO_VERIFIED_CLAIMS, warnings=warnings, directive=cat.info(docnum) if docnum else None,
                                  verification=vinfo, revision=revision), t0, tm)
    cits = [c for cl in claims for c in cl.citations]
    if applicability.applicability_text:
        cits.append(applicability.applicability_text)
    for ex in applicability.explanation:
        cits.extend(ex.evidence)
    if revision:
        for e in revision.edges:
            cits.extend(e.evidence)
    resp = QueryResponse(status=status, answer_claims=claims, applicability=applicability, revision=revision,
                         directive=cat.info(docnum) if docnum else None, citations=_dedupe(cits), warnings=warnings,
                         missing_information=missing, verification=vinfo, candidates=inferred_candidates)
    return _finish(resp, t0, tm)


_BOILERPLATE_SECTIONS = {"preamble/header", "closing"}

_CONFLICT_FLAGS = {"sheet_fr_date_mismatch": "publication date", "sheet_fr_pages_mismatch": "page range",
                   "sheet_fr_docket_format_mismatch": "docket format"}


def _metadata_conflict_warning(docnum: str) -> str | None:
    """Warn when a sheet row for this document carries a reconciliation mismatch vs the Federal Register record.
    Only sheet-vs-FR mismatch flags count (publish_date_differs_from_citation_text_date etc. are sheet-internal noise)."""
    import json
    conn = deps.db()
    try:
        rows = conn.execute("select row, dq_flags_json from records where fr_docnum=?", (docnum,)).fetchall()
    except Exception:
        return None
    finally:
        conn.close()
    what, nrows = [], []
    for r in rows:
        try:
            flags = json.loads(r["dq_flags_json"] or "[]")
        except ValueError:
            continue
        hit = [_CONFLICT_FLAGS[f] for f in flags if f in _CONFLICT_FLAGS]
        if hit:
            nrows.append(r["row"])
            what.extend(h for h in hit if h not in what)
    if not what:
        return None
    return (f"Spreadsheet metadata for this directive conflicts with the Federal Register record "
            f"({', '.join(what)} mismatch; sheet row{'s' if len(nrows) > 1 else ''} {', '.join(str(n) for n in nrows)}); "
            "FR values are shown.")


def _verify(cit_m, drafts, retrieved, mode):
    cat = deps.catalog()
    model_index = {m for d in cat.meta.values() for m in d["models"]} or None
    return deps.module("grounding").verify_answer(drafts, retrieved, model_index=model_index, mode=mode)


def _safe_inj(gm, text) -> bool:
    try:
        return bool(gm.contains_injection_markers(text))
    except Exception:
        return False


def _candidates(req: QueryRequest, tm: dict) -> list[DirectiveInfo]:
    """Plausible directives for a question with no directive id (doc-level retrieval)."""
    hs = deps.module("hybrid_search")
    if hs is None:
        return []
    cat = deps.catalog()
    filters = {}
    if req.aircraft and req.aircraft.model:
        filters["model"] = req.aircraft.model
    if req.aircraft and req.aircraft.make:
        filters["make"] = req.aircraft.make
    t = time.perf_counter()
    try:
        hits = hs.search(req.question, top_k=5, filters=filters or None, doc_level=True)
    except Exception:
        log.exception("candidate retrieval failed")
        return []
    tm["retrieval"] += (time.perf_counter() - t) * 1000
    hits = [h for h in hits if not _below_threshold([h])]
    if not hits:
        return []
    top = hits[0]["score"]
    out = []
    for h in hits:
        if h["score"] >= 0.5 * top:
            info = cat.info(h["fr_docnum"])
            if info:
                out.append(info)
    return out
