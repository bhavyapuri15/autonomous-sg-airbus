"""Evaluation runner (docs/evaluation_spec.md). Honest, reproducible, dev-first.

    .venv/bin/python evaluation/evaluate.py --split dev [--families F1,F2,F3,F6,F7,F8,LAT,CAL] [--use-llm]

* Default is NO LLM (extractive). --use-llm adds an F3-only LLM run (<= 20 calls), reported separately.
* `--split locked` requires `--final` (guard: split.assert_not_locked). No locked file is ever read otherwise.
* Results go to evaluation/results/{YYYYmmdd-HHMMSS}_{split}.json (never overwritten) and latest_{split}.json (copy).
* Every metric carries its n. Nothing is rounded favourably (4 decimals).
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation"))

import split as S  # noqa: E402

RESULTS = ROOT / "evaluation" / "results"
FAMILIES = ["F1", "F2", "F3", "F6", "F7", "F8", "LAT", "CAL"]
FILES = {"F1": "f1_id_lookup", "F2": "f2_retrieval", "F3": "f3_grounded_qa", "F6": "f6_revision",
         "F7": "f7_refusal", "F8": "f8_adversarial"}

# F7 case-file reason code -> accepted pipeline reason codes (documented in notes/evaluation_results.md)
REASON_MAP = {
    "NOT_IN_CORPUS": {"DIRECTIVE_NOT_FOUND"},
    "NEAR_MISS_ID": {"DIRECTIVE_NOT_FOUND"},
    "METADATA_ONLY": {"SOURCE_TEXT_UNAVAILABLE"},
    "MISSING_MODEL": {"MISSING_MODEL"},
    "UNSUPPORTED_COMPARISON": {"UNSUPPORTED_QUESTION"},
    "PROCEDURE_OR_SIGNOFF": {"COMPLIANCE_DETERMINATION_OUT_OF_SCOPE", "UNSUPPORTED_QUESTION", "NO_SUPPORTING_EVIDENCE"},
    "OUT_OF_DOMAIN": {"NO_SUPPORTING_EVIDENCE", "UNSUPPORTED_QUESTION"},
    "AMBIGUOUS_DIRECTIVES": {"DIRECTIVE_AMBIGUOUS"},
}


# ------------------------------------------------------------------------------------ pure metric functions
def recall_at_k(ranked: list, gold: set, k: int) -> float:
    """1.0 if any of the top-k ranked items is in gold else 0.0 (single-relevant-hit recall, per query)."""
    return 1.0 if any(x in gold for x in ranked[:k]) else 0.0


def reciprocal_rank(ranked: list, gold: set, k: int = 10) -> float:
    for i, x in enumerate(ranked[:k], 1):
        if x in gold:
            return 1.0 / i
    return 0.0


def mean(xs: list) -> float | None:
    return round(sum(xs) / len(xs), 4) if xs else None


def precision_recall_f1(pred: list[bool], gold: list[bool]) -> dict:
    """pred/gold: True = 'abstain' (positive class)."""
    tp = sum(1 for p, g in zip(pred, gold) if p and g)
    fp = sum(1 for p, g in zip(pred, gold) if p and not g)
    fn = sum(1 for p, g in zip(pred, gold) if not p and g)
    tn = sum(1 for p, g in zip(pred, gold) if not p and not g)
    prec = tp / (tp + fp) if tp + fp else None
    rec = tp / (tp + fn) if tp + fn else None
    f1 = (2 * prec * rec / (prec + rec)) if prec and rec else (0.0 if prec is not None and rec is not None else None)
    r = lambda v: None if v is None else round(v, 4)
    return dict(tp=tp, fp=fp, fn=fn, tn=tn, n=len(pred), precision=r(prec), recall=r(rec), f1=r(f1))


def percentile(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    k = (len(s) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 2)


def lat_stats(xs: list[float]) -> dict:
    return dict(n=len(xs), p50_ms=percentile(xs, 50), p95_ms=percentile(xs, 95), max_ms=round(max(xs), 2) if xs else None)


def spans_overlap(a0, a1, b0, b1) -> bool:
    return a0 < b1 and b0 < a1


def norm_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"[‐-―−]", "-", s)
    return re.sub(r"\s+", " ", s).strip()


# ------------------------------------------------------------------------------------ case loading
def load_cases(family: str, split: str, final: bool = False) -> list[dict]:
    path = S.CASES_DIR / split / (FILES[family] + ".jsonl")
    S.assert_not_locked(path, final=final)
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def check_split_args(split: str, final: bool):
    """Raises PermissionError for the locked split without --final."""
    if split == "locked" and not final:
        raise PermissionError("--split locked requires --final (and explicit user approval)")
    S.assert_not_locked(S.LOCKED_DIR if split == "locked" else S.CASES_DIR / split, final=final)


def _db():
    return S.connect()


# ------------------------------------------------------------------------------------ F1
def run_f1(cases):
    from backend.retrieval import hybrid_search as hs
    per = {}
    fails = []
    for c in cases:
        exp = set(c["expected"]["fr_docnums"])
        hits = hs.search_ex(c["query"], top_k=5)["hits"]
        docs = []
        for h in hits:
            if h["fr_docnum"] not in docs:
                docs.append(h["fr_docnum"])
        kind = c["expected"]["id_type"]
        d = per.setdefault(kind, dict(n=0, at1=0, at5=0))
        d["n"] += 1
        a1 = bool(docs[:1] and docs[0] in exp)
        a5 = recall_at_k(docs, exp, 5) == 1.0
        d["at1"] += a1
        d["at5"] += a5
        if not a1:
            fails.append(dict(id=c["id"], query=c["query"], expected=sorted(exp)[:6], actual=docs[:3]))
    tot = dict(n=sum(v["n"] for v in per.values()), at1=sum(v["at1"] for v in per.values()), at5=sum(v["at5"] for v in per.values()))
    rate = lambda a, n: round(a / n, 4) if n else None
    return dict(n=tot["n"], acc_at1=rate(tot["at1"], tot["n"]), acc_at5=rate(tot["at5"], tot["n"]),
                by_kind={k: dict(n=v["n"], acc_at1=rate(v["at1"], v["n"]), acc_at5=rate(v["at5"], v["n"])) for k, v in sorted(per.items())},
                failures=fails)


# ------------------------------------------------------------------------------------ F2
def run_f2(cases):
    from backend.retrieval import hybrid_search as hs
    doc_r5, doc_rr, ch_r5, per, fails = [], [], [], {}, []
    for c in cases:
        e = c["expected"]
        # alternates may be plain docnums or gold-evidence dicts ({fr_docnum, section_path, ...})
        gold = set(e["fr_docnums"]) | {a["fr_docnum"] if isinstance(a, dict) else a for a in (e.get("alternates") or [])}
        dl = hs.search(c["query"], top_k=10, doc_level=True)
        docs = [h["fr_docnum"] for h in dl]
        chunks = hs.search(c["query"], top_k=10)
        r5, rr = recall_at_k(docs, gold, 5), reciprocal_rank(docs, gold, 10)
        g = c["gold_evidence"][0]
        c5 = 0.0
        for h in chunks[:5]:
            if h["fr_docnum"] == g["fr_docnum"] and spans_overlap(h["start"], h["end"], g["start_char"], g["end_char"]):
                c5 = 1.0
        doc_r5.append(r5); doc_rr.append(rr); ch_r5.append(c5)
        p = per.setdefault(e["category"], dict(r5=[], rr=[], c5=[]))
        p["r5"].append(r5); p["rr"].append(rr); p["c5"].append(c5)
        if r5 == 0 or c5 == 0:
            fails.append(dict(id=c["id"], category=e["category"], query=c["query"], expected=sorted(gold), expected_span=[g["section_path"], g["start_char"], g["end_char"]],
                              actual_docs=docs[:5], actual_chunks=[(h["fr_docnum"], h["section_path"]) for h in chunks[:3]],
                              doc_recall5=r5, chunk_recall5=c5))
    return dict(n=len(cases), doc_recall_at5=mean(doc_r5), doc_mrr_at10=mean(doc_rr), chunk_recall_at5=mean(ch_r5),
                note="chunk-level gold = whole passage section of the primary doc; alternates count only for doc-level",
                by_category={k: dict(n=len(v["r5"]), doc_recall_at5=mean(v["r5"]), doc_mrr_at10=mean(v["rr"]), chunk_recall_at5=mean(v["c5"])) for k, v in sorted(per.items())},
                failures=fails)


# ------------------------------------------------------------------------------------ answer helpers
def _req(c: dict, use_llm: bool):
    from backend.api.schemas import AircraftConfig, QueryRequest
    inp = c.get("inputs") or {}
    ac = AircraftConfig(**inp["aircraft"]) if inp.get("aircraft") else None
    return QueryRequest(question=c["query"], directive_id=inp.get("directive_id"), aircraft=ac, use_llm=use_llm)


def ask(c: dict, use_llm: bool):
    from backend.answer.pipeline import answer
    return answer(_req(c, use_llm))


def validate_citation(con, cit) -> tuple[bool, str]:
    """doc_text[start:end] == quote (checked against the DB here) and fr_page within the section's FR page range."""
    if cit.source_tier.value != "FR_FULL_TEXT":
        return True, "sheet-tier (not span-checked)"
    r = con.execute("select text from doc_text where fr_docnum=?", (cit.fr_docnum,)).fetchone()
    if r is None or cit.start is None or cit.end is None:
        return False, "no doc_text or offsets"
    if r[0][cit.start:cit.end] != cit.quote:
        return False, "quote != doc_text[start:end]"
    if cit.fr_page is None:
        return False, "fr_page missing"
    secs = con.execute("select fr_page_start,fr_page_end,section_path from sections where fr_docnum=? and start_char<? and end_char>?",
                       (cit.fr_docnum, cit.end, cit.start)).fetchall()
    if not secs:
        return False, "no section covers the span"
    lo = min(s[0] for s in secs if s[0] is not None) if any(s[0] is not None for s in secs) else None
    hi = max((s[1] if s[1] is not None else s[0]) for s in secs if s[0] is not None) if lo is not None else None
    if lo is None:
        return False, "sections have no fr page range"
    if not (lo <= cit.fr_page <= hi):
        return False, f"fr_page {cit.fr_page} outside section range {lo}-{hi}"
    return True, "ok"


def run_f3_mode(cases, use_llm: bool):
    con = _db()
    ok_ans, statuses, rej_checks = 0, {}, {}
    cit_total = cit_valid = gen = ver = rej = 0
    llm_modes = {}
    fails, bad_cits = [], []
    for c in cases:
        resp = ask(c, use_llm)
        st = resp.status.value
        statuses[st] = statuses.get(st, 0) + 1
        span = norm_text(c["expected"]["answer_span"])
        texts = [norm_text(cl.text) for cl in resp.answer_claims]
        if resp.applicability.template_text:
            texts.append(norm_text(resp.applicability.template_text))
        hit = any(span in t for t in texts)
        ok_ans += hit
        v = resp.verification
        gen += v.claims_generated; ver += v.claims_verified; rej += len(v.claims_rejected)
        llm_modes[v.mode] = llm_modes.get(v.mode, 0) + 1
        for rc in v.claims_rejected:
            rej_checks[rc.failed_check] = rej_checks.get(rc.failed_check, 0) + 1
        for ct in resp.citations:
            if ct.source_tier.value != "FR_FULL_TEXT":
                continue
            cit_total += 1
            good, why = validate_citation(con, ct)
            cit_valid += good
            if not good:
                bad_cits.append(dict(case=c["id"], citation_id=ct.citation_id, why=why))
        if not hit:
            fails.append(dict(id=c["id"], query=c["query"], expected=c["expected"]["answer_span"], actual_status=st,
                              actual_reason=resp.abstention_reason, actual_claims=[cl.text[:200] for cl in resp.answer_claims],
                              rejected=[(r.text[:120], r.failed_check) for r in v.claims_rejected][:3], mode=v.mode))
    n = len(cases)
    return dict(n=n, use_llm=use_llm, generation_modes=llm_modes, answer_accuracy=round(ok_ans / n, 4) if n else None, answer_correct=ok_ans,
                status_distribution=statuses, citations_checked=cit_total, citations_valid=cit_valid,
                citation_validity=round(cit_valid / cit_total, 4) if cit_total else None, invalid_citations=bad_cits,
                claims_generated=gen, claims_verified=ver, claims_rejected=rej, rejected_by_check=rej_checks, failures=fails)


def run_f3(cases, use_llm: bool):
    out = dict(extractive=run_f3_mode(cases, False))
    if use_llm:
        from backend.answer import llm
        if not llm.configured():
            out["llm"] = dict(skipped="ANTHROPIC_API_KEY not set")
        else:
            out["llm"] = run_f3_mode(cases, True)
    return out


# ------------------------------------------------------------------------------------ F7
def run_f7(cases, f3_cases):
    pred, gold, rows, fails = [], [], [], []
    st_ok = reason_ok = 0
    by_reason = {}
    for c in cases:
        resp = ask(c, False)
        e = c["expected"]
        st = resp.status.value
        p_abs = st != "ANSWERED"
        pred.append(p_abs); gold.append(True)
        s_ok = st == e["status"]
        r_ok = resp.abstention_reason in REASON_MAP.get(e["expected_reason_code"], set())
        st_ok += s_ok; reason_ok += (s_ok and r_ok)
        b = by_reason.setdefault(e["expected_reason_code"], dict(n=0, abstained=0, status_ok=0, reason_ok=0))
        b["n"] += 1; b["abstained"] += p_abs; b["status_ok"] += s_ok; b["reason_ok"] += (s_ok and r_ok)
        if not (s_ok and r_ok):
            fails.append(dict(id=c["id"], query=c["query"], expected=[e["status"], e["expected_reason_code"]],
                              actual=[st, resp.abstention_reason]))
    neg = []
    for c in f3_cases:   # answerable sample: should NOT abstain
        resp = ask(c, False)
        a = resp.status.value != "ANSWERED"
        pred.append(a); gold.append(False)
        neg.append(dict(id=c["id"], status=resp.status.value, reason=resp.abstention_reason))
    prf = precision_recall_f1(pred, gold)
    return dict(n_refusal=len(cases), n_answerable_sample=len(f3_cases), abstention=prf,
                status_exact_acc=round(st_ok / len(cases), 4) if cases else None, status_and_reason_acc=round(reason_ok / len(cases), 4) if cases else None,
                by_reason=by_reason, false_abstentions=[x for x in neg if x["status"] != "ANSWERED"],
                reason_map={k: sorted(v) for k, v in REASON_MAP.items()}, failures=fails)


# ------------------------------------------------------------------------------------ F6
def run_f6(cases):
    from backend.rules import revisions as rv
    ok, false_ver, flag_ok, fails = 0, 0, 0, []
    by_kind = {}
    for c in cases:
        e = c["expected"]
        dn = c["inputs"]["directive_id"]
        res = rv.revision_status(dn)
        st = res.status.value
        match = st == e["status"]
        edge_ok = True
        if e.get("edge_type"):
            edge_ok = any(ed.type == e["edge_type"] and ed.confidence == "VERIFIED" and dn in (ed.src, ed.dst) for ed in res.edges)
        if e["status"] == "PROPOSAL_STATUS_UNVERIFIED" and e["kind"] == "proposes_to_supersede":
            tt = (res.template_text or "").lower()
            edge_ok = edge_ok and "is superseded" not in tt and "has been superseded" not in tt
        # false-VERIFIED: any authoritative-status flag true, or a higher status than the hand-verified one on an unverified case
        fv = bool(res.current_authoritative_status_verified) or (e["status"] == "PROPOSAL_STATUS_UNVERIFIED" and st != e["status"])
        false_ver += fv
        flag_ok += (not res.current_authoritative_status_verified)
        ok += match
        b = by_kind.setdefault(e["kind"], dict(n=0, status_ok=0, edge_ok=0))
        b["n"] += 1; b["status_ok"] += match; b["edge_ok"] += edge_ok
        if not (match and edge_ok):
            fails.append(dict(id=c["id"], expected=[e["status"], e.get("edge_type")], actual=[st, [(x.type, x.confidence) for x in res.edges][:5]]))
    n = len(cases)
    return dict(n=n, status_accuracy=round(ok / n, 4) if n else None, status_correct=ok,
                false_verified_count=false_ver, current_authoritative_status_verified_false_in=f"{flag_ok}/{n}",
                by_kind=by_kind, failures=fails)


# ------------------------------------------------------------------------------------ latency
def latency_queries(split: str, final: bool = False) -> list[str]:
    qs = [c["query"] for c in load_cases("F2", split, final)]
    f1 = load_cases("F1", split, final)
    qs += [c["query"] for c in f1[::max(1, len(f1) // 6)]][:6]
    return qs


def latency_worker(path: str, split: str, final: bool = False):
    """Runs in a fresh process: pass1 (first sight of each query) then pass2/pass3 (warm). Prints JSON."""
    qs = latency_queries(split, final)
    if path == "search":
        from backend.retrieval import hybrid_search as hs
        fn = lambda q: hs.search(q, top_k=10)
    else:
        from backend.answer.pipeline import answer
        from backend.api.schemas import QueryRequest
        fn = lambda q: answer(QueryRequest(question=q, use_llm=False))
    passes = []
    for _ in range(3):
        ts = []
        for q in qs:
            t = time.perf_counter(); fn(q); ts.append((time.perf_counter() - t) * 1000)
        passes.append(ts)
    print(json.dumps(passes))


def run_latency(split: str):
    out = {}
    for path in ("search", "answer"):
        # forward --final for the (approved) locked run; the worker re-checks the split guard
        r = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--latency-worker", path, "--split", split]
                           + (["--final"] if split == "locked" else []),
                           capture_output=True, text=True, cwd=str(ROOT))
        passes = json.loads(r.stdout.strip().splitlines()[-1])
        out[path] = dict(n_queries=len(passes[0]),
                         cold_first_call_ms=round(passes[0][0], 2),
                         cold_first_pass=lat_stats(passes[0]),
                         cold_first_pass_excl_first_call=lat_stats(passes[0][1:]),
                         warm=lat_stats(passes[1] + passes[2]))
    import sqlite3
    sdb = ROOT / "data" / "indexes" / "search.sqlite"
    con = sqlite3.connect(f"file:{sdb}?mode=ro", uri=True)
    chunks = con.execute("select count(*) from chunks").fetchone()[0]
    con.close()
    c2 = _db()
    pages = c2.execute("select count(*) from pages").fetchone()[0]
    docs = c2.execute("select count(*) from documents").fetchone()[0]
    emb = ROOT / "data" / "indexes" / "embeddings.f32.npy"
    out["index"] = dict(chunks=chunks, pages=pages, documents=docs, embeddings_mb=round(emb.stat().st_size / 1e6, 2),
                        sqlite_mb=round((ROOT / "data/indexes/ad.sqlite").stat().st_size / 1e6, 1),
                        search_sqlite_mb=round(sdb.stat().st_size / 1e6, 1))
    out["definitions"] = ("cold = fresh process: first call (includes model/index load) and first pass over unseen queries; "
                          "warm = passes 2-3 over the same queries (OS/SQLite caches hot, embedding model loaded)")
    return out


# ------------------------------------------------------------------------------------ calibration
OOD_CODES = {"OUT_OF_DOMAIN", "UNSUPPORTED_COMPARISON", "PROCEDURE_OR_SIGNOFF"}


def top_cosine(q: str) -> float | None:
    from backend.config import ANSWER_TOP_K
    from backend.retrieval import hybrid_search as hs
    hits = hs.search(q, top_k=ANSWER_TOP_K)
    v = [h["dense_cosine"] for h in hits if h.get("dense_cosine") is not None]
    return max(v) if v else None


def run_calibration(split: str):
    from backend import config
    ans = [top_cosine(c["query"]) for c in load_cases("F2", split)]
    f7 = load_cases("F7", split)
    neg_all = [(c["expected"]["expected_reason_code"], top_cosine(c["query"])) for c in f7 if c["expected"]["expected_reason_code"] in OOD_CODES]
    neg = [v for _, v in neg_all]
    ood = [v for k, v in neg_all if k == "OUT_OF_DOMAIN"]
    vals = sorted(set(ans + neg))
    cands = [(a + b) / 2 for a, b in zip(vals, vals[1:])]
    sweep = []
    for t in cands:
        pred = [v < t for v in ans] + [v < t for v in neg]
        gold = [False] * len(ans) + [True] * len(neg)
        prf = precision_recall_f1(pred, gold)
        ans_recall = sum(1 for v in ans if v >= t) / len(ans)
        sweep.append(dict(t=round(t, 4), ans_recall=round(ans_recall, 4), **{k: prf[k] for k in ("precision", "recall", "f1")}))
    ok = [s for s in sweep if s["ans_recall"] >= 0.95]
    best = max(ok, key=lambda s: (s["f1"] or 0, s["t"])) if ok else None
    # among equally-best F1, choose the middle of the plateau to avoid sitting on a sample edge
    if best:
        plateau = [s["t"] for s in ok if s["f1"] == best["f1"]]
        best = dict(best, plateau=[min(plateau), max(plateau)], t_chosen=round(statistics.median(plateau), 4))
    d = lambda xs: dict(n=len(xs), min=round(min(xs), 4), p5=percentile(xs, 5), median=percentile(xs, 50), p95=percentile(xs, 95), max=round(max(xs), 4)) if xs else dict(n=0)
    return dict(current_threshold=config.MIN_TOP_DENSE_COSINE, answerable_F2=d(ans), refusal_ood_unsupported=d(neg), out_of_domain_only=d(ood),
                answerable_values=[round(v, 4) for v in sorted(ans)], refusal_values=[(k, round(v, 4)) for k, v in sorted(neg_all, key=lambda x: x[1])],
                chosen=best, sweep_at_chosen_neighbourhood=[s for s in sweep if best and abs(s["t"] - best["t_chosen"]) < 0.05][:12])


# ------------------------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev", choices=["dev", "locked"])
    ap.add_argument("--final", action="store_true", help="required for --split locked (needs user approval)")
    ap.add_argument("--families", default=",".join(FAMILIES))
    ap.add_argument("--use-llm", action="store_true", help="also run F3 with the LLM (<= 20 calls), reported separately")
    ap.add_argument("--latency-worker", choices=["search", "answer"])
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    check_split_args(a.split, a.final)          # raises PermissionError for locked without --final
    if a.latency_worker:
        return latency_worker(a.latency_worker, a.split, a.final)
    fams = [f.strip().upper() for f in a.families.split(",") if f.strip()]
    res = dict(split=a.split, timestamp=datetime.now().isoformat(timespec="seconds"), families=fams, llm_requested=a.use_llm, metrics={})
    M = res["metrics"]
    t0 = time.time()
    f3_cases = load_cases("F3", a.split, a.final) if ("F3" in fams or "F7" in fams) else []
    if "F1" in fams: M["F1"] = run_f1(load_cases("F1", a.split, a.final)); print("F1 done", flush=True)
    if "F2" in fams: M["F2"] = run_f2(load_cases("F2", a.split, a.final)); print("F2 done", flush=True)
    if "F3" in fams: M["F3"] = run_f3(f3_cases, a.use_llm); print("F3 done", flush=True)
    if "F6" in fams: M["F6"] = run_f6(load_cases("F6", a.split, a.final)); print("F6 done", flush=True)
    if "F7" in fams: M["F7"] = run_f7(load_cases("F7", a.split, a.final), f3_cases); print("F7 done", flush=True)
    if "F8" in fams:
        import adversarial
        M["F8"] = adversarial.run_all(); print("F8 done", flush=True)
    if "LAT" in fams: M["latency"] = run_latency(a.split); print("LAT done", flush=True)
    if "CAL" in fams: M["calibration"] = run_calibration(a.split); print("CAL done", flush=True)
    from backend import config
    res["config"] = dict(MIN_TOP_DENSE_COSINE=config.MIN_TOP_DENSE_COSINE, ANSWER_TOP_K=config.ANSWER_TOP_K)
    res["runtime_s"] = round(time.time() - t0, 1)
    print(summarize(res))
    if not a.no_write:
        RESULTS.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        p = RESULTS / f"{stamp}_{a.split}.json"
        assert not p.exists(), "never overwrite results"
        txt = json.dumps(res, indent=1, default=str)
        p.write_text(txt)
        (RESULTS / f"latest_{a.split}.json").write_text(txt)
        print(f"wrote {p.relative_to(ROOT)} and latest_{a.split}.json")
    return res


def summarize(res: dict) -> str:
    M = res["metrics"]
    L = [f"== split={res['split']} threshold={res.get('config', {}).get('MIN_TOP_DENSE_COSINE')} ({res['runtime_s']}s) =="]
    if "F1" in M:
        f = M["F1"]; L.append(f"F1 n={f['n']} acc@1={f['acc_at1']} acc@5={f['acc_at5']}")
        for k, v in f["by_kind"].items():
            L.append(f"    {k}: n={v['n']} @1={v['acc_at1']} @5={v['acc_at5']}")
    if "F2" in M:
        f = M["F2"]; L.append(f"F2 n={f['n']} doc R@5={f['doc_recall_at5']} MRR@10={f['doc_mrr_at10']} chunk R@5={f['chunk_recall_at5']}")
        for k, v in f["by_category"].items():
            L.append(f"    {k}: n={v['n']} docR@5={v['doc_recall_at5']} MRR={v['doc_mrr_at10']} chunkR@5={v['chunk_recall_at5']}")
    if "F3" in M:
        for mode, f in M["F3"].items():
            if "skipped" in f:
                L.append(f"F3[{mode}] skipped: {f['skipped']}"); continue
            L.append(f"F3[{mode}] n={f['n']} answer_acc={f['answer_accuracy']} ({f['answer_correct']}/{f['n']}) cit_valid={f['citation_validity']} "
                     f"({f['citations_valid']}/{f['citations_checked']}) status={f['status_distribution']} claims gen/ver/rej={f['claims_generated']}/{f['claims_verified']}/{f['claims_rejected']}")
    if "F6" in M:
        f = M["F6"]; L.append(f"F6 n={f['n']} status_acc={f['status_accuracy']} false_VERIFIED={f['false_verified_count']} auth_status_verified_false_in={f['current_authoritative_status_verified_false_in']}")
    if "F7" in M:
        f = M["F7"]; ab = f["abstention"]
        L.append(f"F7 refusal n={f['n_refusal']} + answerable n={f['n_answerable_sample']}: precision={ab['precision']} recall={ab['recall']} f1={ab['f1']} "
                 f"(tp={ab['tp']} fp={ab['fp']} fn={ab['fn']} tn={ab['tn']}); status_exact={f['status_exact_acc']} status+reason={f['status_and_reason_acc']}")
    if "F8" in M:
        f = M["F8"]; L.append(f"F8 n={f['n']} pass={f['passed']} fail={f['failed']} blocked={f['blocked']}")
    if "latency" in M:
        for p in ("search", "answer"):
            f = M["latency"][p]
            L.append(f"LAT {p}: n={f['n_queries']} cold-first-call={f['cold_first_call_ms']}ms cold-pass={f['cold_first_pass']} warm={f['warm']}")
        L.append(f"    index: {M['latency']['index']}")
    if "calibration" in M:
        f = M["calibration"]; L.append(f"CAL answerable={f['answerable_F2']} refusal={f['refusal_ood_unsupported']} chosen={f['chosen']}")
    return "\n".join(L)


if __name__ == "__main__":
    main()
