# Claim verification report (Task 2.8)

Files: `backend/verification/{normalize,citations,grounding}.py`, `tests/test_verification.py`.
All checks are deterministic (stdlib + pydantic). Order: V1..V8, then V9. First failure is reported.

| Check | Catches | Known blind spots |
|---|---|---|
| Normalization / V2 | Quote not a contiguous normalized substring (NFKC, curly quotes, dashes, zero-width/soft-hyphen removal, line-break de-hyphenation, whitespace, casefold). Offsets map back exactly to original `doc_text`. Word-boundary guard (quote cannot start/end mid-word). Cyrillic look-alikes do not match. | A quote that is literally present but taken out of context. Genuine compounds broken at a line end ("non-\nstructural") normalize to "nonstructural" and will not match "non-structural" (false reject). First occurrence is cited if the quote repeats. |
| V1 | `chunk_id` not in retrieved set (also every id in a union). SHEET_* tier chunks are rejected (technical claims never allowed). | Trusts the caller that `retrieved` is the true per-request set. |
| V3 | Quote < 6 words, unless a line-aligned table row containing " \| ". | A 6-word quote can still be unrepresentative. |
| V4 | Any claim identifier absent from the quote: tokens containing a digit with letters or `-/.` (P/N, serials, AD numbers, dockets, SB ids), numbers with units (value+unit, "three"=3, commas ignored), dates (format-independent), FR/CFR citations, `model_index` models. Token-boundary: "A320-214" vs "A320-21" fails both ways. | Identifiers with no digits (e.g. names); unit not in the lexicon is left to V8; plain numeric serials are only checked by V8. |
| V5 | Negator (not, no, never, none, except, unless, without, prohibited, cannot, n't, "other than"...) within +-5 tokens of a shared content word on one side but not the other; antonym pairs. Compared against the quote's whole enclosing sentence (so an "except..." after the quote is seen). | Negation by scope farther than 5 tokens, implicit negation ("fail to", "absence of"), antonyms outside the list, exceptions in a different sentence/paragraph. Strict symmetry causes some false rejects. |
| V6 | < 80% of claim content lemmas in the quote (union for two-quote claims); quantifiers/modals (all, every, always, must, never, only, any, each, required, mandatory, both, entire) must appear verbatim. Quantifier failures report `V6_LOW_COVERAGE:quantifier=<w>` (ratio otherwise). | Bag-of-words: word-order/role swaps ("A inspects B" vs "B inspects A"), 20% of unsupported words (one word in five), synonyms are false rejects. |
| V7 | Applicability, revision, supersession, withdrawal, finality, current-status wording (explicit regex lexicon in `RESERVED`; tested incl. false positives such as "revising the AFM" and "Service Bulletin ..., Revision 04"). Also rejects any claim whose quote contains prompt-injection markers (`V7_RESERVED_TOPIC:injection`). | Paraphrases outside the lexicon ("is covered"); "applicable" in benign procedural phrases is a false reject. Lexicon is English only. |
| V8 | Any claim number (digits, comma-thousands, decimals, written one..twenty, hundred/thousand/million) not in the quote. Zero-padded serials compared as strings. | Numbers carried by words beyond twenty; number semantics (what the number refers to). |
| V9 | Optional `judge(claim, quote)->bool`; runs only after V1-V8 pass; can only reject; judge exception = reject (fail closed). Orchestrator wires the LLM. | Judge is itself an LLM; not measured here. |

## Gates (`verify_answer`)
Dedupe (normalized text/quote), count generated/verified/rejected, warning when > 50% of unique claims are rejected, warning when any retrieved chunk contains injection markers (source text is never altered). `wrap_sources` escapes `& < >` (and quotes in ids).

## Honest limits
Deterministic checks verify that wording, identifiers, numbers and polarity are *traceable to a verbatim span*; they cannot verify meaning. Remaining unverifiable without V9 or a human: subtle relational errors (subject/object swap, wrong scope attached to a true fact), a faithful quote that is misleading out of its wider context (earlier paragraphs, tables, footnotes), implied conditions beyond the enclosing sentence, and semantic over-generalization using only words present in the quote. V9 adds an entailment second opinion that catches some of these but is probabilistic and can only reject. Offsets/pages are exact for the quote location; page resolution needs `page_spans` else falls back to the chunk's first page.

## Tests
`.venv/bin/pytest tests/test_verification.py -q`: 52 tests (pass cases, >=3 failure cases per check, adversarial, offset round-trip, determinism).
