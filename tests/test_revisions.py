import json, re, sqlite3
import pytest
from backend import config
from backend.api.schemas import RevisionStatus
from backend.rules import revisions as R
from backend.ingestion import final_rules_ingest as fri


# ------------------------------------------------------------------ unit tests (SYNTHETIC snippets, not from the corpus)
def test_citation_match_exact_volume_and_page():
    t = "The NPRM was published in the Federal Register (66 FR 21107). Another is 66 FR 21108 and 67 FR 21107."
    m = R.find_citations(t, 66, 21107)
    assert len(m) == 1 and t[m[0]["start"]:m[0]["end"]] == "66 FR 21107"


def test_date_needs_context_and_matches_iso():
    t = "The NPRM was published on March 23, 2005 in the Register."
    assert len(R.find_dates(t, "2005-03-23")) == 1
    assert R.find_dates(t, "2005-03-24") == []
    assert R.find_dates("Effective March 23, 2005 only.", "2005-03-23") == []   # no NPRM/proposed/published context


def test_date_guard_rejects_when_adjacent_citation_disagrees():
    t = "the NPRM published on March 23, 2005 (70 FR 99999) was"
    sp = R.find_dates(t, "2005-03-23")[0]
    assert R.date_guard_ok(t, sp, "70 FR 14585") is False
    assert R.date_guard_ok(t, sp, "70 FR 99999") is True
    t2 = "the NPRM published on March 23, 2005 was"
    assert R.date_guard_ok(t2, R.find_dates(t2, "2005-03-23")[0], "70 FR 14585") is True


def test_supersede_proposal_only_after_verb_and_no_negation_leak():
    t = "This proposed AD would supersede AD 2010-01-02. It does not mention AD 2011-03-04."
    assert [x[0] for x in R.supersede_proposals(t)] == ["2010-01-02"]
    assert R.supersede_proposals("AD 2010-01-02 was issued. The FAA is removing nothing.") == []
    t = "The FAA proposes to supersede AD 2003-05-06 and AD 2004-07-08, which require inspections."
    assert [x[0] for x in R.supersede_proposals(t)] == ["2003-05-06", "2004-07-08"]


def test_reanchor_whitespace_normalized_and_prefers_keyword_paragraph():
    text = "Intro 70 FR 14585 unrelated.\n\nThe NPRM was published in the Federal Register (70 FR 14585)."
    s, e, mode, n, kw = fri.reanchor(text, "70 FR 14585")
    assert text[s:e] == "70 FR 14585" and n == 2 and kw and s > 40
    s, e, mode, n, kw = fri.reanchor("a  March\n 1,  2000 b", "March 1, 2000")
    assert mode == "whitespace_normalized" and "March" in "a  March\n 1,  2000 b"[s:e]
    assert fri.reanchor("nothing", "70 FR 1") is None


# synthetic DB for status precedence
@pytest.fixture()
def syn():
    c = sqlite3.connect(":memory:")
    c.executescript("""
    CREATE TABLE documents(fr_docnum,doc_class,publication_date,source,start_page,pdf_url,xml_url);
    CREATE TABLE relations(id INTEGER PRIMARY KEY,src,dst,type,confidence,evidence_json,note);
    CREATE TABLE sections(fr_docnum,section_path,label,fr_page_start,fr_page_end,pdf_page_start,pdf_page_end,start_char,end_char);
    CREATE TABLE pages(fr_docnum,pdf_page,text);
    CREATE TABLE final_rule_info(fr_docnum,ad_number,ad_start,ad_end,effective_on);
    INSERT INTO documents VALUES('N','NPRM','2020-01-01','organiser_sheet',1,NULL,NULL),('W','WITHDRAWAL','2020-06-01','organiser_sheet',2,NULL,NULL),
      ('S','SNPRM','2020-03-01','organiser_sheet',3,NULL,NULL),('F','FINAL_RULE','2020-09-01','fr_final_rule_lookup',4,NULL,NULL),('U','NPRM','2021-01-01','organiser_sheet',5,NULL,NULL);
    INSERT INTO final_rule_info VALUES('F','2020-01-01',0,1,'2020-10-01');
    """)
    return c


def _edge(c, s, d, t, conf="VERIFIED"):
    c.execute("INSERT INTO relations(src,dst,type,confidence,evidence_json,note) VALUES(?,?,?,?,?,?)", (s, d, t, conf, "[]", None))


def test_precedence_withdrawn_over_supplemented_over_finalized(syn):
    _edge(syn, "F", "N", "FINALIZES")
    assert R.revision_status("N", syn).status == RevisionStatus.FINALIZED
    _edge(syn, "S", "N", "SUPPLEMENTS")
    assert R.revision_status("N", syn).status == RevisionStatus.SUPPLEMENTED
    _edge(syn, "W", "N", "WITHDRAWS")
    r = R.revision_status("N", syn)
    assert r.status == RevisionStatus.WITHDRAWN and "imposes no requirement" in r.template_text
    assert r.current_authoritative_status_verified is False


def test_candidate_edges_never_change_status_and_unverified_default(syn):
    _edge(syn, "F", "U", "FINALIZES", "CANDIDATE"); _edge(syn, "W", "U", "WITHDRAWS", "CANDIDATE")
    r = R.revision_status("U", syn)
    assert r.status == RevisionStatus.PROPOSAL_STATUS_UNVERIFIED and "unverified" in r.template_text
    assert "legally current" not in r.template_text.replace("not shown to be legally current", "")


def test_finalized_text_has_warning_and_flag_false(syn):
    _edge(syn, "F", "N", "FINALIZES")
    r = R.revision_status("N", syn)
    assert "Later amendments or supersession of the final AD were not checked." in r.template_text
    assert r.current_authoritative_status_verified is False
    assert "AD 2020-01-01 [quoted]" in r.template_text


def test_proposes_to_supersede_never_says_is_superseded(syn):
    _edge(syn, "N", "AD:2010-01-02", "PROPOSES_TO_SUPERSEDE")
    t = R.revision_status("N", syn).template_text
    assert "proposes to supersede AD 2010-01-02" in t and "is superseded" not in t and "was superseded" not in t


# ------------------------------------------------------------------ integration tests on the real DB
@pytest.fixture(scope="module")
def conn():
    if not config.DB_PATH.exists():
        pytest.skip("DB not built")
    c = sqlite3.connect(config.DB_PATH); c.row_factory = None
    yield c
    c.close()


def _edges(conn, typ=None, conf=None):
    q = "SELECT src,dst,type,confidence,evidence_json,note FROM relations WHERE 1=1"
    a = []
    if typ: q += " AND type=?"; a.append(typ)
    if conf: q += " AND confidence=?"; a.append(conf)
    return [(s, d, t, c, json.loads(e), n) for s, d, t, c, e, n in conn.execute(q, a)]


def test_every_verified_text_evidence_equals_doc_text_slice(conn):
    n = 0
    for s, d, t, c, ev, note in _edges(conn, conf="VERIFIED"):
        assert ev, (s, d, t)
        for e in ev:
            if "meta_field" in e: continue
            text = conn.execute("SELECT text FROM doc_text WHERE fr_docnum=?", (e["fr_docnum"],)).fetchone()[0]
            assert text[e["start"]:e["end"]] == e["quote"], (s, d, t)
            n += 1
    assert n > 200


def test_no_verified_edge_from_docket_alone(conn):
    assert not [e for e in _edges(conn, "SAME_DOCKET") if e[3] == "VERIFIED"]
    for s, d, t, c, ev, note in _edges(conn, conf="VERIFIED"):
        assert ev and all(("quote" in e and e["quote"]) or "meta_field" in e for e in ev)
    for s, d, t, c, ev, note in _edges(conn, conf="VERIFIED"):
        if t in ("WITHDRAWS", "SUPPLEMENTS"):          # docket + text reference required
            dk = lambda x: R.o1.normalize_dockets(json.loads(conn.execute("SELECT docket_ids_json FROM documents WHERE fr_docnum=?", (x,)).fetchone()[0]))
            assert R.docket_overlap(dk(s), dk(d)), (s, d)
            pd = lambda x: conn.execute("SELECT publication_date FROM documents WHERE fr_docnum=?", (x,)).fetchone()[0]
            assert pd(d) < pd(s)


def test_proposes_to_supersede_not_rendered_as_superseded(conn):
    edges = _edges(conn, "PROPOSES_TO_SUPERSEDE")
    assert len(edges) > 20
    for s, d, t, c, ev, n in edges[:60]:
        assert d.startswith("AD:") and re.search(r"supersede", ev[0]["quote"], re.I)
        txt = R.revision_status(s, conn).template_text
        assert f"{d[3:]} is superseded" not in txt and f"{d[3:]} was superseded" not in txt
        assert f"proposes to supersede AD {d[3:]}" in txt


def test_2026_21387_unverified(conn):
    # no WITHDRAWS/SUPPLEMENTS/FINALIZES edge points at it (checked in DB), so status must be unverified
    assert not conn.execute("SELECT 1 FROM relations WHERE dst='2026-21387' AND type IN ('WITHDRAWS','SUPPLEMENTS','FINALIZES') AND confidence='VERIFIED'").fetchone()
    r = R.revision_status("2026-21387", conn)
    assert r.status == RevisionStatus.PROPOSAL_STATUS_UNVERIFIED and r.current_authoritative_status_verified is False


def test_three_real_withdrawals(conn):
    # Read by hand. 2010-12673 text: "That NPRM was published in the Federal Register on November 5, 2009 (74 FR 57266)" and
    # E9-26683 is 74 FR 57266, 2009-11-05, same docket FAA-2009-1028 -> withdrawal of E9-26683.
    # E6-1415: "published ... March 23, 2005 (70 FR 14585)"; 05-5694 is 70 FR 14585, docket FAA-2005-20691.
    # 2014-30911: "the proposed rule, which was published ... January 30, 2013 (78 FR 6247), is withdrawn"; 2013-01953 is 78 FR 6247.
    for s, d, quote in [("2010-12673", "E9-26683", "74 FR 57266"), ("E6-1415", "05-5694", "70 FR 14585"), ("2014-30911", "2013-01953", "78 FR 6247")]:
        e = [x for x in _edges(conn, "WITHDRAWS", "VERIFIED") if x[0] == s]
        assert [x[1] for x in e] == [d]
        assert e[0][4][0]["quote"] == quote
        assert R.revision_status(d, conn).status == RevisionStatus.WITHDRAWN


def test_o1_example_2026_02923_finalized_by_2026_21855(conn):
    r = R.revision_status("2026-02923", conn)
    assert r.status == RevisionStatus.FINALIZED
    e = [x for x in r.edges if x.type == "FINALIZES" and x.confidence == "VERIFIED"]
    assert [x.src for x in e] == ["2026-21855"] and e[0].evidence[0].fr_docnum == "2026-21855"
    assert e[0].evidence[0].fr_page and e[0].evidence[0].pdf_page
    assert "AD 2026-21-09" in r.template_text and r.current_authoritative_status_verified is False


def test_final_rule_docs_and_flags(conn):
    assert conn.execute("SELECT count(*) FROM documents WHERE source='fr_final_rule_lookup'").fetchone()[0] == 75
    assert conn.execute("SELECT count(*) FROM documents WHERE is_rfc=1 AND doc_class='FINAL_RULE'").fetchone()[0] == 2
    assert conn.execute("SELECT count(*) FROM final_rule_links WHERE o1_status='VERIFIED_FINAL_RULE' AND status!='VERIFIED'").fetchone()[0] == 0


def test_overlay_and_status_distribution(conn):
    ov = R.revision_overlay("2026-21387", conn)
    assert ov and all("legally current" not in o or "not shown" in o for o in ov)
    assert any("final rule" in o for o in R.revision_overlay("2026-02923", conn))
