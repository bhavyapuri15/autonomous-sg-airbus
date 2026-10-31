"""Exact identifier router: dockets, FR document numbers, FR citations, AD-number mentions.

Exact hits are authoritative lookups (never embeddings). Near misses (edit distance 1) are returned
separately as suggestions and must never be merged into results. An AD number is never claimed to
BE a document: matches are documents that *mention* it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.retrieval.chunker import canon_docket

_FR_CITE = re.compile(r"(?<![\w-])(\d{1,3})\s*(?:FR|F\.R\.)\s*(\d{1,6})(?![\w-])", re.I)
_DOCKET_FAA = re.compile(r"(?<![\w-])FAA[-\s_]*(\d{4})[-\s_]*(\d{3,5})(?:[-\s]*R(\d))?(?![\w-])", re.I)
_DOCKET_PROJ = re.compile(r"(?<![\w-])((?:MCAI|AD)-\d{4}-\d{5}-[A-Z])(?![\w-])", re.I)
_DOCKET_LEGACY = re.compile(r"(?<![\w-])(\d{2,4})-([A-Z]{2,4})-(\d{1,4})(?:-AD)?(?:[-\s]*R(\d))?(?![\w-])", re.I)
_AD_NUM = re.compile(r"(?<![\w-])((?:19|20)\d{2}-\d{2}-\d{2})(?![\w-])")
_DOCNUMS = [
    re.compile(r"(?<![\w-])([A-Za-z]\d{1,2}-\d{4}-\d{5})(?![\w-])"),   # R1-2022-23012
    re.compile(r"(?<![\w-])([A-Za-z]\d{1,2}-\d{3,5})(?![\w-])"),       # E9-322
    re.compile(r"(?<![\w-])(\d{4}-\d{4,5})(?![\w-])"),                 # 2026-21387
    re.compile(r"(?<![\w-])(\d{2}-\d{3,5})(?![\w-])"),                 # 01-10467
    re.compile(r"(?<![\w-])(\d{4}-\d{2})(?![\w-])"),                   # 2011-54
]


def edit1(a: str, b: str) -> bool:
    """True iff Levenshtein distance(a, b) == 1."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    s, l = (a, b) if len(a) < len(b) else (b, a)
    i = j = 0
    skipped = False
    while i < len(s) and j < len(l):
        if s[i] == l[j]:
            i += 1
            j += 1
        elif skipped:
            return False
        else:
            skipped = True
            j += 1
    return True


@dataclass
class RouteResult:
    exact: list[dict] = field(default_factory=list)      # {fr_docnum, id_type, id_value, label, chunk_idx?}
    near_miss: list[dict] = field(default_factory=list)  # {id_type, query_id, suggestion, fr_docnum, near_miss: True}
    detected: list[dict] = field(default_factory=list)   # {id_type, value, normalized}
    remaining: str = ""                                   # query with identifier strings removed


class IDRouter:
    def __init__(self, docs: list[dict], ad_mention_lookup=None, known_ad_numbers=()):
        """docs: dicts with fr_docnum, volume, start_page, end_page, publication_date, dockets.
        ad_mention_lookup(ad_number) -> [(fr_docnum, chunk_idx)]."""
        self.docs = {d["fr_docnum"]: d for d in docs}
        self.by_docnum = {d.upper(): d for d in self.docs}
        self.by_docket: dict[str, list[str]] = {}
        for d in docs:
            for k in d["dockets"]:
                for key in {k, re.sub(r"-AD$", "", k)}:
                    self.by_docket.setdefault(key, []).append(d["fr_docnum"])
        for k, v in self.by_docket.items():
            v.sort(key=lambda dn: (self.docs[dn]["publication_date"] or "", dn))
        self.ad_lookup = ad_mention_lookup
        self.known_ads = sorted(known_ad_numbers)

    # -- detection ----------------------------------------------------------------------
    def detect(self, query: str) -> tuple[list[dict], str]:
        """Return detected identifier strings (type, value, normalized) and the query with them removed."""
        work = query
        det: list[dict] = []

        def consume(rx, typ, norm):
            nonlocal work
            def rep(m):
                n = norm(m)
                if n is not None:
                    det.append(dict(id_type=typ, value=m.group(0), normalized=n))
                    return " "
                return m.group(0)
            work = rx.sub(rep, work)

        consume(_FR_CITE, "fr_citation", lambda m: (int(m.group(1)), int(m.group(2))))
        consume(_DOCKET_FAA, "docket", lambda m: f"FAA-{m.group(1)}-{m.group(2)}")
        consume(_DOCKET_PROJ, "docket", lambda m: canon_docket(m.group(1)))
        consume(_DOCKET_LEGACY, "docket", lambda m: f"{m.group(1)}-{m.group(2).upper()}-{m.group(3)}-AD")
        consume(_AD_NUM, "ad_number", lambda m: m.group(1))
        for rx in _DOCNUMS:
            consume(rx, "fr_docnum", lambda m: m.group(1).upper())
        return det, re.sub(r"\s+", " ", work).strip()

    # -- lookup -------------------------------------------------------------------------
    def route(self, query: str, near_limit: int = 3) -> RouteResult:
        det, remaining = self.detect(query)
        res = RouteResult(detected=det, remaining=remaining)
        seen_docs: set[tuple] = set()

        def add(dn, typ, val, label, chunk_idx=None):
            key = (dn, chunk_idx)
            if key in seen_docs:
                return
            seen_docs.add(key)
            res.exact.append(dict(fr_docnum=dn, id_type=typ, id_value=val, label=label, chunk_idx=chunk_idx))

        for d in det:
            typ, n, raw = d["id_type"], d["normalized"], d["value"]
            if typ == "fr_citation":
                vol, page = n
                hits = [x for x in self.docs.values() if x["volume"] == vol and x["start_page"] is not None
                        and x["start_page"] <= page <= x["end_page"]]
                hits.sort(key=lambda x: (x["start_page"] != page, x["publication_date"] or "", x["fr_docnum"]))
                for x in hits:
                    add(x["fr_docnum"], typ, f"{vol} FR {page}",
                        f"FR citation {vol} FR {page} falls in pages {x['start_page']}-{x['end_page']}")
                if not hits:
                    for x in self.docs.values():
                        if x["volume"] == vol and x["start_page"] is not None and \
                           (abs(x["start_page"] - page) <= 1 and edit1(str(x["start_page"]), str(page))):
                            res.near_miss.append(dict(id_type=typ, query_id=f"{vol} FR {page}",
                                                      suggestion=f"{vol} FR {x['start_page']}", fr_docnum=x["fr_docnum"], near_miss=True))
            elif typ == "docket":
                keys = [n, re.sub(r"-AD$", "", n)]
                found = next((self.by_docket[k] for k in keys if k in self.by_docket), None)
                if found:
                    for dn in found:
                        add(dn, typ, n, f"docket {n}")
                else:
                    cands = [k for k in self.by_docket if edit1(k, n) or edit1(k, re.sub(r"-AD$", "", n))]
                    for k in sorted(cands)[:near_limit]:
                        for dn in self.by_docket[k][:1]:
                            res.near_miss.append(dict(id_type=typ, query_id=raw.strip(), suggestion=k, fr_docnum=dn, near_miss=True))
            elif typ == "fr_docnum":
                if n in self.by_docnum:
                    add(self.by_docnum[n], typ, n, f"FR document number {n}")
                else:
                    for k in sorted(k for k in self.by_docnum if edit1(k, n))[:near_limit]:
                        res.near_miss.append(dict(id_type=typ, query_id=n, suggestion=self.by_docnum[k],
                                                  fr_docnum=self.by_docnum[k], near_miss=True))
            elif typ == "ad_number":
                rows = self.ad_lookup(n) if self.ad_lookup else []
                if rows:
                    for dn, ci in rows[:25]:
                        add(dn, typ, n, f"mentions AD {n}", chunk_idx=ci)
                else:
                    for k in [a for a in self.known_ads if edit1(a, n)][:near_limit]:
                        rows2 = self.ad_lookup(k) if self.ad_lookup else []
                        res.near_miss.append(dict(id_type=typ, query_id=n, suggestion=k,
                                                  fr_docnum=rows2[0][0] if rows2 else None, near_miss=True))
        return res
