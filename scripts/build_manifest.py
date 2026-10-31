#!/usr/bin/env python3
"""Write data/processed/external_data_manifest.json from the built DB + cached files. No network. Deterministic apart from
the recorded `fetch_date` fields, which come from the mtime of the cached files (UTC date)."""
import datetime as dt, hashlib, json, sqlite3, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend import config


def sha(p):
    p = Path(p)
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def fdate(*paths):
    ts = [Path(p).stat().st_mtime for p in paths if Path(p).exists()]
    return dt.datetime.fromtimestamp(max(ts), dt.timezone.utc).date().isoformat() if ts else None


SOURCES = [
    dict(name="organiser_sheet", description="Organiser dataset workbook: 431 FAA AD NPRM rows (the evaluation corpus index)",
         url_pattern="organiser Drive folder (public); file data/raw/sheet_snapshot/dataset.xlsx", acquisition_script="manual download of the organiser workbook; verified by SHA256 in backend/ingestion/sheets_loader.py",
         licence="Organiser-provided challenge data; used only for this challenge."),
    dict(name="organiser_index_workbook", description="Organiser index workbook v2 (record_id, ISO dates, revision_chains, supersedes_ad, serial flag)",
         url_pattern="https://drive.google.com/drive/folders/1FOw-3WXMylypPpY3wZMyzpYSbnKC4Ybt (file id 144lTTfdJLSmWH3Eeyqez6u6Tv7gMfz1I)",
         acquisition_script="manual download of the public Drive file (2026-10-31 13:10); parsed read-only by backend/ingestion/index_loader.py (openpyxl, nothing executed)",
         licence="Organiser-provided challenge data; used only for this challenge."),
    dict(name="federal_register_documents", description="FR metadata JSON, full-text XML and PDF for the NPRM/SNPRM/withdrawal documents referenced by the sheet",
         url_pattern="https://www.federalregister.gov/api/v1/documents/{docnum}.json ; https://www.federalregister.gov/documents/full_text/xml/{yyyy}/{mm}/{dd}/{docnum}.xml ; https://www.govinfo.gov/content/pkg/FR-{date}/pdf/{docnum}.pdf",
         acquisition_script="scripts/ingest.py (backend/ingestion/document_downloader.py; cache-first, 0 network calls on re-run)",
         licence="Federal Register content is a US government work (public domain, 17 U.S.C. 105)."),
    dict(name="fr_final_rule_lookup", description="Enrichment: final rules / related documents found by FR docket search, linked only with textual evidence",
         url_pattern="https://www.federalregister.gov/api/v1/documents.json?conditions[docket_id]={docket}",
         acquisition_script="scripts/fetch_final_rules.py then scripts/ingest.py (backend/ingestion/final_rules.py, final_rules_ingest.py)",
         licence="Federal Register content is a US government work (public domain, 17 U.S.C. 105)."),
]


def build():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    rec_by_doc = {}
    for r in conn.execute("SELECT record_id, fr_docnum FROM organiser_index WHERE fr_docnum IS NOT NULL ORDER BY record_id"):
        rec_by_doc.setdefault(r["fr_docnum"], []).append(r["record_id"])
    links = {}
    for r in conn.execute("SELECT dataset_docnum, rule_docnum FROM final_rule_links ORDER BY 1,2"):
        links.setdefault(r["rule_docnum"], set()).update(rec_by_doc.get(r["dataset_docnum"], []))
    docs = []
    for d in conn.execute("SELECT * FROM documents ORDER BY source, fr_docnum"):
        dn = d["fr_docnum"]
        org = d["source"] == "organiser_sheet"
        base = (config.FR_DOCS_DIR if org else config.FR_FINAL_RULES_DIR) / dn
        meta = config.FR_METADATA_DIR / f"{dn}.json" if org else base / "metadata.json"
        docs.append(dict(
            fr_docnum=dn, source="organiser_sheet" if org else "fr_final_rule_lookup",
            record_ids=sorted(rec_by_doc.get(dn, [])) if org else sorted(links.get(dn, [])),
            source_url=d["html_url"] or f"https://www.federalregister.gov/d/{dn}", xml_url=d["xml_url"], pdf_url=d["pdf_url"],
            xml_sha256=d["xml_sha256"], pdf_sha256=d["pdf_sha256"], json_sha256=d["metadata_sha256"],
            fetch_date=fdate(meta, base / "full_text.xml", base / "document.pdf")))
    workbooks = []
    for name, p, expect, src in (("organiser_sheet", config.SHEET_XLSX, config.SHEET_SHA256, "organiser Drive folder (public)"),
                                 ("organiser_index_workbook", config.INDEX_XLSX, config.INDEX_SHA256,
                                  "https://drive.google.com/drive/folders/1FOw-3WXMylypPpY3wZMyzpYSbnKC4Ybt (file id 144lTTfdJLSmWH3Eeyqez6u6Tv7gMfz1I)")):
        h = sha(p)
        workbooks.append(dict(name=name, path=str(Path(p).relative_to(config.ROOT)), sha256=h, expected_sha256=expect, sha256_ok=h == expect,
                              bytes=Path(p).stat().st_size if Path(p).exists() else None, source=src, fetch_date=fdate(p)))
    out = dict(schema_version=1,
               note="Only public Federal Register / govinfo data and the organiser workbooks are used. fetch_date = UTC date of the cached file mtime (the only non-deterministic-by-design field).",
               sources=SOURCES, workbooks=workbooks,
               counts=dict(documents=len(docs), organiser_sheet=sum(1 for x in docs if x["source"] == "organiser_sheet"),
                           fr_final_rule_lookup=sum(1 for x in docs if x["source"] == "fr_final_rule_lookup")),
               documents=docs)
    conn.close()
    config.EXTERNAL_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    config.EXTERNAL_MANIFEST.write_text(json.dumps(out, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    return out


if __name__ == "__main__":
    o = build()
    print("wrote", config.EXTERNAL_MANIFEST, o["counts"], "workbooks ok:", [w["sha256_ok"] for w in o["workbooks"]])
