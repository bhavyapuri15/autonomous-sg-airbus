"""Organiser update (31 Oct 2026): regulatory stage, enforceability, dataset history, proposed supersession, citation format,
applicability labels. Real-DB tests use real examples (skipped if the organiser tables are not built); fixture tests cover
ties / missing dates / disagreement / conflicts that the real data does not contain."""
import sqlite3

import pytest

from backend import citation_meta
from backend.api.schemas import (AircraftConfig, CitationRef, DirectiveInfo, Enforceability, RegulatoryStage, SourceTier)
from backend.rules import applicability as A
from backend.rules import revisions as R


def _real():
    from backend.config import DB_PATH
    c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    ok = all(c.execute("select 1 from sqlite_master where name=?", (t,)).fetchone() for t in ("organiser_index", "revision_chains"))
    c.close()
    return ok


needs_real = pytest.mark.skipif(not _real(), reason="organiser tables not in the DB")


# ------------------------------------------------------------------------------------------------ real data
@needs_real
def test_single_publication_docket():
    r = R.revision_status("2026-02923")
    h = r.dataset_history
    assert h.dataset_status == "SINGLE_PUBLICATION" and h.versions_total == 1 and h.latest_record_id == "NPRM-127"
    assert [e.record_id for e in h.history] == ["NPRM-127"] and h.history[0].is_latest
    assert "LATEST_IN_DATASET" in r.status_flags and "SUPERSEDED_IN_DATASET" not in r.status_flags
    assert r.regulatory_stage == RegulatoryStage.PROPOSED_RULE
    assert "Regulatory stage: Proposed rule (NPRM). Latest version in the supplied dataset: NPRM-127 (2026-02-13)." in r.template_text
    assert r.enforceability == Enforceability.FINAL_RULE_PUBLISHED_VERIFIED       # verified FINALIZES edge from 2026-21855
    assert "FINAL_RULE_VERIFIED" in r.status_flags


@needs_real
def test_repeated_docket_chain_and_latest_selection():
    first, last = R.revision_status("E7-5656"), R.revision_status("2011-12165")
    h = first.dataset_history
    assert h.versions_total == 4 and h.docket == "FAA-2007-27715"
    assert [e.record_id for e in h.history] == ["NPRM-302", "NPRM-299", "NPRM-291", "NPRM-270"]      # chronological
    dates = [e.publish_date for e in h.history]
    assert dates == sorted(dates)
    assert h.latest_record_id == "NPRM-270" == max(h.history, key=lambda e: e.publish_date).record_id
    assert h.dataset_status == "SUPERSEDED_IN_DATASET" and h.this_version == 1 and not h.warnings
    assert "SUPERSEDED_IN_DATASET" in first.status_flags and "LATEST_IN_DATASET" not in first.status_flags
    assert last.dataset_history.dataset_status == "LATEST_IN_DATASET" and "LATEST_IN_DATASET" in last.status_flags
    assert first.enforceability == Enforceability.NOT_VERIFIED
    assert first.current_authoritative_status_verified is False
    assert "CURRENT_AUTHORITATIVE_STATUS_UNKNOWN" in first.status_flags


@needs_real
def test_withdrawal_relationship():
    nprm, wd = R.revision_status("E9-26683"), R.revision_status("2010-12673")
    assert nprm.enforceability == Enforceability.PROPOSAL_WITHDRAWN and "WITHDRAWN_IN_DATASET" in nprm.status_flags
    assert any(e.type == "WITHDRAWS" and e.src == "2010-12673" and e.dst == "E9-26683" and e.confidence == "VERIFIED" for e in nprm.edges)
    assert wd.regulatory_stage == RegulatoryStage.WITHDRAWAL_NOTICE and wd.enforceability == Enforceability.PROPOSAL_WITHDRAWN
    assert "Current enforceability: proposal withdrawn" in nprm.template_text


@needs_real
def test_correction_relationship_r1_docs():
    r = R.revision_status("R1-2022-22698")
    assert any(e.type == "CORRECTS" and e.confidence == "VERIFIED" for e in r.edges)
    assert "CORRECTED" in r.status_flags


@needs_real
def test_ad_number_in_sheet_does_not_make_final_rule():
    c = sqlite3.connect("file:" + str(__import__("backend.config", fromlist=["x"]).DB_PATH) + "?mode=ro", uri=True)
    # NPRM-131 (2026-00842): organiser ad_number present, no VERIFIED final rule in the evidence graph
    ad, dn = c.execute("select ad_number, fr_docnum from organiser_index where record_id='NPRM-131'").fetchone()
    assert ad and not c.execute("select 1 from relations where dst=? and type='FINALIZES'", (dn,)).fetchone()
    c.close()
    r = R.revision_status(dn)
    assert r.enforceability == Enforceability.NOT_VERIFIED and "FINAL_RULE_VERIFIED" not in r.status_flags
    assert r.current_authoritative_status_verified is False
    assert "Current enforceability: not verified." in r.template_text


@needs_real
def test_proposed_supersession_not_operative_and_deduplicated():
    r = R.revision_status("2026-21298")          # organiser supersedes_ad 2026-09-02 AND text edge to the same AD
    ps = [p for p in r.proposed_supersedes if p.ad_number == "2026-09-02"]
    assert len(ps) == 1
    p = ps[0]
    assert p.sources == ["document_text", "organiser_supersedes_ad_field"] and p.source == "document_text"
    assert p.evidence.source_tier == SourceTier.FR_FULL_TEXT and p.additional_evidence[0].source_tier == SourceTier.SHEET_METADATA
    assert p.operative_supersession_verified is False
    assert "proposes to supersede AD 2026-09-02 (proposal; not an operative supersession)" in r.template_text


@needs_real
def test_operative_supersession_only_with_verified_final_rule_supersedes_edge():
    r = R.revision_status("R1-2022-22698")   # FINALIZED by 2023-05082 whose text SUPERSEDES AD 2022-14-14
    p = next(p for p in r.proposed_supersedes if p.ad_number == "2022-14-14")
    assert p.operative_supersession_verified is True and p.operative_final_rule == "2023-05082"
    assert "organiser_supersedes_ad_field" in p.sources
    r = R.revision_status("2026-13541")      # also finalized (2026-21278) and its text supersedes organiser AD 2009-04-13
    assert next(p for p in r.proposed_supersedes if p.ad_number == "2009-04-13").operative_supersession_verified
    # every other organiser supersedes_ad row without a VERIFIED final rule must be non-operative
    c = sqlite3.connect("file:" + str(__import__("backend.config", fromlist=["x"]).DB_PATH) + "?mode=ro", uri=True)
    nof = [r_[0] for r_ in c.execute("select fr_docnum from organiser_index where supersedes_ad!='' and fr_docnum!='' and fr_docnum not in "
                                     "(select dst from relations where type='FINALIZES' and confidence='VERIFIED')")]
    c.close()
    assert nof
    for dn in nof:
        assert not any(p.operative_supersession_verified for p in R.revision_status(dn).proposed_supersedes), dn


@needs_real
def test_final_rule_lookup_doc_not_in_dataset():
    r = R.revision_status("2026-21855")
    assert r.dataset_history.dataset_status == "NOT_IN_DATASET" and r.regulatory_stage == RegulatoryStage.FINAL_RULE
    assert citation_meta.enrich(CitationRef(citation_id="x", fr_docnum="2026-21855", quote="q", source_tier="FR_FULL_TEXT")).record_ids == []


# ------------------------------------------------------------------------------------------------ fixture DB
@pytest.fixture()
def fx():
    c = sqlite3.connect(":memory:")
    c.executescript("""
    CREATE TABLE documents(fr_docnum,doc_class,publication_date,source,start_page,pdf_url,xml_url,volume,html_url,docket_ids_json);
    CREATE TABLE relations(id INTEGER PRIMARY KEY,src,dst,type,confidence,evidence_json,note);
    CREATE TABLE sections(fr_docnum,section_path,label,heading,fr_page_start,fr_page_end,pdf_page_start,pdf_page_end,start_char,end_char);
    CREATE TABLE pages(fr_docnum,pdf_page,text);
    CREATE TABLE final_rule_info(fr_docnum,ad_number,ad_start,ad_end,effective_on,supersedes_json);
    CREATE TABLE organiser_index(record_id PRIMARY KEY,sheet_row,docket_number,publish_date,supersedes_ad,ad_number,fr_docnum);
    CREATE TABLE revision_chains(docket_number,version,versions_total,status,record_id,publish_date,subject);
    CREATE TABLE records(row,record_id,fr_docnum);
    """)
    for dn, cls, d in [("A", "NPRM", "2020-01-01"), ("B", "SNPRM", "2020-05-01"), ("C", "NPRM", "2020-05-01"), ("D", "NPRM", "2021-01-01"),
                       ("E", "NPRM", "2021-02-01"), ("W", "WITHDRAWAL", "2021-03-01"), ("F", "FINAL_RULE", "2021-06-01")]:
        src = "fr_final_rule_lookup" if cls == "FINAL_RULE" else "organiser_sheet"
        c.execute("insert into documents values(?,?,?,?,1,NULL,NULL,85,?,?)", (dn, cls, d, src, f"https://www.federalregister.gov/d/{dn}", '["Docket No. FAA-T-1"]'))
    return c


def _oi(c, rid, dn, docket, date, sup=None, ad=None):
    c.execute("insert into organiser_index values(?,?,?,?,?,?,?)", (rid, 1, docket, date, sup, ad, dn))


def _chain(c, docket, rows):
    for i, (rid, date, st) in enumerate(rows, 1):
        c.execute("insert into revision_chains values(?,?,?,?,?,?,'s')", (docket, i, len(rows), st, rid, date))


def _edge(c, s, d, t, conf="VERIFIED"):
    c.execute("insert into relations(src,dst,type,confidence,evidence_json) values(?,?,?,?,'[]')", (s, d, t, conf))


def test_tie_on_latest_date_is_warned_not_resolved(fx):
    for rid, dn, d in [("NPRM-1", "A", "2020-01-01"), ("NPRM-2", "B", "2020-05-01"), ("NPRM-3", "C", "2020-05-01")]:
        _oi(fx, rid, dn, "T-1", d)
    _chain(fx, "T-1", [("NPRM-1", "2020-01-01", "earlier"), ("NPRM-2", "2020-05-01", "earlier"), ("NPRM-3", "2020-05-01", "latest")])
    r = R.revision_status("B", fx)
    h = r.dataset_history
    assert any(w.startswith("TIE:") and "NPRM-2" in w and "NPRM-3" in w and "NPRM-3" in w.split("kept:")[1] for w in h.warnings)
    assert h.latest_record_id == "NPRM-3" and h.dataset_status == "SUPERSEDED_IN_DATASET"       # organiser marker kept
    assert "tied on publication date" in r.template_text


def test_missing_publish_date_is_warned(fx):
    _oi(fx, "NPRM-1", "A", "T-1", None)
    _oi(fx, "NPRM-2", "B", "T-1", "2020-05-01")
    _chain(fx, "T-1", [("NPRM-1", None, "earlier"), ("NPRM-2", "2020-05-01", "latest")])
    h = R.revision_status("A", fx).dataset_history
    assert any(w.startswith("MISSING_DATE") and "NPRM-1" in w for w in h.warnings)
    assert h.history[-1].record_id == "NPRM-1"           # undated sorts last, never silently "latest"
    assert h.latest_record_id == "NPRM-2"


def test_organiser_latest_older_than_other_date_is_disagreement(fx):
    _oi(fx, "NPRM-1", "A", "T-1", "2020-01-01"); _oi(fx, "NPRM-2", "B", "T-1", "2020-05-01")
    _chain(fx, "T-1", [("NPRM-2", "2020-05-01", "earlier"), ("NPRM-1", "2020-01-01", "latest")])
    h = R.revision_status("A", fx).dataset_history
    assert any(w.startswith("DISAGREEMENT") for w in h.warnings) and h.latest_record_id == "NPRM-1"


def test_organiser_latest_contradicting_verified_evidence_warns(fx):
    _oi(fx, "NPRM-1", "A", "T-1", "2020-01-01"); _oi(fx, "NPRM-2", "B", "T-1", "2020-05-01")
    _chain(fx, "T-1", [("NPRM-1", "2020-01-01", "latest"), ("NPRM-2", "2020-05-01", "earlier")])
    _edge(fx, "B", "A", "SUPPLEMENTS")      # evidence: B (SNPRM) comes after A, organiser says A is latest
    assert any("verified evidence" in w for w in R.revision_status("A", fx).dataset_history.warnings)
    # latest being the withdrawal of this NPRM is consistent: no warning
    fx.execute("delete from relations"); fx.execute("delete from organiser_index"); fx.execute("delete from revision_chains")
    _oi(fx, "NPRM-1", "A", "T-1", "2020-01-01"); _oi(fx, "NPRM-4", "W", "T-1", "2021-03-01")
    _chain(fx, "T-1", [("NPRM-1", "2020-01-01", "earlier"), ("NPRM-4", "2021-03-01", "latest")])
    _edge(fx, "W", "A", "WITHDRAWS")
    r = R.revision_status("A", fx)
    assert r.dataset_history.warnings == [] and r.enforceability == Enforceability.PROPOSAL_WITHDRAWN


def test_no_final_rule_evidence_is_not_verified_and_candidate_edges_do_not_count(fx):
    _oi(fx, "NPRM-5", "D", "T-2", "2021-01-01", ad="2021-01-01")           # organiser ad_number present
    _edge(fx, "F", "D", "FINALIZES", "CANDIDATE"); _edge(fx, "W", "D", "WITHDRAWS", "CANDIDATE")
    r = R.revision_status("D", fx)
    assert r.enforceability == Enforceability.NOT_VERIFIED
    assert "FINAL_RULE_VERIFIED" not in r.status_flags and "WITHDRAWN_IN_DATASET" not in r.status_flags
    assert r.dataset_history.dataset_status == "SINGLE_PUBLICATION" and r.status_flags[0] == "LATEST_IN_DATASET"
    assert r.status_flags[-1] == "CURRENT_AUTHORITATIVE_STATUS_UNKNOWN" and r.current_authoritative_status_verified is False


def test_verified_withdrawal_and_final_rule_conflict_is_not_resolved(fx):
    _edge(fx, "W", "D", "WITHDRAWS"); _edge(fx, "F", "D", "FINALIZES")
    r = R.revision_status("D", fx)
    assert r.enforceability == Enforceability.NOT_VERIFIED
    assert {"WITHDRAWN_IN_DATASET", "FINAL_RULE_VERIFIED"} <= set(r.status_flags)


def test_supersession_sources_and_operative_rule(fx):
    _oi(fx, "NPRM-6", "E", "T-3", "2021-02-01", sup="2010-01-02 and 2011-03-04")
    _edge(fx, "E", "AD:2010-01-02", "PROPOSES_TO_SUPERSEDE")
    r = R.revision_status("E", fx)
    by = {p.ad_number: p for p in r.proposed_supersedes}
    assert set(by) == {"2010-01-02", "2011-03-04"}
    assert by["2010-01-02"].sources == ["document_text", "organiser_supersedes_ad_field"]
    assert by["2011-03-04"].source == "organiser_supersedes_ad_field" and by["2011-03-04"].evidence.quote.startswith("supersedes_ad:")
    assert not any(p.operative_supersession_verified for p in r.proposed_supersedes)
    # verified final rule whose text supersedes only one of them
    _edge(fx, "F", "E", "FINALIZES"); _edge(fx, "F", "AD:2011-03-04", "SUPERSEDES")
    by = {p.ad_number: p for p in R.revision_status("E", fx).proposed_supersedes}
    assert by["2011-03-04"].operative_supersession_verified and not by["2010-01-02"].operative_supersession_verified


def test_candidate_final_rule_supersedes_is_not_operative(fx):
    _oi(fx, "NPRM-6", "E", "T-3", "2021-02-01", sup="2010-01-02")
    _edge(fx, "F", "E", "FINALIZES", "CANDIDATE"); _edge(fx, "F", "AD:2010-01-02", "SUPERSEDES")
    assert not R.revision_status("E", fx).proposed_supersedes[0].operative_supersession_verified


def test_status_field_current_is_ignored():
    """Spec: status='Current' is meaningless; no code path reads a status column for regulatory state."""
    import inspect
    src = inspect.getsource(R.revision_status) + inspect.getsource(R.dataset_history)
    assert "status_raw" not in src and "'Current'" not in src


# ------------------------------------------------------------------------------------------------ citation format
@needs_real
def test_enrich_fills_all_fields_on_dataset_doc():
    c = citation_meta.enrich(CitationRef(citation_id="x", fr_docnum="2026-21387", quote="q", source_tier="FR_FULL_TEXT"))
    assert c.record_ids == ["NPRM-001"] and c.docket_number == "FAA-2026-11814"
    assert c.federal_register_citation.startswith("91 FR ") and c.source_url.startswith("https://www.federalregister.gov/")
    sec = R._cit_ref  # noqa
    from backend.api import deps
    q = deps.applicability_quote("2026-21387")
    e = citation_meta.enrich(q)
    assert e.section and "Applicability" in e.section and e.federal_register_citation == f"91 FR {q.fr_page}" and e.record_ids == ["NPRM-001"]


@needs_real
def test_enrich_sheet_citation_and_directive_info():
    c = citation_meta.enrich(CitationRef(citation_id="s", fr_docnum="", quote="docket: x", source_tier="SHEET_METADATA", sheet_row=271))
    assert c.record_ids == ["NPRM-270"]
    d = citation_meta.enrich_directive(DirectiveInfo(fr_docnum="2011-12165"))
    assert d.record_ids == ["NPRM-270"] and d.regulatory_stage == "WITHDRAWAL_NOTICE" and d.source_url


def test_enrich_never_overwrites_and_unknown_doc_is_untouched():
    c = CitationRef(citation_id="x", fr_docnum="NOPE-1", quote="q", source_tier="FR_FULL_TEXT")
    assert citation_meta.enrich(c) is c


# ------------------------------------------------------------------------------------------------ applicability labels
def test_applicability_labels_synthetic_unknown_stage():
    cfg = AircraftConfig(model="A320-214", serial="123")
    _, ev, res = A.evaluate_text("(c) This AD applies to all Airbus Model A320-214 airplanes.", cfg)
    assert res.value.value == "APPLICABLE" and res.basis == "UNKNOWN" and "proposed rule" not in res.label
    _, ev, res = A.evaluate_text("(c) This AD applies to all Airbus Model A330-300 airplanes.", cfg)
    assert res.value.value == "NOT_APPLICABLE" and res.label.startswith("Not applicable")


@needs_real
def test_applicability_labels_real_proposal():
    res = A.evaluate_document("2026-21387", AircraftConfig(model="AS355NP", serial="1234"))
    assert res.basis == "PROPOSED_RULE"
    assert res.label == "Applicable under the proposed rule" and "under the proposed rule" in res.template_text.lower()
    assert "proposed AD would apply" in res.template_text and "must" not in res.template_text.lower()
    res = A.evaluate_document("2026-21387", AircraftConfig(model="A320-214"))
    assert res.label == "Not applicable under the proposed rule" and "would not apply" in res.template_text
    res = A.evaluate_document("2026-21387", AircraftConfig(model="AS355NP"))     # no serial -> may be UNKNOWN; label never "Applicable" then
    if res.value.value == "UNKNOWN":
        assert res.label == "Applicability not determined" and res.basis == "PROPOSED_RULE"


@needs_real
def test_applicability_basis_final_rule_doc():
    res = A.evaluate_document("2026-21855", AircraftConfig(model="A320-214"))
    assert res.basis == "FINAL_RULE"
    assert res.label in ("Applicable under the published final rule", "Not applicable under the published final rule",
                         "Applicability not determined")
