"""SQLite FTS5 lexical index (BM25) + search.sqlite writer.

Two FTS columns: `body` (unicode61 over the embedding-input text) and `ids` (normalised identifier
tokens: uppercase alphanumerics only, so PA-28-140 / S/N 28-7125001 / P/N 3G6410A00131 match
regardless of punctuation). User strings never reach FTS syntax unescaped: every term is a quoted
alphanumeric string built here.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path

from backend.config import INDEXES

SEARCH_DB = INDEXES / "search.sqlite"

STOP = frozenset("""a an and are as at be by for from has have how i in is it its of on or that the this to was were
what when where which who will with does do not no can any all about than then there these those their into per""".split())

_TOKEN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9\-/\.]*[A-Za-z0-9])?")
_AD_RE = re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b")

SCHEMA = """
create table chunks(idx integer primary key, chunk_id text unique, fr_docnum text, section_path text, label text,
 heading text, kind text, start_char int, end_char int, text text, context_prefix text, fr_page_start int,
 fr_page_end int, pdf_page_start int, pdf_page_end int, doc_class text, source text, dockets_json text,
 make_json text, models_json text, publication_date text, title text, is_applicability int, n_words int);
create index chunks_doc on chunks(fr_docnum);
create table docs(fr_docnum text primary key, title text, doc_class text, source text, publication_date text,
 volume int, start_page int, end_page int, pdf_url text, xml_url text, dockets_json text, make_json text,
 models_json text, ad_numbers_json text);
create table ad_mentions(ad_number text, chunk_idx int);
create index ad_mentions_n on ad_mentions(ad_number);
create table info(k text primary key, v text);
create virtual table fts using fts5(body, ids, tokenize="unicode61 remove_diacritics 2");
"""


def norm_id(tok: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", tok).upper()


def id_tokens(text: str) -> list[str]:
    """Normalised identifier-like tokens (contain a digit, >=3 chars after normalisation)."""
    out = []
    for m in _TOKEN.finditer(text):
        t = m.group(0)
        if any(ch.isdigit() for ch in t):
            n = norm_id(t)
            if len(n) >= 3:
                out.append(n)
    return out


def write_index(path: Path, chunks: list[dict], meta: dict[str, dict], info: dict) -> None:
    path = Path(path)
    tmp = path.with_suffix(".sqlite.tmp")
    for p in (tmp,):
        if p.exists():
            p.unlink()
    c = sqlite3.connect(tmp)
    c.executescript(SCHEMA)
    for i, ch in enumerate(chunks):
        c.execute("insert into chunks values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            i, ch["chunk_id"], ch["fr_docnum"], ch["section_path"], ch["label"], ch["heading"], ch["kind"],
            ch["start_char"], ch["end_char"], ch["text"], ch["context_prefix"], ch["fr_page_start"],
            ch["fr_page_end"], ch["pdf_page_start"], ch["pdf_page_end"], ch["doc_class"], ch["source"],
            json.dumps(ch["dockets"]), json.dumps(ch["make_norm"]), json.dumps(ch["models"]),
            ch["publication_date"], ch["title"], int(ch["is_applicability"]), ch["n_words"]))
        c.execute("insert into fts(rowid, body, ids) values(?,?,?)",
                  (i, ch["embed_text"], " ".join(id_tokens(ch["embed_text"]))))
        for ad in sorted(set(_AD_RE.findall(ch["text"]))):
            c.execute("insert into ad_mentions values(?,?)", (ad, i))
    for dn in sorted(meta):
        m = meta[dn]
        c.execute("insert into docs values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            dn, m["title"], m["doc_class"], m["source"], m["publication_date"], m["volume"], m["start_page"],
            m["end_page"], m["pdf_url"], m["xml_url"], json.dumps(m["dockets"]), json.dumps(m["make_norm"]),
            json.dumps(m["models"]), json.dumps(m["ad_numbers"])))
    for k, v in sorted(info.items()):
        c.execute("insert into info values(?,?)", (k, json.dumps(v)))
    c.execute("insert into fts(fts) values('optimize')")
    c.commit()
    c.close()
    os.replace(tmp, path)


def build_match_query(q: str, max_terms: int = 48) -> str | None:
    """Sanitised FTS5 query: OR of quoted alnum terms, hyphen/slash compounds also as phrases,
    plus normalised identifier terms against the `ids` column. Returns None if nothing usable."""
    terms: list[str] = []
    seen = set()

    def add(t):
        if t not in seen:
            seen.add(t)
            terms.append(t)

    for m in _TOKEN.finditer(q):
        tok = m.group(0)
        parts = re.findall(r"[A-Za-z0-9]+", tok.lower())
        if not parts:
            continue
        if len(parts) > 1:
            add('body:"%s"' % " ".join(parts))
        for p in parts:
            if p not in STOP or len(parts) > 1:
                add('body:"%s"' % p)
        if any(ch.isdigit() for ch in tok):
            n = norm_id(tok)
            if len(n) >= 3:
                add('ids:"%s"' % n)
    # any leftover punctuation-separated alnum words (e.g. inside odd tokens) are covered above
    terms = terms[:max_terms]
    return " OR ".join(terms) if terms else None


def bm25_search(conn: sqlite3.Connection, q: str, limit: int = 50, allowed_temp: bool = False):
    """Returns [(chunk_idx, score)] best first; score = -bm25() so higher is better. Never raises on user input."""
    mq = build_match_query(q)
    if not mq:
        return []
    sql = "select rowid, -bm25(fts, 1.0, 2.0) from fts where fts match ?"
    if allowed_temp:
        sql += " and rowid in (select id from allowed)"
    sql += " order by bm25(fts, 1.0, 2.0), rowid limit ?"
    try:
        return [(r[0], r[1]) for r in conn.execute(sql, (mq, limit))]
    except sqlite3.OperationalError:
        return []
