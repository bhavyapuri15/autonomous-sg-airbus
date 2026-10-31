# Evaluation Methodology (Opus design, binding)

## 1. Splits (C3)
- **Unit of split:** the *docket group*, i.e. the connected component of documents sharing any docket. This keeps an NPRM and its withdrawal in the same split.
- **Rule:** `locked` if `int(sha256("airbus-c4-split|" + min(docket_norm)), 16) % 10 < 3` (≈30%); otherwise `dev`.
- **Locked-set storage:** the locked case files live in `evaluation/test_cases/locked/`. Their SHA256 manifest is written to `evaluation/LOCKED_MANIFEST.sha256` **before** any tuning and is committed.
- **Locked-set access:** tuning scripts refuse to read locked files (enforced by a guard in `evaluation/evaluate.py`; `--split locked` requires `--final` plus explicit user approval).
- **Reporting:** results always carry the split, case count and denominators.

## 2. Case families
Every case records `{id, family, split, provenance: real|synthetic, query, inputs, expected, gold_evidence[], notes}`.

| Family | Construction | Gold | Metric |
|---|---|---|---|
| F1 ID lookup | Deterministic from metadata: docket, FR docnum, FR citation, AD-number queries, incl. format variants ("FAA 2026-11814", lowercase) | Expected docnum(s) | Exact-ID accuracy@1 |
| F2 Natural-language retrieval | Questions written from the source text without copying the wording (e.g. "Which proposal addresses cracked tail rotor blades on AW139?"). LLM-drafted from a source passage, then **filtered**: the gold chunk must contain the answer (checked by the orchestrator/Opus on a sample). Each query is paraphrased away from the passage wording, with an overlap ratio check. | Gold chunk_id(s) and docnum | Recall@5, MRR@10 (doc-level and chunk-level) |
| F3 Grounded QA | A subset of F2 with a short factual answer span (compliance time, part number, unsafe condition) | Gold answer span | Answer accuracy (span match), citation validity, unsupported-claim rate |
| F4 Applicability, real | Real (c) paragraphs. Configs are built by the deterministic generator from the paragraph's own literals: inside, boundary, outside, excluded, wrong model, missing serial, missing fact. Gold labels are **hand-checked** by the Opus reviewer on every case, since the generator could share the parser's bugs. | APPLICABLE / NOT_APPLICABLE / UNKNOWN + missing | Accuracy; **unsafe-error count** (gold UNKNOWN or the opposite, predicted definitive); per-class confusion matrix |
| F5 Applicability, synthetic | The spec table §4 cases | — | Must be 100% |
| F6 Revision | Real withdrawal / SNPRM / final-rule links: expected status and edges | status + edge types | Accuracy; false-VERIFIED count (must be 0) |
| F7 Refusal | Nonexistent IDs, near-miss IDs, metadata-only records, missing config, unsupported/superlative questions, maintenance-procedure requests | ABSTAINED / NEEDS_MORE_INFORMATION | Abstention precision and recall |
| F8 Adversarial | 16 scenarios (prompt §3.6) incl. injected text in a *copied* chunk, similar IDs, conflicting metadata | Expected status/value | Pass/fail + severity |
| F9 Impact (A6) | 8 realistic tasks; manual baseline (FR website search + reading) vs the tool | Correct answer + time + steps | Median time and correctness, both arms |

## 3. Metrics
- **Retrieval:**
  - Recall@5 and MRR@10, chunk-level and doc-level, on F1 and F2.
  - Latency is measured on retrieval only (no LLM): p50/p95/max over ≥ 30 queries; warm and cold reported separately.
- **Grounding:**
  - *Citation validity* = verified citations / all citations shown. It must be 100%, because the verifier gates them.
  - *Unsupported-claim rate* = claims judged unsupported by an **independent** check / claims shown.
    - Check (a) is the deterministic V-checks.
    - Check (b) is an Opus-reviewed sample of ≥ 40 shown claims, labelled by hand against the quote.
    - Report check (b) as the honest estimate, with its denominator.
- **Answer accuracy (F3):** the gold span or value appears in a verified claim.
- **Applicability (F4/F5):** accuracy, the unsafe-error count (blocking if > 0) and UNKNOWN rate (coverage).
- **Revision (F6):** accuracy and false-VERIFIED count.
- **Abstention (F7/F8):** precision, recall, F1.
- **Reporting rule:** every number is reported with n. No metric may be described as "zero hallucination"; report the measured rate and the sample size.

## 4. Process
1. Generate the case files (dev + locked) with a script. Write the locked manifest and commit it.
2. Tune only on dev.
3. Run final eval on locked **once**, with user approval. Report both.
4. Each run saves `evaluation/results/{timestamp}_{split}.json`. These are append-only and never overwritten (C6).
5. `/evaluation/summary` serves the latest dev run and, if present, the final locked run, both labelled.
