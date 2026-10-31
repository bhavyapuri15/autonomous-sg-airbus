# O1 final-rule lookup report

Run: `.venv/bin/python scripts/fetch_final_rules.py` (second run: NETWORK CALLS: 0; shasum of final_rule_links.json identical across runs: 61d29dbe041e94b789c83560e941d2747b3aabe9).

- Dataset docs: 420. Dockets queried: 590 (normalized, incl. Project/Directorate/Product identifiers). Fuzzy hits discarded: 0 (data/raw/fr_final_rules/discarded_hits.json).
- Rules found: FINAL_RULE 63, FINAL_RULE_REQUEST_FOR_COMMENTS 2, CORRECTION 7, OTHER_RULE 3.
- Link status (modern = dataset doc published 2021+, legacy = earlier). Counts are per link, except NO_FINAL_RULE which is per dataset doc:
  VERIFIED 35 modern / 23 legacy; CANDIDATE 3 / 17; CONFLICT_REVIEW 0 / 1; NO_FINAL_RULE_FOUND_IN_FR 149 / 203.
- AD number and amendment found in text: 64 of 65 final-type rules (1 miss: 04-6499, no "Amendment 39-" regulatory heading in the text). 14 rules contain supersession language.

## Safeguards
- Date-only evidence is rejected when an adjacent FR citation differs from the dataset doc's citation (2 cases, e.g. 03-30674 vs 04-5431, where the rule cites "68 FR 69501" and the doc is 68 FR 69051). These are downgraded to CANDIDATE.
- A rule published before the dataset doc can never be VERIFIED.
- CORRECTION and OTHER_RULE rules are never VERIFIED.

## Limitations
- NO_FINAL_RULE_FOUND_IN_FR is not proof that no final rule exists. Legacy pre-1994 documents may not be in the FR API, and the final rule may sit under a different docket id.
- The FR search is by docket id. A final rule filed under a new docket would be missed.
- The one CONFLICT_REVIEW case, 2011-19048 (withdrawal, docket 2009-NE-18-AD / FAA-2009-0555 -> E9-19633), has a rule published before the withdrawal. It is flagged, not resolved.
