# External data

## What is used
- Only public data. The organiser workbooks (the dataset sheet and the v2 index workbook) plus public Federal Register data:
  the FR API (`federalregister.gov/api/v1`), FR full-text XML, and govinfo PDFs.
- No paid, private, scraped-behind-login or third-party-licensed sources.
- Federal Register content is a US government work (17 U.S.C. 105, public domain).
- The organiser workbooks are challenge data and are used only for this challenge.
- The workbooks are parsed read-only with openpyxl. Nothing in them is executed, and raw files are never modified.

## Sources
| source | what | acquired by |
|---|---|---|
| `organiser_sheet` | `data/raw/sheet_snapshot/dataset.xlsx` (SHA256 `3bc255f5…b1fd0`), 431 NPRM rows | organiser download, SHA verified on every build |
| `organiser_index_workbook` | `data/raw/organiser_v2/challenge4_index/challenge4_ad_index.xlsx` (SHA256 `10b46b2b…3206678`), public Drive folder `1FOw-3WXMylypPpY3wZMyzpYSbnKC4Ybt`, file `144lTTfdJLSmWH3Eeyqez6u6Tv7gMfz1I`, fetched 2026-10-31 13:10 | manual download, SHA verified on every build |
| `federal_register_documents` | FR metadata JSON, XML and PDF for the 420 documents referenced by the sheet | `scripts/ingest.py` |
| `fr_final_rule_lookup` | enrichment: final rules and related FR documents found by docket search | `scripts/fetch_final_rules.py`, then `scripts/ingest.py` |

The machine-readable manifest is `data/processed/external_data_manifest.json`. For each source it lists the URL pattern, acquisition script and licence note.
For each document it lists `fr_docnum`, `record_ids`, `source_url`, the XML, PDF and JSON SHA256 values, `source` (`organiser_sheet` or `fr_final_rule_lookup`) and `fetch_date`.
It also lists both workbooks with their SHA256 values.
`fetch_date` is the UTC date of the cached file's mtime. It is the only field that depends on when the data was fetched; everything else is deterministic.

## Reproduce
```
.venv/bin/python scripts/fetch_final_rules.py   # optional enrichment (network, cached after the first run)
.venv/bin/python scripts/ingest.py              # download (cache-first) -> atomic DB build -> validation -> notes/reconciliation.md -> manifest
.venv/bin/python scripts/build_manifest.py      # manifest only (no network)
.venv/bin/python scripts/build_index.py         # search index (chunks, embeddings)
.venv/bin/pytest tests/test_index.py tests/test_ingestion.py tests/test_retrieval.py -q
```
A re-run with a warm cache makes 0 network calls. The DB build is atomic (temp file plus `os.replace`) and deterministic: two builds give the same `content_sha256`.

## Provenance and relationships
- The index `record_id` is mapped to an original sheet row and then to an FR document number.
  Each row is verified on docket, ISO publish date, pages and subject. The mapping method and any discrepancy are stored per row in `organiser_index.match_method` and `discrepancies_json`.
- The final-rule lookup is an enrichment, not part of the organiser corpus. It is stored with `source = fr_final_rule_lookup` and kept separate from organiser documents.
- Relationships (supersession, finalisation, withdrawal) are evidence-checked against document text and are never inferred from a shared docket alone.
  Organiser fields such as `supersedes_ad` are recorded as proposed supersession only, and are cross-checked against our text-derived edges in `notes/reconciliation.md`.
- The index `mentions_serial_numbers` flag is a hint only and is never used as evidence.
