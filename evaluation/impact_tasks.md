# F9 Impact benchmark (amendment A6): manual vs assisted

Eight realistic engineer tasks built from **dev-split** documents only (none is in `locked/`). The gold answers below were read from
`doc_text` of `data/indexes/ad.sqlite`; evidence is `{fr_docnum, section_path, start_char:end_char}` (0-based offsets, end exclusive).
Results are NOT filled in. A blank table is at the end.

## Tasks

| # | Task text (given to the participant) | Gold answer | Evidence |
|---|---|---|---|
| T1 | "Does the proposed AD for Bell 206L-4 helicopters with STC SR02684LA (docket FAA-2026-8796) apply to my aircraft?" | Yes, as proposed: applicability covers all Bell Textron Canada 206L, 206L-1, 206L-3, 206L-4 with STC SR02684LA installed. It is a proposal, not a final rule. | 2026-18522, `proposed_ad/(c)`, 10691:10908 |
| T2 | "Is a Bombardier CL-604 (CL-600-2B16) with serial number 5555 within the November 2004 proposed AD (docket FAA-2004-19563)?" | No: the proposal covers serial numbers 5301 through 5550 inclusive; 5555 is outside that range. | 04-24937, `proposed_ad/(c)`, 10574:10759 |
| T3 | "Was the NPRM for docket FAA-2012-0962 (Cessna) withdrawn? If so, when?" | Yes. Withdrawal published 2013-01-18 (document 2013-01000) withdrawing the NPRM published 2012-09-11, 77 FR 55770. | 2013-01000, `preamble/SUPPLEMENTARY INFORMATION/The Withdrawal`, 2918:3240; NPRM 2012-22332 |
| T4 | "Which propeller adapter ring part number must not be installed on DG Aviation gliders under the October 2026 proposal?" | P/N 10 M 067, version a, or any earlier approved part number. | 2026-20393, `proposed_ad/(i)`, 13886:14096 |
| T5 | "How many flight hours do I have for the floor crossbeam ultrasonic inspection on an A320-214 in the March 2004 proposal (docket 2002-NM-224-AD)?" | Within 450 flight hours from the effective date of the AD (one-time inspection). | 04-5968, `proposed_ad/(a)`, 10299:11166 |
| T6 | "Which EASA AD sets the required actions in the July 2026 Rolls-Royce Deutschland proposal, docket FAA-2026-7209?" | EASA AD 2025-0086, dated April 16, 2025. | 2026-13541, `proposed_ad/(g)`, 14052:14327 |
| T7 | "Why did the FAA withdraw the AmSafe seatbelt hook NPRM (docket FAA-2019-0021)?" | A significant portion of affected hook assemblies were replaced, the rest are likely out of service, and a new risk assessment found an acceptable level of risk. | 2019-16127, `preamble/SUMMARY`, 297:1294 |
| T8 | "What unsafe condition prompted the Sept 30, 2026 Airbus Helicopters Deutschland proposal under docket FAA-2026-11792?" | A report of loss of tail rotor controls due to a broken control rod of the yaw actuator. | 2026-19971, `proposed_ad/(e)`, 14019:14370 |

## Protocol

Participants: the same people for both arms, with arm order counterbalanced (half do T1-T4 manual first, half assisted first), and a
different task set per arm per person so nobody sees a task twice. Use a stopwatch; stop the clock when the participant states a final answer.

**Manual arm.** Use only federalregister.gov (search box, document pages, PDF/HTML text) and a PDF reader. No LLM, no local index.
Start from the task text only. The participant writes down the answer and the document (FR document number and page) used as evidence.

**Assisted arm.** Use only our UI (search or ask box, answer card, citations panel, source viewer). The participant may open citations.
The answer is taken from the UI output, but the participant must confirm the cited quote supports it. Record if the UI abstained or was wrong.

**Record per task and arm**
- time-to-answer (seconds, stopwatch);
- correctness: 1 correct / 0.5 partly correct (e.g. right document, incomplete answer) / 0 wrong or no answer, judged against the gold column by someone other than the participant;
- documents opened (distinct FR documents or pages viewed) and steps (searches, clicks to new views, queries typed);
- for the assisted arm: whether the UI status was ANSWERED / ABSTAINED / NEEDS_MORE_INFORMATION and whether the cited quote supported the answer;
- free-text notes (confusion, wrong turns).

**Reporting.** Median time and mean correctness per arm with n (tasks x participants), all raw rows published. No significance claim without
enough participants; with a small n, state it is anecdotal. A 10-minute cap per task; a timeout counts as 0 correct with time = 600 s.

## Results (blank)

| task | participant | arm | time (s) | correct (0/0.5/1) | docs opened | steps | UI status (assisted) | quote supported? | notes |
|---|---|---|---|---|---|---|---|---|---|
| T1 | | manual | | | | | n/a | n/a | |
| T1 | | assisted | | | | | | | |
| T2 | | manual | | | | | n/a | n/a | |
| T2 | | assisted | | | | | | | |
| T3 | | manual | | | | | n/a | n/a | |
| T3 | | assisted | | | | | | | |
| T4 | | manual | | | | | n/a | n/a | |
| T4 | | assisted | | | | | | | |
| T5 | | manual | | | | | n/a | n/a | |
| T5 | | assisted | | | | | | | |
| T6 | | manual | | | | | n/a | n/a | |
| T6 | | assisted | | | | | | | |
| T7 | | manual | | | | | n/a | n/a | |
| T7 | | assisted | | | | | | | |
| T8 | | manual | | | | | n/a | n/a | |
| T8 | | assisted | | | | | | | |
