"""Deterministic stratified selection of source passages for F2/F3 (candidate list only).

The authoritative F2/F3 inputs are the hand-written files evaluation/sources/f2_{split}.jsonl; this module
only proposes passages (with a reserve) so the question writer works from a reproducible, stratified sample."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import split as S  # noqa: E402

QUOTA = {"APPL": 14, "UNSAFE": 12, "ACTIONS": 16, "PARTS": 8, "SUMMARY": 14, "DISC": 14, "WITHDRAW": 12}
ACTION_H = re.compile(r"^(required actions|actions|compliance|actions and compliance)$|inspect|replac|modif|install|repair|revis|updat|"
                      r"measure|test|check|replace", re.I)


def h(*parts) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest(), 16)


def categorize(doc_class, path, heading, label, text):
    if not 150 <= len(text) <= 1400:
        return None
    if doc_class == "WITHDRAWAL":
        if path in ("preamble/SUPPLEMENTARY INFORMATION/The Withdrawal",) or (path == "preamble/SUMMARY"):
            return "WITHDRAW"
        return None
    if doc_class not in ("NPRM", "SNPRM"):
        return None
    if path == "preamble/SUMMARY":
        return "SUMMARY"
    if path in ("preamble/SUPPLEMENTARY INFORMATION/Discussion", "preamble/SUPPLEMENTARY INFORMATION/Background"):
        return "DISC"
    if path.startswith("proposed_ad/") and path.count("/") == 1:
        hd = (heading or "").strip()
        if hd == "Applicability":
            return "APPL"
        if hd == "Unsafe Condition":
            return "UNSAFE"
        if "parts installation" in hd.lower():
            return "PARTS"
        if ACTION_H.search(hd) and not re.search(r"alternative|credit|previous|related|material|affected|special flight", hd, re.I):
            return "ACTIONS"
    return None


def pool(split: str):
    con = S.connect()
    sm = S.load_split_map()
    mk = {r[0]: (r[1] or "") for r in con.execute("select fr_docnum, make_norm from records where fr_docnum is not null")}
    docs = {r[0]: r for r in con.execute(
        "select fr_docnum,title,doc_class,era,publication_date from documents where source='organiser_sheet'")}
    out = []
    for d, path, heading, label, text, s, e in con.execute(
            "select fr_docnum,section_path,heading,label,text,start_char,end_char from sections order by fr_docnum, seq"):
        if d not in docs or sm["docs"][d]["split"] != split:
            continue
        cat = categorize(docs[d][2], path, heading, label, text)
        if cat:
            out.append(dict(fr_docnum=d, section_path=path, cat=cat, era=docs[d][3], title=docs[d][1], date=docs[d][4],
                            make=mk.get(d, ""), group=sm["docs"][d]["group"], start=s, end=e, text=text, doc_class=docs[d][2]))
    return out


def select(split: str, reserve: float = 1.2):
    cands = pool(split)
    used_doc, used_group, used_make = {}, {}, {}
    chosen = []
    for cat, q in QUOTA.items():
        want = round(q * reserve)
        items = [c for c in cands if c["cat"] == cat]
        picked = []
        era_n = {"modern": 0, "legacy": 0}
        while len(picked) < want:
            def rank(c):
                return (used_doc.get(c["fr_docnum"], 0), used_group.get(c["group"], 0) > 1, used_make.get(c["make"], 0) > 2,
                        era_n[c["era"]], h(split, cat, c["fr_docnum"], c["section_path"]))
            rem = [c for c in items if c not in picked and used_doc.get(c["fr_docnum"], 0) < 2]
            if not rem:
                break
            c = min(rem, key=rank)
            picked.append(c)
            era_n[c["era"]] += 1
            used_doc[c["fr_docnum"]] = used_doc.get(c["fr_docnum"], 0) + 1
            used_group[c["group"]] = used_group.get(c["group"], 0) + 1
            used_make[c["make"]] = used_make.get(c["make"], 0) + 1
        chosen += picked
    return chosen


if __name__ == "__main__":
    sp = sys.argv[1]
    ch = select(sp)
    import collections
    print(collections.Counter(c["cat"] for c in ch), collections.Counter(c["era"] for c in ch), len(ch), file=sys.stderr)
    for i, c in enumerate(ch):
        print(f"### {i} {c['cat']} {c['fr_docnum']} {c['section_path']} [{c['doc_class']} {c['date']} {c['make'][:30]}]\nTITLE: {c['title'][:160]}\n{c['text'].strip()}\n")
