# Phase 0 Baseline — 2026-10-31

All figures are measured by the scripts named here. None are estimates.

## Repository
- The directory was empty at the start of the session. I ran `git init` on branch `main`. No commits yet, so there is no commit hash.
- `.gitignore` excludes `data/`, `.venv/`, indexes, `.env` and `node_modules` (constraint C1).
- Scripts so far: `scripts/inspect_dataset.py` (schema profile) and `scripts/probe_sources.py` (FR metadata, cache-aware).

## Environment
- macOS 15.5, Apple M4 (10 cores), 16 GB RAM, no CUDA, 131 GB free.
- Python 3.12 in `.venv`; Node v26.4.0; npm 11.17; tesseract and gh present.
- `ANTHROPIC_API_KEY` is set (value not inspected).

## Dataset snapshot
- Source: public XLSX export of sheet `1mYrS0aDdU_qYk8ldH47aFc27LdYXAc_f`, saved to `data/raw/sheet_snapshot/dataset.xlsx`.
- SHA256 `3bc255f5f790b3adf41b8b70525dd1867310820801ac960fedf9b3ddc2fb1fd0`.
- One worksheet, `AD Notice of Proposed Rulemaki`: 431 data rows × 22 columns.
- Profile output: `data/processed/schema_profile.json`, sha1 `056dcfda…`; regenerates byte-identically.
- The rows are FAA AD **Notices of Proposed Rulemaking**, not final ADs. FR `action` breakdown:
  - NPRM: 281
  - Withdrawal: 107
  - Supplemental NPRM: 18
  - Other: 14
- Two row populations:
  - **Modern** (174 rows, 2021–2026): office fields, Model in 86 rows, FR URL in col R.
  - **Legacy** (257 rows, 2001–2021): no Model; col R holds pasted notice text (169 rows), a short URL, or nothing.
- Data-quality issues:
  - Status = "Current" on all 431 rows, so it carries no information.
  - Docket numbers repeat: 99 values across 207 rows.
  - Make is unnormalized (91 distinct values).
  - 3 reference columns are 100% empty.
  - 123 rows have Comments Due ≤ Publish Date.
  - Page formats vary (7 variants; 431/431 parse with a relaxed regex).
- Serial-number language appears in only 16 Summaries. The sheet contains no serial ranges.

## Source documents (Federal Register API, public)
- Manifest `data/processed/source_manifest.csv`: 431 rows, sha256 `bbaefa59…a87573b`.
- 428 rows resolved to an FR document number; 3 unresolved (rows 397, 410, 412, all `-AD-W` dockets).
- 420 unique FR documents, all type "Proposed Rule". All 420 have XML and PDF URLs.
- How document numbers were resolved:
  - Col R URL: 237
  - FR docket search (± 2 days): 191, inferred (spot-check pending)
- **Total `page_length` across unique docs: 1,324 FR pages**, which meets the ≥ 1,000-page target once ingested.
- Sheet citation vs FR record: 12 date mismatches and 13 page mismatches, flagged and not resolved.
- Full text has been downloaded for a 5-document sample only.
  - XML carries `<PRTPAGE>` markers, giving exact FR page boundaries.
  - Each PDF page header contains its FR page number, confirming a 1:1 PDF-page ↔ FR-page mapping.
  - Proposed AD paragraphs are present: (b) Affected ADs, (c) Applicability, (e) Unsafe Condition, Compliance.
- Organiser Drive folder: HTTP 401, not listable without credentials.
- drs.faa.gov (col A hyperlinks): Angular app shell only; API returns 403; no usable public endpoint.

## Not yet measured
Indexed pages, extraction failures across the full corpus, retrieval and evaluation metrics, latency.
