import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evaluation"))
import generate_cases as G  # noqa: E402
import split as S  # noqa: E402

CASES = S.CASES_DIR


def load(rel):
    return [json.loads(l) for l in (CASES / rel).read_text().splitlines() if l.strip()]


def all_cases():
    out = []
    for sp in ("dev", "locked"):
        for p in sorted((CASES / sp).glob("*.jsonl")):
            out += load(f"{sp}/{p.name}")
    return out


def test_every_doc_in_exactly_one_split_and_groups_do_not_straddle():
    sm = S.build_split()
    con = S.connect()
    docs = [r[0] for r in con.execute("select fr_docnum from documents where source='organiser_sheet'")]
    assert set(docs) == set(sm["docs"]) and len(docs) == len(sm["docs"])
    by_group = {}
    for d, v in sm["docs"].items():
        assert v["split"] in ("dev", "locked")
        by_group.setdefault(v["group"], set()).add(v["split"])
    assert all(len(s) == 1 for s in by_group.values())
    for row, v in sm["rows"].items():
        assert sm["groups"][v["group"]]["split"] == v["split"]
        assert by_group.get(v["group"], {v["split"]}) == {v["split"]}
    assert S.is_locked("zzz") in (True, False)
    assert json.loads(S.SPLIT_MAP.read_text()) == json.loads(json.dumps(sm))


def test_cases_stay_in_their_split():
    sm = S.load_split_map()
    for c in all_cases():
        for g in c["gold_evidence"]:
            assert sm["docs"][g["fr_docnum"]]["split"] == c["split"], c["id"]
        for d in c["expected"].get("fr_docnums", []):
            assert sm["docs"][d]["split"] == c["split"], c["id"]
        assert c["provenance"] in ("real", "synthetic")


def test_gold_spans_round_trip():
    con = S.connect()
    texts = {d: t for d, t in con.execute("select fr_docnum, text from doc_text")}
    n = 0
    for c in all_cases():
        if c["family"] not in ("F2", "F3"):
            continue
        for g in c["gold_evidence"] + c["expected"].get("alternates", []):
            seg = texts[g["fr_docnum"]][g["start_char"]:g["end_char"]]
            row = con.execute("select text from sections where fr_docnum=? and section_path=? and start_char=?",
                              (g["fr_docnum"], g["section_path"], g["start_char"])).fetchone()
            assert row and row[0] == seg, c["id"]
            n += 1
        if c["family"] == "F3":
            g = c["gold_evidence"][0]
            assert c["expected"]["answer_span"] in texts[g["fr_docnum"]][g["start_char"]:g["end_char"]]
        assert c["expected"]["trigram_overlap"] <= G.MAX_OVERLAP
    assert n > 50


def test_synthetic_ids_do_not_exist():
    docs, texts, sections, rows, ad_numbers = G.load_db()
    known = G.all_known_ids(docs, rows, ad_numbers)
    checked = 0
    for c in all_cases():
        for x in c["expected"].get("synthetic_ids", []):
            assert not G.id_exists(x, known, texts), (c["id"], x)
            checked += 1
    assert checked >= 20


def test_deterministic_regeneration_is_byte_identical():
    files = G.build_all()
    for rel, txt in files.items():
        assert (CASES / rel).read_text() == txt, rel
    # F2/F3 inputs are hand-written source files that are validated, never regenerated
    for sp in ("dev", "locked"):
        assert (G.SOURCES / f"f2_{sp}.jsonl").exists()


def test_locked_manifest_matches():
    lines = [l.split("  ", 1) for l in G.MANIFEST.read_text().splitlines() if l.strip()]
    assert lines
    listed = set()
    for digest, rel in lines:
        assert hashlib.sha256((S.EVAL_DIR / rel).read_bytes()).hexdigest() == digest, rel
        listed.add(rel)
    expected = {f"test_cases/locked/{p.name}" for p in S.LOCKED_DIR.glob("*.jsonl")} | {"test_cases/split_map.json"}
    assert listed == expected


def test_leakage_guard():
    with pytest.raises(PermissionError):
        S.assert_not_locked(S.LOCKED_DIR / "f1_id_lookup.jsonl")
    S.assert_not_locked(S.LOCKED_DIR / "f1_id_lookup.jsonl", final=True)
    S.assert_not_locked(CASES / "dev" / "f1_id_lookup.jsonl")
