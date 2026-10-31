"""Deterministic chunker over the core DB (data/indexes/ad.sqlite, read-only).

Every chunk's stored text is the raw span doc_text[start:end] (asserted). The text used
for BM25/embeddings (`embed_text`) additionally carries title | class | heading context.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import defaultdict

from backend.config import DB_PATH

AD_MAX_WORDS = 450
OTHER_MAX_WORDS = 350
MIN_WORDS = 4  # drop trivial banner fragments ("SUPPLEMENTARY INFORMATION:") unless AD paragraph

_DOCKET_PATTERNS = [
    re.compile(r"\bFAA[-\s]+\d{4}[-\s]+\d{3,5}\b", re.I),
    re.compile(r"\b(?:MCAI|AD)-\d{4}-\d{5}-[A-Z]\b", re.I),
    re.compile(r"\b\d{2,4}-[A-Z]{2,4}-\d{1,4}(?:-AD)?\b", re.I),
    re.compile(r"\b(?:Notice No\.\s*)?(\d{2}-\d{2})\b"),
]


def canon_docket(s: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "-", s.upper()).strip("-")


def extract_dockets(raw: str) -> list[str]:
    """Canonical docket ids found inside a raw docket string (e.g. 'Docket No. FAA-2009-1028')."""
    out: list[str] = []
    for pat in _DOCKET_PATTERNS[:3]:
        for m in pat.finditer(raw):
            out.append(canon_docket(m.group(0)))
    if not out:
        m = _DOCKET_PATTERNS[3].search(raw)
        if m:
            out.append(canon_docket(m.group(1)))
    seen, res = set(), []
    for d in out:
        if d not in seen:
            seen.add(d)
            res.append(d)
    return res


def connect_ro(path=DB_PATH) -> sqlite3.Connection:
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def wc(t: str) -> int:
    return len(t.split())


def load_doc_meta(conn) -> dict[str, dict]:
    recs = defaultdict(list)
    for r in conn.execute("select * from records where fr_docnum is not null and fr_docnum != '' order by row"):
        recs[r["fr_docnum"]].append(r)
    meta = {}
    for d in conn.execute("select * from documents order by fr_docnum"):
        rs = recs.get(d["fr_docnum"], [])
        dockets: list[str] = []
        for raw in json.loads(d["docket_ids_json"] or "[]") + [r["docket_norm"] or "" for r in rs]:
            for x in extract_dockets(raw):
                if x not in dockets:
                    dockets.append(x)
        makes = sorted({r["make_norm"] for r in rs if r["make_norm"]})
        models: list[str] = []
        for r in rs:
            for m in json.loads(r["models_json"] or "[]"):
                if m not in models:
                    models.append(m)
        meta[d["fr_docnum"]] = dict(
            fr_docnum=d["fr_docnum"], title=d["title"], doc_class=d["doc_class"], source=d["source"],
            publication_date=d["publication_date"], volume=d["volume"], start_page=d["start_page"],
            end_page=d["end_page"], pdf_url=d["pdf_url"], xml_url=d["xml_url"],
            dockets=dockets, make_norm=makes, models=sorted(models),
            ad_numbers=sorted({r["ad_number"] for r in rs if r["ad_number"]}),
        )
    return meta


def _paragraph_spans(text: str, base: int):
    """Split on blank lines; returns [(start,end)] absolute offsets of non-empty paragraphs."""
    spans, pos = [], 0
    for part in re.split(r"(\n\n+)", text):
        if part and not part.startswith("\n\n") and part.strip():
            spans.append((base + pos, base + pos + len(part)))
        pos += len(part)
    return spans


def _pack(spans, doc_text, limit):
    """Greedy-pack consecutive paragraph spans to <= limit words (a paragraph is never cut)."""
    groups, cur, cw = [], [], 0
    for s, e in spans:
        w = wc(doc_text[s:e])
        if cur and cw + w > limit:
            groups.append((cur[0][0], cur[-1][1]))
            cur, cw = [], 0
        cur.append((s, e))
        cw += w
    if cur:
        groups.append((cur[0][0], cur[-1][1]))
    return groups


class _Pages:
    """Refine page numbers of a piece inside a multi-page section by locating its first/last
    characters in the PDF page text (whitespace-normalised). Falls back to the section range."""

    def __init__(self, conn, docnum):
        self.rows = [(r["pdf_page"], r["fr_page"], re.sub(r"\s+", " ", r["text"] or ""))
                     for r in conn.execute("select pdf_page, fr_page, text from pages where fr_docnum=? order by pdf_page", (docnum,))]

    def locate(self, snippet: str, lo: int, hi: int):
        sn = re.sub(r"\s+", " ", snippet).strip()
        if len(sn) < 12:
            return None
        for pdf, fr, t in self.rows:
            if lo <= pdf <= hi and sn in t:
                return pdf, fr
        return None


def build_chunks(conn=None) -> tuple[list[dict], dict[str, dict]]:
    own = conn is None
    conn = conn or connect_ro()
    try:
        meta = load_doc_meta(conn)
        texts = {r["fr_docnum"]: r["text"] for r in conn.execute("select fr_docnum, text from doc_text")}
        secs = defaultdict(list)
        for r in conn.execute("select * from sections order by fr_docnum, seq"):
            secs[r["fr_docnum"]].append(r)
        chunks: list[dict] = []
        for dn in sorted(meta):
            if dn not in texts:
                continue
            chunks.extend(_chunk_doc(conn, dn, texts[dn], secs.get(dn, []), meta[dn]))
        return chunks, meta
    finally:
        if own:
            conn.close()


def _make(doc_text, m, *, section_path, label, heading, kind, start, end, ctx, pages, applicability):
    text = doc_text[start:end]
    assert text and text == doc_text[start:end]
    pre = f"{ctx}" if ctx else ""
    h = heading or label or section_path.rsplit("/", 1)[-1]
    embed = f"{m['title']} | {m['doc_class']} | {h}\n{pre}{text}"
    return dict(
        chunk_id=f"{m['fr_docnum']}:{section_path}:{hashlib.sha256(text.encode()).hexdigest()[:8]}",
        fr_docnum=m["fr_docnum"], section_path=section_path, label=label, heading=heading, kind=kind,
        start_char=start, end_char=end, text=text, context_prefix=ctx or "",
        fr_page_start=pages[0], fr_page_end=pages[1], pdf_page_start=pages[2], pdf_page_end=pages[3],
        doc_class=m["doc_class"], source=m["source"], dockets=m["dockets"], make_norm=m["make_norm"],
        models=m["models"], publication_date=m["publication_date"], title=m["title"],
        is_applicability=applicability, n_words=wc(text), embed_text=embed,
    )


def _chunk_doc(conn, dn, doc_text, sections, m):
    out = []
    ad_groups: dict[str, list] = {}
    order: list = []
    for s in sections:
        if s["kind"] == "proposed_ad_paragraph" and s["top_path"]:
            if s["top_path"] not in ad_groups:
                ad_groups[s["top_path"]] = []
                order.append(("ad", s["top_path"], s["seq"]))
            ad_groups[s["top_path"]].append(s)
        else:
            order.append(("sec", s, s["seq"]))
    pages_cache: list = []

    def pg():
        if not pages_cache:
            pages_cache.append(_Pages(conn, dn))
        return pages_cache[0]

    for kind, item, _ in sorted(order, key=lambda x: x[2]):
        if kind == "ad":
            out.extend(_chunk_ad(doc_text, m, ad_groups[item]))
        else:
            out.extend(_chunk_plain(doc_text, m, item, pg))
    # unique chunk ids (identical repeated text inside one section path is practically impossible)
    seen = defaultdict(int)
    for c in out:
        seen[c["chunk_id"]] += 1
        if seen[c["chunk_id"]] > 1:
            c["chunk_id"] += f"~{seen[c['chunk_id']]}"
    if not out:  # never leave a document without any chunk
        n = len(doc_text)
        out.append(_make(doc_text, m, section_path="doc", label=None, heading=None, kind="other",
                         start=0, end=n, ctx="", pages=(m["start_page"], m["end_page"], 1, None), applicability=False))
    return out


def _chunk_ad(doc_text, m, grp):
    top = grp[0]
    start = min(s["start_char"] for s in grp)
    end = max(s["end_char"] for s in grp)
    top_sec = next((s for s in grp if s["section_path"] == top["top_path"]), top)
    heading = top_sec["heading"]
    is_app = bool(heading and heading.strip().lower().startswith("applicab"))
    span_pages = lambda secs: (  # noqa: E731
        min(s["fr_page_start"] for s in secs), max(s["fr_page_end"] for s in secs),
        min(s["pdf_page_start"] for s in secs), max(s["pdf_page_end"] for s in secs))
    whole = doc_text[start:end]
    if is_app or wc(whole) <= AD_MAX_WORDS:
        return [_make(doc_text, m, section_path=top["top_path"], label=top_sec["label"], heading=heading,
                      kind="proposed_ad_paragraph", start=start, end=end, ctx="", pages=span_pages(grp),
                      applicability=is_app)]
    kids = sorted((s for s in grp if s["ancestor_path"] == top["top_path"] and s["section_path"] != top["top_path"]),
                  key=lambda s: s["start_char"])
    if len(kids) < 2:
        return [_make(doc_text, m, section_path=top["top_path"], label=top_sec["label"], heading=heading,
                      kind="proposed_ad_paragraph", start=start, end=end, ctx="", pages=span_pages(grp),
                      applicability=False)]
    # pieces: head (parent intro) + direct children packed up to AD_MAX_WORDS; boundaries at child starts
    units = []
    if kids[0]["start_char"] > start:
        units.append((start, kids[0]["start_char"], [top_sec], "head", top_sec))
    for i, k in enumerate(kids):
        e = kids[i + 1]["start_char"] if i + 1 < len(kids) else end
        units.append((k["start_char"], e, [s for s in grp if s["start_char"] >= k["start_char"] and s["end_char"] <= e and s is not top_sec], "kid", k))
    pieces, cur = [], []
    for u in units:
        w = wc(doc_text[u[0]:u[1]])
        if cur and sum(wc(doc_text[x[0]:x[1]]) for x in cur) + w > AD_MAX_WORDS:
            pieces.append(cur)
            cur = []
        cur.append(u)
    if cur:
        pieces.append(cur)
    ctx = f"{top_sec['label'] or ''} {heading or ''}".strip() + ": "
    res = []
    for idx, p in enumerate(pieces):
        ps, pe = p[0][0], p[-1][1]
        secs = [s for u in p for s in u[2]]
        pages = span_pages(secs) if secs else span_pages([top_sec])
        if p[0][3] == "head":  # intro belongs to the top section's first page
            pages = (min(pages[0], top_sec["fr_page_start"]), pages[1], min(pages[2], top_sec["pdf_page_start"]), pages[3])
        if idx == len(pieces) - 1:
            pages = (pages[0], max(pages[1], top_sec["fr_page_end"]), pages[2], max(pages[3], top_sec["pdf_page_end"]))
        first = p[0][4]
        path = top["top_path"] if p[0][3] == "head" else first["section_path"]
        res.append(_make(doc_text, m, section_path=path, label=first["label"], heading=heading, kind="proposed_ad_paragraph",
                         start=ps, end=pe, ctx=ctx, pages=pages, applicability=False))
    return res


def _chunk_plain(doc_text, m, s, pg):
    start, end = s["start_char"], s["end_char"]
    text = doc_text[start:end]
    if not text.strip() or (wc(text) < MIN_WORDS and s["kind"] != "proposed_ad_paragraph"):
        return []
    base_pages = (s["fr_page_start"], s["fr_page_end"], s["pdf_page_start"], s["pdf_page_end"])
    ctx = ""
    if wc(text) <= OTHER_MAX_WORDS:
        return [_make(doc_text, m, section_path=s["section_path"], label=s["label"], heading=s["heading"], kind=s["kind"],
                      start=start, end=end, ctx=ctx, pages=base_pages, applicability=False)]
    pieces = _pack(_paragraph_spans(text, start), doc_text, OTHER_MAX_WORDS)
    if len(pieces) <= 1:
        return [_make(doc_text, m, section_path=s["section_path"], label=s["label"], heading=s["heading"], kind=s["kind"],
                      start=start, end=end, ctx=ctx, pages=base_pages, applicability=False)]
    ctx = f"{s['heading'] or s['section_path'].rsplit('/', 1)[-1]}: "
    res = []
    multi = s["pdf_page_end"] > s["pdf_page_start"]
    for ps, pe in pieces:
        pages = base_pages
        if multi:
            a = pg().locate(doc_text[ps:ps + 40], s["pdf_page_start"], s["pdf_page_end"])
            b = pg().locate(doc_text[max(ps, pe - 40):pe], s["pdf_page_start"], s["pdf_page_end"])
            if a and b and b[0] >= a[0]:
                pages = (a[1], b[1], a[0], b[0])
        res.append(_make(doc_text, m, section_path=s["section_path"], label=s["label"], heading=s["heading"], kind=s["kind"],
                         start=ps, end=pe, ctx=ctx, pages=pages, applicability=False))
    return res
