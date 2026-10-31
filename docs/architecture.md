# Architecture Proposal (Phase 0.6) — PENDING APPROVAL

## 1. Data interpretation
- **The sheet is a metadata index of mixed formats.** It is not a document corpus.
- **Authoritative text comes from Federal Register (FR) full text.** That means XML for structure plus the govinfo PDF for the page viewer, covering 420 documents and 1,324 pages.
- **Sheet text is a lower-trust tier.** Summary and the text pasted into col R are classified as `SHEET_METADATA` / `SHEET_EMBEDDED_TEXT`. They may support only metadata claims (C8).
- **3 rows have no FR document.** They are kept as metadata-only records, and every technical question about them is refused.
- **Domain framing.** Every document is a *proposed* AD. Each document is labelled with an FR `action`: NPRM, SNPRM, withdrawal or correction.
  - Applicability answers say "applies *as proposed* in FR doc X".
  - The system never says "this AD is in force".
  - Whether a final rule was later issued is reported as UNKNOWN unless we verify it (see Option O1).

## 2. Pipeline
```
sheet.xlsx ─▶ sheets_loader (raw cells + hyperlinks + row provenance)
           ─▶ schema_normalizer (canonical record, normalized make/models, data-quality flags)
FR API     ─▶ document_downloader (cached XML/PDF/JSON, SHA256, manifest)
           ─▶ fr_xml_parser (sections, AD paragraphs (a)…(x), PRTPAGE→FR page, char offsets)
           ─▶ pdf_parser (PyMuPDF page text; verifies FR page ↔ PDF page via header)
           ─▶ chunker ─▶ SQLite (records, docs, pages, chunks, rules, relations) + FTS5 + embeddings
```

## 3. Storage and retrieval
- **Database:** SQLite, one file, deterministic build. Tables:
  - `records` (sheet rows)
  - `documents`
  - `pages`
  - `chunks`
  - `applicability_rules`
  - `relations` (docket / supersede / withdraw / correction)
  - `ingest_log`
- **Exact lookup** runs first. A regex router recognises:
  - docket IDs (`FAA-YYYY-NNNN`, `YYYY-NM-NNN-AD`)
  - FR document numbers
  - AD numbers (`YYYY-NN-NN`)
  - model tokens (normalized index)
  - serial/part-number strings
- **BM25** uses SQLite FTS5. It needs no extra dependency and handles identifiers well.
- **Dense search** uses `BAAI/bge-small-en-v1.5` (MIT licence) running locally, with brute-force cosine similarity in numpy.
  - About 5k chunks is too small to justify FAISS.
  - We will add FAISS only if latency measurements require it.
- **Fusion:** Reciprocal Rank Fusion. A cross-encoder reranker is optional and goes through a 3.8 go/no-go decision.
- **Metadata filters:** make, model, product type, FR action, docket and date.

## 4. Chunking
- **Regulatory text** is chunked one AD paragraph per chunk, e.g. "(c) Applicability" including all its sub-paragraphs and exceptions. Applicability and exception text are never split apart.
- **Preamble text** is chunked by `HD` heading, with a soft limit of about 350 tokens and paragraph-boundary overlap.
- **Chunk ID:** `{fr_docnum}:{section_path}:{sha256(text)[:8]}`, which is stable and content-addressed.
- **Each chunk carries:**
  - its FR page span
  - its PDF page span
  - character offsets into the normalized document text
  - its source record rows

## 5. Applicability engine (deterministic, three-valued) — C7
- **Input:** the (c) Applicability paragraph, plus excluded-configuration paragraphs where present.
- **Parsing:** a rule-based parser turns the paragraph into a small rule language:
  - `make`
  - `models[]`
  - `serial: {ranges[], list[], excluded[]}`
  - `part_numbers[]`
  - `conditions[]`
  - `unparsed_residue`
- **Evidence:** every rule element stores its exact source span and offsets.
- **Optional LLM help:** an LLM may *propose* rule candidates, but a candidate is accepted only if:
  - it parses into the rule language, and
  - every literal in it (model, serial, part number) appears verbatim in the cited span.
- **Evaluation** uses Kleene logic: APPLICABLE / NOT_APPLICABLE / UNKNOWN.
  - Model is matched exactly after normalization. Families such as "-series" only match when the source says so.
  - Serial ranges are compared numerically only when both bounds and the query share a pure-integer format. Otherwise only an exact list match counts, and anything else is UNKNOWN.
  - Equipment, part-number or modification conditions return UNKNOWN unless the user supplies that configuration.
  - Any `unparsed_residue` that could restrict scope forces UNKNOWN.
  - Missing input returns UNKNOWN, never NOT_APPLICABLE.
- **Overlays:** WITHDRAWN documents get the overlay "proposal withdrawn — no proposed requirement".

## 6. Revision model
Each docket is a graph built from three sources:
- FR metadata: `docket_ids`, `action`, `correction_of`, dates.
- Text patterns: "proposes to supersede AD YYYY-NN-NN", "withdraws the NPRM published…", "supplemental".
- Sheet rows: duplicate dockets.

Statuses:
- `LATEST_IN_DATASET`
- `SUPERSEDED_IN_DATASET` (by an SNPRM)
- `WITHDRAWN_IN_DATASET`
- `CORRECTED`
- `CURRENT_AUTHORITATIVE_STATUS_UNKNOWN`, which is always shown unless O1 verifies a final rule

Conflicting dates or links are surfaced as warnings and never resolved silently.

## 7. Answering and citation verification
1. Route the query (ID lookup or natural-language search), then extract configuration (model, serial).
2. Retrieve the top-k chunks.
3. Run the applicability and revision engines. They are deterministic, and their outputs fill the response fields directly.
4. Generate with Claude, which returns JSON claims of the form `[{text, chunk_id, quote}]`.
5. Verify each claim:
   - the `chunk_id` was in the retrieved set
   - the `quote` is an exact normalized substring of the chunk
   - every ID, number, model or serial in the claim also appears in its quote
   - the claim does not contradict the engine outputs
6. Drop claims that fail. If no claims survive, or a needed field is unresolved, return `ABSTAINED` or `NEEDS_MORE_INFORMATION`.

Additional rules:
- **No-LLM fallback:** an extractive answer made of verified quotes, so the system still works without the API.
- **Prompt injection:** source text is passed as quoted data, and the generator's output can never set the applicability or revision fields.
- **UI disclaimer:** "Decision-support only; not a certified compliance determination."

## 8. Evaluation
- **Split:** the dev set and the locked set are separated by docket hash, so related documents never cross the split.
- **Locked set protection:** its manifest hash is recorded before any tuning (C3).
- **Test families:**
  - ID lookup (generated deterministically from metadata)
  - natural-language factual questions, with answers verified against source spans
  - applicability: real (c) paragraphs, plus synthetic boundary cases labelled `synthetic`
  - revision and withdrawal
  - refusal and adversarial cases (the 16 from §3.6)
- **Metrics:**
  - Recall@5 and MRR
  - exact-ID accuracy
  - citation validity
  - unsupported-claim rate
  - applicability and revision accuracy
  - abstention precision and recall
  - p50/p95 latency, with retrieval measured separately from generation
- Every metric is reported with its denominator.

## 9. Stack
- **Backend:** FastAPI + Pydantic, SQLite/FTS5, PyMuPDF, lxml, sentence-transformers (CPU/MPS), anthropic SDK, pytest.
- **Frontend:** Next.js + TypeScript + Tailwind, with pdf.js for the source PDF opened at the cited page (text-layer highlight).
- **Reproducibility:** pinned `requirements.txt` and `package-lock.json`; `scripts/reproduce.sh` verifies the snapshot and source hashes.

## 10. Options needing approval
- **O1:** query the FR API for *final rules* sharing each docket. This is public and authoritative data, but it is outside the organiser's sheet. It would let revision status say "final rule published (FR doc Y)" instead of UNKNOWN.
- **O2:** send retrieved FR passages (public US government text) to the Claude API for generation and optional rule-candidate extraction.
- **O3:** download a local embedding model from HuggingFace (about 130 MB, MIT licence).
