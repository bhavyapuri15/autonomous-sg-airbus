"""Docket-group split (evaluation_spec section 1) and the locked-set leakage guard.

Run:  python evaluation/split.py   -> writes evaluation/test_cases/split_map.json
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "indexes" / "ad.sqlite"
EVAL_DIR = ROOT / "evaluation"
CASES_DIR = EVAL_DIR / "test_cases"
SPLIT_MAP = CASES_DIR / "split_map.json"
LOCKED_DIR = CASES_DIR / "locked"
SALT = "airbus-c4-split|"

_PREFIX = re.compile(r"^(?:docket\s*(?:no\.?|number|id)?|(?:project|product|directorate)\s+identifier"
                     r"|faa\s+rules)\s*[:.]?\s*", re.I)


def connect() -> sqlite3.Connection:
    """Fresh read-only connection (the DB is rebuilt atomically by another agent)."""
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


def normalize_dockets(raw) -> list[str]:
    if isinstance(raw, str):
        raw = [raw]
    out: list[str] = []
    for item in raw or []:
        for tok in re.split(r"[;,]|\s+and\s+|\s+(?=(?:project|product|directorate)\s+identifier)", item or "", flags=re.I):
            t = " ".join(tok.split())
            if not t or re.match(r"^(amendment|ad)\s+\d", t, re.I):
                continue
            t = _PREFIX.sub("", t).strip(" .")
            m = re.match(r"^FAA[\s-]+(\d{4}-\d+)$", t, re.I)
            if m:
                t = "FAA-" + m.group(1)
            t = t.upper()
            if t and t not in out:
                out.append(t)
    return out


def docket_key(d: str) -> str:
    """Comparison key: drop the withdrawal '-W' and the optional '-AD' suffix, so an NPRM and its
    withdrawal (2003-CE-05-AD vs 2003-CE-05-AD-W) land in the same group."""
    d = d.upper().strip()
    d = re.sub(r"-W$", "", d)
    return re.sub(r"-AD$", "", d)


class UF:
    def __init__(self):
        self.p: dict[str, str] = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


def is_locked(key: str) -> bool:
    return int(hashlib.sha256((SALT + key).encode()).hexdigest(), 16) % 10 < 3


def build_split(con=None) -> dict:
    con = con or connect()
    uf = UF()
    item_dockets: dict[str, list[str]] = {}   # item id ('doc:<docnum>' / 'row:<n>') -> dockets
    for docnum, dj in con.execute("select fr_docnum, docket_ids_json from documents where source='organiser_sheet'"):
        item_dockets[f"doc:{docnum}"] = [docket_key(d) for d in normalize_dockets(json.loads(dj or "[]"))]
    for row, dn, docnum in con.execute("select row, docket_norm, fr_docnum from records"):
        ds = [docket_key(d) for d in normalize_dockets([dn or ""])]
        if docnum and f"doc:{docnum}" in item_dockets:
            item_dockets[f"doc:{docnum}"] = sorted(set(item_dockets[f"doc:{docnum}"]) | set(ds))
        elif not docnum:
            item_dockets[f"row:{row}"] = ds
    for item, ds in item_dockets.items():
        uf.find(item)
        for d in ds:
            uf.union(item, "dk:" + d)
    groups: dict[str, list[str]] = {}
    for item, ds in item_dockets.items():
        groups.setdefault(uf.find(item), []).append(item)
    docs: dict[str, dict] = {}
    rows: dict[str, dict] = {}
    gkeys: dict[str, dict] = {}
    for root, items in groups.items():
        dks = sorted({d for it in items for d in item_dockets[it]})
        key = dks[0] if dks else sorted(items)[0]
        split = "locked" if is_locked(key) else "dev"
        gkeys[key] = {"split": split, "dockets": dks, "items": sorted(items)}
        for it in items:
            kind, ident = it.split(":", 1)
            (docs if kind == "doc" else rows)[ident] = {"split": split, "group": key}
    # records that carry an FR docnum inherit that doc's split
    row_split = {}
    for row, docnum in con.execute("select row, fr_docnum from records"):
        row_split[str(row)] = docs[docnum] if docnum else rows[str(row)]
    return {"docs": dict(sorted(docs.items())), "rows": dict(sorted(row_split.items(), key=lambda kv: int(kv[0]))),
            "groups": dict(sorted(gkeys.items()))}


def write_split_map() -> dict:
    m = build_split()
    SPLIT_MAP.parent.mkdir(parents=True, exist_ok=True)
    SPLIT_MAP.write_text(json.dumps(m, indent=1, sort_keys=True) + "\n")
    return m


def load_split_map() -> dict:
    return json.loads(SPLIT_MAP.read_text())


def assert_not_locked(path, *, final: bool = False) -> Path:
    """Leakage guard: tuning code calls this before reading any case file.
    Raises PermissionError for anything under test_cases/locked unless final=True
    (evaluate.py passes final=True only for `--split locked --final` with user approval)."""
    p = Path(path).resolve()
    if (p == LOCKED_DIR.resolve() or LOCKED_DIR.resolve() in p.parents) and not final:
        raise PermissionError(f"{p} is in the locked evaluation set; use --split locked --final (needs user approval)")
    return p


def main():
    m = write_split_map()
    for sp in ("dev", "locked"):
        nd = sum(1 for v in m["docs"].values() if v["split"] == sp)
        nr = sum(1 for v in m["rows"].values() if v["split"] == sp)
        ng = sum(1 for v in m["groups"].values() if v["split"] == sp)
        print(f"{sp}: docs={nd} rows={nr} groups={ng}")


if __name__ == "__main__":
    sys.exit(main())
