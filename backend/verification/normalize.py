"""Text normalization shared by the claim verifier and UI quote matching.

normalize_with_map() returns the normalized (casefolded) text plus, for every
normalized character, the [start, end) span of the original characters that
produced it.  find_quote() uses this to return EXACT original offsets.

Steps: NFKC (per grapheme unit), curly->straight quotes, dashes -> "-",
zero-width/soft-hyphen removal, de-hyphenation of line-break hyphens (a hyphen
between a letter and whitespace+letter), whitespace collapse + strip, casefold.
No fuzzy matching: a quote must be a contiguous substring after normalization.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

_QUOTES = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'",
    "´": "'", "`": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"',
    "«": '"', "»": '"',
}
_DASHES = {c: "-" for c in "‐‑‒–—―−﹘﹣－"}
_DROP = frozenset("­​‌‍⁠﻿")


@dataclass(frozen=True)
class Normalized:
    text: str
    starts: tuple  # starts[i] = original start index of normalized char i
    ends: tuple    # ends[i] = original end index (exclusive) of normalized char i


def _map_char(ch: str) -> str:
    return _QUOTES.get(ch) or _DASHES.get(ch) or ch


def _units(text: str):
    """Yield (normalized_piece, orig_start, orig_end) per char + combining marks."""
    i, n = 0, len(text)
    while i < n:
        j = i + 1
        while j < n and unicodedata.combining(text[j]):
            j += 1
        raw = text[i:j]
        if raw in _DROP or (j == i + 1 and raw in _DROP):
            i = j
            continue
        mapped = "".join(_map_char(c) for c in raw if c not in _DROP)
        piece = unicodedata.normalize("NFKC", mapped)
        piece = "".join(_map_char(c) for c in piece)
        piece = unicodedata.normalize("NFKC", piece.casefold())
        piece = "".join(_map_char(c) for c in piece if c not in _DROP)
        yield piece, i, j
        i = j


def normalize_with_map(text: str) -> Normalized:
    chars: list[tuple[str, int, int]] = []
    for piece, s, e in _units(text):
        for c in piece:
            chars.append((" " if c.isspace() else c, s, e))
    out: list[str] = []
    starts: list[int] = []
    ends: list[int] = []
    n = len(chars)
    i = 0
    while i < n:
        c, s, e = chars[i]
        if c == " ":
            j = i
            while j < n and chars[j][0] == " ":
                j += 1
            if out:  # no leading space
                out.append(" ")
                starts.append(s)
                ends.append(chars[j - 1][2])
            i = j
            continue
        if c == "-" and text[s] in "-\u2010\u2011" and out and out[-1].isalpha() and i + 1 < n and chars[i + 1][0] == " ":
            j = i + 1
            while j < n and chars[j][0] == " ":
                j += 1
            if j < n and chars[j][0].isalpha():
                i = j  # drop hyphen + whitespace: "air- plane" -> "airplane"
                continue
        out.append(c)
        starts.append(s)
        ends.append(e)
        i += 1
    if out and out[-1] == " ":
        out.pop(); starts.pop(); ends.pop()
    return Normalized("".join(out), tuple(starts), tuple(ends))


def normalize(text: str) -> str:
    return normalize_with_map(text).text


@lru_cache(maxsize=512)
def _cached(text: str) -> Normalized:
    return normalize_with_map(text)


def find_quote(doc_text: str, quote: str, norm: Normalized | None = None):
    """Locate `quote` in `doc_text`; return exact original (start, end) or None.

    Contiguous normalized substring match with word-boundary guards (a quote may
    not begin or end in the middle of a word)."""
    q = normalize(quote)
    if not q:
        return None
    nd = norm or _cached(doc_text)
    t = nd.text
    pos = 0
    while True:
        k = t.find(q, pos)
        if k < 0:
            return None
        end = k + len(q)
        ok = True
        if q[0].isalnum() and k > 0 and t[k - 1].isalnum():
            ok = False
        if q[-1].isalnum() and end < len(t) and t[end].isalnum():
            ok = False
        if ok:
            return nd.starts[k], nd.ends[end - 1]
        pos = k + 1
