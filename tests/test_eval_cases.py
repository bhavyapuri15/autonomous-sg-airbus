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
    files = G.build_all(write=False)
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
    expected = {f"test_cases/locked/{p.name}" for p in S.LOCKED_DIR.glob("*.jsonl") if not p.name.startswith(("f10_", "f11_", "f12_", "f13_"))} | {"test_cases/split_map.json"}
    assert listed == expected


def test_leakage_guard():
    with pytest.raises(PermissionError):
        S.assert_not_locked(S.LOCKED_DIR / "f1_id_lookup.jsonl")
    S.assert_not_locked(S.LOCKED_DIR / "f1_id_lookup.jsonl", final=True)
    S.assert_not_locked(CASES / "dev" / "f1_id_lookup.jsonl")


# ---------------------------------------------------------------- F10-F13 (organiser update, separate manifest)
import generate_update_cases as GU  # noqa: E402
import evaluate as E  # noqa: E402


def _new(split, name):
    return load(f"{split}/{name}.jsonl")


NEW_FILES = ["f10_record_id", "f11_revision_chain", "f12_regulatory", "f13_supersession"]


def test_update_locked_manifest_matches():
    lines = [l.split("  ", 1) for l in GU.MANIFEST.read_text().splitlines() if l.strip()]
    listed = set()
    for digest, rel in lines:
        assert hashlib.sha256((S.EVAL_DIR / rel).read_bytes()).hexdigest() == digest, rel
        listed.add(rel)
    assert listed == {f"test_cases/locked/{n}.jsonl" for n in NEW_FILES} | {"test_cases/split_map.json"}


def test_update_cases_deterministic_and_in_split():
    for rel, txt in GU.render(GU.build()).items():
        assert (CASES / rel).read_text() == txt, rel
    sm = S.load_split_map()
    con = S.connect()
    row_of = dict(con.execute("select record_id, sheet_row from organiser_index"))
    for sp in ("dev", "locked"):
        for n in NEW_FILES:
            for c in _new(sp, n):
                assert c["split"] == sp and c["family"] == n.split("_")[0].upper()
                d = c["inputs"].get("directive_id")
                if d in row_of:
                    assert sm["rows"][str(row_of[d])]["split"] == sp, c["id"]
                elif d:
                    assert sm["docs"][d]["split"] == sp, c["id"]


def test_f10_gold_is_organiser_link_not_db():
    idx, _ = GU.load_index()
    link = {r["record_id"]: str(r["federal_register_link"]) for r in idx}
    cases = [c for sp in ("dev", "locked") for c in _new(sp, "f10_record_id")]
    look = [c for c in cases if c["expected"]["check"] == "lookup"]
    assert len({c["expected"]["record_id"] for c in look}) >= 220
    for c in look:
        assert c["expected"]["gold_fr_docnum"] in link[c["expected"]["record_id"]], c["id"]
    neg = [c for c in cases if c["expected"]["check"] == "nonexistent"]
    assert len(neg) == 5 and all(c["expected"]["record_id"] not in link for c in neg)


def test_f11_gold_matches_xlsx_markers():
    _, chains = GU.load_index()
    cases = {c["inputs"]["directive_id"]: c for sp in ("dev", "locked") for c in _new(sp, "f11_revision_chain") if c["expected"]["check"] == "chain"}
    assert len(cases) == len(chains) >= 200
    for ch in chains:
        e = cases[ch["record_id"]]["expected"]
        assert e["dataset_status"] == ("LATEST_IN_DATASET" if ch["status"] == "latest" else "SUPERSEDED_IN_DATASET")
    singles = [c for sp in ("dev", "locked") for c in _new(sp, "f11_revision_chain") if c["expected"]["check"] == "single"]
    assert singles and all(c["expected"]["dataset_status"] == "SINGLE_PUBLICATION" for c in singles)


def test_f12_f13_case_content():
    f12 = _new("dev", "f12_regulatory")
    enf = [c["expected"]["enforceability"] for c in f12 if c["expected"]["check"] == "enforceability"]
    assert enf.count("NOT_VERIFIED") == 15 and enf.count("PROPOSAL_WITHDRAWN") == 4 and enf.count("FINAL_RULE_PUBLISHED_VERIFIED") == 4
    adn = [c for sp in ("dev", "locked") for c in _new(sp, "f12_regulatory") if c["expected"]["check"] == "adnum"]
    assert len(adn) == 21
    f13 = [c for sp in ("dev", "locked") for c in _new(sp, "f13_supersession")]
    assert len(f13) == 62 and sum(c["expected"]["operative_gold"] for c in f13) >= 1


def test_final_rule_regex_independent_samples():
    assert GU.final_rule_supersedes("2026-21331", "2025-04-05")
    assert not GU.final_rule_supersedes("2026-21331", "1999-01-01")


def test_evaluator_refuses_locked_new_families():
    for fam in ("F10", "F11", "F12", "F13"):
        with pytest.raises(PermissionError):
            E.load_cases(fam, "locked", final=False)
    with pytest.raises(PermissionError):
        E.main(["--split", "locked", "--families", "F10,F11,F12,F13", "--no-write"])
