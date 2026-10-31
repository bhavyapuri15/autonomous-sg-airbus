# Task 1 ingestion report
Run: `.venv/bin/python scripts/ingest.py` (download -> build DB -> validate -> coverage -> reconcile). Idempotent: second run made 0 network calls; content hash identical across builds (`18fba977...af84`, sha256 over sorted dumps of records/documents/doc_text/sections/pages; `ingest_log` excluded).

## Downloads
420/420 docs have full_text.xml + document.pdf (0 failures). SHA256 of xml/pdf/metadata stored in `documents`. 801 network calls this session (sequential, 0.5 s sleep, cache-first); 5 sample docs were already cached.

## DB (data/indexes/ad.sqlite, not committed)
records 431; documents 420 (source=organiser_sheet; doc_class NPRM 282, WITHDRAWAL 115, SNPRM 18, OTHER 4, CORRECTION 1; each OTHER logged as warn in ingest_log); pages 1324 (>= 1000), image-only pages 0; sections: see `sections` table. `ingest_final_rule_links(conn, path)` hook in build_db.py is a no-op when `data/processed/final_rule_links.json` is absent (and logs a warning, inserting nothing, if present: format TBD).

## Canonical text rules (offsets refer to doc_text.text)
Blocks (P, HD, FP, AMDPAR, ...) with whitespace collapsed, joined by "\n\n"; GPOTABLE rendered as title / CHED header / ROW lines joined by "\n" with " | " between cells; one repair: whitespace between an inline element end and `. , ; : ) ]` is dropped (the cached XML is pretty-printed, e.g. `</E>\n .`).
Sections: preamble (header, each PREAMB part, SUPPLEMENTARY INFORMATION by HD1/HD2 heading), regtext/amendment, proposed_ad/* (top-level (a)..(z) plus nested (1), (i) with `ancestor_path`, `top_path`, so a whole top-level paragraph is one contiguous span), closing. Three AD layouts handled: modern HD1 `(c) Applicability`; legacy `<E T=03>Applicability:</E>` unlabeled/labelled paragraphs and HD1-unlabeled headings followed by `(a)`; AD text continuing in SECTION after a short EXTRACT.

## Page mapping validation (A4), full corpus (`data/processed/page_mapping_validation.json`)
(a) PDF header FR page == start_page + pdf_page - 1: 1324/1324 pages (header parsed on all pages; first pages of legacy docs use the section banner "Proposed Rules / Federal Register / NNNNN / Vol.").
(b) Snippets (start/middle/end, up to 40 chars, never crossing a PRTPAGE marker; windows containing table `|` or newlines skipped: 14,739 windows, so table sections are NOT snippet-validated): 29,977/29,977 found on the exact expected PDF page (strict), 100%. Multi-page sections: 1,562/1,562. Legacy 12,221/12,221; modern 17,756/17,756 (see JSON for per-class). Normalisation for comparison: accents stripped, only [a-z0-9] kept (insensitive to whitespace, hyphenation, quotes, PDF font artefacts). Weakness: this is lenient on punctuation; windows are 40 normalised chars.
Bugs found by the validation and fixed in the parser: (1) PRTPAGE inside `<ROW>` of a GPOTABLE and inside `<GPH>` were dropped; (2) a `prtpage_count_mismatch` warning now flags any XML marker not recorded; (3) if an XML genuinely omits a marker, `_repair_missing_markers` locates the PDF page start in the text (would be tagged `prtpage_repaired_from_pdf` in documents.parse_warnings_json; used for 0 documents after fix (1)). Initial pre-fix strict rate was 96.1% -> 98.8% (normalisation) -> 100%.

## Section parsing coverage (data/processed/ingest_failures.json -> parse_coverage)
Docs with a top-level AD paragraph headed "Applicability" (any label): 290/420 (modern 163/173, legacy 127/247). With label exactly (c): 241/420. Excluding WITHDRAWAL and OTHER (301 docs: 282 NPRM, 18 SNPRM, 1 CORRECTION): 288/301 have an Applicability paragraph; 13 have AD paragraphs under other headings (legacy plain-language ADs "(a) What airplanes are affected", e.g. 01-13183, 03-12111, 03-12113, 03-25088/89, 03-5387, 04-22585, 04-23028, 05-5707, 07-1167, E6-18462, E7-25411) -> applicability engine must handle these as UNKNOWN or read (a).
NPRM docs with 'serial number' in the Applicability paragraph: 56/282 (modern 23/158, legacy 33/124); SNPRM 0/18. (c)-Applicability paragraphs containing a table: 6/241; any Applicability paragraph with a table: 11 docs.
Withdrawals with no AD paragraphs: 113/115 (the 2 exceptions, 2012-19238 and 2012-20968, are rescissions that quote the AD being rescinded). Docs with no sections at all: none. Non-withdrawal docs without AD paragraphs: 03-19584, 03-19585, 04-1658, 2024-25883 (OTHER: comment extension / public meeting) and E8-18239 (NPRM for a Special FAR 73, stored as proposed_ad/unparsed).

## Inferred-match check (191 rows)
191/191 match_verified=true (title Jaccard >= 0.5, sheet page range == FR range, sheet publish date or citation-text date == FR date). Caveat: the search used sheet date +-2 days and page ranges to disambiguate, so date/page agreement is partly circular; title overlap is independent. Legacy rows: sheet "Citation Publish Date" is 1 day before the FR date in all verified legacy rows (citation text matches FR), flagged `publish_date_differs_from_citation_text_date`.

## Reconciliation
See `notes/reconciliation.md` (all numbers produced by reconcile.py): 431 -> 428 -> 420; 8 docnums shared by 16 rows; 3 unresolved rows (397, 410, 412); 99 duplicate dockets; 12 date / 13 page mismatches over 14 rows.

## Known limitations
- doc_class is derived from FR `action`; "extension of comment period / public meeting" -> OTHER by rule.
- Applicability detection is heading-based; legacy variants beyond those listed may be mis-sectioned (sections are always valid contiguous spans; the text check `doc_text[start:end]==text` holds for all).
- Table sections are not covered by the snippet check; sub-paragraph label nesting is heuristic (lowercase "(i)" vs roman is resolved by the layout mode).
- DB `pdf_page_*` use `fr_page - start_page + 1` (validated by (a)).
