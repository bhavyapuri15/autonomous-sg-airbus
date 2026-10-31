"""Tests for O1 final-rule lookup. Unit tests use SYNTHETIC snippets (not real FR text)."""
import json

import pytest

from backend import config
from backend.ingestion import final_rules as fr

# SYNTHETIC text, invented for tests
SYN = ("The FAA issued a notice of proposed rulemaking (NPRM). The NPRM was published in the Federal Register "
       "on April 2, 2026 (91 FR 16595).\n\n"
       "2026-12-05 Example Aero Co.: Amendment 39-23456; Docket No. FAA-2026-0001; Project Identifier AD-2025-00001-T.\n\n"
       "This AD supersedes AD 2010-01-02 and AD 2011-03-04. Also removing Airworthiness Directive (AD) 2012-05-06.")
DOC = {"docnum": "x", "citation": "91 FR 16595", "publication_date": "2026-04-02", "doc_class": "NPRM"}


def rule(cls="FINAL_RULE", date="2026-10-27"):
    return {"doc_class": cls, "publication_date": date}


def test_docket_normalization():
    assert fr.normalize_dockets(["Docket No. FAA-2013-0056", "Project Identifier AD-2024-00429-A"]) == \
        ["FAA-2013-0056", "AD-2024-00429-A"]
    assert fr.normalize_dockets(["Docket No. FAA 2004-19119"]) == ["FAA-2004-19119"]
    assert fr.normalize_dockets(["Docket No. FAA-2022-0992 Project Identifier MCAI-2022-00173-R", "Amendment 39-1", "AD 2022-23-02"]) == \
        ["FAA-2022-0992", "MCAI-2022-00173-R"]
    assert fr.normalize_dockets(["Docket No. 95-CE-35-AD, 96-NM-1-AD"]) == ["95-CE-35-AD", "96-NM-1-AD"]
    assert fr.shared_dockets(["99-NE-46-AD"], ["99-NE-46"]) == ["99-NE-46-AD"]


def test_doc_class():
    assert fr.doc_class("Proposed rule; withdrawal.") == "WITHDRAWAL"
    assert fr.doc_class("Supplemental notice of proposed rulemaking (SNPRM).") == "SNPRM"
    assert fr.doc_class("Notice of proposed rulemaking (NPRM).") == "NPRM"
    assert fr.doc_class("Proposed rule; correction.") == "CORRECTION"


def test_citation_and_date_extraction():
    assert [c["citation"] for c in fr.extract_citations(SYN)] == ["91 FR 16595"]
    d = fr.extract_dates(SYN)
    assert d and d[0]["date"] == "2026-04-02"
    assert SYN[d[0]["start"]:d[0]["end"]] == "April 2, 2026"
    assert fr.extract_dates("Effective on December 1, 2026, nothing else.") == []  # no NPRM context


def test_backrefs_match_and_mismatch():
    ev = fr.find_backrefs(SYN, DOC)
    assert {e["type"] for e in ev} == {"nprm_citation", "nprm_date"}
    for e in ev:
        assert SYN[e["start"]:e["end"]] == e["quote"]
    other = dict(DOC, citation="91 FR 99999", publication_date="2026-01-01")
    assert fr.find_backrefs(SYN, other) == []
    # same date but a different adjacent citation must be rejected
    conf = []
    assert fr.find_backrefs(SYN, dict(DOC, citation="91 FR 16596"), conf) == [] and conf


def test_ad_and_amendment():
    ad, am = fr.extract_ad_amendment(SYN)
    assert ad["value"] == "2026-12-05" and SYN[ad["start"]:ad["end"]] == "2026-12-05"
    assert am["value"] == "39-23456" and SYN[am["start"]:am["end"]] == "Amendment 39-23456"
    assert fr.extract_ad_amendment("no ad here") == (None, None)


def test_supersedes():
    s = fr.extract_supersedes(SYN)
    assert [x["ad_number"] for x in s] == ["2010-01-02", "2011-03-04", "2012-05-06"]
    for x in s:
        assert SYN[x["start"]:x["end"]] == x["quote"]


def test_status_table():
    ev = fr.find_backrefs(SYN, DOC)
    assert fr.decide_status(DOC, rule(), [])[0] == "CANDIDATE_SAME_DOCKET"
    assert fr.decide_status(DOC, rule(), ev)[0] == "VERIFIED_FINAL_RULE"
    assert fr.decide_status(DOC, rule("FINAL_RULE_REQUEST_FOR_COMMENTS"), ev)[0] == "VERIFIED_FINAL_RULE"
    assert fr.decide_status(DOC, rule("CORRECTION"), ev)[0] == "CANDIDATE_SAME_DOCKET"
    assert fr.decide_status(DOC, rule("OTHER_RULE"), ev)[0] == "CANDIDATE_SAME_DOCKET"
    assert fr.decide_status(DOC, rule(date="2025-01-01"), ev)[0] == "CANDIDATE_SAME_DOCKET"  # rule before NPRM
    w = dict(DOC, doc_class="WITHDRAWAL")
    assert fr.decide_status(w, rule(), [])[0] == "CONFLICT_REVIEW"


# ---- integration on cached real data
LINKS = config.PROCESSED / "final_rule_links.json"


@pytest.mark.skipif(not LINKS.exists(), reason="run scripts/fetch_final_rules.py first")
def test_verified_links_quotes_are_exact_substrings():
    d = json.loads(LINKS.read_text())
    docs = {x["docnum"]: x for x in fr.load_dataset_docs()}
    ver = [l for l in d["links"] if l["status"] == "VERIFIED_FINAL_RULE"]
    assert ver
    for l in ver:
        xml = (config.FR_FINAL_RULES_DIR / l["rule_docnum"] / "full_text.xml").read_bytes()
        text = fr.normalized_text(xml)
        doc = docs[l["dataset_docnum"]]
        assert l["evidence"]
        for e in l["evidence"]:
            assert text[e["start"]:e["end"]] == e["quote"]
            if e["type"] == "nprm_citation":
                assert e["quote"] == doc["citation"]
        # at least one evidence item ties to this exact dataset doc
        assert any((e["type"] == "nprm_citation" and e["quote"] == doc["citation"]) or
                   (e["type"] == "nprm_date" and fr.extract_dates(e["quote"] + " NPRM")[0]["date"] == doc["publication_date"])
                   for e in l["evidence"])
        assert fr.shared_dockets(doc["dockets"], next(r for r in d["rules"] if r["fr_docnum"] == l["rule_docnum"])["docket_ids"])


@pytest.mark.skipif(not LINKS.exists(), reason="run scripts/fetch_final_rules.py first")
def test_ad_quotes_exact():
    d = json.loads(LINKS.read_text())
    for r in d["rules"]:
        if r["ad_number"]:
            text = fr.normalized_text((config.FR_FINAL_RULES_DIR / r["fr_docnum"] / "full_text.xml").read_bytes())
            for k in ("ad_number", "amendment"):
                v = r[k]
                assert text[v["start"]:v["end"]] == v["quote"]
