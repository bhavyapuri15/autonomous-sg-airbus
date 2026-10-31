"""PyMuPDF page text + FR page header parsing, and snippet normalisation for page-mapping validation."""
import re, unicodedata
import pymupdf

DASHES = dict.fromkeys(map(ord, "‐‑‒–—−"), "-")
QUOTES = {ord("‘"): "'", ord("’"): "'", ord("“"): '"', ord("”"): '"'}
HEAD_EVEN = re.compile(r"^\s*(\d{3,6})\s*\n\s*Federal Register\s*/")
HEAD_ODD = re.compile(r"^\s*Federal Register\s*/[^\n]*?(\d{3,6})\s*(?:\n|$)")
BANNER = re.compile(r"Proposed Rules\s*\n\s*Federal Register\s*\n\s*(\d{3,6})\s*\n\s*Vol\.")  # first page of a FR section banner


def header_fr_page(text):
    """FR page number parsed from the page header. None when not found (e.g. first page of an FR section banner)."""
    m = HEAD_EVEN.match(text) or HEAD_ODD.match(text) or BANNER.search(text[:800])
    if m:
        return int(m.group(1))
    return None


def read_pages(pdf_path):
    """Returns list of text per PDF page (1-based order)."""
    doc = pymupdf.open(pdf_path)
    try:
        return [p.get_text() for p in doc]
    finally:
        doc.close()


def strip_marks(s):
    """NFKD and drop combining marks: PDF text often decomposes/replaces accented glyphs (Cote vs Côte)."""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm_for_match(s):
    """Normalisation applied identically to XML snippets and PDF page text: accents stripped (NFKD), then ONLY ASCII
    letters/digits kept, lower-cased. This makes the comparison insensitive to whitespace, line-break hyphenation,
    quote/dash glyphs and PDF font-mapping artefacts (e.g. circumflex U+02C6 for o-circumflex, '+' for sz-ligature).
    Comparing 40-char snippets this way is still highly selective."""
    return re.sub(r"[^a-z0-9]+", "", strip_marks(s).lower())
