"""Deterministic SQLite build from cached sheet + FR metadata/XML/PDF. No network, no wall-clock in content tables."""
import csv, datetime as dt, hashlib, json, re, sqlite3, sys
from pathlib import Path
from backend import config
from backend.ingestion import sheets_loader, schema_normalizer as sn, fr_xml_parser as fxp, pdf_parser as pp
from backend.ingestion.document_downloader import sha256_file, load_metadata

SCHEMA = """
CREATE TABLE records(
 row INTEGER PRIMARY KEY, docket_raw TEXT, docket_norm TEXT, fr_docnum TEXT, docnum_source TEXT, match_confidence TEXT,
 subject TEXT, status_raw TEXT, issue_date TEXT, publish_date TEXT, comments_due_date TEXT,
 make_raw TEXT, make_norm TEXT, models_raw TEXT, models_json TEXT, product_type TEXT, product_subtype TEXT,
 ad_number TEXT, citation TEXT, page_number_raw TEXT, summary TEXT, col_r_raw TEXT, col_r_kind TEXT, drs_url TEXT,
 comments TEXT, dq_flags_json TEXT, match_verified INTEGER, match_verify_detail TEXT);
CREATE TABLE documents(
 fr_docnum TEXT PRIMARY KEY, title TEXT, fr_type TEXT, action_raw TEXT, doc_class TEXT, publication_date TEXT, volume INTEGER,
 start_page INTEGER, end_page INTEGER, page_length INTEGER, docket_ids_json TEXT, cfr_refs_json TEXT, correction_of_json TEXT,
 pdf_url TEXT, xml_url TEXT, html_url TEXT, xml_sha256 TEXT, pdf_sha256 TEXT, metadata_sha256 TEXT,
 source TEXT, extraction_status TEXT, era TEXT, parse_warnings_json TEXT);
CREATE TABLE doc_text(fr_docnum TEXT PRIMARY KEY, text TEXT);
CREATE TABLE sections(
 id TEXT PRIMARY KEY, fr_docnum TEXT, seq INTEGER, section_path TEXT, kind TEXT, label TEXT, heading TEXT,
 ancestor_path TEXT, top_path TEXT, level INTEGER, start_char INTEGER, end_char INTEGER, text TEXT, has_table INTEGER,
 fr_page_start INTEGER, fr_page_end INTEGER, pdf_page_start INTEGER, pdf_page_end INTEGER);
CREATE INDEX sections_doc ON sections(fr_docnum, seq);
CREATE TABLE pages(
 fr_docnum TEXT, pdf_page INTEGER, fr_page INTEGER, text TEXT, char_count INTEGER, header_fr_page INTEGER,
 is_image_only INTEGER, mapping_ok INTEGER, PRIMARY KEY(fr_docnum, pdf_page));
CREATE TABLE ingest_log(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, stage TEXT, fr_docnum TEXT, level TEXT, message TEXT);
"""
CONTENT_TABLES = {"records": "row", "documents": "fr_docnum", "doc_text": "fr_docnum", "sections": "id", "pages": "fr_docnum,pdf_page"}

# ---- doc_class rule table (ordered; first match wins). Applied to lower-cased FR `action`, then title. -----------------
DOC_CLASS_RULES = [
    ("WITHDRAWAL", r"withdraw|rescission|rescind"),
    ("CORRECTION", r"\bcorrection\b"),
    ("SNPRM", r"supplemental notice of proposed rulemaking"),
    ("OTHER", r"extension of (the )?comment period|notice of public meeting"),
    ("FINAL_RULE", r"^final rule|\bfinal rule\b|^rule\b"),
    ("NPRM", r"notice of proposed rulemaking"),
]


def classify_doc(action, fr_type="", title=""):
    a = (action or "").lower()
    for cls, pat in DOC_CLASS_RULES:
        if re.search(pat, a):
            return cls
    t = (title or "").lower()
    if re.search(r"\bwithdrawal\b", t): return "WITHDRAWAL"
    return "OTHER"


def era_of(pub_date):
    return "modern" if (pub_date or "") >= "2021-10-01" else "legacy"   # sheet: modern = Service/Office filled, publish >= 2021-10-29


def log(conn, stage, msg, docnum=None, level="info"):
    conn.execute("INSERT INTO ingest_log(ts,stage,fr_docnum,level,message) VALUES(?,?,?,?,?)",
                 (dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), stage, docnum, level, msg))


def _manifest():
    with open(config.SOURCE_MANIFEST, newline="") as f:
        return {int(r["row"]): r for r in csv.DictReader(f)}


def _conf(src, docnum):
    if not docnum: return "none"
    return "inferred_search" if (src or "").startswith("search_") else "direct_url"


TOK = re.compile(r"[a-z0-9]+")
STOP = {"airworthiness", "directives", "directive", "the", "and", "of", "model", "models", "airplanes", "airplane", "series"}


def _tokens(s): return {t for t in TOK.findall((s or "").lower()) if t not in STOP}


def verify_inferred(rec, doc_meta):
    """Sheet vs FR for an inferred match. Returns (verified, detail dict)."""
    sub, ttl = _tokens(rec["subject"]), _tokens(doc_meta.get("title"))
    overlap = round(len(sub & ttl) / len(sub | ttl), 3) if (sub | ttl) else 1.0
    sp = sn.parse_pages(rec["page_number_raw"])
    pages_ok = sp == (doc_meta.get("start_page"), doc_meta.get("end_page"))
    cd = sn.citation_date(rec["citation"])
    fr_d = doc_meta.get("publication_date")
    date_via = "publish_date" if rec["publish_date"] == fr_d else ("citation_text_date" if cd == fr_d else None)
    date_ok = date_via is not None
    title_ok = overlap >= 0.5
    reasons = [n for n, ok in (("title_overlap", title_ok), ("pages", pages_ok), ("publish_date", date_ok)) if not ok]
    return (not reasons), dict(title_jaccard=overlap, sheet_pages=sp, fr_pages=[doc_meta.get("start_page"), doc_meta.get("end_page")],
                               sheet_publish=rec["publish_date"], sheet_citation_date=cd, fr_publish=fr_d, date_matched_via=date_via, failed=reasons)


def build(db_path=None, verbose=True):
    db_path = Path(db_path or config.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists(): db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    sha = sheets_loader.verify_sha()
    log(conn, "build", f"sheet sha256 verified {sha}")
    man = _manifest()
    failures = []

    # ---- documents / doc_text / sections / pages ----------------------------------------------------------------
    docnums = sorted({r["docnum"] for r in man.values() if r["fr_fetch_status"] == "ok" and r["docnum"]})
    metas = {}
    for n, dn in enumerate(docnums, 1):
        mp = config.FR_METADATA_DIR / f"{dn}.json"
        m = json.loads(mp.read_text()); metas[dn] = m
        d = config.FR_DOCS_DIR / dn
        xml_p, pdf_p = d / "full_text.xml", d / "document.pdf"
        cls = classify_doc(m.get("action"), m.get("type"), m.get("title"))
        if cls == "OTHER":
            log(conn, "classify", f"OTHER action={m.get('action')!r} title={m.get('title')!r}", dn, "warn")
        status, warnings = "ok", []
        sp = m.get("start_page")
        pages = []
        if pdf_p.exists():
            try:
                pages = pp.read_pages(pdf_p)
            except Exception as e:
                status = "pdf_parse_error"
                failures.append(dict(fr_docnum=dn, stage="pdf_parse", reason=repr(e)))
        else:
            status = "pdf_missing"
            failures.append(dict(fr_docnum=dn, stage="pdf", reason="document.pdf missing"))
        if xml_p.exists():
            try:
                doc = fxp.parse_fr_xml(xml_p.read_bytes(), sp, m.get("end_page"), pdf_pages=pages)
                warnings += doc.warnings
            except Exception as e:  # recorded, never silent
                doc = None; status = "xml_parse_error"; failures.append(dict(fr_docnum=dn, stage="xml_parse", reason=repr(e)))
        else:
            doc = None; status = "xml_missing"; failures.append(dict(fr_docnum=dn, stage="xml", reason="full_text.xml missing"))
        if doc is not None and not any(s["kind"] == "proposed_ad_paragraph" for s in doc.sections):
            warnings.append("no_ad_paragraphs")
        if pages and m.get("page_length") and len(pages) != m["page_length"]:
            warnings.append(f"pdf_pages_{len(pages)}_vs_page_length_{m['page_length']}")
        vol = None
        mm = re.match(r"(\d+) FR", m.get("citation") or "")
        if mm: vol = int(mm.group(1))
        conn.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            dn, m.get("title"), m.get("type"), m.get("action"), cls, m.get("publication_date"), vol, sp, m.get("end_page"),
            m.get("page_length"), json.dumps(m.get("docket_ids") or []),
            json.dumps([f"{c.get('title')} CFR {c.get('part')}" for c in (m.get("cfr_references") or [])]),
            json.dumps(m.get("correction_of")), m.get("pdf_url"), m.get("full_text_xml_url"), m.get("html_url"),
            sha256_file(xml_p) if xml_p.exists() else None, sha256_file(pdf_p) if pdf_p.exists() else None, sha256_file(mp),
            "organiser_sheet", status, era_of(m.get("publication_date")), json.dumps(sorted(warnings))))
        if doc is not None:
            conn.execute("INSERT INTO doc_text VALUES(?,?)", (dn, doc.text))
            npdf = len(pages)
            def pdfp(fr):
                p = fr - sp + 1
                return p if 1 <= p <= npdf else None
            for s in doc.sections:
                conn.execute("INSERT INTO sections VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                    f"{dn}:{s['seq']:04d}", dn, s["seq"], s["path"], s["kind"], s["label"], s["heading"], s["ancestor"], s["top"],
                    s["level"], s["start_char"], s["end_char"], s["text"], int(s["has_table"]), s["fr_page_start"], s["fr_page_end"],
                    pdfp(s["fr_page_start"]), pdfp(s["fr_page_end"])))
        for i, t in enumerate(pages, 1):
            hdr = pp.header_fr_page(t)
            fr = sp + i - 1
            conn.execute("INSERT INTO pages VALUES(?,?,?,?,?,?,?,?)", (dn, i, fr, t, len(t), hdr, int(len(t) < 50),
                                                                       None if hdr is None else int(hdr == fr)))
        if verbose and n % 50 == 0: print(f"  built {n}/{len(docnums)} docs", file=sys.stderr)

    # ---- records ---------------------------------------------------------------------------------------------------
    inferred = {"true": 0, "false": 0}
    for raw in sheets_loader.load_rows():
        rec = sn.normalize(raw)
        mr = man[rec["row"]]
        dn = mr["docnum"] if mr["fr_fetch_status"] == "ok" else None
        src = mr["docnum_source"]
        conf = _conf(src, dn)
        flags = list(rec["flags"])
        notes = mr["metadata_mismatch_notes"]
        for key, name in (("date_mismatch", "sheet_fr_date_mismatch"), ("pages_mismatch", "sheet_fr_pages_mismatch"), ("docket_mismatch", "sheet_fr_docket_format_mismatch")):
            if key in notes: flags.append(name)
        if not dn: flags.append("no_fr_document")
        verified = detail = None
        if conf == "inferred_search":
            ok, det = verify_inferred(rec, metas[dn])
            verified = int(ok); detail = json.dumps(det, sort_keys=True)
            flags.append("match_verified=true" if ok else "match_verified=false:" + ",".join(det["failed"]))
            inferred["true" if ok else "false"] += 1
        conn.execute("INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            rec["row"], rec["docket_raw"], rec["docket_norm"], dn, src or None, conf, rec["subject"], rec["status_raw"],
            rec["issue_date"], rec["publish_date"], rec["comments_due_date"], rec["make_raw"], rec["make_norm"], rec["models_raw"],
            json.dumps(rec["models"]), rec["product_type"], rec["product_subtype"], rec["ad_number"], rec["citation"],
            rec["page_number_raw"], rec["summary"], rec["col_r_raw"], rec["col_r_kind"], rec["drs_url"], rec["comments"],
            json.dumps(sorted(flags)), verified, detail))
    log(conn, "build", f"inferred match verification {inferred}")
    ingest_final_rule_links(conn, config.PROCESSED / "final_rule_links.json")
    for f in failures:
        log(conn, "build", json.dumps(f), f["fr_docnum"], "error")
    conn.commit()
    h = content_hash(conn)
    conn.close()
    return dict(db=str(db_path), content_sha256=h, failures=failures, inferred=inferred)


def ingest_final_rule_links(conn, path):
    """HOOK (format TBD): ingest data/processed/final_rule_links.json produced by the final-rules agent.
    No-op when the file is absent. When present it must insert documents with source='fr_final_rule_lookup';
    that is NOT implemented yet, so presence is logged loudly and nothing is inserted."""
    path = Path(path)
    if not path.exists():
        return 0
    log(conn, "final_rules", f"{path} exists but ingest_final_rule_links is not implemented; skipped", level="warn")
    return 0


def content_hash(conn):
    h = hashlib.sha256()
    for t, order in CONTENT_TABLES.items():
        h.update(t.encode())
        for row in conn.execute(f"SELECT * FROM {t} ORDER BY {order}"):
            h.update(json.dumps(row, ensure_ascii=False, default=str).encode()); h.update(b"\n")
    return h.hexdigest()


# ------------------------------------------------------------------------------------------------------------------
# Page-mapping validation (amendment A4)
# ------------------------------------------------------------------------------------------------------------------
def _windows(sec, markers, doc_text, width=40):
    """Return [(which, snippet_text, expected_fr_page)] for start/middle/end; never crossing a PRTPAGE marker; skip table lines."""
    import bisect
    text = doc_text[sec["start_char"]:sec["end_char"]]
    off = [m[0] for m in markers]
    def page(c):
        i = bisect.bisect_right(off, c) - 1
        return markers[i][1] if i >= 0 else sec["_start_page"]
    def within(a, b):  # shrink [a,b) so it doesn't cross a marker; keep the part containing a
        for o in off:
            if a < o < b: b = o
        return a, b
    cand = []
    L = len(text)
    # candidate absolute windows
    s0 = sec["start_char"]
    cand.append(("start", s0, s0 + width))
    mid = s0 + max(0, L // 2 - width // 2)
    cand.append(("middle", mid, mid + width))
    e0 = sec["end_char"]
    cand.append(("end", max(s0, e0 - width), e0))
    out = []
    for which, a, b in cand:
        if which == "end":   # keep the part containing the last char
            for o in off:
                if a < o < b: a = o
        else:
            a, b = within(a, b)
        snippet = doc_text[a:b]
        if "|" in snippet or "\n" in snippet:   # table rendering lines are not comparable to PDF text
            snippet = None
        if snippet is None or len(pp.norm_for_match(snippet)) < 10:
            out.append((which, None, None)); continue
        out.append((which, snippet, page(a if which != "end" else b - 1)))
    return out


def validate_page_mapping(db_path=None, out_path=None):
    conn = sqlite3.connect(db_path or config.DB_PATH)
    conn.row_factory = sqlite3.Row
    docs = {r["fr_docnum"]: dict(r) for r in conn.execute("SELECT * FROM documents")}
    # (a) header check
    a_total = a_ok = a_missing = 0
    a_fail = []
    page_txt, pdf_texts = {}, {}
    for r in conn.execute("SELECT fr_docnum,pdf_page,fr_page,header_fr_page,text FROM pages ORDER BY fr_docnum,pdf_page"):
        pdf_texts.setdefault(r["fr_docnum"], []).append(r["text"])
        page_txt.setdefault(r["fr_docnum"], {})[r["pdf_page"]] = pp.norm_for_match(r["text"])
        a_total += 1
        if r["header_fr_page"] is None: a_missing += 1
        elif r["header_fr_page"] == r["fr_page"]: a_ok += 1
        else: a_fail.append(dict(fr_docnum=r["fr_docnum"], pdf_page=r["pdf_page"], expected_fr_page=r["fr_page"], header_fr_page=r["header_fr_page"]))
    # (b) snippets
    stats = {}
    def bump(key, ok_strict, ok_range):
        s = stats.setdefault(key, dict(snippets=0, strict_ok=0, range_ok=0)); s["snippets"] += 1; s["strict_ok"] += ok_strict; s["range_ok"] += ok_range
    b_fail, no_snip = [], 0
    secs_checked = {}
    from backend.ingestion import fr_xml_parser
    for dn, d in docs.items():
        if d["extraction_status"] not in ("ok",): continue
        text = conn.execute("SELECT text FROM doc_text WHERE fr_docnum=?", (dn,)).fetchone()
        if not text: continue
        text = text[0]
        # re-derive markers from the section parse (single source of truth is the parser)
        xml = (config.FR_DOCS_DIR / dn / "full_text.xml").read_bytes()
        pd = fr_xml_parser.parse_fr_xml(xml, d["start_page"], d["end_page"], pdf_pages=pdf_texts.get(dn))
        assert pd.text == text
        pages = page_txt.get(dn, {})
        for s in conn.execute("SELECT * FROM sections WHERE fr_docnum=? ORDER BY seq", (dn,)):
            sec = dict(s); sec["_start_page"] = d["start_page"]
            multi = sec["fr_page_end"] > sec["fr_page_start"]
            for which, snip, exp_fr in _windows(sec, pd.markers, text):
                if snip is None:
                    no_snip += 1; continue
                ns = pp.norm_for_match(snip)
                exp_pdf = exp_fr - d["start_page"] + 1
                strict = ns in pages.get(exp_pdf, "")
                lo, hi = sec["pdf_page_start"], sec["pdf_page_end"]
                rng = lo is not None and hi is not None and any(ns in pages.get(p, "") for p in range(lo, hi + 1))
                rng = rng or strict
                extra = ("on_repaired_page(circular_check)",) if exp_fr in getattr(pd, "repaired_pages", []) else ()
                for key in extra + ("overall", "multi_page" if multi else "single_page", "era_" + d["era"], f"{d['era']}_{'multi' if multi else 'single'}",
                            "class_" + d["doc_class"]):
                    bump(key, int(strict), int(rng))
                if not strict:
                    found_where = [p for p, t in pages.items() if ns in t]
                    b_fail.append(dict(fr_docnum=dn, section_id=sec["id"], section_path=sec["section_path"], which=which,
                                       snippet=snip, expected_pdf_page=exp_pdf, found_on_pdf_pages=found_where, era=d["era"],
                                       multi_page=multi, reason="wrong_page" if found_where else "not_found_on_any_page"))
    for s in stats.values():
        s["strict_rate"] = round(s["strict_ok"] / s["snippets"], 4) if s["snippets"] else None
        s["range_rate"] = round(s["range_ok"] / s["snippets"], 4) if s["snippets"] else None
    res = dict(
        header_check=dict(pdf_pages=a_total, header_matches=a_ok, header_missing=a_missing, header_mismatch=len(a_fail),
                          rate_over_pages_with_header=round(a_ok / (a_total - a_missing), 4) if a_total - a_missing else None,
                          mismatches=a_fail),
        snippet_check=dict(windows_without_comparable_snippet=no_snip, stats=stats, failures=b_fail))
    out_path = Path(out_path or config.PROCESSED / "page_mapping_validation.json")
    out_path.write_text(json.dumps(res, indent=1, sort_keys=True, ensure_ascii=False))
    conn.close()
    return res


def parse_coverage(db_path=None):
    """Section-parsing coverage by doc_class and era (all denominators included)."""
    conn = sqlite3.connect(db_path or config.DB_PATH); conn.row_factory = sqlite3.Row
    docs = [dict(r) for r in conn.execute("SELECT fr_docnum,doc_class,era,extraction_status FROM documents ORDER BY fr_docnum")]
    ad = {}
    for r in conn.execute("SELECT * FROM sections WHERE kind='proposed_ad_paragraph' AND level=1 ORDER BY fr_docnum,seq"):
        ad.setdefault(r["fr_docnum"], []).append(dict(r))
    nsec = dict(conn.execute("SELECT fr_docnum,count(*) FROM sections GROUP BY 1").fetchall())
    out = {"by_class_era": {}, "no_sections_at_all": [], "non_withdrawal_without_ad_paragraphs": [], "withdrawals": {},
           "applicability_without_label_c": []}
    tot = collections.Counter() if False else None
    import collections
    agg = collections.defaultdict(lambda: dict(docs=0, with_ad_paragraphs=0, with_applicability=0, with_label_c_applicability=0,
                                               applicability_serial_number=0, applicability_with_table=0))
    for d in docs:
        dn = d["fr_docnum"]
        if not nsec.get(dn): out["no_sections_at_all"].append(dn)
        secs = ad.get(dn, [])
        appl = [s for s in secs if (s["heading"] or "").lower().startswith("applicab")]
        c_appl = [s for s in appl if s["label"] == "(c)"]
        if not secs and d["doc_class"] != "WITHDRAWAL": out["non_withdrawal_without_ad_paragraphs"].append(f"{dn} [{d['doc_class']}]")
        if secs and not appl: out["applicability_without_label_c"].append(f"{dn} [{d['doc_class']}] (no Applicability heading)")
        for key in (f"{d['doc_class']}|{d['era']}", f"{d['doc_class']}|ALL", "ALL|ALL", f"ALL|{d['era']}"):
            a = agg[key]; a["docs"] += 1; a["with_ad_paragraphs"] += bool(secs); a["with_applicability"] += bool(appl)
            a["with_label_c_applicability"] += bool(c_appl)
            a["applicability_serial_number"] += any("serial number" in s["text"].lower() for s in appl)
            a["applicability_with_table"] += any(s["has_table"] for s in appl)
    out["by_class_era"] = {k: agg[k] for k in sorted(agg)}
    out["c_applicability_paragraphs_with_table"] = conn.execute(
        "SELECT count(*) FROM sections WHERE label='(c)' AND level=1 AND heading LIKE 'Applicab%' AND has_table=1").fetchone()[0]
    out["c_applicability_paragraphs_total"] = conn.execute(
        "SELECT count(*) FROM sections WHERE label='(c)' AND level=1 AND heading LIKE 'Applicab%'").fetchone()[0]
    w = [d for d in docs if d["doc_class"] == "WITHDRAWAL"]
    out["withdrawals"] = dict(total=len(w), without_ad_paragraphs=sum(1 for d in w if not ad.get(d["fr_docnum"])))
    conn.close()
    return out
