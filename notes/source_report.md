# Source verification report (Phase 0.4)
Script: `scripts/probe_sources.py` (idempotent; 2nd/3rd run = 0 network calls). Manifest: `data/processed/source_manifest.csv` (431 rows).

## FR metadata
- 431 rows -> 428 resolved & fetched OK, 3 unresolved (rows 397, 410, 412: legacy "-AD-W" dockets, search_no_match). 420 unique FR docs, all `Proposed Rule`.
- docnum sources: col R /documents/ URL 174, col R /d/ URL 46, col R /a/ URL 17, FR search by docket (+-2 days) 191 (189 docket_id, 2 term), none 3.
- All 420 docs expose xml/pdf/raw-text/html URLs. Actions: NPRM 281, withdrawal 107, SNPRM 18, other 14. 4 have correction_of.
- Sum page_length (unique docs) = 1,324 (max 24 pages/doc). Years: 2026=133, rest 2001-2025.
- Sheet-vs-FR mismatches: date 12, pages 13 (same rows, e.g. row 159 sheet 2024-09-26 p78826 vs FR 2024-05-24 p45800; rows 162, 175), docket 4 (formatting only). Sheet link/citation is unreliable for those rows; FR record linked by docket/URL disagrees with sheet citation.
- Search fallback worked: no AMBIGUOUS hits appeared; searched rows matched with consistent page range.
## Full text (sample of 5: 2026-21387, 2026-07218, 2016-23938, E6-3907, 01-10467; hashes in `data/processed/fulltext_sample_hashes.json`)
- XML has structure: tags AGENCY/ACTION/SUMMARY/DATES, HD headings; modern NPRMs contain proposed AD sections (a) Comments Due Date, (b) Affected ADs, (c) Applicability, (e) Unsafe Condition, Compliance. 0 of 5 sample docs contained "serial number" (not all ADs have it); E6-3907 is a 1-page withdrawal with no applicability.
- Excerpt (2026-21387 XML): "(c) Applicability | This AD applies to all Airbus Helicopters Model AS350B3, AS355F, AS355F1, AS355F2, AS355N, AS355NP, EC130B4, and EC130T2 helicopters, certificated in any category."
- PDF (govinfo) text-extractable via pymupdf: 1-4 pages, ~6,700-7,100 chars/page.
## DRS (drs.faa.gov, col A hyperlinks)
- 6 targets (2 modern, 1 R1, 3 opaque hex): all HTTP 200 text/html, 22,889 bytes, byte-identical Angular SPA shell (no doc text, no PDF links). Document API not discoverable in main bundle (only `/api/disclaimer/accept/{id}` and an AI search-agent path); direct /api/ guesses -> 403. Treat DRS as not retrievable without a browser session; not crawled further.
## Legacy pasted text in col R (169 rows)
- Length 157-20,269 chars (median 3,241). Contains: "applicability" 104, "applies to" 76, "serial number" 40, "model" 106; Applicability+Compliance both 102; amendment/withdrawal text 140. Mostly the regulatory text section of the notice, not the full preamble -> fragment. Classify as `sheet-embedded text` (unverified). Prefer FR full text where docnum resolved.
## Drive folder
- GET `drive.google.com/embeddedfolderview?id=13h0...` returned HTTP 401 (login page, no items); HEAD returned 500. Not listable without credentials.
## regulations.gov
- Not needed: FR provides full text; regulations.gov docket pages need an API key. Not scraped.
## Limitations
- 3 rows unresolved; sheet-citation mismatches not adjudicated; sample is 5 docs only; no full-text bulk download yet.
