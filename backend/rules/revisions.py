"""Revision evidence graph (spec section 1 / amendment A5) and deterministic revision status.

Build-time: build_graph(conn) fills `relations` and `revision_warnings` from the DB content only (no network).
Query-time: revision_status(fr_docnum) -> RevisionResult, revision_overlay(fr_docnum) -> list[str].

Trust rules: never claim a relationship without a quoted span; a shared docket alone is only SAME_DOCKET (CANDIDATE);
a proposal is never called legally current; PROPOSES_TO_SUPERSEDE is never rendered as "is superseded".
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import defaultdict

from backend import config
from backend.api.schemas import CitationRef, RevisionEdge, RevisionResult, RevisionStatus, SourceTier
from backend.ingestion import final_rules as o1, pdf_parser as pp

MONTHS = o1.MONTHS
MONTH_NUM = o1.MONTH_NUM
_CIT = re.compile(r"\b(\d{1,3}) FR (\d{1,6})\b")
_DATE = re.compile(rf"\b({MONTHS})\s+(\d{{1,2}}),\s+(\d{{4}})\b")
_CTX = re.compile(r"NPRM|SNPRM|proposed|supplemental|published|notice of proposed", re.I)
_AD = re.compile(r"\b\d{2,4}-\d{2}-\d{2}\b")
_SUP_PROP = re.compile(r"\b(?:proposes\s+to\s+(?:also\s+)?supersede|would\s+(?:also\s+)?supersede)\b", re.I)
_FRDOC = re.compile(r"FR Doc\.?\s*([A-Z0-9]+-\d+)")
PROPOSAL = ("NPRM", "SNPRM")
WARN_FINALIZED = "Later amendments or supersession of the final AD were not checked."


# ------------------------------------------------------------------------------------------ pure matchers (unit-tested)
def find_citations(text, volume, start_page):
    """Spans of `V FR P` equal to the target's citation."""
    return [dict(start=m.start(), end=m.end(), quote=m.group(0)) for m in _CIT.finditer(text)
            if int(m.group(1)) == volume and int(m.group(2)) == start_page]


def find_dates(text, iso_date, window=200):
    """Spans of 'Month D, YYYY' equal to iso_date with NPRM/proposed/published context within `window` chars."""
    out = []
    for m in _DATE.finditer(text):
        iso = f"{m.group(3)}-{MONTH_NUM[m.group(1)]:02d}-{int(m.group(2)):02d}"
        if iso == iso_date and _CTX.search(text[max(0, m.start() - window): m.end() + window]):
            out.append(dict(start=m.start(), end=m.end(), quote=m.group(0)))
    return out


def date_guard_ok(text, span, target_citation, window=60):
    """O1 guard: date-only evidence is rejected when an adjacent FR citation disagrees with the target's citation."""
    near = [m.group(0) for m in _CIT.finditer(text[max(0, span["start"] - window): span["end"] + window])]
    return not (any(c != target_citation for c in near) and target_citation not in near)


def sentence_span(text, s, e, cap=600):
    a = text.rfind("\n\n", 0, s); a = 0 if a < 0 else a + 2
    b = text.find("\n\n", e); b = len(text) if b < 0 else b
    bound = re.compile(r"(?<![A-Z])(?<!\bNo)(?<!\bCo)(?<!\bInc)(?<!\bCorp)(?<!\bNos)(?<!\bLtd)[.;]\s+(?=[A-Z(])")
    for m in bound.finditer(text, a, s):
        a = m.end()
    m = bound.search(text, e, b)
    if m: b = m.start() + 1
    if b - a > cap:
        return s, e
    return a, b


def supersede_proposals(text):
    """[(ad_number, start, end)] for 'proposes to supersede' / 'would supersede' with an AD number AFTER the verb in the same
    sentence. Sentences with a negator before the AD number are skipped."""
    out = []
    for m in _SUP_PROP.finditer(text):
        a, b = sentence_span(text, m.start(), m.end(), cap=1200)
        tail = text[m.end():b]
        for am in _AD.finditer(tail):
            out.append((am.group(0), a, b))
    return out


def docket_overlap(a, b):
    return o1.shared_dockets(a, b)


# ------------------------------------------------------------------------------------------ build
def build_graph(conn) -> dict:
    conn.executescript("""
    DROP TABLE IF EXISTS relations; DROP TABLE IF EXISTS revision_warnings;
    CREATE TABLE relations(id INTEGER PRIMARY KEY, src TEXT, dst TEXT, type TEXT, confidence TEXT, evidence_json TEXT, note TEXT);
    CREATE INDEX relations_src ON relations(src); CREATE INDEX relations_dst ON relations(dst);
    CREATE TABLE revision_warnings(id INTEGER PRIMARY KEY, fr_docnum TEXT, kind TEXT, message TEXT, related_json TEXT);
    """)
    docs = {}
    for r in conn.execute("SELECT fr_docnum,doc_class,publication_date,volume,start_page,docket_ids_json,source,correction_of_json,is_rfc "
                          "FROM documents ORDER BY fr_docnum"):
        docs[r[0]] = dict(dn=r[0], cls=r[1], date=r[2], vol=r[3], sp=r[4], dockets=o1.normalize_dockets(json.loads(r[5])),
                          source=r[6], corr=json.loads(r[7]) if r[7] else None, rfc=r[8])
    text = {r[0]: r[1] for r in conn.execute("SELECT fr_docnum,text FROM doc_text")}
    ds = {k: v for k, v in docs.items() if v["source"] == "organiser_sheet"}
    edges, warns = {}, []

    def add(src, dst, typ, conf, ev, note=None):
        key = (src, dst, typ)
        if key in edges and edges[key][0] == "VERIFIED":
            return
        if key in edges and conf != "VERIFIED":
            return
        edges[key] = (conf, ev, note)

    def warn(dn, kind, msg, related=None):
        warns.append((dn, kind, msg, json.dumps(related or [], sort_keys=True)))

    # ---- WITHDRAWS / SUPPLEMENTS / CORRECTS (text) ------------------------------------------------------------------
    by_cit = defaultdict(list)
    for d in ds.values():
        if d["vol"] and d["sp"]:
            by_cit[(d["vol"], d["sp"])].append(d)
    for s in sorted(ds.values(), key=lambda d: d["dn"]):
        if s["cls"] not in ("WITHDRAWAL", "SNPRM", "CORRECTION"):
            continue
        typ = {"WITHDRAWAL": "WITHDRAWS", "SNPRM": "SUPPLEMENTS", "CORRECTION": "CORRECTS"}[s["cls"]]
        t_text = text.get(s["dn"], "")
        for t in sorted(ds.values(), key=lambda d: d["dn"]):
            if t["dn"] == s["dn"] or t["cls"] not in PROPOSAL + (("WITHDRAWAL",) if False else ()):
                continue
            tc = f"{t['vol']} FR {t['sp']}"
            share = docket_overlap(s["dockets"], t["dockets"])
            cits = find_citations(t_text, t["vol"], t["sp"]) if t["vol"] else []
            dates, rej = [], []
            for sp_ in find_dates(t_text, t["date"]):
                (dates if date_guard_ok(t_text, sp_, tc) else rej).append(sp_)
            ev = [dict(fr_docnum=s["dn"], start=x["start"], end=x["end"], quote=t_text[x["start"]:x["end"]]) for x in cits + dates]
            if not ev and not (share and rej):
                if not share:
                    continue
            if not ev and share:
                continue            # docket only: handled by SAME_DOCKET below (never VERIFIED, never typed)
            late = bool(t["date"] and s["date"] and t["date"] >= s["date"])
            notes = []
            if rej: notes.append("date evidence rejected: adjacent FR citation disagrees")
            if late:
                notes.append("target published on/after source: cannot be VERIFIED")
                warn(s["dn"], "DATES_OUT_OF_ORDER", f"{s['dn']} ({s['date']}) references {t['dn']} ({t['date']}) which is not earlier", [t["dn"]])
            if share and cits and not late:
                add(s["dn"], t["dn"], typ, "VERIFIED", ev, "docket match + FR citation in text")
            elif share and dates and not cits and not late:
                nd = sum(1 for o in ds.values() if o["date"] == t["date"] and docket_overlap(s["dockets"], o["dockets"]) and o["cls"] in PROPOSAL)
                if nd == 1:
                    add(s["dn"], t["dn"], typ, "VERIFIED", ev, "docket match + publication date in text (no FR citation)")
                else:
                    add(s["dn"], t["dn"], typ, "CANDIDATE", ev, f"date matches {nd} same-docket proposals; ambiguous")
            elif cits and not share:
                add(s["dn"], t["dn"], typ, "CANDIDATE", ev, "FR citation in text but no shared docket" + ("; " + "; ".join(notes) if notes else ""))
            else:
                add(s["dn"], t["dn"], typ, "CANDIDATE", ev, "; ".join(notes) or "unverified")
    # CORRECTS from FR metadata
    for d in ds.values():
        if d["corr"]:
            tgt = str(d["corr"]).rstrip("/").split("/")[-1].split("?")[0]
            add(d["dn"], tgt, "CORRECTS", "VERIFIED", [dict(meta_field="correction_of", value=d["corr"])],
                "FR correction_of metadata" + ("" if tgt in docs else "; corrected document not in this dataset"))

    # ---- FINALIZES / SUPERSEDES from final-rule data --------------------------------------------------------------------
    links = conn.execute("SELECT dataset_docnum,rule_docnum,o1_status,status,evidence_json,note FROM final_rule_links "
                         "ORDER BY dataset_docnum,rule_docnum").fetchall() if _has(conn, "final_rule_links") else []
    for dn, rn, o1s, st, evj, note in links:
        r, d = docs[rn], docs[dn]
        final_like = r["cls"] == "FINAL_RULE"
        ev = json.loads(evj)
        evo = [dict(fr_docnum=e["fr_docnum"], start=e["start"], end=e["end"], quote=e["quote"]) for e in ev]
        out_of_order = bool(r["date"] and d["date"] and r["date"] < d["date"])
        if out_of_order:
            warn(rn, "DATES_OUT_OF_ORDER", f"final rule {rn} ({r['date']}) is dated before proposal {dn} ({d['date']}); not linked as its outcome", [dn])
        if st == "CONFLICT_REVIEW" or (final_like and d["cls"] == "WITHDRAWAL"):
            warn(dn, "FINAL_RULE_FOR_WITHDRAWN", f"final rule {rn} shares docket with withdrawal {dn}; O1 CONFLICT_REVIEW; not resolved", [rn])
        if not final_like:
            add(*sorted([dn, rn]), "SAME_DOCKET", "CANDIDATE", [], f"{r['cls']} rule in same docket; relationship unverified")
        elif d["cls"] not in PROPOSAL:
            add(*sorted([dn, rn]), "SAME_DOCKET", "CANDIDATE", [], "final rule in same docket as a non-proposal document; relationship unverified")
        elif out_of_order:
            add(*sorted([dn, rn]), "SAME_DOCKET", "CANDIDATE", [], "same docket; final rule predates proposal")
        elif st == "VERIFIED":
            add(rn, dn, "FINALIZES", "VERIFIED", evo, "O1: rule text cites the proposal and shares its docket")
        else:
            add(rn, dn, "FINALIZES", "CANDIDATE", evo, "same docket only; rule text has no verified back-reference" if not evo else note)
    for rn, supj in conn.execute("SELECT fr_docnum, supersedes_json FROM final_rule_info ORDER BY fr_docnum") if _has(conn, "final_rule_info") else []:
        for x in json.loads(supj):
            add(rn, "AD:" + x["ad_number"], "SUPERSEDES", "VERIFIED",
                [dict(fr_docnum=rn, start=x["start"], end=x["end"], quote=text[rn][x["start"]:x["end"]])], "final-rule text")

    # ---- PROPOSES_TO_SUPERSEDE ----------------------------------------------------------------------------------------
    for d in sorted(ds.values(), key=lambda d: d["dn"]):
        if d["cls"] in PROPOSAL:
            t = text.get(d["dn"], "")
            for ad, a, b in supersede_proposals(t):
                add(d["dn"], "AD:" + ad, "PROPOSES_TO_SUPERSEDE", "VERIFIED", [dict(fr_docnum=d["dn"], start=a, end=b, quote=t[a:b])],
                    "proposal only; the AD is not claimed to be superseded")

    # ---- SAME_DOCKET among dataset docs ---------------------------------------------------------------------------------
    linked = {frozenset((s, d)) for (s, d, _t) in edges}
    nodes = sorted(ds)
    for i, a in enumerate(nodes):
        for b in nodes[i + 1:]:
            sh = docket_overlap(ds[a]["dockets"], ds[b]["dockets"])
            if sh and frozenset((a, b)) not in linked:
                add(a, b, "SAME_DOCKET", "CANDIDATE", [], f"shared docket {sh[0]}; relationship unverified (unordered)")

    # ---- conflict warnings ----------------------------------------------------------------------------------------------
    wd = defaultdict(list)
    for (s, d, t), (c, ev, n) in edges.items():
        if t == "WITHDRAWS" and c == "VERIFIED": wd[d].append(s)
    for d, ss in sorted(wd.items()):
        if len(ss) > 1: warn(d, "MULTIPLE_WITHDRAWALS", f"{d} is withdrawn by several documents: {sorted(ss)}", sorted(ss))
    for (s, d, t), (c, ev, n) in sorted(edges.items()):
        if t == "FINALIZES" and d in wd:
            warn(d, "FINAL_RULE_FOR_WITHDRAWN", f"{d} has a withdrawal ({wd[d]}) and a {c} final-rule link from {s}", [s])
        if t in ("WITHDRAWS", "SUPPLEMENTS", "FINALIZES") and c == "VERIFIED" and docs.get(s) and docs.get(d) \
                and docs[s]["date"] and docs[d]["date"] and docs[s]["date"] < docs[d]["date"]:
            warn(s, "DATES_OUT_OF_ORDER", f"{t} {s} -> {d} but source predates target", [d])
    for (s, d, t), (c, ev, n) in sorted(edges.items()):
        conn.execute("INSERT INTO relations(src,dst,type,confidence,evidence_json,note) VALUES(?,?,?,?,?,?)",
                     (s, d, t, c, json.dumps(ev, sort_keys=True, ensure_ascii=False), n))
    for w in sorted(set(warns)):
        conn.execute("INSERT INTO revision_warnings(fr_docnum,kind,message,related_json) VALUES(?,?,?,?)", w)
    cnt = defaultdict(int)
    for (s, d, t), (c, ev, n) in edges.items(): cnt[f"{t}/{c}"] += 1
    return dict(edges=dict(sorted(cnt.items())), warnings=len(set(warns)))


def _has(conn, table):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE name=?", (table,)).fetchone() is not None


# ------------------------------------------------------------------------------------------ query
def _conn(conn=None):
    if conn is not None:
        return conn
    c = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True)
    return c


def _cit_ref(conn, ev):
    if "meta_field" in ev:
        return CitationRef(citation_id=hashlib.sha256(f"meta|{ev['value']}".encode()).hexdigest()[:12], fr_docnum="",
                           quote=f"{ev['meta_field']}: {ev['value']}", source_tier=SourceTier.SHEET_METADATA)
    dn, s, e = ev["fr_docnum"], ev["start"], ev["end"]
    doc = conn.execute("SELECT start_page,pdf_url,xml_url FROM documents WHERE fr_docnum=?", (dn,)).fetchone()
    sec = conn.execute("SELECT section_path,label,fr_page_start,fr_page_end,pdf_page_start,pdf_page_end FROM sections WHERE fr_docnum=? "
                       "AND start_char<=? AND end_char>=? ORDER BY (end_char-start_char) LIMIT 1", (dn, s, e)).fetchone()
    fr_page = pdf_page = None
    if sec:
        fr_page, pdf_page = sec[2], sec[4]
        if sec[3] != sec[2] and sec[4] is not None and sec[5] is not None:
            q = pp.norm_for_match(ev["quote"])
            for p, t in conn.execute("SELECT pdf_page,text FROM pages WHERE fr_docnum=? AND pdf_page BETWEEN ? AND ? ORDER BY pdf_page",
                                     (dn, sec[4], sec[5])):
                if q and q in pp.norm_for_match(t):
                    pdf_page = p; fr_page = doc[0] + p - 1; break
    return CitationRef(citation_id=hashlib.sha256(f"{dn}|{s}|{e}".encode()).hexdigest()[:12], fr_docnum=dn,
                       section_path=sec[0] if sec else None, label=sec[1] if sec else None, fr_page=fr_page, pdf_page=pdf_page,
                       quote=ev["quote"], start=s, end=e, source_tier=SourceTier.FR_FULL_TEXT,
                       pdf_url=doc[1] if doc else None, xml_url=doc[2] if doc else None)


_ORDER = {"WITHDRAWS": 0, "SUPPLEMENTS": 1, "FINALIZES": 2, "CORRECTS": 3, "PROPOSES_TO_SUPERSEDE": 4, "SUPERSEDES": 5, "SAME_DOCKET": 6}


def _edges_for(conn, dn):
    rows = conn.execute("SELECT src,dst,type,confidence,evidence_json,note FROM relations WHERE src=? OR dst=?", (dn, dn)).fetchall()
    rows.sort(key=lambda r: (_ORDER[r[2]], r[3] != "VERIFIED", r[0], r[1]))
    return rows


def _fmt(conn, dn):
    r = conn.execute("SELECT publication_date,source,doc_class FROM documents WHERE fr_docnum=?", (dn,)).fetchone()
    return f"FR {dn}" + (f", {r[0]}" if r else "")


def revision_status(fr_docnum, conn=None) -> RevisionResult:
    conn = _conn(conn)
    doc = conn.execute("SELECT doc_class,publication_date,source FROM documents WHERE fr_docnum=?", (fr_docnum,)).fetchone()
    rows = _edges_for(conn, fr_docnum)
    edges = [RevisionEdge(src=s, dst=d, type=t, confidence=c, evidence=[_cit_ref(conn, e) for e in json.loads(ev)], note=n)
             for s, d, t, c, ev, n in rows]
    V = lambda t, side: [r for r in rows if r[2] == t and r[3] == "VERIFIED" and (r[1] if side == "dst" else r[0]) == fr_docnum]
    sents, status = [], RevisionStatus.PROPOSAL_STATUS_UNVERIFIED
    wd_by, sup_by, fin_by = V("WITHDRAWS", "dst"), V("SUPPLEMENTS", "dst"), V("FINALIZES", "dst")
    is_wd = bool(doc and doc[0] == "WITHDRAWAL")
    kind = {"NPRM": "NPRM", "SNPRM": "SNPRM"}.get(doc[0] if doc else "", "document")
    head = f"Proposal ({kind}, {_fmt(conn, fr_docnum)})." if kind != "document" else f"{doc[0] if doc else 'Document'} ({_fmt(conn, fr_docnum)})."
    if is_wd:
        status = RevisionStatus.WITHDRAWN
        tg = [r[1] for r in V("WITHDRAWS", "src")]
        sents.append(f"This document is a withdrawal" + (f" of {', '.join(_fmt(conn, t) for t in tg)}" if tg else " (the withdrawn proposal could not be identified from its text)") + "; it imposes no requirement.")
    elif doc and doc[2] == "fr_final_rule_lookup":
        sents.append(f"This is a final-rule-lookup document ({doc[0]}); revision status applies to dataset proposals only.")
    else:
        sents.append(head)
        if wd_by:
            status = RevisionStatus.WITHDRAWN
            sents.append("This proposal was withdrawn by " + "; ".join(_fmt(conn, r[0]) for r in wd_by) + "; it imposes no requirement.")
        if sup_by:
            status = status if wd_by else RevisionStatus.SUPPLEMENTED
            sents.append("A later supplemental proposal revises this one: " + "; ".join(_fmt(conn, r[0]) for r in sup_by) + ".")
            sents.extend(_successor_outcomes(conn, [r[0] for r in sup_by]))
        if fin_by:
            status = status if (wd_by or sup_by) else RevisionStatus.FINALIZED
            for r in fin_by:
                ad = conn.execute("SELECT ad_number,ad_start,ad_end,effective_on FROM final_rule_info WHERE fr_docnum=?", (r[0],)).fetchone()
                adtxt = f", AD {ad[0]} [quoted]" if ad and ad[0] else ""
                sents.append(f"A final rule ({_fmt(conn, r[0]).replace('FR ', 'FR ')}{adtxt}) was published on "
                             f"{conn.execute('SELECT publication_date FROM documents WHERE fr_docnum=?', (r[0],)).fetchone()[0]}; "
                             f"check the final rule's applicability." + (f" Effective date (per rule metadata): {ad[3]}." if ad and ad[3] else ""))
            sents.append("Current status of the final AD was not verified. " + WARN_FINALIZED)
        if wd_by and fin_by:
            sents.append("Conflict: a final-rule link also exists for this withdrawn proposal; not resolved (see revision warnings).")
    for r in V("PROPOSES_TO_SUPERSEDE", "src"):
        sents.append(f"This proposal proposes to supersede {r[1][3:] and 'AD ' + r[1][3:]} (proposal only; no effective change is claimed).")
    for r in V("SUPERSEDES", "src"):
        sents.append(f"The final rule's text states it supersedes AD {r[1][3:]}.")
    cand = [r for r in rows if r[3] == "CANDIDATE" and r[2] in ("SAME_DOCKET", "FINALIZES", "WITHDRAWS", "SUPPLEMENTS")]
    if cand:
        others = sorted({(r[1] if r[0] == fr_docnum else r[0]) for r in cand})
        sents.append("Related documents (same docket or unconfirmed link), relationship unverified: " + ", ".join(others[:6]) + ("..." if len(others) > 6 else "") + ".")
    if status != RevisionStatus.FINALIZED:
        sents.append("Current regulatory status was not verified.")
    return RevisionResult(status=status, current_authoritative_status_verified=False, edges=edges, template_text=" ".join(sents),
                          latest_in_dataset=_latest(conn, fr_docnum) if doc else None)


def _successor_outcomes(conn, start):
    """Follow VERIFIED SUPPLEMENTS edges forward and report what happened to each successor proposal
    (withdrawn / finalized), quoting only VERIFIED edges. Status of the original document is not changed:
    the withdrawal or final rule cites the successor, not necessarily this document."""
    out, seen, todo = [], set(start), list(start)
    while todo:
        s = todo.pop(0)
        for (w,) in conn.execute("SELECT src FROM relations WHERE type='WITHDRAWS' AND confidence='VERIFIED' AND dst=?", (s,)):
            out.append(f"The supplemental proposal {_fmt(conn, s)} was later withdrawn by {_fmt(conn, w)}.")
        for (f,) in conn.execute("SELECT src FROM relations WHERE type='FINALIZES' AND confidence='VERIFIED' AND dst=?", (s,)):
            out.append(f"The supplemental proposal {_fmt(conn, s)} was later finalized by {_fmt(conn, f)}.")
        for (n,) in conn.execute("SELECT src FROM relations WHERE type='SUPPLEMENTS' AND confidence='VERIFIED' AND dst=?", (s,)):
            if n not in seen:
                seen.add(n); todo.append(n)
                out.append(f"{_fmt(conn, s)} was itself supplemented by {_fmt(conn, n)}.")
    return out


def _latest(conn, dn):
    """Newest dataset doc in the VERIFIED-edge connected component (dataset fact, not legal currency)."""
    adj = defaultdict(set)
    for s, d in conn.execute("SELECT src,dst FROM relations WHERE confidence='VERIFIED' AND type IN ('WITHDRAWS','SUPPLEMENTS','FINALIZES','CORRECTS')"):
        adj[s].add(d); adj[d].add(s)
    seen, st = {dn}, [dn]
    while st:
        for n in adj[st.pop()]:
            if n not in seen: seen.add(n); st.append(n)
    ds = {r[0]: r for r in conn.execute("SELECT fr_docnum,publication_date,start_page FROM documents WHERE source='organiser_sheet'")}
    cand = [ds[n] for n in seen if n in ds]
    if not cand: return None
    return max(cand, key=lambda r: (r[1] or "", r[2] or 0, r[0]))[0]


def revision_overlay(fr_docnum, conn=None) -> list[str]:
    conn = _conn(conn)
    res = revision_status(fr_docnum, conn)
    out = []
    ver = lambda t: [e for e in res.edges if e.type == t and e.confidence == "VERIFIED"]
    if res.status == RevisionStatus.WITHDRAWN:
        out.append("Proposal withdrawn; no proposed requirement." if not any(e.dst == fr_docnum for e in ver("WITHDRAWS")) else
                   "Proposal withdrawn by " + ", ".join(e.src for e in ver("WITHDRAWS") if e.dst == fr_docnum) + "; no proposed requirement.")
    if res.status == RevisionStatus.SUPPLEMENTED:
        out.append("A later supplemental proposal (" + ", ".join(e.src for e in ver("SUPPLEMENTS") if e.dst == fr_docnum) + ") revises this one; evaluate that document too.")
        out.extend(_successor_outcomes(conn, [e.src for e in ver("SUPPLEMENTS") if e.dst == fr_docnum]))
    for e in ver("FINALIZES"):
        if e.dst == fr_docnum:
            out.append(f"A final rule (FR {e.src}) was published; evaluate the final rule's applicability, not this proposal's.")
    for e in ver("PROPOSES_TO_SUPERSEDE"):
        out.append(f"Proposes to supersede {e.dst} (proposal only).")
    if res.status == RevisionStatus.FINALIZED:
        out.append(WARN_FINALIZED)
    elif res.status != RevisionStatus.WITHDRAWN:
        out.append("Revision status unverified; this proposal is not shown to be legally current.")
    return out
