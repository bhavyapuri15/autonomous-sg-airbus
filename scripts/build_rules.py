#!/usr/bin/env python
"""Extract applicability rules for all docs -> data/processed/applicability_rules.json (deterministic)."""
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.config import DB_PATH, PROCESSED  # noqa: E402
from backend.rules.applicability import extract_rule  # noqa: E402


def main():
    c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=30)
    docs = c.execute("select fr_docnum, doc_class, publication_date from documents order by fr_docnum").fetchall()
    c.close()
    out, era, cls, resid = {}, Counter(), Counter(), Counter()
    for dn, dc, pub in docs:
        r = extract_rule(dn)
        out[dn] = r.to_dict()
        if r.failure_reason == "NO_APPLICABILITY_PARAGRAPH":
            continue
        e = "modern" if (pub or "")[:4] >= "2021" else "legacy"
        era[(e, r.parse_status)] += 1
        cls[(dc, r.parse_status)] += 1
        if r.parse_status != "FULL":
            for l in r.residue[:1]:
                import re
                resid[re.sub(r"\d+", "N", l.text[:50])] += 1
    PROCESSED.mkdir(parents=True, exist_ok=True)
    (PROCESSED / "applicability_rules.json").write_text(json.dumps(out, sort_keys=True, indent=1, default=str) + "\n")
    print("docs:", len(docs), " with (c) paragraph:", sum(era.values()))
    print("by era:", dict(sorted(era.items())))
    print("by doc_class:", dict(sorted(cls.items())))
    print("overall:", dict(Counter(k[1] for k, v in era.items() for _ in range(v))))
    print("top residue (first residue run, digits->N):")
    for k, v in resid.most_common(15):
        print(f"  {v:3d}  {k!r}")


if __name__ == "__main__":
    main()
