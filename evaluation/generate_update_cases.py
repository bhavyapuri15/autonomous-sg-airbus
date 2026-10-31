"""Cases for the organiser's 31-Oct clarifications: families F10-F13 (docs: evaluation/README.md, last section).

Gold comes from ORGANISER data (xlsx read with openpyxl), FR metadata JSON, cached final-rule XML (own regex), or hand-checked text --
never from the system's outputs.  The ad.sqlite DB is used only for (a) record_id -> sheet_row (to apply split_map.json) and
(b) relations / documents lookups to *select* cases, never as the expected value (except the documented adnum_misuse check).

    .venv/bin/python evaluation/generate_update_cases.py [--manifest]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evaluation"))
import split as S  # noqa: E402

XLSX = ROOT / "data/raw/organiser_v2/challenge4_index/challenge4_ad_index.xlsx"
FRMETA = ROOT / "data/raw/fr_metadata"
FINALS = ROOT / "data/raw/fr_final_rules"
CASES = S.CASES_DIR
MANIFEST = S.EVAL_DIR / "LOCKED_MANIFEST_UPDATE.sha256"
REVISION_Q = "What is the revision status of this proposal?"

# FR document type/action -> our regulatory_stage (documented in README). Order matters: first match wins.
STAGE_RULES = [("withdraw", "WITHDRAWAL_NOTICE"), ("rescission", "WITHDRAWAL_NOTICE"), ("correction", "CORRECTION"),
               ("supplemental", "SUPPLEMENTAL_PROPOSAL"), ("notice of proposed rulemaking", "PROPOSED_RULE")]
# 'extension of comment period' / 'public meeting' NPRM-actions have no gold stage (OTHER is ambiguous) -> excluded
STAGE_EXCLUDE = ("extension of", "public meeting")

# 15 hand-checked NOT_VERIFIED cases (dev split): FR text read by hand -> "The FAA proposes to adopt a new AD", published
# 2026-06-29..2026-10-15 with comment periods closing 2026-08-13..2026-11-30 (no withdrawal, no final rule in text or dataset).
HAND_NOT_VERIFIED = ["2026-16795", "2026-17056", "2026-18375", "2026-18468", "2026-18520", "2026-18575", "2026-18956", "2026-19090",
                     "2026-19255", "2026-19355", "2026-19892", "2026-20700", "2026-21123", "2026-15072", "2026-13023"]
HAND_NOT_VERIFIED = list(dict.fromkeys(HAND_NOT_VERIFIED))
NEG_IDS = {"dev": ["NPRM-0", "NPRM-999", "NPRM-432"], "locked": ["NPRM-500", "NPRM-9999"]}
LINK = re.compile(r"federalregister\.gov/(?:documents/\d{4}/\d{2}/\d{2}/([A-Za-z0-9-]+)/|d/([A-Za-z0-9-]+)|a/([A-Za-z0-9-]+))")


def norm_ad(x: str) -> str:
    return re.sub(r"\s+", "", x or "").strip()


def load_index():
    wb = openpyxl.load_workbook(XLSX, read_only=True)
    cols = ["record_id", "docket_number", "subject", "issue_date", "publish_date", "make", "model", "product_type", "product_subtype",
            "ad_number", "supersedes_ad", "mentions_serial_numbers", "citation", "pages", "federal_register_link", "summary"]
    idx = [dict(zip(cols, r)) for r in wb["nprm_index"].iter_rows(min_row=4, values_only=True) if r[0]]
    chains = [dict(zip(["docket_number", "version", "versions_total", "status", "record_id", "publish_date", "subject"], r))
              for r in wb["revision_chains"].iter_rows(min_row=4, values_only=True) if r[0]]
    return idx, chains


def link_docnum(link, publish_date=None) -> str | None:
    """First FR docnum in the organiser link cell. Rows whose cell holds two links ('<NPRM link>\\nWithdrawal: <withdrawal link>') are
    withdrawal rows: the first link is the NPRM being withdrawn, so the row's own document is the one whose FR metadata
    publication_date is within 3 days of the row's publish_date (the organiser date is sometimes one day off; organiser + FR data only); no match -> None (row skipped)."""
    found = [next(g for g in m.groups() if g) for m in LINK.finditer(str(link or ""))]
    found = list(dict.fromkeys(found))
    if len(found) <= 1:
        return found[0] if found else None
    for d in found:
        p = FRMETA / f"{d}.json"
        if p.exists() and publish_date and abs((date.fromisoformat(json.loads(p.read_text())["publication_date"])
                                                - date.fromisoformat(str(publish_date)[:10])).days) <= 3:
            return d
    return None


def final_rule_supersedes(rule: str, ad: str) -> bool:
    """Independent regex over the cached final-rule XML: 'supersede(s/ing) [the existing] [Airworthiness Directive (AD)|AD] X' or
    'remov(e/es/ing) ... AD X'. Whitespace collapsed (the XML has 'AD 2025-04- 05')."""
    p = FINALS / rule / "full_text.xml"
    if not p.exists():
        return False
    t = re.sub(r"<[^>]+>", " ", p.read_text(errors="ignore"))
    t = re.sub(r"&amp;", "&", t)
    t = re.sub(r"(\d)-\s+(\d)", r"\1-\2", re.sub(r"\s+", " ", t))
    x = re.escape(ad)
    pre = r"(?:the\s+)?(?:existing\s+)?(?:Airworthiness Directive \(AD\)|AD)\s+"
    return bool(re.search(rf"\bsupersed(?:e|es|ed|ing)\s+{pre}{x}\b", t, re.I) or re.search(rf"\bremov(?:e|es|ed|ing)\s+{pre}{x}\b", t, re.I))


def case(fam, sub, n, split, query, inputs, expected, gold_evidence, notes, prov="real"):
    return dict(id=f"{fam}-{split}-{sub}-{n:03d}", family=fam, split=split, provenance=prov, query=query, inputs=inputs,
                expected=dict(expected, check=sub), gold_evidence=gold_evidence, notes=notes)


def build() -> dict[str, list[dict]]:
    sm = S.load_split_map()
    con = S.connect()
    idx, chains = load_index()
    row_of = {r[0]: r[1] for r in con.execute("select record_id, sheet_row from organiser_index")}  # only to apply split_map
    sp = lambda rid: sm["rows"][str(row_of[rid])]["split"]
    out: dict[str, list[dict]] = {}

    def add(fam, name, c):
        out.setdefault(f"{c['split']}/{name}.jsonl", []).append(c)

    # ---------------- F10 record-id lookup (gold = docnum parsed from organiser federal_register_link)
    cnt = {}
    for r in idx:
        d = link_docnum(r["federal_register_link"], r["publish_date"])
        if not d:
            continue
        num = int(r["record_id"].split("-")[1])
        for form, q in (("canonical", r["record_id"]), ("lower_unpadded", f"nprm {num}"), ("question", f"What does record {r['record_id']} propose?")):
            s = sp(r["record_id"])
            cnt[s] = cnt.get(s, 0) + 1
            add("F10", "f10_record_id", case("F10", "lookup", cnt[s], s, q, {}, dict(record_id=r["record_id"], gold_fr_docnum=d, form=form),
                                              [], f"gold docnum parsed from the organiser federal_register_link of {r['record_id']} ({r['federal_register_link']})"))
    for s, ids in NEG_IDS.items():
        for i, rid in enumerate(ids, 1):
            add("F10", "f10_record_id", case("F10", "nonexistent", i, s, rid, {}, dict(record_id=rid, gold_fr_docnum=None, form="canonical"), [],
                                             "record id is outside the organiser index NPRM-001..NPRM-431; must yield no exact-id result", prov="synthetic"))

    # ---------------- F11 dataset revision chains (gold = organiser xlsx revision_chains markers)
    by_docket = {}
    for c in chains:
        by_docket.setdefault(c["docket_number"], []).append(c)
    counts = {}
    for c in chains:
        latest = [x for x in by_docket[c["docket_number"]] if str(x["status"]).lower() == "latest"]
        assert len(latest) == 1, c["docket_number"]
        s = sp(c["record_id"])
        counts[s] = counts.get(s, 0) + 1
        add("F11", "f11_revision_chain", case("F11", "chain", counts[s], s, REVISION_Q, {"directive_id": c["record_id"]},
            dict(dataset_status="LATEST_IN_DATASET" if str(c["status"]).lower() == "latest" else "SUPERSEDED_IN_DATASET", latest_record_id=latest[0]["record_id"],
                 versions_total=c["versions_total"], this_version=c["version"], docket=c["docket_number"]), [],
            f"organiser revision_chains: docket {c['docket_number']} version {c['version']}/{c['versions_total']} status={c['status']}"))
    dk_count = {}
    for r in idx:
        dk_count[r["docket_number"]] = dk_count.get(r["docket_number"], 0) + 1
    singles = sorted((r for r in idx if dk_count[r["docket_number"]] == 1 and r["docket_number"] not in by_docket),
                     key=lambda r: hashlib.sha256(("f11single|" + r["record_id"]).encode()).hexdigest())
    kept = {"dev": [], "locked": []}
    for r in singles:
        s = sp(r["record_id"])
        if len(kept[s]) < (45 if s == "dev" else 20):
            kept[s].append(r)
    for s, rs in kept.items():
        for i, r in enumerate(sorted(rs, key=lambda r: r["record_id"]), 1):
            add("F11", "f11_revision_chain", case("F11", "single", i, s, REVISION_Q, {"directive_id": r["record_id"]},
                dict(dataset_status="SINGLE_PUBLICATION", latest_record_id=r["record_id"], versions_total=1, this_version=1, docket=r["docket_number"]), [],
                f"docket {r['docket_number']} appears once in the organiser nprm_index and not in revision_chains"))

    # ---------------- F12 regulatory stage / enforceability
    docs = [r[0] for r in con.execute("select fr_docnum from documents where source='organiser_sheet' order by fr_docnum")]
    cnt = {}
    skipped = []
    for dn in docs:
        p = FRMETA / f"{dn}.json"
        m = json.loads(p.read_text()) if p.exists() else {}
        act = (m.get("action") or "").lower()
        if (m.get("type") or "") != "Proposed Rule" or any(x in act for x in STAGE_EXCLUDE):
            skipped.append(dn)
            continue
        stage = next((v for k, v in STAGE_RULES if k in act), None)
        if not stage:
            skipped.append(dn)
            continue
        s = sm["docs"][dn]["split"]
        cnt[s] = cnt.get(s, 0) + 1
        add("F12", "f12_regulatory", case("F12", "stage", cnt[s], s, REVISION_Q, {"directive_id": dn}, dict(regulatory_stage=stage, fr_action=m.get("action")),
            [{"fr_docnum": dn}], f"gold from data/raw/fr_metadata/{dn}.json type='{m.get('type')}' action='{m.get('action')}'"))
    ecnt = {}
    for l in (S.CASES_DIR / "dev" / "f6_revision.jsonl").read_text().splitlines():          # dev F6 only (read-only)
        c6 = json.loads(l)
        kind = c6["expected"]["kind"]
        if kind not in ("withdrawn_nprm", "finalized_nprm"):
            continue
        dn = c6["inputs"]["directive_id"]
        ecnt["dev"] = ecnt.get("dev", 0) + 1
        add("F12", "f12_regulatory", case("F12", "enforceability", ecnt["dev"], "dev", REVISION_Q, {"directive_id": dn},
            dict(enforceability="PROPOSAL_WITHDRAWN" if kind == "withdrawn_nprm" else "FINAL_RULE_PUBLISHED_VERIFIED", source=f"dev F6 case {c6['id']}",
                 evidence_docnums=[g["quote_in_docnum"] for g in c6["gold_evidence"] if g["quote_in_docnum"] != dn]),
            [{"fr_docnum": dn}],
            "hand-checked evidence re-used from the dev F6 case: " + c6["gold_evidence"][0]["quote"][:300]))
    for dn in HAND_NOT_VERIFIED:
        assert sm["docs"][dn]["split"] == "dev"
        ecnt["dev"] += 1
        add("F12", "f12_regulatory", case("F12", "enforceability", ecnt["dev"], "dev", REVISION_Q, {"directive_id": dn},
            dict(enforceability="NOT_VERIFIED", source="hand-checked"), [{"fr_docnum": dn}],
            "text read by hand: 2026 NPRM 'proposes to adopt a new AD', comment period open/recently closed, no withdrawal or final rule in text or dataset"))
    acnt = {}
    ver_final = {}   # NPRM docnum -> final rule docnums (VERIFIED FINALIZES edges in relations; documented use of the relations table)
    for src, dst in con.execute("select src,dst from relations where type='FINALIZES' and confidence='VERIFIED'"):
        ver_final.setdefault(dst, []).append(src)
    for r in idx:
        if not r["ad_number"]:
            continue
        s = sp(r["record_id"])
        acnt[s] = acnt.get(s, 0) + 1
        dn = con.execute("select fr_docnum from organiser_index where record_id=?", (r["record_id"],)).fetchone()[0]
        rules = ver_final.get(dn, [])
        add("F12", "f12_regulatory", case("F12", "adnum", acnt[s], s, REVISION_Q, {"directive_id": r["record_id"]},
            dict(ad_number=r["ad_number"], final_allowed=bool(rules), final_rules=rules), [],
            "organiser row has an ad_number; FINAL_RULE_PUBLISHED_VERIFIED is allowed only if relations has a VERIFIED FINALIZES edge"))

    # ---------------- F13 proposed vs operative supersession
    cnt = {}
    for r in idx:
        if not r["supersedes_ad"]:
            continue
        ad = norm_ad(r["supersedes_ad"])
        s = sp(r["record_id"])
        cnt[s] = cnt.get(s, 0) + 1
        dn = con.execute("select fr_docnum from organiser_index where record_id=?", (r["record_id"],)).fetchone()[0]
        rules = ver_final.get(dn, [])
        op_rules = [x for x in rules if final_rule_supersedes(x, ad)]
        add("F13", "f13_supersession", case("F13", "supersedes", cnt[s], s, REVISION_Q, {"directive_id": r["record_id"]},
            dict(supersedes_ad=ad, operative_gold=bool(op_rules), operative_final_rules=op_rules, verified_final_rules=rules), [],
            "organiser supersedes_ad = proposed supersession; operative gold = own regex over cached final-rule XML of a VERIFIED final rule"))
    for k in out:
        out[k].sort(key=lambda c: c["id"])
    return out


def render(files):
    return {rel: "".join(json.dumps(c, sort_keys=True) + "\n" for c in cs) for rel, cs in files.items()}


def write_manifest():
    lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  test_cases/locked/{p.name}" for p in sorted(S.LOCKED_DIR.glob("f1[0-3]_*.jsonl"))]
    lines.append(f"{hashlib.sha256(S.SPLIT_MAP.read_bytes()).hexdigest()}  test_cases/split_map.json")
    MANIFEST.write_text("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", action="store_true")
    a = ap.parse_args()
    files = render(build())
    for rel, txt in files.items():
        (CASES / rel).parent.mkdir(parents=True, exist_ok=True)
        (CASES / rel).write_text(txt)
        print(rel, txt.count("\n"))
    if a.manifest:
        write_manifest()
        print("wrote", MANIFEST.name)


if __name__ == "__main__":
    main()
