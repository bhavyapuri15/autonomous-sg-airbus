import json, re, sqlite3, tempfile
from pathlib import Path
import pymupdf, pytest
from backend import config
from backend.ingestion import build_db, fr_xml_parser as fxp, pdf_parser as pp
from backend.ingestion.build_db import classify_doc

# ------------------------------------------------------------------ unit tests on small snippets
XML_PAGES = b"""<PRORULE><PREAMB><SUM><HD SOURCE="HED">SUMMARY:</HD><P>First para on start page.</P></SUM></PREAMB>
<SUPLINF><HD SOURCE="HED">SUPPLEMENTARY INFORMATION:</HD><HD SOURCE="HD1">Background</HD>
<P>Alpha beta <PRTPAGE P="101"/>gamma delta.</P><P>Third on page 101.</P></SUPLINF></PRORULE>"""


def test_text_before_first_marker_is_start_page():
    d = fxp.parse_fr_xml(XML_PAGES, 100)
    s = next(x for x in d.sections if x["path"] == "preamble/SUMMARY")
    assert (s["fr_page_start"], s["fr_page_end"]) == (100, 100)
    assert d.page_at(0) == 100


def test_paragraph_crossing_marker_spans_two_pages():
    d = fxp.parse_fr_xml(XML_PAGES, 100)
    s = next(x for x in d.sections if x["path"].endswith("/Background"))
    assert (s["fr_page_start"], s["fr_page_end"]) == (100, 101)
    i = d.text.index("gamma")
    assert d.page_at(i) == 101 and d.page_at(i - 2) == 100
    assert d.text[s["start_char"]:s["end_char"]] == s["text"]


def test_whitespace_and_punctuation_repair():
    x = b'<R><P>See <E T="02">ADDRESSES</E>\n   . Then   a\xc2\xa0b</P></R>'
    d = fxp.parse_fr_xml(x, 1)
    assert d.text == "See ADDRESSES. Then a b"


XML_TABLE = b"""<R><PREAMB><SUM><HD SOURCE="HED">SUMMARY:</HD><P>x</P></SUM></PREAMB><SUPLINF><HD SOURCE="HD1">The Proposed Amendment</HD>
<PART><SECTION><EXTRACT><FP>Acme: Docket No. X.</FP><HD SOURCE="HD1">(c) Applicability</HD>
<P>This AD applies to:</P>
<GPOTABLE><TTITLE>Table 1 to Paragraph (c) of This AD&#8212;Applicability</TTITLE><BOXHD><CHED H="1">Model</CHED><CHED H="1">Serial Nos.</CHED></BOXHD>
<ROW><ENT I="01">A1</ENT><ENT>100 through 200</ENT></ROW><ROW><ENT I="01">A2</ENT><ENT>All</ENT></ROW></GPOTABLE>
<HD SOURCE="HD1">(d) Subject</HD><P>JASC 1234.</P></EXTRACT></SECTION></PART></SUPLINF></R>"""


def test_gpotable_rendering_and_section_has_table():
    d = fxp.parse_fr_xml(XML_TABLE, 1)
    c = next(s for s in d.sections if s["path"] == "proposed_ad/(c)")
    assert c["has_table"] is True
    assert ("Table 1 to Paragraph (c) of This AD—Applicability\nModel | Serial Nos.\nA1 | 100 through 200\nA2 | All") in c["text"]
    dd = next(s for s in d.sections if s["path"] == "proposed_ad/(d)")
    assert dd["has_table"] is False and dd["start_char"] >= c["end_char"]


XML_AD = b"""<R><SUPLINF><HD SOURCE="HD1">The Proposed Amendment</HD><PART><SECTION><EXTRACT><FP>Acme: Docket.</FP>
<HD SOURCE="HD1">(h) Exceptions</HD><P>(1) One.</P><P>(2) Two:</P><P>(i) Roman one.</P><P>(ii) Roman two.</P><P>(3) Three.</P>
<HD SOURCE="HD1">(i) Credit</HD><P>Text.</P></EXTRACT></SECTION></PART></SUPLINF></R>"""


def test_ad_paragraph_nesting_is_contiguous():
    d = fxp.parse_fr_xml(XML_AD, 1)
    by = {s["path"]: s for s in d.sections}
    h = by["proposed_ad/(h)"]
    assert by["proposed_ad/(h)/(2)/(i)"]["ancestor"] == "proposed_ad/(h)/(2)"
    for p in ("proposed_ad/(h)/(1)", "proposed_ad/(h)/(3)", "proposed_ad/(h)/(2)/(ii)"):
        assert h["start_char"] <= by[p]["start_char"] and by[p]["end_char"] <= h["end_char"]
    assert "(3) Three." in h["text"] and "Credit" not in h["text"]


@pytest.mark.parametrize("action,cls", [
    ("Notice of proposed rulemaking (NPRM).", "NPRM"),
    ("Notice of proposed rulemaking (NPRM), DOT.", "NPRM"),
    ("Proposed rule; withdrawal.", "WITHDRAWAL"),
    ("Notice of proposed rulemaking (NPRM); withdrawal.", "WITHDRAWAL"),
    ("Proposed rule; rescission.", "WITHDRAWAL"),
    ("Supplemental notice of proposed rulemaking (SNPRM).", "SNPRM"),
    ("Supplemental notice of proposed rulemaking; reopening of comment period.", "SNPRM"),
    ("Proposed rule; correction.", "CORRECTION"),
    ("Notice of proposed rulemaking (NPRM); extension of the comment period.", "OTHER"),
    ("Notice of public meeting; reopening of the comment periods.", "OTHER"),
    ("Final rule.", "FINAL_RULE"),
    ("Something unexpected", "OTHER"),
])
def test_doc_class(action, cls):
    assert classify_doc(action) == cls


def test_header_parse():
    assert pp.header_fr_page("66019 \nFederal Register / Vol. 91, No. 200 / Monday / Proposed Rules \nabc") == 66019
    assert pp.header_fr_page("Federal Register / Vol. 91 / Proposed Rules 66021\nabc") == 66021
    assert pp.header_fr_page("This section of the FEDERAL REGISTER contains") is None


# ------------------------------------------------------------------ tests on the built DB
@pytest.fixture(scope="module")
def conn():
    if not config.DB_PATH.exists():
        pytest.skip("DB not built; run scripts/ingest.py")
    c = sqlite3.connect(config.DB_PATH); c.row_factory = sqlite3.Row
    yield c
    c.close()


def test_counts(conn):
    assert conn.execute("SELECT count(*) FROM records").fetchone()[0] == 431
    assert conn.execute("SELECT count(DISTINCT row) FROM records").fetchone()[0] == 431
    assert conn.execute("SELECT count(*) FROM documents WHERE source='organiser_sheet'").fetchone()[0] == 420
    assert conn.execute("SELECT count(*) FROM doc_text WHERE fr_docnum IN (SELECT fr_docnum FROM documents WHERE source='organiser_sheet')").fetchone()[0] == 420
    assert conn.execute("SELECT count(*) FROM pages").fetchone()[0] >= 1000


def test_section_offsets_and_pages(conn):
    docs = {r["fr_docnum"]: dict(r) for r in conn.execute("SELECT * FROM documents")}
    text = {r[0]: r[1] for r in conn.execute("SELECT * FROM doc_text")}
    n = 0
    for s in conn.execute("SELECT * FROM sections"):
        d = docs[s["fr_docnum"]]; t = text[s["fr_docnum"]]
        assert t[s["start_char"]:s["end_char"]] == s["text"], s["id"]
        assert s["start_char"] < s["end_char"] <= len(t)
        assert d["start_page"] <= s["fr_page_start"] <= s["fr_page_end"] <= d["end_page"], s["id"]
        if s["pdf_page_start"] is not None:
            assert s["pdf_page_start"] == s["fr_page_start"] - d["start_page"] + 1
        n += 1
    assert n > 5000


def test_every_document_has_extraction_status_recorded(conn):
    bad = conn.execute("SELECT fr_docnum, extraction_status FROM documents WHERE extraction_status!='ok'").fetchall()
    assert bad == [] or all(r["extraction_status"] for r in bad)   # failures are explicit, never silent


def test_2026_21387_applicability(conn):
    s = conn.execute("SELECT * FROM sections WHERE fr_docnum='2026-21387' AND section_path='proposed_ad/(c)'").fetchone()
    assert s["text"] == ("(c) Applicability\n\nThis AD applies to all Airbus Helicopters Model AS350B3, AS355F, AS355F1, "
                         "AS355F2, AS355N, AS355NP, EC130B4, and EC130T2 helicopters, certificated in any category.")
    # exact in the source XML (independent of our parser)
    xml = (config.FR_DOCS_DIR / "2026-21387" / "full_text.xml").read_text()
    assert "This AD applies to all Airbus Helicopters Model AS350B3, AS355F, AS355F1, AS355F2, AS355N, AS355NP, EC130B4, and EC130T2 helicopters, certificated in any category." in xml
    assert (s["fr_page_start"], s["fr_page_end"], s["pdf_page_start"], s["pdf_page_end"]) == (66022, 66022, 4, 4)
    pdf = pymupdf.open(config.FR_DOCS_DIR / "2026-21387" / "document.pdf")
    page4 = pp.norm_for_match(pdf[3].get_text())
    assert pp.norm_for_match("This AD applies to all Airbus Helicopters Model AS350B3, AS355F, AS355F1") in page4
    assert pdf[3].get_text().lstrip().startswith("66022")
    for i in range(3):
        assert pp.norm_for_match("This AD applies to all Airbus Helicopters Model AS350B3") not in pp.norm_for_match(pdf[i].get_text())


def test_determinism_two_builds():
    with tempfile.TemporaryDirectory() as td:
        a = build_db.build(Path(td) / "a.sqlite", verbose=False)
        b = build_db.build(Path(td) / "b.sqlite", verbose=False)
    assert a["content_sha256"] == b["content_sha256"]


def test_missing_prtpage_repaired_from_pdf_text():
    xml = b"""<R><SUPLINF><HD SOURCE="HED">SUPPLEMENTARY INFORMATION:</HD><P>Alpha alpha alpha alpha one.</P>
<P>Bravo bravo bravo bravo two continues here.</P></SUPLINF></R>"""
    pdf_pages = ["10\nFederal Register / Vol. 1 / Proposed Rules\nAlpha alpha alpha alpha one.\n",
                 "11\nFederal Register / Vol. 1 / Proposed Rules\nBravo bravo bravo bravo two continues here.\n"]
    d = fxp.parse_fr_xml(xml, 10, 11, pdf_pages=pdf_pages)
    assert d.page_at(d.text.index("Bravo")) == 11 and d.page_at(d.text.index("Alpha")) == 10
    assert any(w.startswith("prtpage_repaired_from_pdf") for w in d.warnings)
    d2 = fxp.parse_fr_xml(xml, 10, 11)       # without PDF nothing is guessed
    assert d2.page_at(d2.text.index("Bravo")) == 10


def test_prtpage_inside_table_row_and_graphic_not_dropped():
    xml = b"""<R><SUPLINF><P>x</P><GPOTABLE><ROW><ENT>a</ENT></ROW><ROW><PRTPAGE P="5"/><ENT>b</ENT></ROW></GPOTABLE>
<GPH><PRTPAGE P="6"/><GID>g</GID></GPH><P>after</P></SUPLINF></R>"""
    d = fxp.parse_fr_xml(xml, 4, 6)
    assert [p for _, p in d.markers] == [5, 6]
    assert d.page_at(d.text.index("after")) == 6
