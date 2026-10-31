# Applicability engine report (v1)

See bottom for gaps/limitations. Generated from `scripts/build_rules.py`.

## Coverage

```
docs: 495  with (c) paragraph: 351
by era: {('legacy', 'FAILED'): 29, ('legacy', 'FULL'): 76, ('legacy', 'PARTIAL'): 40, ('modern', 'FAILED'): 10, ('modern', 'FULL'): 145, ('modern', 'PARTIAL'): 51}
by doc_class: {('CORRECTION', 'FULL'): 2, ('FINAL_RULE', 'FAILED'): 8, ('FINAL_RULE', 'FULL'): 37, ('FINAL_RULE', 'PARTIAL'): 15, ('NPRM', 'FAILED'): 29, ('NPRM', 'FULL'): 175, ('NPRM', 'PARTIAL'): 67, ('SNPRM', 'FAILED'): 2, ('SNPRM', 'FULL'): 7, ('SNPRM', 'PARTIAL'): 7, ('WITHDRAWAL', 'PARTIAL'): 2}
overall: {'PARTIAL': 91, 'FULL': 221, 'FAILED': 39}
top residue (first residue run, digits->N):
    8  'with an original airworthiness certificate or orig'
    6  '(a)'
    6  'Installation of Supplemental Type Certificate (STC'
    4  'airplanes'
    3  'the airplanes listed in Table N of this AD'
    3  'that'
    3  'Note N:\n\nThis AD requires revisions to certain ope'
    2  'and AN CN-NR Variant F airplanes'
    2  'all BN-N, BN-NA, BN-NB, BN-NT, and BN-NT-NR series'
    2  'Dowty Propellers type RN/N-N-N/N propeller ass'
    2  'This action applies to'
    2  'except for those airplanes that have had Airbus Mo'
    2  'Pratt'
    2  'Various restricted category helicopters'
    2  'Piper Aircraft, Inc. (Piper) airplanes'
```

## 10 FULL examples (paragraph, structured summary)

### 2026-21387 (NPRM)
> (c) Applicability
> 
> This AD applies to all Airbus Helicopters Model AS350B3, AS355F, AS355F1, AS355F2, AS355N, AS355NP, EC130B4, and EC130T2 helicopters, certificated in any category.

`[{"models": ["AS350B3", "AS355F", "AS355F1", "AS355F2", "AS355N", "AS355NP", "EC130B4", "EC130T2"]}]`

### 2022-02072 (NPRM)
> (c) Applicability
> 
> This AD applies to Piper Aircraft, Inc., Model PA-34-200 airplanes, serial numbers 34-7250001 through 34-7450220, certificated in any category.

`[{"models": ["PA-34-200"], "serial": {"kind": "serial", "all": false, "ranges": [["34-7250001", "34-7450220", true, true]], "list": [], "excluded": []}}]`

### 2013-08188 (NPRM)
> (c) Applicability
> 
> This AD applies to GROB-WERKE Model G 115E airplanes, serial numbers 82086/E through 82184/E, certificated in any category.

`[{"models": ["G 115E"], "serial": {"kind": "serial", "all": false, "ranges": [["82086/E", "82184/E", true, true]], "list": [], "excluded": []}}]`

### 05-12688 (NPRM)
> Applicability: Model R22 series helicopters, serial numbers (S/N) 0002 through 2519, certificated in any category.

`[{"models": ["R22"], "serial": {"kind": "serial", "all": false, "ranges": [["0002", "2519", true, true]], "list": [], "excluded": []}}]`

### 2025-07753 (NPRM)
> (c) Applicability
> 
> This AD applies to Bombardier, Inc., airplanes, certificated in any category, identified in paragraphs (c)(1) through (3) of this AD.
> 
> (1) Model CL-600-1A11 (600) airplanes, serial numbers 1001 through 1085 inclusive.
> 
> (2) Model CL-600-2A12 (601) airplanes, serial numbers 3001 through 3066 inclusive.
> 
> (3) Model CL-600-2B16 (601-3A, 601-3R, and 604 Variants) airplanes, serial numbers 5001 through 5194 inclusive, 5301 through 5665 inclusive, 5701 through 5988 inclusive, and 6050 through 6190 inclusive.

`[{"models": ["CL-600-1A11", "600"], "serial": {"kind": "serial", "all": false, "ranges": [["1001", "1085", true, true]], "list": [], "excluded": []}}, {"models": ["CL-600-2A12", "601"], "serial": {"kind": "serial", "all": false, "ranges": [["3001", "3066", true, true]], "list": [], "excluded": []}}, {"models": ["CL-600-2B16", "601-3A", "601-3R", "604 VARIANTS"], "serial": {"kind": "serial", "all": false, "ranges": [["5001", "5194", true, true], ["5301", "5665", true, true], ["5701", "5988", true, true], ["6050", "6190", true, true]], "list": [], "excluded": []}}]`

### 2018-13335 (NPRM)
> (c) Applicability
> 
> This AD applies to Bombardier, Inc., Model DHC-8-400, -401, and -402 airplanes, certificated in any category, having serial numbers 4001, and 4003 through 4533 inclusive.

`[{"models": ["DHC-8-400", "DHC-8-401", "DHC-8-402"], "serial": {"kind": "serial", "all": false, "ranges": [["4003", "4533", true, true]], "list": ["4001"], "excluded": []}}]`

### 2011-11753 (NPRM)
> Applicability: Model 206A, 206B, and 206B3 helicopters, with Litter Kit, part number 206-706-122 or 206-706-324, installed, certificated in any category.

`[{"models": ["206A", "206B", "206B3"], "conditions": ["part_number_installed:206-706-122|206-706-324"]}]`

### 02-21507 (NPRM)
> Applicability: Model Falcon 2000 series airplanes, serial numbers 2 through 132, except serial numbers 123, 130, and 131; certificated in any category; excluding those airplanes on which the actions specified in Dassault Service Bulletin F2000-A223, dated October 17, 2001, has been done.

`[{"models": ["FALCON 2000"], "serial": {"kind": "serial", "all": false, "ranges": [["2", "132", true, true]], "list": [], "excluded": ["123", "130", "131"]}, "exclusions": ["service_bulletin_accomplished:F2000-A223|2001"]}]`

### 2023-05082 (FINAL_RULE)
> (c) Applicability
> 
> This AD applies to Alexander Schleicher GmbH & Co. Segelflugzeugbau Model ASW-15 and ASW-15B gliders, all serial numbers, certificated in any category, equipped with wooden wing root ribs.

`[{"models": ["ASW-15", "ASW-15B"], "serial": {"kind": "serial", "all": true, "ranges": [], "list": [], "excluded": []}, "conditions": ["free_text:wooden wing root ribs"]}]`

### 2026-18372 (NPRM)
> (c) Applicability
> 
> This AD applies to all Airbus SAS airplanes, certificated in any category, as identified in paragraphs (c)(1) through (8) of this AD.
> 
> (1) Model A330-201, -202, -203, -223, and -243 airplanes.
> 
> (2) Model A330-301, -302, -303, -321, -322, -323, -341, -342, and -343 airplanes.
> 
> (3) Model A330-841 airplanes.
> 
> (4) Model A330-941 airplanes.
> 
> (5) Model A340-211, -212, and -213 airplanes.
> 
> (6) Model A340-311, -312, and -313 airplanes.
> 
> (7) Model A340-541 airplanes.
> 
> (8) Model A340-642 airplanes.

`[{"models": ["A330-201", "A330-202", "A330-203", "A330-223", "A330-243"]}, {"models": ["A330-301", "A330-302", "A330-303", "A330-321", "A330-322", "A330-323", "A330-341", "A330-342", "A330-343"]}, {"models": ["A330-841"]}, {"models": ["A330-941"]}, {"models": ["A340-211", "A340-212", "A340-213"]}, {"models": ["A340-311", "A340-312", "A340-313"]}, {"models": ["A340-541"]}, {"models": ["A340-642"]}]`

## Spec ambiguities / places where UNKNOWN was chosen
- Series (`is_series`): spec says U only when config starts with base + space/hyphen. Implemented stricter: ANY prefix/suffix relation between config model and a listed model (either direction, spaces ignored) gives U, never F. Reason: "A300 B4-103" vs listed "B4-103" (family prefix given only on first list item), "737-200" vs "737-200C", "G115E" vs "G 115E".
- Slash designations (PA-28-150/160/180, CFM56-7B26/3) are single ModelRefs; queries equal to a slash expansion give U.
- Parenthetical designations "DC-9-81 (MD-81)" become alias ModelRefs (equal -> T). Alias lists that do not tokenize (e.g. "(HP)") leave the group unparsed.
- "A to B" without "inclusive": hi_incl=null (boundary U). "through" = inclusive per spec.
- Line numbers / engine serial numbers (ESN) parse but evaluate to U (SERIAL_KIND_UNSUPPORTED): config has only an aircraft serial.
- Several model groups in one sentence with qualifiers (serial, conditions) inside: qualifier text goes to residue (scope ambiguous) except ALL_SERIALS.
- Serial limits right after a part-number condition are treated as component serials (U).
- External refs: any "as identified/listed/specified in <doc>" -> rule UNKNOWN even if the model is not listed (spec step 2 precedes model check).
- Make is only used for ALL_MODELS_OF_MAKE.
- A hyphenated pure-digit token "34-7250001" is accepted only as a range bound ("through") or "d-d inclusive"; bare in a list -> residue.

## Limitations (v1, all fall to PARTIAL/UNKNOWN)
- Tables (6 in corpus) are never parsed; conjunctive "that: (1) ... (2) ..." items are not typed; component/propeller enumerations; "Note ... to paragraph (c)" text; "with an original airworthiness certificate ... issued on or before" qualifiers; STC-installed qualifiers in intros; non-ASCII makes (e.g. "Hélicoptères"); multi-document external refs separated by ';'.
- Free-text "equipped with ..." conditions are keyed by uppercase body text; user must supply the same key in facts.
- Overlays (withdrawn/finalized) are only a hook (`revision_overlay` -> warnings).
- Rules extracted from the latest ad.sqlite (495 docs incl. FINAL_RULE); final-rule paragraphs are parsed the same way.
