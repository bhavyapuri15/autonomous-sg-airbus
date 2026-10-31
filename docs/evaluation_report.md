# Evaluation report

Sources: `evaluation/results/20261031-124158_dev.json` (first dev baseline, commit `8c49bae`), `20261031-125924_dev.json` (final dev, commit `8d46ef3`), `20261031-130856_locked.json` (locked, commit `f788c5c`). Methodology: `docs/evaluation_spec.md`, `evaluation/README.md`. All rates are as stored in the result files. The tables in section 3 are generated directly from those files; per-case failure notes in section 5 come from `notes/evaluation_results.md`, which describes the **baseline** run and not the final one.

## 1. Protocol and what each run is
- **Split.** Docket-group split: dev 305 docs / 314 rows / 237 groups; locked 115 docs / 117 rows / 83 groups. The locked manifest (`evaluation/LOCKED_MANIFEST.sha256`) was committed before retrieval or answer tuning.
- **Locked run.** Approved once, with the system frozen at commit `8d46ef3`. It crashed three times on evaluator bugs and was re-run after three evaluator-only fixes (`4db3468` dict-form alternates in F2 gold; `6b4d4df` and `846b759` forward `--final` to the latency worker). No system code changed. A further evaluator commit (`c9731b8`) prevents calibration from ever running on locked.
- **Locked has no F6 revision cases**, and the F8 adversarial scenarios in the locked run use dev directives (16 of 16, same scenarios). F8 is therefore not held out.
- **Dev is tuned.** The final-dev F1 = 1.0 came after router fixes made for the baseline failures, and the F7 dev scores follow a threshold calibration on the same dev data.
- **Case provenance.** F2/F3 questions were written by a Claude Sonnet agent from corpus passages (trigram overlap with the passage at most 0.35) and checked for answerability by the author only. 42/36 F2 questions and 20/19 F3 questions are small samples; one case moves F3 by 5 points.
- **F7 sample.** The "answerable" negatives for precision are the same dev/locked F3 cases (non-LLM). F7 is mostly synthetic (dev 24 of 30; locked 21 of 24).
- **F3 LLM** runs use `claude-sonnet-5-5` as quote selector. Each LLM figure is from a single run; run-to-run variation was not measured.

## 2. Headline summary
| Metric | Baseline dev | Final dev | Locked |
|---|---|---|---|
| F1 acc@1 (n) | 0.9556 (1125) | 1.0 (1125) | 0.9952 (414) |
| F2 doc R@5 / MRR@10 / chunk R@5 (n) | 0.8333 / 0.6955 / 0.7143 (42) | same | 0.8056 / 0.6871 / 0.5556 (36) |
| F3 accuracy extractive / LLM (n) | 0.25 / 0.3 (20) | 0.3 / 0.75 (20) | 0.2105 / 0.5789 (19) |
| F6 accuracy / false-VERIFIED (n) | 1.0 / 0 (20) | 1.0 / 0 (20) | no cases |
| F7 P / R / F1 (n) | 0.8286 / 0.9667 / 0.8923 (50) | 0.9375 / 1.0 / 0.9677 (50) | 0.92 / 0.9583 / 0.9388 (43) |
| F8 pass | 16/16 | 16/16 | 16/16 (dev directives) |

## 3. Full tables (generated from the three result files; values copied as stored)

### F1 exact-ID lookup (acc@1 / acc@5)
| Kind | Baseline dev (n) | Final dev (n) | Locked (n) |
| --- | --- | --- | --- |
| **All** | 0.9556 / 0.9787 (1125) | 1.0 / 1.0 (1125) | 0.9952 / 1.0 (414) |
| docnum | 1.0 / 1.0 (305) | 1.0 / 1.0 (305) | 1.0 / 1.0 (115) |
| citation_start | 1.0 / 1.0 (291) | 1.0 / 1.0 (291) | 1.0 / 1.0 (102) |
| citation_mid | 1.0 / 1.0 (142) | 1.0 / 1.0 (142) | 1.0 / 1.0 (47) |
| docket_exact | 0.9872 / 1.0 (235) | 1.0 / 1.0 (235) | 0.9882 / 1.0 (85) |
| docket_variant | 0.6908 / 0.8421 (152) | 1.0 / 1.0 (152) | 0.9846 / 1.0 (65) |

### F2 natural-language retrieval (doc R@5 / doc MRR@10 / chunk R@5)
| Category | Baseline dev (n) | Final dev (n) | Locked (n) |
| --- | --- | --- | --- |
| **All** | 0.8333 / 0.6955 / 0.7143 (42) | 0.8333 / 0.6955 / 0.7143 (42) | 0.8056 / 0.6871 / 0.5556 (36) |
| APPL | 0.6923 / 0.559 / 0.5385 (13) | 0.6923 / 0.559 / 0.5385 (13) | 0.4444 / 0.3007 / 0.1111 (9) |
| ACTIONS | 0.6667 / 0.331 / 0.5 (6) | 0.6667 / 0.331 / 0.5 (6) | 0.6667 / 0.713 / 0.5 (6) |
| SUMMARY | 0.6667 / 0.4861 / 0.3333 (3) | 0.6667 / 0.4861 / 0.3333 (3) | 1.0 / 1.0 / 1.0 (2) |
| DISC | 1.0 / 1.0 / 1.0 (6) | 1.0 / 1.0 / 1.0 (6) | no cases |
| PARTS | 1.0 / 0.8333 / 1.0 (3) | 1.0 / 0.8333 / 1.0 (3) | 1.0 / 0.75 / 1.0 (2) |
| UNSAFE | 1.0 / 0.875 / 0.75 (4) | 1.0 / 0.875 / 0.75 (4) | 1.0 / 0.725 / 0.6 (10) |
| WITHDRAW | 1.0 / 0.9286 / 1.0 (7) | 1.0 / 0.9286 / 1.0 (7) | 1.0 / 1.0 / 0.8571 (7) |

F2 numbers are identical in the two dev runs. Locked categories: no DISC cases.

### F3 grounded answers
| Measure | Baseline dev | Final dev | Locked |
| --- | --- | --- | --- |
| extractive: n | 20 | 20 | 19 |
| extractive: answer accuracy (correct/n) | 0.25 (5/20) | 0.3 (6/20) | 0.2105 (4/19) |
| extractive: status distribution | {"NEEDS_MORE_INFORMATION": 5, "ANSWERED": 14, "ABSTAINED": 1} | {"ANSWERED": 18, "ABSTAINED": 2} | {"ABSTAINED": 2, "ANSWERED": 17} |
| extractive: citation validity (valid/checked) | 1.0 (36/36) | 1.0 (90/90) | 1.0 (109/109) |
| extractive: claims generated / verified / rejected | 43 / 36 / 7 | 42 / 42 / 0 | 33 / 33 / 0 |
| extractive: generation modes | {"none": 5, "extractive": 15} | {"extractive": 20} | {"none": 1, "extractive": 18} |
| llm: n | 20 | 20 | 19 |
| llm: answer accuracy (correct/n) | 0.3 (6/20) | 0.75 (15/20) | 0.5789 (11/19) |
| llm: status distribution | {"NEEDS_MORE_INFORMATION": 5, "ABSTAINED": 9, "ANSWERED": 6} | {"ANSWERED": 17, "ABSTAINED": 3} | {"ABSTAINED": 4, "ANSWERED": 15} |
| llm: citation validity (valid/checked) | 1.0 (8/8) | 1.0 (72/72) | 1.0 (79/79) |
| llm: claims generated / verified / rejected | 18 / 8 / 10 | 23 / 23 / 0 | 18 / 17 / 1 |
| llm: generation modes | {"none": 5, "llm": 15} | {"llm": 20} | {"none": 1, "llm": 18} |

Baseline LLM run: 5 of the 20 cases never reached generation (`generation_modes`: none 5), which depressed that baseline figure.

### F6 revision status
| Measure | Baseline dev | Final dev | Locked |
| --- | --- | --- | --- |
| n | 20 | 20 | 0 |
| status accuracy | 1.0 | 1.0 | no cases |
| false-VERIFIED count | 0 | 0 | no cases |
| current_authoritative_status_verified false in | 20/20 | 20/20 | 0/0 |

| F6 kind (dev) | n | status_ok | edge_ok |
| --- | --- | --- | --- |
| withdrawn_nprm | 4 | 4 | 4 |
| withdrawal_doc | 4 | 4 | 4 |
| finalized_nprm | 4 | 4 | 4 |
| supplemented_nprm | 4 | 4 | 4 |
| no_evidence | 3 | 3 | 3 |
| proposes_to_supersede | 1 | 1 | 1 |

### F7 abstention
| Measure | Baseline dev | Final dev | Locked |
| --- | --- | --- | --- |
| refusal cases / answerable sample | 30 / 20 | 30 / 20 | 24 / 19 |
| tp / fp / fn / tn | 29 / 6 / 1 / 14 | 30 / 2 / 0 / 18 | 23 / 2 / 1 / 17 |
| precision | 0.8286 | 0.9375 | 0.92 |
| recall | 0.9667 | 1.0 | 0.9583 |
| f1 | 0.8923 | 0.9677 | 0.9388 |
| status exact accuracy | 0.9333 | 1.0 | 0.9583 |
| status + reason accuracy | 0.8667 | 1.0 | 0.9167 |

| F7 by reason (status_ok / reason_ok of n) | Baseline dev | Final dev | Locked |
| --- | --- | --- | --- |
| NOT_IN_CORPUS | 9 / 9 of 9 | 9 / 9 of 9 | 9 / 9 of 9 |
| NEAR_MISS_ID | 4 / 4 of 4 | 4 / 4 of 4 | 4 / 4 of 4 |
| METADATA_ONLY | 3 / 3 of 3 | 3 / 3 of 3 | no cases |
| MISSING_MODEL | 3 / 1 of 3 | 3 / 3 of 3 | 3 / 2 of 3 |
| UNSUPPORTED_COMPARISON | 3 / 3 of 3 | 3 / 3 of 3 | 2 / 2 of 2 |
| PROCEDURE_OR_SIGNOFF | 3 / 3 of 3 | 3 / 3 of 3 | 2 / 2 of 2 |
| OUT_OF_DOMAIN | 3 / 3 of 3 | 3 / 3 of 3 | 2 / 2 of 2 |
| AMBIGUOUS_DIRECTIVES | 0 / 0 of 2 | 2 / 2 of 2 | 1 / 1 of 2 |

### F8 adversarial scenarios
| Run | n | passed | failed | blocked |
| --- | --- | --- | --- | --- |
| Baseline dev | 16 | 16 | 0 | 0 |
| Final dev | 16 | 16 | 0 | 0 |
| Locked (dev directives) | 16 | 16 | 0 | 0 |

Scenarios (final dev): F8-01-serial-lower-bound; F8-02-serial-upper-bound; F8-03-serial-outside-range; F8-04-serial-explicit-exclusion; F8-05-wrong-model; F8-06-missing-model; F8-07-missing-serial; F8-08-conflicting-metadata; F8-09-unavailable-source; F8-10-nonexistent-directive; F8-11-multiple-revisions; F8-12-unknown-current-revision; F8-13-unsupported-technical-request; F8-14-ambiguous-question; F8-15-prompt-injection-in-source; F8-16-similar-identifiers.

### Latency (ms) and index size
| Measure | Baseline dev | Final dev | Locked |
| --- | --- | --- | --- |
| search() warm p50 / p95 / max | 10.65 / 15.55 / 18.74 (n=96) | 11.23 / 16.64 / 19.94 (n=96) | 9.35 / 14.85 / 19.25 (n=84) |
| search() cold first pass p50 / p95 / max | 11.68 / 16.89 / 466.83 (n=48) | 11.41 / 18.23 / 565.4 (n=48) | 9.99 / 14.99 / 439.77 (n=42) |
| search() cold first call | 466.83 ms | 565.4 ms | 439.77 ms |
| answer() warm p50 / p95 / max | 28.8 / 38.69 / 43.57 (n=96) | 29.48 / 42.31 / 79.43 (n=96) | 21.95 / 36.99 / 38.87 (n=84) |
| answer() cold first pass p50 / p95 / max | 32.91 / 60.13 / 383.49 (n=48) | 29.76 / 43.6 / 911.87 (n=48) | 22.94 / 39.83 / 841.26 (n=42) |
| answer() cold first call | 24.91 ms | 25.46 ms | 841.26 ms |
| queries | 48 | 48 | 42 |

Index: 13513 chunks, 1596 pages, 495 documents, embeddings 20.76 MB, ad.sqlite 35.6 MB, search.sqlite 34.5 MB. `answer()` is called with `use_llm=False`, so no LLM time is included. Cold = fresh process; warm = passes 2-3 over the same queries. The notes caveat that the baseline cold first answer() call (24.91 ms) was not investigated; use the first-pass column. Latency was measured on a single development machine.

### Calibration of the abstention threshold (dev only; never run on locked)
`MIN_TOP_DENSE_COSINE = 0.684`. Answerable dev F2 queries (n=42): min 0.686, p5 0.7, median 0.75, p95 0.81, max 0.8356. Gate-dependent refusals (n=9): min 0.4981, median 0.68, max 0.7333. Out-of-domain only (n=3): 0.4981, 0.51, 0.63. Chosen t = 0.6838 (answerable recall 1.0, precision 1.0, recall 0.6667, F1 0.8).
The threshold sits 0.002 below the lowest dev answerable cosine, so it is tight and fitted to n=42 / n=9. The three UNSUPPORTED/PROCEDURE cosines overlap the answerable range and are mostly caught by regex rules, not the gate. The threshold is the same in all three runs; the locked run did not recalibrate it.
## 4. Reading the results
- **F1.** Docket-variant forms (lowercase, spaces, bare numbers) were the weak point at baseline (0.6908 @1). After the router fix (`cb83a3f`) dev reached 1.0; locked docket_variant is 0.9846 (n=65) and docket_exact 0.9882 (n=85). The two locked misses (`F1-04-11705-docket_exact`, `...docket_variant`, query "S. 2002-CE-05-AD") put another member of the same docket group first; the expected document was within the top 5 (acc@5 = 1.0).
- **F2.** Retrieval did not change between the dev runs and degrades on locked, most visibly for Applicability questions (locked APPL doc R@5 0.4444, chunk R@5 0.1111, n=9; dev APPL 0.6923, 0.5385, n=13). Short "(c) Applicability" chunks rank below longer preamble chunks of similar Airbus/Boeing proposals.
- **F3.** Citation validity is 1.0 in every run, but answer accuracy is modest. The extractive mode is weak at selecting the right sentence. The LLM mode selects better (dev 0.75, locked 0.5789) because it picks verbatim quotes that the verifier then checks. The dev to locked drop (LLM 0.75 to 0.5789; extractive 0.3 to 0.2105) is the honest generalisation estimate, with n=19 to 20 and wide uncertainty.
- **F6.** 20 of 20 on dev, 0 false-VERIFIED, and `current_authoritative_status_verified` is false in 20 of 20. Expectations were read from document text, not from the relations table. There is no locked F6 evidence.
- **F7.** Dev recall 1.0 and status+reason 1.0 are on tuned data (threshold 0.684 calibrated on 42 answerable and 9 refusal queries). Locked: recall 0.9583 (23/24 refusals), precision 0.92 (2 false abstentions on answerable cases: `F3-locked-002` NO_SUPPORTING_EVIDENCE, `F3-locked-020` NO_VERIFIED_CLAIMS). Locked misses: `F7-locked-23-AMBIGUOUS_DIRECTIVES` (a comparison question was ANSWERED) and `F7-locked-15-MISSING_MODEL` (right status, reason DIRECTIVE_AMBIGUOUS instead of MISSING_MODEL).
- **F8.** 16 of 16 in all runs; scenarios are hand-built, and locked reuses dev directives. The baseline note records that F8-08 (conflicting metadata) passed only because both sheet rows were exposed, with no warning; the later commit `b4e296b` added a sheet-vs-FR conflict warning (not re-measured separately).

## 5. Failure analysis
From `notes/evaluation_results.md` (baseline dev run; several items were addressed by later commits, see section 6; the final-dev failure lists are in the result file).
1. **F3 ambiguity (5 cases, baseline):** factual questions classified as applicability with no directive given and more than one candidate gave NEEDS_MORE_INFORMATION/DIRECTIVE_AMBIGUOUS. Commit `b4e296b` added factual-vs-applicability intent routing; in the final dev run the extractive status distribution is ANSWERED 18, ABSTAINED 2.
2. **Verifier cost on the right answer (baseline):** the correct sentence for `F3-dev-010` was rejected (`V6_ORDER_MISMATCH:0.75`). The V6 order check was later fixed (greedy forward alignment). `F3-dev-010` and `F3-dev-021` are still false abstentions (NO_VERIFIED_CLAIMS) in final dev.
3. **Extractive sentence selection:** the answer is often in the right document but the wrong sentence is chosen (gold spans that are EASA / Transport Canada AD references or unsafe-condition phrases). Final-dev extractive failures: 14 of 20 cases.
4. **LLM mode baseline:** 10 of 18 LLM claims were rejected (V6/V7/V5), leaving 9 of 20 cases ABSTAINED. Final dev: 23 generated, 23 verified, 0 rejected; locked: 18 generated, 17 verified, 1 rejected (`V7_RESERVED_TOPIC`).
5. **F2 Applicability misses:** see section 4.
6. **F2 chunk-level misses with the right document retrieved:** the wrong section ranks first (dev chunk R@5 0.7143 vs doc R@5 0.8333; locked 0.5556 vs 0.8056).
7. **F7 baseline misses:** MISSING_MODEL cases reported DIRECTIVE_AMBIGUOUS when the docket maps to several documents. A comparison question ("Airbus vs Boeing proposal") was ANSWERED at baseline (dev, fixed); a similar one is ANSWERED in locked.
8. **F6 limitation:** `01-10467` is SUPPLEMENTED; a later withdrawal of the follow-on SNPRM appears only through `latest_in_dataset`. Commit `c19b519` added reporting of successor-proposal outcomes (withdrawn or finalized) along VERIFIED SUPPLEMENTS chains. The status of the original document is unchanged by design.

## 6. Opus review findings and the fixes they led to
These come from the commit messages in `git log`. Each fix is described as stated there; the effect on the final metrics is only what the result files show.

| Commit | Review finding | Fix |
|---|---|---|
| `e872319` | Verifier false accepts: an added unsupported action and a role swap; a V7 paraphrase gap ("covers ... models") | Added V6 unsupported-word check, V6 order agreement, V7 "covers" pattern, regression tests. 55/55 tests pass (at that commit). |
| `77a2771` | Applicability engine audit: hand audit of 12 random FULL parses (all faithful); 18 adversarial probes incl. range exclusions, "does not apply", "other than", model exclusions (all safe). Decision on external references | External references ("as identified in EASA AD X") are treated as an unknown AND-condition: unlisted models are a definite NOT_APPLICABLE, while listed models stay UNKNOWN pending the external document. Rule coverage: 221 FULL / 91 PARTIAL / 39 FAILED (non-FULL is always UNKNOWN). |
| `cb83a3f` | Router: docket variants and bare FAA dockets failed; review found prose such as "737 max 8" could be detected as a docket | Docket variants, bare FAA dockets and group ordering added. Legacy dockets now require a real FAA directorate code, and non-hyphenated forms need an AD suffix. Dev F1 acc@1 0.956 to 1.000 (n=1125), docket_variant 0.691 to 1.000. |
| `b4e296b` | Pipeline and verifier quality issues in dev | Directive-scoped queries bypass the corpus relevance gate; intent routing (factual vs applicability); LLM used as a verbatim quote selector; IDF sentence selection; comparison/ambiguity gives NEEDS_MORE_INFORMATION; sheet-vs-FR conflict warning. V6 order check used the first occurrence of repeated words (identical text scored 0.75), so it became greedy forward alignment. V7 now allows verbatim source excerpts on applicability/revision/finality topics but still blocks paraphrases and all current-status wording. |
| `3b2b5ae` | Opus claim review (dev): 14 of 20 extractive answers mixed sentences from different directives; 5 claims were header/closing boilerplate | Corpus-wide answers use one directive (rank order, at most 3 tried), show its revision status and list other matches as candidates. **Measured trade-off (dev F3, n=20): extractive answer accuracy 0.50 to 0.30; LLM 0.75 to 0.75; mixing 14/20 to 0.** Interpretation (ours, not separately measured): the earlier higher extractive number likely included credit for answers mixing several directives; the change was accepted for correctness of scoping. Intermediate run: `20261031-125418_dev.json` (0.5 / 0.75). |
| `c19b519` | Dev F8-11: NPRM to SNPRM to SNPRM to withdrawal showed only SUPPLEMENTED | Revision outcomes of successor proposals are reported along VERIFIED SUPPLEMENTS chains. Status of the original doc is unchanged; text and overlay say so. |
| `1a11cbb` | Independent audit of the revision graph | 247 VERIFIED edges, each with citation/date evidence; audit found 0 problems (as stated in the commit message). |

Final F3 extractive dev accuracy (0.3, 6/20) is above the 0.25 baseline but below the 0.50 intermediate; the report keeps the 0.30 figure.

## 7. Impact benchmark (F9)
**Pending: manual arm not yet run.** `evaluation/impact_tasks.md` defines eight dev-split tasks, the protocol (manual federalregister.gov arm vs assisted UI arm; time, correctness, steps) and a blank results table. No results are recorded. If it is run by a single person, it is anecdotal and will be reported as such.

## 8. Not evaluated
- Organiser-index families F10-F13 are added (dev results in `evaluation/results/20261031-132953_dev.json`); their locked split has not been run.
- Frontend behaviour beyond unit tests (`vitest`).
- Latency under concurrent load, and on other hardware.


## 9. Corpus fix after these runs (31 Oct, after the F10-F13 dev run)
F11 (revision chains) found that legacy withdrawal rows linking the withdrawn NPRM's URL first were mapped to the NPRM's FR document. The resolver now accepts a linked document only when its publication date is within 3 days of the row's publish date (and, for other URLs in the cell, its docket matches). 12 rows were re-resolved to their withdrawal notices; organiser FR documents went 420 -> 428 and shared-document rows 16 -> 0. The four withdrawn NPRMs that have no sheet row of their own left the corpus.

All results in sections 2-7 were measured on the pre-fix corpus and are left as recorded. Dev re-run on the fixed corpus with the **unchanged, frozen case files** (`--no-write`):

| Family | Before (n) | After (n) |
|---|---|---|
| F11 revision chain status | 0.9635 (192) | 1.0 (192) |
| F1 exact-ID acc@1 | 1.0 (1125) | 0.9929 (1125) |
| F12 stage accuracy | 1.0 (304) | 0.9934 (304) |
| F6 revision status | 1.0 (20) | 1.0 (20) |

All 10 F1/F12 misses are cases whose frozen gold names one of the two removed NPRM documents (2019-14901, 2022-20442); their docket queries now return the withdrawal notice. The case files and locked manifests were not regenerated at that point; they were regenerated afterwards, see 9.1. F8-08 (conflicting metadata) was built on the mis-mapped 2018-12886, whose two-row conflict was the bug itself; it now targets 2016-05517 (sheet pages 29148-29149 vs FR 81 FR 13303) and passes (F8 16/16). F2, F3, F7, F10, F13 and latency are unchanged on the fixed corpus.

### 9.1 Case files regenerated for the fixed corpus (31 Oct)
The case generators were re-run against the fixed corpus (`generate_cases.py --manifest`, `generate_update_cases.py --manifest`)
and both locked manifests were rewritten. This is a gold correction, not tuning: gold still comes only from the organiser sheet and
the FR documents, never from system output, and **the locked split was not re-run** (the locked results in this report remain the
pre-fix runs). What changed, with case ids ignored (ids are sequential, so insertions renumber later cases):

- Partition: no existing document changed split or docket group. 4 documents left the corpus (the mis-mapped shared NPRMs) and 12 joined
  it (the re-resolved withdrawal notices and the documents they replaced); each was assigned by the same hashed docket-group rule.
- F1: cases on the 4 removed documents dropped, cases on the 12 new ones added (dev 1125 -> 1142, locked 414 -> 421); a docket query
  now also accepts the withdrawal notice filed under the same docket.
- F2/F3 locked: one passage (F2/F3-locked-013) gains an alternate, because the same SUMMARY text also appears in the newly mapped withdrawal
  notice 2021-11813. Questions and answer spans are unchanged.
- F10: only additions, for records that previously had no FR document (dev 492 -> 516, locked 188 -> 200).
- F12: 2 proposed-rule stage cases on removed documents replaced by withdrawal-notice cases (dev 342 -> 348, locked 118 -> 120).
- F6 (hand-written, dev): F6-dev-19 targeted 2019-14901, which left the corpus when NPRM-205 was mapped to its own withdrawal notice
  2020-06503. Repointed to 2026-21298 (NPRM-002), the most recent dev organiser NPRM meeting the same no-evidence criteria, checked
  against the document text.
- F7, F11, F13 and all locked F7 cases are byte-identical.
- `generate_cases.py --manifest` now hashes only its own families (F1, F2, F3, F7 plus the split map); F10-F13 stay in
  `LOCKED_MANIFEST_UPDATE.sha256`.

Dev run on the regenerated cases (`evaluation/results/20261031-161448_dev.json`):

| Family | Frozen cases, fixed corpus (n) | Regenerated cases (n) |
|---|---|---|
| F1 exact-ID acc@1 | 0.9929 (1125) | 1.0 (1142) |
| F12 stage accuracy | 0.9934 (304) | 1.0 (310) |
| F10 record-ID acc@1 | 1.0 (492) | 0.9942 (513) |
| F2 doc Recall@5 / MRR@10 | 0.8333 / 0.6952 (42) | 0.8333 / 0.6952 (42) |
| F3 citation validity | 1.0 (90 citations) | 1.0 (90 citations) |
| F6, F11, F13 | 1.0 | 1.0 |
| F7 abstention F1 | 0.9677 | 0.9677 |
| F8 | 16/16 | 16/16 |

The 3 F10 misses are all NPRM-180 (canonical, unpadded and question forms). Its gold is parsed from the organiser link, which points to
2021-13636, an NPRM on a different docket; the row's own docket and publish date identify 2021-13482, which the system returns. Before the
fix this case scored 1.0 because the mis-mapping agreed with the bad link. The gold was not edited to match the system.
