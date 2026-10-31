"""Applicability engine tests. 'synthetic' = built strings through extract->evaluate->render;
'real:<docnum>' = real corpus paragraphs (expected values verified by reading the paragraph)."""
import sqlite3

import pytest

from backend.api.schemas import AircraftConfig as C
from backend.config import DB_PATH
from backend.rules.applicability import (all_lits, evaluate, evaluate_document, evaluate_text, extract_rule,
                                         extract_rule_from_text, load_doc)

A = "APPLICABLE"
N = "NOT_APPLICABLE"
U = "UNKNOWN"


def run(par, **kw):
    rule, ev, res = evaluate_text(par, C(**kw))
    return rule, res


def val(par, **kw):
    r, res = run(par, **kw)
    return res.value.value


RANGE = "This AD applies to Acme Aero Model AB-100 and AB-200 airplanes, serial numbers 1000 through 2000, certificated in any category."


# ---------------- synthetic (spec section 4)
def test_s01_lower_bound():  # synthetic
    assert val(RANGE, model="AB-100", serial="1000") == A


def test_s02_upper_bound():  # synthetic
    assert val(RANGE, model="AB-100", serial="2000") == A


def test_s03_outside():  # synthetic
    assert val(RANGE, model="AB-100", serial="999") == N
    assert val(RANGE, model="AB-100", serial="2001") == N


def test_s04_excluded_inside_range():  # synthetic
    p = "This AD applies to Acme Aero Model AB-100 airplanes, serial numbers 1000 through 2000, except serial numbers 1500 and 1600, certificated in any category."
    r, res = run(p, model="AB-100", serial="1500")
    assert r.parse_status == "FULL" and res.value.value == N
    assert val(p, model="AB-100", serial="1501") == A


def test_s05_model_not_listed():  # synthetic
    r, res = run(RANGE, model="ZZ-900", serial="1500")
    assert r.parse_status == "FULL" and res.value.value == N


def test_s06_model_null():  # synthetic
    r, res = run(RANGE, serial="1500")
    assert res.value.value == U and res.missing == ["model"]


def test_s07_serial_null_ranges():  # synthetic
    r, res = run(RANGE, model="AB-100")
    assert res.value.value == U and res.missing == ["serial"]


def test_s08_serial_null_all_serials():  # synthetic
    p = "This AD applies to all Acme Aero Model AB-100 airplanes, all serial numbers, certificated in any category."
    assert val(p, model="AB-100") == A


def test_s09_prefixed_serials():  # synthetic
    p = "This AD applies to Piper Aircraft, Inc. Model PA-28-140 airplanes, serial numbers 28-7125001 through 28-7125666, certificated in any category."
    assert val(p, model="PA-28-140", serial="28-7125100") == A
    assert val(p, model="PA-28-140", serial="28R-7125001") == U


def test_s10_leading_zeros():  # synthetic
    p = "This AD applies to Robinson Helicopter Model R22 series helicopters, serial numbers 0002 through 2519, certificated in any category."
    assert val(p, model="R22", serial="205") == A


def test_s11_suffix():  # synthetic
    p = "This AD applies to GROB Model G 115E airplanes, serial numbers 82086/E through 82184/E, certificated in any category."
    assert val(p, model="G 115E", serial="82100/E") == A
    assert val(p, model="G 115E", serial="82100") == U


def test_s12_up_to_boundary():  # synthetic
    p = "This AD applies to Acme Aero Model AB-100 airplanes, serial numbers up to 50, certificated in any category."
    assert val(p, model="AB-100", serial="50") == U
    assert val(p, model="AB-100", serial="49") == A
    assert val(p, model="AB-100", serial="51") == N


def test_s13_two_clauses():  # synthetic
    p = ("This AD applies to Acme Aero airplanes, certificated in any category, identified in paragraphs (c)(1) and (2) of this AD.\n\n"
         "(1) Model AB-100 airplanes, serial numbers 1 through 10 inclusive.\n\n"
         "(2) Model AB-200 airplanes, serial numbers 100 through 200 inclusive.")
    rule, res = run(p, model="AB-200", serial="150")
    assert rule.parse_status == "FULL" and res.value.value == A
    assert val(p, model="AB-100", serial="150") == N
    assert val(p, model="AB-100", serial="5") == A


def test_s14_part_number():  # synthetic
    p = "This AD applies to Acme Aero Model AB-100 airplanes, certificated in any category, equipped with actuator part number (P/N) PN-123 or PN-456."
    r, res = run(p, model="AB-100")
    assert r.parse_status == "FULL" and res.value.value == U
    assert res.missing and res.missing[0].startswith("part_number_installed:PN-123|PN-456")
    key = r.clauses[0].conditions[0].key
    assert val(p, model="AB-100", facts={key: True}) == A
    assert val(p, model="AB-100", facts={key: False}) == N


def test_s15_modification_exclusion():  # synthetic
    p = ("This AD applies to Acme Aero Model AB-100 airplanes, certificated in any category, "
         "excluding those airplanes on which Modification 5068 has been incorporated.")
    r, res = run(p, model="AB-100")
    assert r.parse_status == "FULL" and res.value.value == U
    key = r.clauses[0].exclusions[0].key
    assert key.startswith("modification_incorporated:") or key.startswith("service_bulletin_accomplished:")
    assert val(p, model="AB-100", facts={key: True}) == N
    assert val(p, model="AB-100", facts={key: False}) == A


def test_s16_component_serial():  # synthetic
    p = ("This AD applies to Acme Aero Model AB-100 airplanes, equipped with auxiliary pumps part number (P/N) 782655-3, "
         "serial numbers 1 through 365.")
    r, res = run(p, model="AB-100", serial="5")
    assert r.clauses and r.clauses[0].serial.subject == "component"
    assert res.value.value == U


def test_s17_series():  # synthetic
    p = "This AD applies to Robinson Helicopter Model R22 series helicopters, certificated in any category."
    assert val(p, model="R22") == A
    assert val(p, model="R22 Beta") == U


def test_s18_shorthand():  # synthetic
    p = "This AD applies to Airbus Model A310-203, -204, and -221 airplanes, certificated in any category."
    r, res = run(p, model="A310-204")
    assert res.value.value == A
    assert any(s.step == "warning" for s in res.explanation)
    assert r.clauses[0].models[1].expanded_from_shorthand


def test_s19_residue_unknown():  # synthetic
    p = RANGE + " Plus some unparsed restriction text."
    r, res = run(p, model="AB-100", serial="1500")
    assert r.parse_status == "PARTIAL" and r.residue and res.value.value == U
    r, res = run(p, model="ZZ", serial="1")
    assert res.value.value == U


def test_s20_malformed_serial():  # synthetic
    assert val(RANGE, model="AB-100", serial="12A$") == U


def test_s21_inclusive_digit_range():  # synthetic
    p = "This AD applies to Gulfstream Model GV-SP series airplanes, certificated in any category; serial numbers 5044-5063 inclusive."
    r, res = run(p, model="GV-SP", serial="5050")
    assert r.parse_status == "FULL" and res.value.value == A
    p2 = p.replace(" inclusive", "")
    r2, res2 = run(p2, model="GV-SP", serial="5050")
    assert r2.parse_status != "FULL" and res2.value.value == U


def test_s22_conjunctive_free_text():  # synthetic
    p = ("This AD applies to Piper Aircraft, Inc. Models PA-18 and PA-19 airplanes, all serial numbers, that:\n\n"
         "(1) Are certificated in any category; and\n\n(2) Are now or at any time equipped with a magneto switch.")
    r, res = run(p, model="PA-18", serial="5")
    assert res.value.value == U  # conjunctive items are not typed in v1 -> residue -> UNKNOWN
    p2 = "This AD applies to Piper Aircraft, Inc. Models PA-18 airplanes, certificated in any category, equipped with a magneto switch."
    r2, res2 = run(p2, model="PA-18")
    assert r2.clauses[0].conditions[0].kind == "free_text" and res2.value.value == U
    assert val(p2, model="PA-18", facts={r2.clauses[0].conditions[0].key: True}) == A


def test_s23_offsets_roundtrip():  # synthetic
    for p in (RANGE, "This AD applies to Airbus Model A310-203, -204 airplanes, certificated in any category, equipped with a main cargo door."):
        r = extract_rule_from_text(p, 0, len(p), "SYN")
        n = 0
        for text, a, b in all_lits(r):
            assert p[a:b] == text
            n += 1
        assert n > 3


def test_external_ref_unknown_even_if_model_listed():  # synthetic
    p = ("This AD applies to Airbus SAS Model A350-941 airplanes, certificated in any category, as identified in "
         "European Union Aviation Safety Agency (EASA) AD 2026-0074, dated April 8, 2026.")
    r, res = run(p, model="A350-941")
    assert r.external_refs and res.value.value == U
    # Opus review decision: an external reference can only narrow the listed scope, so an unlisted model is a
    # definite NOT_APPLICABLE (Kleene: FALSE AND UNKNOWN = FALSE).
    assert val(p, model="B737") == "NOT_APPLICABLE"


def test_family_prefix_model_is_unknown():  # synthetic
    p = "This AD applies to Airbus Model A300 B4-2C, B4-103, and B4-203 airplanes, certificated in any category."
    assert val(p, model="A300 B4-103") in (A, U)  # never NOT_APPLICABLE
    assert val(p, model="B4-103") == A


def test_overlay_warning_hook():  # synthetic
    rule = extract_rule_from_text(RANGE, 0, len(RANGE), "SYN")
    ev = evaluate(rule, C(model="AB-100", serial="1500"), revision_overlay=["withdrawn"])
    assert "withdrawn" in ev.warnings and ev.value == "T"


# ---------------- real documents
def _ev(doc, **kw):
    res = evaluate_document(doc, C(**kw))
    return res


def test_real_2026_21387_listed_model():
    # real:2026-21387  "all Airbus Helicopters Model AS350B3, AS355F, ... EC130T2 helicopters, certificated in any category"
    assert _ev("2026-21387", model="AS355NP", serial="1234").value.value == A


def test_real_2026_21387_unlisted_model():
    # real:2026-21387  AS350B2 is not in the list AS350B3, AS355F, AS355F1, AS355F2, AS355N, AS355NP, EC130B4, EC130T2
    res = _ev("2026-21387", model="AS350B2")
    assert res.value.value == N and res.rule_parse_status == "FULL"


def test_real_2026_21387_no_model():
    # real:2026-21387
    res = _ev("2026-21387")
    assert res.value.value == U and res.missing == ["model"]


def test_real_2026_21387_citation():
    # real:2026-21387  evidence quotes are verbatim doc_text slices with sha256-based ids
    res = _ev("2026-21387", model="AS355NP")
    T = load_doc("2026-21387")[0]
    cites = [e for s in res.explanation for e in s.evidence]
    assert cites
    for c in cites:
        assert T[c.start:c.end] == c.quote and len(c.citation_id) == 12 and c.source_tier.value == "FR_FULL_TEXT"
    assert res.applicability_text and "Applicability" in res.applicability_text.quote


def test_real_2013_08188_suffix_serials():
    # real:2013-08188 "Model G 115E airplanes, serial numbers 82086/E through 82184/E"
    assert _ev("2013-08188", model="G 115E", serial="82100/E").value.value == A
    assert _ev("2013-08188", model="G 115E", serial="82100").value.value == U
    assert _ev("2013-08188", model="G 115E", serial="82185/E").value.value == N


def test_real_2022_02072_prefixed_serials():
    # real:2022-02072 "Model PA-34-200 airplanes, serial numbers 34-7250001 through 34-7450220"
    assert _ev("2022-02072", model="PA-34-200", serial="34-7300000").value.value == A
    assert _ev("2022-02072", model="PA-34-200", serial="34-7450221").value.value == N
    assert _ev("2022-02072", model="PA-34-200", serial="34-7250001").value.value == A


def test_real_2025_07753_multi_clause():
    # real:2025-07753 "(2) Model CL-600-2A12 (601) airplanes, serial numbers 3001 through 3066 inclusive."
    assert _ev("2025-07753", model="CL-600-2A12", serial="3001").value.value == A
    assert _ev("2025-07753", model="CL-600-2A12", serial="1001").value.value == N   # 1001 belongs to the CL-600-1A11 row only
    assert _ev("2025-07753", model="CL-600-1A11", serial="1001").value.value == A


def test_real_2018_13335_list_and_range():
    # real:2018-13335 "having serial numbers 4001, and 4003 through 4533 inclusive"; 4002 is in neither
    assert _ev("2018-13335", model="DHC-8-402", serial="4001").value.value == A
    assert _ev("2018-13335", model="DHC-8-402", serial="4002").value.value == N
    assert _ev("2018-13335", model="DHC-8-402", serial="4533").value.value == A


def test_real_05_12688_zero_padded():
    # real:05-12688 "Model R22 series helicopters, serial numbers (S/N) 0002 through 2519"
    assert _ev("05-12688", model="R22", serial="205").value.value == A
    assert _ev("05-12688", model="R22 Beta", serial="205").value.value == U


def test_real_2011_11753_part_number_condition():
    # real:2011-11753 "Model 206A, 206B, and 206B3 helicopters, with Litter Kit, part number 206-706-122 or 206-706-324, installed"
    r = extract_rule("2011-11753")
    assert r.parse_status == "FULL"
    key = r.clauses[0].conditions[0].key
    assert key == "part_number_installed:206-706-122|206-706-324"
    assert _ev("2011-11753", model="206B").value.value == U
    assert _ev("2011-11753", model="206B", facts={key: True}).value.value == A
    assert _ev("2011-11753", model="206B", facts={key: False}).value.value == N


def test_real_2026_18375_external_reference():
    # real:2026-18375 "... as identified in European Union Aviation Safety Agency (EASA) AD 2026-0074" -> scope lives in EASA AD
    res = _ev("2026-18375", model="A350-941")
    assert res.value.value == U and "EASA" in res.template_text


def test_real_2021_03483_serial_range():
    # real:2021-03483 "Model GVII-G600 airplanes, serial numbers 73001 through 73043"
    assert _ev("2021-03483", model="GVII-G600", serial="73043").value.value == A
    assert _ev("2021-03483", model="GVII-G600", serial="73044").value.value == N


# ---------------- corpus properties
def _all_docs():
    c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=30)
    try:
        return [r[0] for r in c.execute("select fr_docnum from documents order by fr_docnum")]
    finally:
        c.close()


@pytest.fixture(scope="module")
def corpus():
    out = []
    for d in _all_docs():
        r = extract_rule(d)
        if r.failure_reason in ("NO_APPLICABILITY_PARAGRAPH", "NO_DOC_TEXT"):
            continue
        out.append(r)
    return out


def test_property_all_lits_roundtrip(corpus):
    assert len(corpus) > 200
    docs = {}
    for r in corpus:
        T = docs.setdefault(r.fr_docnum, load_doc(r.fr_docnum)[0])
        for text, a, b in all_lits(r):
            assert T[a:b] == text, (r.fr_docnum, a, b)


def test_property_safety(corpus):
    full = [r for r in corpus if r.parse_status == "FULL"]
    assert len(full) > 100
    for r in full:
        cfg = C(model="ZZ-NOT-A-REAL-MODEL-9", serial="1", facts={})
        ev = evaluate(r, cfg)
        assert ev.value in ("F", "U"), r.fr_docnum
        if any(c.all_models for c in r.clauses):
            assert ev.value == "U"
        else:
            assert ev.value == "F", r.fr_docnum
        # every listed model must never be NOT_APPLICABLE, and with an external reference must stay UNKNOWN
        if r.external_refs:
            for cl in r.clauses:
                for m in (cl.models if not cl.all_models else []):
                    assert evaluate(r, C(model=m.normalized, serial=None)).value == "U", (r.fr_docnum, m.normalized)
        assert evaluate(r, C(model=None)).value == "U"
    for r in corpus:
        if r.parse_status != "FULL":
            assert evaluate(r, C(model="ZZ-NOT-A-REAL-MODEL-9")).value == "U"
            assert evaluate(r, C(model="A320-214", serial="1")).value == "U"
