#!/usr/bin/env python3
"""Retrieval fusion ablation on the dev F2 cases: BM25 only, dense only, and RRF at several k. Dev split only, by design.

The system code is not changed: the fusion loops of backend/retrieval/hybrid_search.py are switched off in an in-memory copy
of the module (the patch asserts that both loops are found exactly once, so it fails loudly if that code changes).
Scoring is evaluate.run_f2, so the "rrf_k60" row must reproduce the official dev F2 numbers.

Usage: .venv/bin/python evaluation/ablate_fusion.py   -> evaluation/ablations/fusion_dev.json
(Written outside evaluation/results/ so the API and the evaluation dashboard do not read it as an evaluation run.)
"""
import json
import subprocess
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation"))

MODES = [("bm25_only", True, False, 60), ("dense_only", False, True, 60), ("rrf_k60", True, True, 60),
         ("rrf_k10", True, True, 10), ("rrf_k200", True, True, 200)]  # rrf_k60 is what the system ships


def patched_hybrid_search():
    path = ROOT / "backend/retrieval/hybrid_search.py"
    src = path.read_text()
    loops = {"USE_BM": "    for i, (r, _) in bm_rank.items():\n        fused[i] = fused.get(i, 0) + 1 / (RRF_K + r)\n",
             "USE_DE": "    for i, r in de_rank.items():\n        fused[i] = fused.get(i, 0) + 1 / (RRF_K + r)\n"}
    for flag, loop in loops.items():
        assert src.count(loop) == 1, f"fusion loop for {flag} not found exactly once; update this script"
        src = src.replace(loop, f"    if {flag}:\n" + "".join("    " + ln + "\n" for ln in loop.splitlines()))
    assert src.count("RRF_K = 60\n") == 1
    src = src.replace("RRF_K = 60\n", "RRF_K = 60\nUSE_BM = True\nUSE_DE = True\n")
    import backend.retrieval  # noqa: F401  (parent package must exist before the module is registered)
    mod = types.ModuleType("backend.retrieval.hybrid_search")
    mod.__file__ = str(path)
    sys.modules[mod.__name__] = mod
    exec(compile(src, str(path), "exec"), mod.__dict__)
    return mod


def main():
    hs = patched_hybrid_search()
    import evaluate as ev
    cases = ev.load_cases("F2", "dev", False)
    rows = {}
    for name, bm, de, k in MODES:
        hs.USE_BM, hs.USE_DE, hs.RRF_K = bm, de, k
        r = ev.run_f2(cases)
        rows[name] = {"doc_recall_at5": r["doc_recall_at5"], "doc_mrr_at10": r["doc_mrr_at10"],
                      "chunk_recall_at5": r["chunk_recall_at5"], "by_category": r["by_category"],
                      "failed_ids": [f["id"] for f in r["failures"]]}
        print(f"{name:10s} doc R@5 {r['doc_recall_at5']:.4f}  MRR@10 {r['doc_mrr_at10']:.4f}  chunk R@5 {r['chunk_recall_at5']:.4f}", flush=True)
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    out = {"split": "dev", "family": "F2", "n": len(cases), "commit": commit,
           "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "note": "Post-hoc ablation after the locked run; dev only. The shipped system (rrf_k60) was not changed.",
           "modes": rows}
    dest = ROOT / "evaluation" / "ablations" / "fusion_dev.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print("wrote", dest.relative_to(ROOT))


if __name__ == "__main__":
    main()
