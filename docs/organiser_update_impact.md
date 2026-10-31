# Organiser Update (31 Oct 2026, 12:45): Change-Impact Matrix

Audited against the repository at commit `f788c5c`, which includes the locked evaluation. Index workbook `challenge4_ad_index.xlsx`: SHA256 `10b46b2b…3206678`, fetched 2026-10-31 13:10 from the public organiser folder.

| Updated requirement | Current implementation (inspected) | Required change | Priority |
|---|---|---|---|
| 431 records (not 432) | Sheet loader reads 431 data rows; docs already say 431. No code assumes 432. | Add a count assertion against the index; note the correction in the README. | Low |
| `challenge4_ad_index.xlsx` (record_id, ISO dates, supersedes_ad, serial flag) | Not ingested. Provenance key is the sheet row number. | New loader plus `organiser_index` table. Map record_id ↔ sheet row ↔ FR docnum, verified by docket + date + pages. Record discrepancies. Add `records.record_id`. | **High** |
| record_id as the primary provenance identifier | Citations carry fr_docnum and sheet_row only. | CitationRef gains `record_ids`, `docket_number`, `federal_register_citation`, `section`, `source_url`. The router resolves `NPRM-NNN`. | **High** |
| `revision_chains` (99 dockets, latest by publish date) | Our evidence graph exists (247 VERIFIED edges). There is no organiser chain or "latest in dataset" per the chain sheet. | Load `revision_chains`. Add `dataset_history` (chronological versions, LATEST/SUPERSEDED_IN_DATASET) separate from evidence edges. Handle ties and missing dates conservatively. | **High** |
| Proposals are not final ADs; show the regulatory stage separately | `doc_class` pill exists, and templates say "proposed AD would apply". There is no explicit stage or enforceability fields, and the UI uses a green APPLICABLE badge. | Add `regulatory_stage` and `enforceability` (NOT_VERIFIED / PROPOSAL_WITHDRAWN / FINAL_RULE_PUBLISHED_VERIFIED). The label becomes "Applicable under the proposed rule". The UI shows the three items separately and drops the single green badge. | **High** |
| `supersedes_ad` = proposed supersession only | Text-derived PROPOSES_TO_SUPERSEDE edges (75) exist, rendered as "proposes to supersede". | Add organiser-field supersessions as `proposed_supersedes` (source = organiser field, not operative), cross-checked against the text edges. | Medium |
| Status field does not identify revisions | Status is already ignored. | None. Add a test. | Low |
| Full-text applicability | Already in place: deterministic parser over FR paragraph (c); UNKNOWN on residue. | Use the `mentions_serial_numbers` flag only as a hint and never as evidence. Add the tests listed in the update. | Medium |
| Citation format: record_id + FR citation and page + section | FR docnum + page + section_path + quote. | Enrich every CitationRef (see above). The UI shows record ID, FR citation and section. | **High** |
| External data manifest (source, URL, script, fetch date, hash, mapping) | Per-file SHA256s exist in the DB; there is no consolidated manifest. | Generate `data/processed/external_data_manifest.json` plus a committed `docs/external_data.md`. | Medium |
| New evaluation families (record-ID, revision chains, regulatory status, proposed vs verified supersession) | F1/F2/F3/F6/F7/F8 exist; dev and locked have each been run once. | Add dev cases for the new families. Locked cases for new families get a new manifest, documented as added after the first locked run. | Medium |
| Corpus verification counts | 420 FR docs, 1,324 dataset pages (+272 final-rule pages), 13,513 chunks. | Recompute against the index (406 links in the index vs our 428 resolved rows) and report. | Medium |
| Early valid submission; assumptions document | No README yet. | README + `docs/assumptions_limitations.md` **now**. Then a push/submission decision by the user. | **High** |
