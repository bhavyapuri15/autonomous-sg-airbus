# Evaluation dataset (first part: split, F1, F2, F3, F7, F9 protocol)

Binding spec: `docs/evaluation_spec.md`. Only documents with `source='organiser_sheet'` (420 docs, 431 sheet rows) are used.

## Split
`python evaluation/split.py` writes `test_cases/split_map.json` (docnum -> split + group key). Unit = docket group (union-find over
all normalised dockets of a doc and its sheet row). Docket keys drop a trailing `-W` (withdrawal) and `-AD`, so an NPRM and its
withdrawal stay together. Group key = min key in the group; `locked` iff `int(sha256("airbus-c4-split|"+key),16) % 10 < 3`.
Result: dev 305 docs / 314 rows / 237 groups; locked 115 docs / 117 rows / 83 groups. The 3 metadata-only rows are all in dev (so
locked F7 has no metadata-only cases). Deviation from spec wording: keys are normalised (no `-W`/`-AD`), otherwise withdrawals would split from their NPRMs.

## Files
`test_cases/{dev,locked}/f1_id_lookup.jsonl, f2_retrieval.jsonl, f3_grounded_qa.jsonl, f7_refusal.jsonl`; F4-F6, F8 are not in this part.
Case schema: `{id, family, split, provenance: real|synthetic, query, inputs{directive_id?,aircraft?}, expected{...}, gold_evidence[{fr_docnum, section_path, start_char, end_char}], notes}`.

## Counts
| family | dev (real/synthetic) | locked (real/synthetic) |
|---|---|---|
| F1 ID lookup | 1125 (1125/0) | 414 (414/0) |
| F2 NL retrieval | 42 (42/0) | 36 (36/0) |
| F3 grounded QA (subset of the F2 passages) | 20 (20/0) | 19 (19/0) |
| F7 refusal | 30 (6/24) | 24 (3/21) |

"real" = derived from real corpus records/text. F7 "synthetic" = invented or edited IDs and hand-written template questions.

## How the cases were made
- **F1** (deterministic, `generate_cases.py`): per doc up to 4 queries chosen by hash: docket exact, FR docnum, "{vol} FR {start_page}",
  and either a docket format variant (lowercase / spaces / bare number without `FAA-` only when unambiguous) or a mid-page citation for multi-page docs.
  Expected = every doc sharing the docket, or every doc whose page range contains the cited page. Citation queries whose page also holds a doc
  from the other split are skipped. Duplicate query strings are dropped.
- **F2/F3**: `select_passages.py` deterministically proposes a stratified candidate sample (Applicability, Unsafe Condition,
  Required Actions/Compliance, Parts Installation, SUMMARY, Discussion/Background, withdrawal text; modern/legacy balanced; one passage per doc where possible).
  The questions were then **written by hand by a Claude Sonnet agent** from each passage (not copying its wording; naming the product and
  publication date to be unambiguous) and stored in `sources/f2_{split}.jsonl`. These files are validated, never regenerated.
  Because of a time box the set is ~40 questions per split (not ~90): 42 dev / 36 locked, with 20 / 19 having an exact `answer_span` (F3).
  Not every stratum is filled equally (locked has few Parts Installation passages). Some passages are in sections that may be duplicated
  across NPRM/SNPRM of the same docket; such duplicates are recorded in `expected.alternates` when the answer span (F3) or identical text (F2) is found.
  Controls enforced in code: word-trigram overlap (share of question trigrams occurring in the passage) must be <= 0.35 (observed max 0.30 dev, 0.21 locked,
  mean ~0.05; stored in `expected.trigram_overlap`); gold = the whole passage section `{fr_docnum, section_path, start_char, end_char}`, asserted equal to `doc_text[start:end]`; every `answer_span` asserted an exact substring of it.
  Answerability from the passage alone was checked by the author only, not by an independent reviewer.
- **F7**: nonexistent docket / FR docnum / AD number (hash-generated, checked absent from all IDs and from every `doc_text`), 1-character near-miss
  edits of real IDs (checked absent), the 3 metadata-only rows, applicability questions with no model, superlative/comparison, sign-off / procedure,
  out-of-domain, ambiguous two-directive questions. `expected.status` is ABSTAINED or NEEDS_MORE_INFORMATION with `expected_reason_code`
  (NOT_IN_CORPUS, NEAR_MISS_ID, METADATA_ONLY, MISSING_MODEL, UNSUPPORTED_COMPARISON, PROCEDURE_OR_SIGNOFF, OUT_OF_DOMAIN, AMBIGUOUS_DIRECTIVES).
  The spec says sign-off requests may be ANSWERED-limited; here they are scored as ABSTAINED, adjust the scorer if the pipeline answers with a disclaimer.
- **F9**: `impact_tasks.md` (protocol and blank results table; no results recorded).

## Locked set discipline
`LOCKED_MANIFEST.sha256` holds the sha256 of each locked file and of `split_map.json`; tests verify it. `split.assert_not_locked(path, final=False)`
raises `PermissionError` for anything under `test_cases/locked/`; the future `evaluate.py` must call it before reading case files and may pass
`final=True` only for `--split locked --final` with user approval. Regenerating (`python evaluation/generate_cases.py --manifest`) rewrites the
manifest, so do not do that after tuning begins. Caveat: the author of the locked questions also saw dev passages and the corpus; the
locked questions were written before any retrieval tuning existed.

Tests: `.venv/bin/python -m pytest tests/test_eval_cases.py`.
