"""Organiser index workbook: loader, record_id mapping, revision_chains invariants, record-id routing."""
import collections
import json
import sqlite3

import pytest

from backend import config
from backend.ingestion import index_loader as il
from backend.retrieval.id_router import IDRouter, load_record_map

pytestmark = pytest.mark.skipif(not config.INDEX_XLSX.exists() or not config.DB_PATH.exists(), reason="index workbook / DB not built")


@pytest.fixture(scope="module")
def conn():
    c = sqlite3.connect(config.DB_PATH)
    c.row_factory = sqlite3.Row
    yield c
    c.close()


@pytest.fixture(scope="module")
def oi(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM organiser_index ORDER BY record_id")]


@pytest.fixture(scope="module")
def chains(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM revision_chains ORDER BY docket_number, version")]


def test_workbook_sha_and_loader():
    assert il.verify_sha() == config.INDEX_SHA256
    d = il.load_index()
    assert len(d["records"]) == config.INDEX_N_RECORDS == 431
    assert len(d["chains"]) == config.INDEX_N_CHAIN_ROWS
    assert len(d["notes"]) == 6


def test_431_unique_records_each_mapped_to_one_sheet_row(conn, oi):
    assert len(oi) == 431
    assert len({r["record_id"] for r in oi}) == 431
    assert len({r["sheet_row"] for r in oi}) == 431 and None not in {r["sheet_row"] for r in oi}
    # records.record_id is the inverse mapping, 1:1
    rec = {r[0]: r[1] for r in conn.execute("SELECT row, record_id FROM records")}
    assert sum(1 for v in rec.values() if v) == 431
    for r in oi:
        assert rec[r["sheet_row"]] == r["record_id"]
    assert collections.Counter(r["match_method"] for r in oi) == {"positional_verified": 431}


def test_mapping_is_verified_not_assumed():
    # a shuffled/shifted index must NOT be accepted positionally
    sheet = [dict(row=2, docket_raw="D-1", publish_date="2020-01-01", page_number_raw="Pages 1-2", subject="A", issue_date="", ad_number="", make_raw="", citation=""),
             dict(row=3, docket_raw="D-2", publish_date="2020-02-02", page_number_raw="Pages 3-4", subject="B", issue_date="", ad_number="", make_raw="", citation="")]
    def x(rid, dk, pd, pg, sub):
        return dict(record_id=rid, docket_number=dk, publish_date=pd, pages=pg, subject=sub, issue_date="", ad_number=None, make="", citation="",
                    federal_register_link=None)
    res = il.map_records([x("NPRM-001", "D-2", "2020-02-02", "Pages 3-4", "B"), x("NPRM-002", "D-1", "2020-01-01", "Pages 1-2", "A")], sheet)
    assert [(r[0]["record_id"], r[1]["row"], r[2]) for r in res] == [("NPRM-001", 3, "content_unique"), ("NPRM-002", 2, "content_unique")]
    bad = il.map_records([x("NPRM-001", "D-9", "2020-01-01", "Pages 1-2", "A")], sheet)
    assert bad[0][2] == "positional_unverified" and bad[0][3]["docket"] == "mismatch"


def test_header_located_by_content_not_row_number():
    d = il.load_index()
    assert d["records"][0]["record_id"] == "NPRM-001" and d["records"][0]["index_sheet_row"] == 4


def test_publish_dates_iso_valid(oi, chains):
    assert all(il.valid_iso(r["publish_date"]) for r in oi)
    assert all(il.valid_iso(r["issue_date"]) for r in oi)
    assert all(il.valid_iso(c["publish_date"]) for c in chains)
    assert not il.valid_iso("2020-13-01") and not il.valid_iso("1/2/2020") and not il.valid_iso(None)


def test_index_dates_agree_with_our_parse(conn, oi):
    # every difference is recorded, never silent
    for r in oi:
        ours = conn.execute("SELECT publish_date FROM records WHERE row=?", (r["sheet_row"],)).fetchone()[0]
        disc = json.loads(r["discrepancies_json"])
        assert (ours == r["publish_date"]) == ("publish_date" not in disc)


def test_fr_docnum_mapping_matches_records(conn, oi):
    for r in oi:
        assert r["fr_docnum"] == conn.execute("SELECT fr_docnum FROM records WHERE row=?", (r["sheet_row"],)).fetchone()[0]
    assert sum(1 for r in oi if r["fr_docnum"]) == 428
    for r in oi:   # index URLs never contradict our resolved docnum
        dns = il.link_docnums(r["federal_register_link"])
        if dns and r["fr_docnum"]:
            assert r["fr_docnum"] in dns, r["record_id"]


def test_serial_flag_is_integer_boolean(oi):
    assert {r["mentions_serial_numbers"] for r in oi} <= {0, 1}
    assert sum(r["mentions_serial_numbers"] for r in oi) == 16


def test_revision_chain_invariants(conn, oi, chains):
    by = collections.defaultdict(list)
    for c in chains:
        by[c["docket_number"]].append(c)
    assert len(by) == config.INDEX_N_CHAIN_DOCKETS == 99 and len(chains) == 207
    sheet = collections.defaultdict(set)
    for row, dk, rid in conn.execute("SELECT row, docket_raw, record_id FROM records"):
        sheet[dk].add(rid)
    assert {k for k, v in sheet.items() if len(v) > 1} == set(by)
    oi_by = {r["record_id"]: r for r in oi}
    for dk, v in by.items():
        assert len(v) > 1 and all(c["versions_total"] == len(v) for c in v)
        assert [c["version"] for c in v] == list(range(1, len(v) + 1))
        lat = [c for c in v if c["status"] == "latest"]
        assert len(lat) == 1 and {c["status"] for c in v} <= {"latest", "earlier"}
        assert lat[0]["publish_date"] == max(c["publish_date"] for c in v)
        assert lat[0]["version"] == len(v)
        dates = [c["publish_date"] for c in v]
        assert len(dates) == len(set(dates)), f"publish_date tie in {dk}"   # none today; a tie would need explicit handling
        assert {c["record_id"] for c in v} == sheet[dk]
        for c in v:
            assert oi_by[c["record_id"]]["docket_number"] == dk and oi_by[c["record_id"]]["publish_date"] == c["publish_date"]


# ---- router ------------------------------------------------------------------------------------------------------------
DOCS = [dict(fr_docnum="2026-21387", volume=91, start_page=66019, end_page=66022, publication_date="2026-10-19", dockets=["FAA-2026-11814"], doc_class="NPRM"),
        dict(fr_docnum="2026-21298", volume=91, start_page=66012, end_page=66016, publication_date="2026-10-19", dockets=["FAA-2026-11811"], doc_class="NPRM")]
RECS = {"NPRM-001": "2026-21387", "NPRM-002": "2026-21298", "NPRM-099": "2026-21387", "NPRM-431": None}


@pytest.mark.parametrize("q", ["NPRM-1", "NPRM-001", "nprm-001", "NPRM 001", "what does NPRM_1 say?"])
def test_record_id_forms_resolve(q):
    res = IDRouter(DOCS, record_ids=RECS).route(q)
    assert [e["fr_docnum"] for e in res.exact] == ["2026-21387"]
    assert res.exact[0]["label"] == "organiser record NPRM-001" and res.exact[0]["id_type"] == "record_id"
    assert res.near_miss == []


def test_unknown_record_id_gives_near_misses_only():
    res = IDRouter(DOCS, record_ids=RECS).route("NPRM-999")
    assert res.exact == []
    assert res.near_miss and all(n["near_miss"] and n["id_type"] == "record_id" for n in res.near_miss)
    assert "NPRM-099" in [n["suggestion"] for n in res.near_miss]


def test_record_without_document_has_no_hit():
    assert IDRouter(DOCS, record_ids=RECS).route("NPRM-431").exact == []


def test_router_unchanged_without_records():
    assert IDRouter(DOCS).route("NPRM-001").exact == []


def test_real_record_map_routes(conn):
    m = load_record_map()
    assert len(m) == 431
    from backend.retrieval.chunker import load_doc_meta
    r = IDRouter(list(load_doc_meta(conn).values()), record_ids=m).route("NPRM 001")
    assert r.exact and r.exact[0]["fr_docnum"] == m["NPRM-001"] and r.exact[0]["label"] == "organiser record NPRM-001"
    assert IDRouter(list(load_doc_meta(conn).values()), record_ids=m).route("NPRM-999").exact == []
