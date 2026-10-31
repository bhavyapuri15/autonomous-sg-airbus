"""O1 integration: final-rule documents (source='fr_final_rule_lookup') + re-anchored evidence in the canonical doc_text.

download_pdfs(): sequential, cache-first, FR/govinfo only (C5); never touches existing cache files (C6).
ingest(conn, links_json): called from build_db.build(); no network. Inserts documents / doc_text / sections / pages for every
rule referenced by a link, plus tables `final_rule_info` and `final_rule_links`.

O1 evidence offsets refer to final_rules.normalized_text(), NOT to doc_text. Each evidence quote is therefore re-anchored in the
canonical doc_text (exact substring, else whitespace-tolerant match mapped back to exact canonical offsets). A VERIFIED link whose
quote cannot be re-anchored is downgraded to CANDIDATE.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from backend import config
from backend.ingestion import final_rules as o1, fr_xml_parser as fxp, pdf_parser as pp
from backend.ingestion import document_downloader as dl

SOURCE = "fr_final_rule_lookup"
KEYWORD_PARA = re.compile(r"NPRM|proposed|published in the Federal Register", re.I)
SCHEMA = """
CREATE TABLE final_rule_info(
 fr_docnum TEXT PRIMARY KEY, ad_number TEXT, ad_start INTEGER, ad_end INTEGER, amendment TEXT, effective_on TEXT,
 supersedes_json TEXT, o1_class TEXT, n_ad_paragraphs INTEGER, has_applicability INTEGER);
CREATE TABLE final_rule_links(
 dataset_docnum TEXT, rule_docnum TEXT, docket TEXT, o1_status TEXT, status TEXT, evidence_json TEXT, note TEXT,
 PRIMARY KEY(dataset_docnum, rule_docnum));
"""


def rules_dir(dn: str) -> Path:
    return config.FR_FINAL_RULES_DIR / dn


def load_links(path=None) -> dict:
    return json.loads(Path(path or config.PROCESSED / "final_rule_links.json").read_text())


# ------------------------------------------------------------------------------------------------ download
def download_pdfs(links=None, log=print) -> dict:
    """Fetch document.pdf for every rule referenced by a link. Returns {'failures': [...], 'fetched': n, 'net_calls': n}."""
    links = links or load_links()
    failures, fetched = [], 0
    for rule in sorted({l["rule_docnum"] for l in links["links"]}):
        meta = json.loads((rules_dir(rule) / "metadata.json").read_text())
        p = rules_dir(rule) / "document.pdf"
        if p.exists() and p.stat().st_size > 0:
            continue
        url = meta.get("pdf_url")
        if not url or not url.startswith(("https://www.govinfo.gov/", "https://www.federalregister.gov/")):  # C5
            failures.append(dict(fr_docnum=rule, reason="no_allowed_pdf_url", url=url)); continue
        r, err = dl.http_get(url)
        if r is None or not r.content.startswith(b"%PDF"):
            failures.append(dict(fr_docnum=rule, url=url, reason=err or "not_a_pdf")); continue
        p.write_bytes(r.content)
        (rules_dir(rule) / "document.pdf.sha256").write_text(hashlib.sha256(r.content).hexdigest() + "\n")
        fetched += 1
        log(f"  fetched rule pdf {rule}")
    return dict(failures=failures, fetched=fetched, net_calls=dl.NET["calls"])


# ------------------------------------------------------------------------------------------------ re-anchoring
def _find_all(text: str, quote: str):
    """Exact occurrences first; else whitespace-tolerant (and de-hyphenation tolerant) matches. Offsets are canonical."""
    occ = [(m.start(), m.end()) for m in re.finditer(re.escape(quote), text)]
    mode = "exact"
    if not occ:
        toks = quote.split()
        if toks:
            rx = r"\s+".join(re.escape(t) for t in toks)
            occ = [(m.start(), m.end()) for m in re.finditer(rx, text)]
            mode = "whitespace_normalized"
    return occ, mode


def _para_bounds(text, s):
    a = text.rfind("\n\n", 0, s); a = 0 if a < 0 else a + 2
    b = text.find("\n\n", s); b = len(text) if b < 0 else b
    return a, b


def reanchor(text: str, quote: str):
    """Returns (start, end, mode, n_occurrences, in_keyword_paragraph) or None. Prefers an occurrence whose paragraph mentions
    NPRM / proposed / published in the Federal Register; ties -> first."""
    occ, mode = _find_all(text, quote)
    if not occ:
        return None
    def key(o):
        a, b = _para_bounds(text, o[0])
        return (0 if KEYWORD_PARA.search(text[a:b]) else 1, o[0])
    best = min(occ, key=key)
    a, b = _para_bounds(text, best[0])
    return best[0], best[1], mode, len(occ), bool(KEYWORD_PARA.search(text[a:b]))


def _date_guard_ok(text, ev, doc_citation):
    """Same guard as O1: a date item is rejected when an adjacent FR citation disagrees with the dataset doc's citation."""
    if ev["type"] != "nprm_date":
        return True
    near = [c["citation"] for c in o1.extract_citations(text[max(0, ev["start"] - 60): ev["end"] + 60])]
    return not (any(c != doc_citation for c in near) and doc_citation not in near)


# ------------------------------------------------------------------------------------------------ ingestion
def _cite_parts(citation):
    m = re.match(r"(\d+) FR (\d+)", citation or "")
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def ingest(conn, path, insert_doc_content, log, doc_columns_sql) -> dict:
    """Insert rule documents and links. `insert_doc_content(conn, dn, doc, pages, start_page)` is build_db's shared helper."""
    path = Path(path)
    if not path.exists():
        return {}
    links = load_links(path)
    conn.executescript(SCHEMA)
    rules = {r["fr_docnum"]: r for r in links["rules"]}
    ref = sorted({l["rule_docnum"] for l in links["links"]})
    texts, stats = {}, dict(rules=0, missing_pdf=[], parse_failures=[], ad_paragraph_docs=0, applicability_docs=0)
    for dn in ref:
        r = rules[dn]
        d = rules_dir(dn)
        xml_p, pdf_p, meta_p = d / "full_text.xml", d / "document.pdf", d / "metadata.json"
        vol, sp = _cite_parts(r.get("citation"))
        pages, status, warnings = [], "ok", []
        if pdf_p.exists():
            try:
                pages = pp.read_pages(pdf_p)
            except Exception as e:
                status = "pdf_parse_error"; stats["parse_failures"].append(dict(fr_docnum=dn, stage="pdf", reason=repr(e)))
        else:
            status = "pdf_missing"; stats["missing_pdf"].append(dn)
        ep = sp + len(pages) - 1 if pages else None
        doc = None
        try:
            doc = fxp.parse_fr_xml(xml_p.read_bytes(), sp, ep, pdf_pages=pages or None)
            warnings += doc.warnings
        except Exception as e:
            status = "xml_parse_error"; stats["parse_failures"].append(dict(fr_docnum=dn, stage="xml", reason=repr(e)))
        n_ad = n_app = 0
        if doc is not None:
            ad = [s for s in doc.sections if s["kind"] == "proposed_ad_paragraph" and s["level"] == 1]
            n_ad = len(ad)
            n_app = sum(1 for s in ad if (s["heading"] or "").lower().startswith("applicab"))
            if not ad:
                warnings.append("no_ad_paragraphs")
        cls = "FINAL_RULE" if r["doc_class"] == "FINAL_RULE_REQUEST_FOR_COMMENTS" else r["doc_class"]
        is_rfc = int(r["doc_class"] == "FINAL_RULE_REQUEST_FOR_COMMENTS")
        conn.execute(f"INSERT INTO documents({doc_columns_sql}) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            dn, r["title"], "Rule", r["action_raw"], cls, r["publication_date"], vol, sp, ep, len(pages) or None,
            json.dumps(r["docket_ids"]), json.dumps(["14 CFR 39"]), json.dumps(None), r["pdf_url"], r["xml_url"], None,
            dl.sha256_file(xml_p), dl.sha256_file(pdf_p) if pdf_p.exists() else None, dl.sha256_file(meta_p),
            SOURCE, status, "modern" if (r["publication_date"] or "") >= "2021-10-01" else "legacy", json.dumps(sorted(warnings)),
            is_rfc, r.get("effective_on")))
        if doc is None:
            continue
        stats["rules"] += 1
        stats["ad_paragraph_docs"] += bool(n_ad); stats["applicability_docs"] += bool(n_app)
        insert_doc_content(conn, dn, doc, pages, sp)
        texts[dn] = doc.text
        ad_m, am_m = o1.extract_ad_amendment(doc.text)
        sup = o1.extract_supersedes(doc.text) if cls == "FINAL_RULE" else []
        conn.execute("INSERT INTO final_rule_info VALUES(?,?,?,?,?,?,?,?,?,?)", (
            dn, ad_m["value"] if ad_m else None, ad_m["start"] if ad_m else None, ad_m["end"] if ad_m else None,
            am_m["value"] if am_m else None, r.get("effective_on"), json.dumps(sup), r["doc_class"], n_ad, int(bool(n_app))))
    # ---- link evidence re-anchoring
    docs = {row[0]: row for row in conn.execute("SELECT fr_docnum, publication_date, volume, start_page FROM documents")}
    re_stats = dict(verified_in=0, verified_kept=0, verified_downgraded=0, evidence_items=0, exact=0, ws_normalized=0, failed=0,
                    multi_occurrence=0, in_keyword_paragraph=0, date_guard_rejected=0, downgraded=[])
    for l in links["links"]:
        dn, rn = l["dataset_docnum"], l["rule_docnum"]
        text = texts.get(rn)
        anchored, note = [], l["notes"]
        o1_status = l["status"]
        status = {"VERIFIED_FINAL_RULE": "VERIFIED", "CANDIDATE_SAME_DOCKET": "CANDIDATE", "CONFLICT_REVIEW": "CONFLICT_REVIEW"}[o1_status]
        if o1_status == "VERIFIED_FINAL_RULE":
            re_stats["verified_in"] += 1
        d_row = docs.get(dn)
        doc_cit = f"{d_row[2]} FR {d_row[3]}" if d_row and d_row[2] else None
        for ev in l["evidence"]:
            re_stats["evidence_items"] += 1
            res = reanchor(text, ev["quote"]) if text else None
            if res is None:
                re_stats["failed"] += 1; continue
            s, e, mode, n, kw = res
            item = dict(fr_docnum=rn, type=ev["type"], start=s, end=e, quote=text[s:e], anchor_mode=mode, occurrences=n)
            if not _date_guard_ok(text, dict(item), doc_cit):
                re_stats["date_guard_rejected"] += 1; continue
            re_stats["exact" if mode == "exact" else "ws_normalized"] += 1
            re_stats["multi_occurrence"] += n > 1; re_stats["in_keyword_paragraph"] += kw
            anchored.append(item)
        if o1_status == "VERIFIED_FINAL_RULE":
            if anchored and text:
                re_stats["verified_kept"] += 1
            else:
                status = "CANDIDATE"; note += " | DOWNGRADED: O1 evidence quote could not be re-anchored in canonical doc_text."
                re_stats["verified_downgraded"] += 1; re_stats["downgraded"].append([dn, rn])
        conn.execute("INSERT INTO final_rule_links VALUES(?,?,?,?,?,?,?)",
                     (dn, rn, l["docket"], o1_status, status, json.dumps(anchored, sort_keys=True), note))
    log(conn, "final_rules", f"final-rule docs {stats['rules']}; reanchor {json.dumps({k: v for k, v in re_stats.items() if k != 'downgraded'})}")
    stats["reanchor"] = re_stats
    return stats
