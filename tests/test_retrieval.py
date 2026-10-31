import random
import sqlite3
import time

import pytest

from backend.config import DB_PATH
from backend.retrieval import hybrid_search as hs
from backend.retrieval.chunker import build_chunks
from backend.retrieval.id_router import IDRouter, edit1

DOCS = [
    dict(fr_docnum="2026-21387", volume=91, start_page=66019, end_page=66022, publication_date="2026-10-19", dockets=["FAA-2026-11814"]),
    dict(fr_docnum="01-10467", volume=66, start_page=21107, end_page=21110, publication_date="2001-04-27", dockets=["2000-NM-120-AD"]),
    dict(fr_docnum="E9-322", volume=74, start_page=1, end_page=3, publication_date="2009-01-09", dockets=[]),
    dict(fr_docnum="R1-2022-23012", volume=87, start_page=5, end_page=9, publication_date="2022-01-09", dockets=[]),
]


@pytest.fixture(scope="module")
def router():
    return IDRouter(DOCS, lambda n: [("2026-21387", 0)] if n == "2026-21-03" else [], ["2026-21-03"])


@pytest.fixture(scope="module")
def built():
    return build_chunks()


def test_chunk_text_equals_span(built):
    chunks, _ = built
    c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    texts = dict(c.execute("select fr_docnum, text from doc_text"))
    assert chunks
    for ch in chunks:
        assert ch["text"] == texts[ch["fr_docnum"]][ch["start_char"]:ch["end_char"]]


def test_chunk_ids_stable_and_unique(built):
    a = [x["chunk_id"] for x in built[0]]
    b = [x["chunk_id"] for x in build_chunks()[0]]
    assert a == b and len(set(a)) == len(a)


def test_applicability_never_split(built):
    chunks, _ = built
    c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    rows = c.execute("select fr_docnum, top_path, min(start_char), max(end_char) from sections "
                     "where kind='proposed_ad_paragraph' and lower(heading) like 'applicab%' and level=1 group by fr_docnum, top_path").fetchall()
    assert len(rows) >= 280
    by = {(x["fr_docnum"], x["start_char"], x["end_char"]) for x in chunks if x["is_applicability"]}
    for dn, tp, s, e in rows:
        assert (dn, s, e) in by


@pytest.mark.parametrize("q,typ,val", [
    ("FAA-2026-11814", "docket", "2026-21387"), ("faa-2026-11814", "docket", "2026-21387"),
    ("FAA 2026-11814", "docket", "2026-21387"), ("FAA-2026-11814-R1", "docket", "2026-21387"),
    ("2000-NM-120-AD", "docket", "01-10467"), ("91 FR 66019", "fr_citation", "2026-21387"),
    ("2026-21387", "fr_docnum", "2026-21387"), ("E9-322", "fr_docnum", "E9-322"),
    ("01-10467", "fr_docnum", "01-10467"), ("R1-2022-23012", "fr_docnum", "R1-2022-23012"),
])
def test_router_formats(router, q, typ, val):
    r = router.route(q)
    assert r.exact and r.exact[0]["fr_docnum"] == val and r.exact[0]["id_type"] == typ


def test_router_ad_vs_docnum(router):
    r = router.route("2026-21-03")
    assert [d["id_type"] for d in r.detected] == ["ad_number"]
    assert r.exact[0]["label"] == "mentions AD 2026-21-03"
    r = router.route("2026-21387")
    assert [d["id_type"] for d in r.detected] == ["fr_docnum"]


def test_near_miss_not_result(router):
    r = router.route("2026-21388")
    assert r.exact == [] and r.near_miss[0]["suggestion"] == "2026-21387" and r.near_miss[0]["near_miss"]
    assert edit1("abc", "abd") and not edit1("abc", "abc")


@pytest.fixture(scope="module")
def ix():
    return hs.get_index(reload=True)


def test_docket_exact_rank1(ix):
    rnd = random.Random(3)
    cnt = {}
    for d in ix.docs.values():
        for k in d["dockets"]:
            cnt.setdefault(k, []).append(d["fr_docnum"])
    uniq = sorted(k for k, v in cnt.items() if len(v) == 1 and k.startswith("FAA-"))
    for k in rnd.sample(uniq, 10):
        h = hs.search(k, 5)
        assert h[0]["fr_docnum"] == cnt[k][0] and "exact_id" in h[0]["match_sources"]


def test_fr_citation(ix):
    h = hs.search("91 FR 66019", 5)
    assert h[0]["fr_docnum"] == "2026-21387"


def test_model_token(ix):
    h = hs.search("AS355NP", 3)
    assert "2026-21387" in [x["fr_docnum"] for x in h]


def test_hostile_query(ix):
    for q in ['"AND OR NOT ( * ', "NEAR(a b) ^ : - \"", "***", "'; drop table fts;--"]:
        assert isinstance(hs.search(q, 5), list)


def test_filters(ix):
    h = hs.search("airworthiness directive", 10, {"doc_class": "WITHDRAWAL"})
    assert h and all(x["doc_class"] == "WITHDRAWAL" for x in h)
    h = hs.search("inspection", 10, {"model": "AS355NP"})
    assert h and all("AS355NP" in ix.docs_models(x["fr_docnum"]) for x in h)
    h = hs.search("inspection", 10, {"date_from": "2026-01-01"})
    assert h and all(x["publication_date"] >= "2026-01-01" for x in h)
    h = hs.search("inspection", 10, {"docket": "FAA-2026-11814"})
    assert h and all(x["fr_docnum"] == "2026-21387" for x in h)


def test_doc_level_and_hit_schema(ix):
    h = hs.search("rotorcraft servo-control torque", 10, doc_level=True)
    assert len({x["fr_docnum"] for x in h}) == len(h)
    s = hs.to_search_hit(h[0])
    assert s.citation.citation_id == h[0]["citation_id"] and s.citation.source_tier.value == "FR_FULL_TEXT"


def test_warm_latency(ix):
    hs.search("warmup", 3)
    ts = []
    for q in ["AS355NP", "FAA-2026-11814", "main rotor servo control", "PA-28-140", "S/N 28-7125001"] * 4:
        t = time.perf_counter(); hs.search(q, 10); ts.append((time.perf_counter() - t) * 1000)
    ts.sort()
    assert ts[int(0.95 * (len(ts) - 1))] < 3000


# ---- exact-ID routing fixes (bare numbers, legacy dockets, groups, near-miss) ----
DOCS2 = [
    dict(fr_docnum="03-30676", volume=68, start_page=1, end_page=2, publication_date="2003-12-01", dockets=["FAA-2003-16645"], doc_class="NPRM"),
    dict(fr_docnum="2003-16645", volume=68, start_page=5, end_page=6, publication_date="2003-12-02", dockets=[], doc_class="NPRM"),  # docnum collides w/ bare docket
    dict(fr_docnum="2026-21387", volume=91, start_page=7, end_page=8, publication_date="2026-10-19", dockets=["FAA-2026-11814"], doc_class="NPRM"),
    dict(fr_docnum="00-11177", volume=65, start_page=9, end_page=10, publication_date="2000-05-05", dockets=["99-NE-46-AD"], doc_class="FINAL_RULE"),
    dict(fr_docnum="01-13183", volume=66, start_page=11, end_page=12, publication_date="2001-05-25", dockets=["99-NE-46"], doc_class="NPRM"),
    dict(fr_docnum="01-30952", volume=66, start_page=13, end_page=14, publication_date="2001-12-19", dockets=["99-NE-46-AD"], doc_class="CORRECTION"),
    dict(fr_docnum="03-27322", volume=68, start_page=15, end_page=16, publication_date="2003-10-30", dockets=["2000-NM-168-AD"], doc_class="WITHDRAWAL"),
    dict(fr_docnum="05-613", volume=70, start_page=17, end_page=18, publication_date="2005-01-10", dockets=["2000-NM-168-AD"], doc_class="NPRM"),
    dict(fr_docnum="2000-NM-1680", volume=1, start_page=1, end_page=1, publication_date="2000-01-01", dockets=["2000-NM-16-AD"], doc_class="NPRM"),
]


@pytest.fixture(scope="module")
def router2():
    return IDRouter(DOCS2)


def test_bare_docket_not_docnum(router2):
    r = router2.route("2026-11814")  # not a docnum; FAA-2026-11814 exists
    assert [e["fr_docnum"] for e in r.exact] == ["2026-21387"] and r.near_miss == []


def test_bare_both_docnum_first(router2):
    r = router2.route("2003-16645")
    assert [e["fr_docnum"] for e in r.exact] == ["2003-16645", "03-30676"]
    assert r.exact[0]["id_type"] == "fr_docnum" and r.exact[1]["id_type"] == "docket"
    assert "FR document number" in r.exact[0]["label"] and "docket" in r.exact[1]["label"]


@pytest.mark.parametrize("q", ["2000 NM 168 AD", "2000-nm-168-ad", "2000NM168AD", "2000 nm 168 ad"])
def test_legacy_docket_spacing(router2, q):
    r = router2.route(q)
    assert r.detected[0]["normalized"] == "2000-NM-168-AD"
    assert {e["fr_docnum"] for e in r.exact} == {"03-27322", "05-613"}


def test_legacy_normalization_never_other_id(router2):
    # '2000 NM 16' must not run into '2000-NM-168' (different existing ID) and vice versa
    assert [e["fr_docnum"] for e in router2.route("2000 NM 16 AD").exact] == ["2000-NM-1680"]
    assert {e["fr_docnum"] for e in router2.route("2000NM168AD").exact} == {"03-27322", "05-613"}


def test_normalized_variants_map_to_own_group_on_real_index(ix):
    import re
    for k, grp in ix.router.by_docket.items():
        m = re.fullmatch(r"(\d{2,4})-([A-Z]{2,4})-(\d{1,4})(-AD)?", k)
        if not m:
            continue
        for q in (f"{m[1]} {m[2]} {m[3]} AD", f"{m[1]}{m[2]}{m[3]}ad".lower()):
            assert [e["fr_docnum"] for e in ix.router.route(q).exact] == ix.router._docket_group(k.removesuffix("-AD")), q


def test_group_order_deterministic(router2):
    r = router2.route("99-NE-46")
    assert [e["fr_docnum"] for e in r.exact] == ["01-13183", "01-30952", "00-11177"]  # NPRM, correction, final
    r = router2.route("2000-NM-168-AD")
    assert [e["fr_docnum"] for e in r.exact] == ["05-613", "03-27322"]  # NPRM before withdrawal


def test_group_all_members_returned(router2):
    assert {e["fr_docnum"] for e in router2.route("99-NE-46-AD").exact} == {"00-11177", "01-13183", "01-30952"}


def test_near_miss_only_when_edit_missing(router2):
    r = router2.route("FAA-2026-11815")
    assert r.exact == [] and r.near_miss and r.near_miss[0]["suggestion"] == "FAA-2026-11814"
    r = router2.route("FAA-2026-11814")
    assert r.exact and r.near_miss == []
    r = router2.route("2026-11815")  # bare edit of a docket
    assert r.exact == [] and any(n["suggestion"] == "FAA-2026-11814" for n in r.near_miss)


def test_near_miss_separate_from_hits(ix):
    out = hs.search_ex("FAA-2026-11815", 5)
    assert out["near_miss"] and all("near_miss" not in h for h in out["hits"])
    assert not any("exact_id" in h["match_sources"] for h in out["hits"])
    assert hs.search_ex("FAA-2026-11814", 5)["near_miss"] == []


@pytest.mark.parametrize("q", ["Does the 737 max 8 proposal require inspections?", "the 2026 AS 355 rule",
                               "range of 2000 nm 168 hours"])
def test_prose_not_detected_as_legacy_docket(q):
    # orchestrator review: ordinary phrases must not become docket IDs (would cause false DIRECTIVE_NOT_FOUND)
    from backend.retrieval import hybrid_search as hs
    assert not [d for d in hs.search_ex(q, top_k=1).get("detected_ids", []) if d["id_type"] == "docket"]
