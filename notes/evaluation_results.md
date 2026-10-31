# Evaluation results (dev split only; locked set untouched)

Source: `evaluation/results/20261031-124158_dev.json` (= `latest_dev.json`). Command: `.venv/bin/python evaluation/evaluate.py --split dev --use-llm`.
Pipeline run with `MIN_TOP_DENSE_COSINE=0.684` (calibrated below; was 0.60). Extractive (no LLM) everywhere except the F3 LLM row. All rates are k/n, no rounding up.

| Metric | Value | n |
|---|---|---|
| F1 exact-ID accuracy@1 / @5 | 0.9556 / 0.9787 | 1125 |
| F1 by kind @1 (@5): docnum | 1.0 (1.0) | 305 |
| citation_start / citation_mid | 1.0 (1.0) / 1.0 (1.0) | 291 / 142 |
| docket_exact | 0.9872 (1.0) | 235 |
| docket_variant | 0.6908 (0.8421) | 152 |
| F2 doc-level Recall@5 / MRR@10 | 0.8333 / 0.6955 | 42 |
| F2 chunk-level Recall@5 (span overlap) | 0.7143 | 42 |
| F2 doc R@5 by category | APPL 0.6923 (13), ACTIONS 0.6667 (6), SUMMARY 0.6667 (3), DISC 1.0 (6), PARTS 1.0 (3), UNSAFE 1.0 (4), WITHDRAW 1.0 (7) | 42 |
| F3 answer accuracy, extractive | 0.25 (5/20) | 20 |
| F3 answer accuracy, LLM (separate run, 15 LLM calls; 5 cases never reached generation) | 0.30 (6/20) | 20 |
| F3 status extractive | ANSWERED 14, NEEDS_MORE_INFORMATION 5, ABSTAINED 1 | 20 |
| F3 status LLM | ANSWERED 6, ABSTAINED 9, NEEDS_MORE_INFORMATION 5 | 20 |
| F3 citation validity (quote == doc_text[start:end] and fr_page in section range), extractive / LLM | 1.0 (36/36) / 1.0 (8/8) | 36 / 8 citations |
| F3 claims generated / verified / rejected, extractive | 43 / 36 / 7 | 43 |
| F3 claims generated / verified / rejected, LLM | 18 / 8 / 10 | 18 |
| F6 status accuracy | 1.0 (20/20) | 20 |
| F6 false-VERIFIED count; `current_authoritative_status_verified` false in | 0; 20/20 | 20 |
| F7 abstention precision / recall / F1 (positive = ABSTAINED or NEEDS_MORE_INFORMATION) | 0.8286 / 0.9667 / 0.8923 (tp 29, fp 6, fn 1, tn 14) | 30 refusal + 20 answerable |
| F7 status exact / status+reason | 0.9333 / 0.8667 | 30 |
| F8 adversarial | 16 pass, 0 fail, 0 blocked | 16 |
| Latency search() warm p50/p95/max (ms) | 10.65 / 15.55 / 18.74 | 96 calls (48 queries x 2 passes) |
| Latency search() cold: first call; first pass p50/p95/max | 466.83 ms; 11.68 / 16.89 / 466.83 | 1; 48 |
| Latency answer(use_llm=False) warm p50/p95/max | 28.8 / 38.69 / 43.57 | 96 |
| Latency answer() cold: first call; first pass p50/p95/max | 24.91 ms (see caveat); 32.91 / 60.13 / 383.49 | 1; 48 |
| Index | 13513 chunks, 1596 pages, 495 documents, embeddings 20.76 MB, ad.sqlite 35.6 MB, search.sqlite 34.5 MB | |

Latency queries: the 42 dev F2 questions + 6 F1 queries. Cold = fresh subprocess; warm = passes 2-3 over the same queries. Caveat: the cold first
answer() call (24.91 ms) is lower than the first search() call; I did not investigate why, so treat "cold" answer numbers by the first-pass column.

## F7 reason-code mapping (case file -> accepted pipeline reason)
NOT_IN_CORPUS, NEAR_MISS_ID -> DIRECTIVE_NOT_FOUND; METADATA_ONLY -> SOURCE_TEXT_UNAVAILABLE; MISSING_MODEL -> MISSING_MODEL;
UNSUPPORTED_COMPARISON -> UNSUPPORTED_QUESTION; PROCEDURE_OR_SIGNOFF -> COMPLIANCE_DETERMINATION_OUT_OF_SCOPE | UNSUPPORTED_QUESTION | NO_SUPPORTING_EVIDENCE;
OUT_OF_DOMAIN -> NO_SUPPORTING_EVIDENCE | UNSUPPORTED_QUESTION; AMBIGUOUS_DIRECTIVES -> DIRECTIVE_AMBIGUOUS. Status is scored first, reason second.
The answerable "negatives" for precision are the same 20 dev F3 cases (non-LLM).

## Abstention threshold calibration (dev only)
Top-hit `dense_cosine` (max over top-8 hits, as in the pipeline gate). Answerable = 42 dev F2 queries: min 0.686, p5 0.70, median 0.75, p95 0.81, max 0.836.
Refusals that depend on the gate = 9 dev F7 OUT_OF_DOMAIN / UNSUPPORTED_COMPARISON / PROCEDURE_OR_SIGNOFF: min 0.498, median 0.68, max 0.733
(OOD alone, n=3: 0.498, 0.511, 0.630). Sweep (midpoints between observed values), constraint answerable recall >= 95%: best abstention F1 = 0.80
(precision 1.0, recall 0.6667, answerable recall 1.0) at t = 0.6838; set `MIN_TOP_DENSE_COSINE = 0.684` (any value in (0.6817, 0.686] gives the same dev decisions).
Honest caveats: answerable min is 0.686, so the threshold sits 0.002 below the lowest dev answerable cosine, i.e. it is tight and fitted to n=42/n=9; the 3
UNSUPPORTED/PROCEDURE cosines (0.67-0.73) overlap the answerable range and are mostly caught by regex rules rather than the gate.
Before/after (threshold 0.60 -> 0.684): F3 extractive unchanged (answer acc 0.25, 36/36 valid citations, same status distribution);
F7 precision 0.8182 -> 0.8286, recall 0.9 -> 0.9667, F1 0.8571 -> 0.8923, status+reason 0.80 -> 0.8667 (n=30, 20).

## F6 / F8 notes
F6: 20 hand-verified dev cases (4 withdrawn NPRMs, 4 withdrawal notices, 4 finalized NPRMs, 4 supplemented, 3 no-evidence, 1 PROPOSES_TO_SUPERSEDE); evidence quote in each case's notes.
Expectations were read from document text, not from the relations table. Limitation: 01-10467 (supplemented by 03-6506, whose follow-on SNPRM 05-1795 was withdrawn by E8-1706 in 2008)
reports SUPPLEMENTED; the later withdrawal appears only via `latest_in_dataset=E8-1706`, not as a status (F8-11 passes on that basis).
F8: all 16 pass, but F8-08 (conflicting metadata) passes only because both sheet rows (181, 214) are exposed in `directive.sheet_rows`; the pipeline emits NO warning about the
sheet date/page conflict (warnings=[]). F8-15 ran on a synthetic in-memory chunk copy (marker flagged; extractive 0 leaked; forged claim rejected V5_POLARITY_MISMATCH; LLM generated 0 claims).

## Top 10 failures and root causes (root causes are observations or labelled hypotheses)
1. F3-dev-002, 005, 008, 020, 032 (5 cases): NEEDS_MORE_INFORMATION/DIRECTIVE_AMBIGUOUS on factual questions. Phrases like "applies to"/"affected" set intent=applicability, no directive given, retrieval returns >1 candidate. Pipeline behaviour (not fixed).
2. F3-dev-010 (both modes): ABSTAINED/NO_VERIFIED_CLAIMS; extractive claim rejected V6_ORDER_MISMATCH:0.75, so the correct answer (a service bulletin reference) is dropped by the verifier.
3. F3-dev-003: ANSWERED but the claims are the header and the SB-exclusion sentence, not "except serial numbers 123, 130, and 131"; the extractive sentence splitter breaks at "[.;]" and the (c) paragraph is long.
4. F3-dev-012, 019, 021: gold span is an EASA/Transport Canada AD reference; extractive returns generic "The FAA proposes..." sentences (term overlap scoring) and correct sentences are rejected V6_ORDER_MISMATCH.
5. F3-dev-014, 016, 027, 038: answer is an unsafe-condition phrase; extractive picks other sentences from the right document (retrieval OK, sentence selection wrong); 038 candidate rejected V7_RESERVED_TOPIC.
6. F3 LLM mode: 10 of 18 LLM claims rejected (V6_UNSUPPORTED_WORDS, V6_LOW_COVERAGE, V7_RESERVED_TOPIC, V5_POLARITY_MISMATCH) leaving 9/20 ABSTAINED/NO_VERIFIED_CLAIMS; the verifier is stricter than the generator's paraphrases (conservative, but costs answer accuracy: 0.30).
7. F2-dev-001, 009, 012, 013 (APPL, doc miss): short "(c) Applicability" chunks rank below preamble/Summary chunks of other similar Airbus/Boeing NPRMs; query names a model list, dense similarity favours generic summaries.
8. F2 chunk-level misses with doc hit (004, 010, 014, 018, 029): right doc retrieved but a different section ranks first (chunk R@5 0.7143 vs doc 0.8333).
9. F1 docket_variant (47 of 152 miss @1): bare numbers like "2003-16645" (no FAA- prefix) and spaced "2000 NM 168 AD" resolve to the wrong/other doc; F1-01-13183-docket_exact ("99-NE-46") puts 00-11177 first (same-docket group, wrong member first).
10. F7-dev-18, 19: MISSING_MODEL expected, got DIRECTIVE_AMBIGUOUS (the docket maps to several documents, ambiguity checked before missing model); F7-dev-29: ABSTAINED/NO_SUPPORTING_EVIDENCE instead of NEEDS_MORE_INFORMATION (status mismatch); F7-dev-30 ("Airbus vs Boeing proposal") was ANSWERED (only false-negative abstention; scored a miss).
