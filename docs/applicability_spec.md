# Applicability Engine Specification (Opus design, binding for implementation)

Scope: deterministic extraction and evaluation of the "(c) Applicability" paragraph of FR AD documents (constraints C7; amendment A3).
**Safety principle:** a wrong APPLICABLE or NOT_APPLICABLE is a blocking defect. A wrong UNKNOWN is only a coverage loss.
When in doubt → UNKNOWN.

## 1. Rule representation

```
ApplicabilityRule
  fr_docnum, section_id, span: (start, end)          # offsets into doc_text
  doc_class                                          # from documents table
  product_kind: airplane|helicopter|rotorcraft|engine|propeller|appliance|glider|unknown
  make: Lit | null                                   # e.g. "Airbus Helicopters"
  clauses: [Clause]                                  # OR-combined (one per table row / enumerated item)
  global_conditions: [Condition]                     # AND-combined with every clause
  global_exclusions: [Condition]                     # rule applies only if NONE hold
  external_refs: [Lit]                               # e.g. "as identified in Service Bulletin X"
  benign: [Lit]                                      # recognised non-restrictive text, e.g. "certificated in any category"
  residue: [Lit]                                     # any text not consumed by the grammar
  parse_status: FULL | PARTIAL | FAILED
  parser_version: str

Clause
  models: [ModelRef] | ALL_MODELS_OF_MAKE
  serial: SerialSpec | ALL_SERIALS | NOT_STATED
  serial_subject: aircraft | component
  component: Lit | null                              # e.g. "auxiliary pumps P/N 782655-3"
  conditions: [Condition]                            # AND-combined, clause-local
  exclusions: [Condition]                            # clause-local

ModelRef    { value, span, normalized, is_series: bool, expanded_from_shorthand: bool, base_span }
SerialSpec  { ranges: [Range], list: [Serial], excluded: [Serial] }
Range       { lo: Serial|null, hi: Serial|null, lo_incl: bool|null, hi_incl: bool|null, span }
Serial      { raw, span, prefix, number: int|null, width, suffix }   # e.g. "28-7125001" → prefix "28-", number 7125001
Condition   { kind, values: [Lit], polarity: + | -, span, text }
  kind ∈ part_number_installed | modification_incorporated | service_bulletin_accomplished | free_text
Lit         { text, start, end }                      # doc_text[start:end] == text (verified)
```

Every `Lit`, `ModelRef`, `Serial` and `Range` stores offsets. The test suite asserts `doc_text[start:end] == text` for all of them.

## 2. Extraction grammar (deterministic)

1. **Locate the paragraph.** Take the section whose label is `(c)` and whose heading matches /Applicability/i, together with its sub-paragraphs and table.
   - If there is no such section, return `parse_status = FAILED` and evaluation returns UNKNOWN (reason `NO_APPLICABILITY_PARAGRAPH`).
   - Withdrawals normally have no (c). They are handled by the revision overlay, not by this engine.
2. **Benign phrases** are consumed and recorded, with no effect on scope:
   - "certificated in any category"
   - "all certificated models"
   - "(type certificate previously held by …)" / "formerly …"
   - lead-ins such as "This AD applies to" or "the following"
3. **Models.**
   - Read "Model(s) X, Y, and Z [airplanes|helicopters|…]" and table Model columns.
   - **Shorthand:** "A310-203, -204" expands to A310-204 only when the dash-token immediately follows a full model in the same comma/and list. The expanded value is the base prefix up to and including the last hyphen, plus the token. Mark `expanded_from_shorthand=true` and store both spans.
   - **Series:** "R22 series" sets `is_series=true`.
   - **Line-break artefacts:** "B4- 622" normalizes to "B4-622". Remove whitespace adjacent to hyphens, uppercase, and collapse internal whitespace. The raw text is kept.
   - **All models:** "all models", or a make with no model, gives `ALL_MODELS_OF_MAKE`, but only when the text literally says "all models" or "all … airplanes" with no model list.
4. **Serials.**
   - **Ranges:**
     - "S/N(s) | serial numbers | MSN(s) A through B": inclusive on both ends.
     - "A through B inclusive": inclusive.
     - "A-B inclusive": a range only when both sides are pure digits of equal width and "inclusive" follows. Otherwise the text goes to residue.
   - **Open-ended ranges:**
     - "A and subsequent", "A and on": lo inclusive.
     - "up to and including B": hi inclusive.
     - "up to B", "prior to B", "before B": `hi_incl = null`. This means the boundary is ambiguous, so evaluating exactly B returns UNKNOWN.
   - **Lists:** "serial numbers A, B, and C", "serial number F406-0091".
   - **Exclusions:** "excluding X, Y" / "except X" directly attached to a range or list go into `SerialSpec.excluded`.
   - **All serials:** "all serial numbers" / "all manufacturer serial numbers" give `ALL_SERIALS`.
   - **Tables:** each row (Model | Serial Nos.) becomes one Clause.
     - Several ranges in one cell joined by "and" go into a single SerialSpec.
     - Enumerated items "(1) …" with "(2) …" become separate Clauses (OR), unless the items are joined by "that: (1) …; and (2) …". That form is a conjunction: the items become conditions of the same clause.
   - **Serial subject:** if the serial phrase follows a component description ("pumps … P/N X, with the following serial numbers"), set `serial_subject = component` and capture `component`.
5. **Conditions and exclusions.**
   - "equipped with … P/N X (or Y)" gives `part_number_installed`, polarity +, values [X, Y].
   - "excluding/except those airplanes on which Modification N … has been incorporated" gives `modification_incorporated` in `exclusions`.
   - "on which Service Bulletin … has (not) been accomplished" gives `service_bulletin_accomplished` with the matching polarity.
   - "now or at any time equipped with <free text>" gives `free_text`, polarity +.
   - Any other "that/which/with/having/equipped/installed/except/excluding/unless/if" clause the grammar can't type becomes `free_text` with the appropriate polarity. If polarity can't be determined, the text goes to residue.
6. **External references.** "as identified in / listed in / specified in <document>" goes into `external_refs`. A Note that merely clarifies (e.g. "Note 1 to paragraph (c)…") is recorded in `benign` only if it contains no restrictive verbs. Otherwise it goes to residue.
7. **parse_status.**
   - FULL: residue is empty after trimming punctuation and stop-words ("and", "or", "the", ";", ",", ".", ":").
   - PARTIAL: some structure was found but residue is non-empty.
   - FAILED: nothing was found.

## 3. Evaluation (Kleene three-valued logic)

**Input:**
```
AircraftConfig {
  model: str | null
  serial: str | null
  make: str | null
  facts: { condition_key → true | false }   # condition_key = (kind, normalized values); absent ⇒ unknown
}
```

**Order of evaluation** (the first terminal outcome wins, and every step adds an explanation item with evidence spans):

1. If `parse_status != FULL` → UNKNOWN (`RULE_NOT_FULLY_PARSED`, with the residue quoted).
2. If `external_refs` is non-empty and could restrict scope → UNKNOWN (`EXTERNAL_DOCUMENT_REQUIRED`, naming the document).
3. If `config.model` is null → NEEDS model. The engine returns UNKNOWN with `missing = [model]`. The answer layer maps this to NEEDS_MORE_INFORMATION.
4. Evaluate each clause → T / F / U:
   - **model_match:**
     - T if the normalized config model equals a ModelRef. A shorthand-expanded match counts as T, with a warning.
     - U if the ModelRef `is_series` and the config model starts with its base followed by a space or hyphen (series membership can't be verified from the text). Equality with the series base itself is T.
     - F otherwise.
     - `ALL_MODELS_OF_MAKE`: T if the make matches through the documented alias map. U if make is absent or doesn't match through aliases.
   - **serial_match:**
     - `ALL_SERIALS` → T.
     - `NOT_STATED` → T. The clause doesn't restrict serials; record this explicitly in the explanation.
     - `serial_subject == component` → U, unless the user supplies that component's serial (out of scope for v1).
     - If `config.serial` is null and a SerialSpec exists → U, `missing = [serial]`.
     - The serial is in `excluded` (exact normalized match) → F.
     - The serial is in `list` → T.
     - **Ranges:** comparable only if config serial and both bounds parse to the same prefix and suffix and all numbers are non-null.
       - Width differences are tolerated only when the leading zeros make it unambiguous; e.g. "0002"–"2519" vs "205" compares numerically. Prefix and suffix must match exactly, case-insensitive.
       - Outside the range → F for this range.
       - Inside the range → T.
       - Exactly on a boundary with inclusivity `null` → U.
       - Not comparable → U, with reason `SERIAL_FORMAT_NOT_COMPARABLE`. Never compare lexicographically.
     - Combine as OR over ranges and the list, then AND NOT excluded.
   - **conditions:** each condition looks up `facts[key]`. If absent → U. Polarity is applied.
   - **exclusions:** for each exclusion, a fact of true → clause F; absent → U.
   - clause = AND(model_match, serial_match, conditions…, NOT exclusions…)
5. rule = OR(clauses) AND(global_conditions) AND NOT(global_exclusions).
6. Map T → APPLICABLE, F → NOT_APPLICABLE, U → UNKNOWN. Also return:
   - `missing`: the inputs that would resolve a U
   - `explanation`: an ordered list of `{step, outcome, evidence: Lit[]}`
   - the deterministic template sentence (see §5)

**Overlays** come from the revision engine and never change the computed value; they add context and warnings:
- doc_class == WITHDRAWAL, or a WITHDRAWAL in the evidence graph withdraws this NPRM → the warning "This proposal was withdrawn (FR doc X); it imposes no requirement."
- A VERIFIED final rule exists → "A final rule (FR doc Y, AD Z) was published; its applicability may differ from the proposal. Check the final rule." In v1 we also parse the final rule's (c) when available and evaluate it separately.
- Proposal only → "Applies as proposed. Proposed ADs are not enforceable until adopted."

## 4. Required tests

Use synthetic literals labelled `synthetic`, plus real paragraphs from the DB labelled `real:<docnum>`.

| # | Case | Expected |
|---|---|---|
| 1 | Serial = lower bound of "through" range | APPLICABLE |
| 2 | Serial = upper bound | APPLICABLE |
| 3 | lo − 1 and hi + 1 | NOT_APPLICABLE |
| 4 | Serial in "excluding" list inside range | NOT_APPLICABLE |
| 5 | Model not listed (parse FULL) | NOT_APPLICABLE |
| 6 | Model null | UNKNOWN, missing=[model] |
| 7 | Serial null, rule has ranges | UNKNOWN, missing=[serial] |
| 8 | Serial null, ALL_SERIALS | APPLICABLE |
| 9 | Prefixed serials "28-7125001" in "28-7125001 through 28-7125666" | APPLICABLE; "28R-7125001" → UNKNOWN (prefix mismatch → not comparable) or NOT_APPLICABLE only if another clause decides F definitively |
| 10 | Leading zeros "0002 through 2519", serial "205" | APPLICABLE |
| 11 | Suffix "82086/E through 82184/E", serial "82100/E" | APPLICABLE; "82100" → UNKNOWN |
| 12 | "up to B" and serial == B | UNKNOWN |
| 13 | Table with 2 rows; model in row 2 with its serial | APPLICABLE; same serial with row-1 model → NOT_APPLICABLE if outside row-1 range |
| 14 | "equipped with P/N X" with no fact | UNKNOWN missing=[part_number_installed X]; fact true → APPLICABLE; false → NOT_APPLICABLE |
| 15 | Exclusion "Modification 5068 incorporated", no fact | UNKNOWN; fact true → NOT_APPLICABLE |
| 16 | Component serial subject | UNKNOWN |
| 17 | "R22 series", query "R22" → APPLICABLE; "R22 Beta" | UNKNOWN |
| 18 | Shorthand "A310-203, -204", query "A310-204" | APPLICABLE + warning |
| 19 | Unparsed residue present | UNKNOWN regardless of model/serial |
| 20 | Malformed serial ("12A$") | UNKNOWN |
| 21 | "5044-5063 inclusive" | range; "5044-5063" without "inclusive" → residue → UNKNOWN |
| 22 | Conjunctive "that: (1) …; and (2) equipped with …" | free_text condition → UNKNOWN unless fact given |
| 23 | Every Lit offset round-trips to doc_text | assert |

Report coverage on the real corpus: the parse_status distribution by era and doc_class, plus a sample of 20 FULL parses that an Opus reviewer checks by hand.

## 5. Deterministic templates (the LLM never writes these)
- APPLICABLE: "Based on paragraph (c) of FR {docnum} ({citation}, p. {page}), the proposed AD would apply to {model} S/N {serial}: {reason}."
- NOT_APPLICABLE: "Based on paragraph (c) of FR {docnum}, the proposed AD would not apply to {model} S/N {serial}: {reason}."
- UNKNOWN: "Applicability cannot be determined from the source: {reason}. Needed: {missing}."
- Each `{reason}` is built from explanation items whose evidence quotes are shown verbatim.
