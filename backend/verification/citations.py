"""Claim-level verification V1-V8 (+ optional V9 judge hook). Deterministic.

See docs/verification_spec.md section 3. A claim must pass every check.
"""
from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from backend.api.schemas import Claim, CitationRef, RejectedClaim, SourceTier
from .normalize import _cached, find_quote, normalize


@dataclass
class EvidenceChunk:
    chunk_id: str
    fr_docnum: str
    text: str
    start_char: int
    section_path: Optional[str] = None
    label: Optional[str] = None
    fr_page_start: Optional[int] = None
    pdf_page_start: Optional[int] = None
    page_spans: Optional[list] = None  # (doc_start, doc_end, fr_page, pdf_page)
    pdf_url: Optional[str] = None
    xml_url: Optional[str] = None
    source_tier: str = "FR_FULL_TEXT"


@dataclass
class DraftClaim:
    text: str
    chunk_id: str
    quote: str
    quotes: Optional[list] = None  # [(chunk_id, quote), ...] two-quote union (V6)


@dataclass
class VerifiedClaim:
    claim: Claim

    @property
    def text(self):
        return self.claim.text

    @property
    def citations(self):
        return self.claim.citations


# ---------------------------------------------------------------- lexicons
STOP = frozenset("""a an the of to in on at by for from with as is are was were be been being this that these
those it its and or but if then than so such which who whom whose what when where while into onto over
under about per via also would could will can do does did has have had their there they them he she
his her we our us you your i me my within upon during between""".split())
NEGATORS = frozenset("""not no never none neither nor except excluding unless without prohibited cannot
nothing nobody""".split())
QUANTIFIERS = ("all", "every", "always", "must", "never", "only", "any", "each", "required",
               "mandatory", "both", "entire")
ANTONYMS_RAW = [
    ("applicable", "inapplicable"), ("required", "optional"), ("mandatory", "optional"),
    ("before", "after"), ("increase", "decrease"), ("include", "exclude"),
    ("permitted", "prohibited"), ("allowed", "prohibited"), ("minimum", "maximum"),
    ("earlier", "later"), ("above", "below"), ("more", "less"), ("more", "fewer"),
    ("greater", "less"), ("higher", "lower"), ("upper", "lower"), ("forward", "aft"),
    ("left", "right"), ("first", "last"), ("initial", "repetitive"), ("over", "under"),
    ("inboard", "outboard"), ("start", "end"), ("open", "closed"), ("mandatory", "recommended"),
    ("required", "recommended"), ("must", "may"), ("shall", "may"),
]
WORDNUMS = {w: str(i) for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen twenty".split())}
MAGNITUDES = ("hundred", "thousand", "million")
MONTHS = {m: i + 1 for i, m in enumerate(
    "january february march april may june july august september october november december".split())}


def lemma(w: str) -> str:
    if w.isdigit():
        return w
    if w.endswith("'s"):
        w = w[:-2]
    if len(w) > 4 and w.endswith("ies"):
        w = w[:-3] + "y"
    elif len(w) > 4 and w.endswith("ied"):
        w = w[:-3] + "y"
    elif len(w) > 5 and w.endswith("ing"):
        w = w[:-3]
    elif len(w) > 4 and w.endswith("ed"):
        w = w[:-2]
    elif len(w) > 4 and w.endswith("ly"):
        w = w[:-2]
    elif len(w) > 4 and w.endswith("es"):
        w = w[:-2]
    elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    if len(w) > 3 and w.endswith("e"):
        w = w[:-1]
    return w


ANTONYMS = [(lemma(a), lemma(b)) for a, b in ANTONYMS_RAW]
_WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


def _words(t: str) -> list:
    return _WORD.findall(t)


def _is_negator(w: str) -> bool:
    return w in NEGATORS or w.endswith("n't")


def content_lemmas(t: str) -> list:
    out = []
    for w in _words(t):
        if _is_negator(w) or w in STOP:
            continue
        out.append(lemma(w))
    return out


# ---------------------------------------------------------------- V4
_MON = "|".join(sorted(MONTHS, key=len, reverse=True))
_MONABBR = r"(?:%s|jan|feb|mar|apr|jun|jul|aug|sept?|oct|nov|dec)" % _MON
_DATE_PATTERNS = [
    re.compile(r"\b(?P<m>%s)\.?\s+(?P<d>\d{1,2})(?:st|nd|rd|th)?,?\s+(?P<y>\d{4})\b" % _MONABBR),
    re.compile(r"\b(?P<d>\d{1,2})(?:st|nd|rd|th)?\s+(?P<m>%s)\.?,?\s+(?P<y>\d{4})\b" % _MONABBR),
    re.compile(r"\b(?P<m>%s)\.?,?\s+(?P<y>\d{4})\b" % _MONABBR),
]
_NUMDATE = re.compile(r"(?<![\w/])\d{1,2}/\d{1,2}/\d{2,4}(?![\w/])")
_NUM = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
_WN = "|".join(WORDNUMS)
_UNIT_RE = re.compile(
    r"(?<![a-z0-9./-])(?P<n>%s|%s)(?:\s*-\s*|\s*)(?:flight\s+)?"
    r"(?P<u>hours?|hrs?|cycles?|landings?|days?|weeks?|months?|years?|minutes?|seconds?|percent|%%|"
    r"inch(?:es)?|feet|foot|ft|miles?|nm|pounds?|lbs?|psi|knots?|degrees?|mm|cm|kg|gallons?|flights?)"
    r"(?![a-z0-9])" % (_NUM, _WN))
_UNIT_ALIAS = {"hr": "hour", "hrs": "hour", "percent": "%", "inches": "inch", "feet": "ft",
               "foot": "ft", "lbs": "lb", "pound": "lb", "pounds": "lb"}
_IDTOK = re.compile(r"[a-z0-9](?:[a-z0-9/\-\.]*[a-z0-9])?")
_FRCIT = re.compile(r"\b\d{1,3}\s+fr\s+\d{1,6}\b")
_CFR = re.compile(r"\b\d{1,2}\s+cfr\s+(?:part\s+|section\s+)?\d+(?:\.\d+)?\b")
_DOCKET = re.compile(r"\b(?:faa|nm|ce|ne|asw|swr|ane)?-?\d{4}-\d{3,5}(?:-[a-z]{1,3})?\b")


def _numstr(s: str) -> str:
    s = s.replace(",", "")
    if s in WORDNUMS:
        return WORDNUMS[s]
    if s.isdigit() and s.startswith("0") and len(s) > 1:
        return s
    v = float(s)
    return str(int(v)) if v == int(v) else repr(v)


def _canon_unit(u: str) -> str:
    u = _UNIT_ALIAS.get(u, u)
    return u.rstrip("s")


def _dates(t: str) -> set:
    found, covered = set(), []
    for pat in _DATE_PATTERNS:
        for m in pat.finditer(t):
            if any(m.start() < ce and m.end() > cs for cs, ce in covered):
                continue
            covered.append((m.start(), m.end()))
            mon = next(v for k, v in MONTHS.items() if k.startswith(m.group("m")[:3]))
            found.add(("date", m.group("y"), mon, m.groupdict().get("d") and int(m.group("d"))))
    for m in _NUMDATE.finditer(t):
        found.add(("numdate", m.group(0)))
    return found


def _idtokens(t: str) -> set:
    toks = set()
    for m in _IDTOK.finditer(t):
        tok = m.group(0)
        if not any(c.isdigit() for c in tok) or re.fullmatch(r"\d+(?:\.\d+)?", tok):
            continue
        toks.add(tok)
        if "/" in tok:
            toks.update(p for p in tok.split("/") if p)
    return toks


def _identifiers(t: str) -> dict:
    """Return {'tok': set, 'unit': set, 'date': set, 'fr': set}."""
    toks = _idtokens(t)
    toks_claim_view = {x for x in toks}
    units = {(_numstr(m.group("n")), _canon_unit(m.group("u"))) for m in _UNIT_RE.finditer(t)}
    fr = {re.sub(r"\s+", " ", m.group(0)) for m in _FRCIT.finditer(t)}
    fr |= {re.sub(r"\s+", " ", m.group(0)) for m in _CFR.finditer(t)}
    return {"tok": toks_claim_view, "unit": units, "date": _dates(t), "fr": fr}


def _model_regex(m: str):
    return re.compile(r"(?<![a-z0-9])%s(?![a-z0-9])(?![-/.][a-z0-9])" % re.escape(m))


def check_identifiers(claim_n: str, quote_n: str, model_index) -> Optional[str]:
    c, q = _identifiers(claim_n), _identifiers(quote_n)
    for tok in sorted(c["tok"] - q["tok"]):
        return tok.upper()
    for n, u in sorted(c["unit"] - q["unit"]):
        return f"{n} {u}"
    for d in sorted(c["date"] - q["date"], key=str):
        return "date:" + "-".join(str(x) for x in d[1:] if x)
    for f in sorted(c["fr"] - q["fr"]):
        return f.upper()
    if model_index:
        for m in sorted(model_index):
            if m in claim_n:
                rx = _model_regex(m)
                if rx.search(claim_n) and not rx.search(quote_n):
                    return m.upper()
    return None


# ---------------------------------------------------------------- V5
def _sentences(t: str) -> list:
    return [s for s in re.split(r"(?<=[.;!?])\s+", t) if s]


def polarity_flags(t: str) -> dict:
    flags: dict = {}
    for sent in _sentences(t):
        toks = _words(sent)
        neg = [i for i, w in enumerate(toks) if _is_negator(w)]
        neg += [i for i, w in enumerate(toks) if w == "than" and i and toks[i - 1] == "other"]
        for i, w in enumerate(toks):
            if _is_negator(w) or w in STOP:
                continue
            isneg = any(abs(k - i) <= 5 and k != i for k in neg)
            flags.setdefault(lemma(w), set()).add(isneg)
    return flags


def check_polarity(claim_n: str, quote_ctx_n: str) -> bool:
    """True if polarity is consistent."""
    cf, qf = polarity_flags(claim_n), polarity_flags(quote_ctx_n)
    for w in cf.keys() & qf.keys():
        if cf[w] != qf[w]:
            return False
    cl, ql = set(cf), set(qf)
    for a, b in ANTONYMS:
        if (a in cl and b not in cl and b in ql and a not in ql) or \
           (b in cl and a not in cl and a in ql and b not in ql):
            return False
    return True


def _sentence_context(text: str, s: int, e: int, cap: int = 400) -> str:
    left = text[max(0, s - cap):s]
    ms = list(re.finditer(r"[.;!?]\s|\n\s*\n", left))
    ls = max(0, s - cap) + (ms[-1].end() if ms else 0)
    if e > 0 and text[e - 1] in ".;!?":
        le = e
    else:
        m = re.search(r"[.;!?](?:\s|$)|\n\s*\n", text[e:e + cap])
        le = e + (m.start() + 1 if m else min(cap, len(text) - e))
    return text[ls:le]


# ---------------------------------------------------------------- V6
# Content words a claim may add without quote support (generic framing only, never technical content).
PARAPHRASE_ALLOW = {lemma(w) for w in (
    "proposal", "proposed", "proposes", "propose", "ad", "nprm", "faa", "document", "notice", "states", "says",
    "specifies", "according", "rule", "operator", "operators", "owner", "part")}


def unsupported_words(claim_n: str, quote_n: str) -> list:
    """Claim content lemmas absent from the quote and not generic framing words (A1: no added facts)."""
    ql = set(content_lemmas(quote_n))
    # Tokens with digits are identifiers/numbers, already checked exactly by V4 and V8.
    return [w for w in content_lemmas(claim_n)
            if w not in ql and w not in PARAPHRASE_ALLOW and w not in WORDNUMS and not any(c.isdigit() for c in w)]


def order_agreement(claim_n: str, quote_n: str):
    """Fraction of adjacent claim content-lemma pairs that keep their relative order in the quote.

    Catches role swaps ("replace X with Y" vs "replace Y with X") that bag-of-words coverage misses.
    Returns None when there are too few pairs to judge."""
    qpos = {}
    words = lambda t: [w for w in content_lemmas(t) if not any(c.isdigit() for c in w)]
    for i, w in enumerate(words(quote_n)):
        qpos.setdefault(w, i)
    seq = [qpos[w] for w in words(claim_n) if w in qpos]
    pairs = [(a, b) for a, b in zip(seq, seq[1:]) if a != b]
    if len(pairs) < 4:
        return None
    return sum(1 for a, b in pairs if a < b) / len(pairs)


def coverage(claim_n: str, quote_n: str):
    cl = content_lemmas(claim_n)
    if not cl:
        return 0.0, None
    ql = set(content_lemmas(quote_n))
    ratio = sum(1 for w in cl if w in ql) / len(cl)
    qwords = set(_words(quote_n))
    for qn in QUANTIFIERS:
        if qn in _words(claim_n) and qn not in qwords:
            return ratio, qn
    return ratio, None


# ---------------------------------------------------------------- V7
_R = r"(?:ad|airworthiness\s+directive|nprm|snprm|proposal|proposed\s+(?:ad|rule)|notice|rule)"
_DOCV = (r"(?:revised|amended|replaced|cancell?ed|rescinded|revoked|withdrawn|superseded|finali[sz]ed|"
         r"adopted|effective|final|terminated|retracted|in\s+effect|in\s+force)")
RESERVED = [
    ("applicability", r"\b(?:appl(?:y|ies|ied)|applying)\s+to\b"),
    ("applicability", r"\b(?:in)?applicab(?:le|ility)\b"),
    ("applicability", r"\b(?:is|are|was|were|be|been)\s+(?:not\s+)?(?:affected|exempt|eligible)\b"),
    ("applicability", r"\baffected\s+(?:airplane|aircraft|helicopter|rotorcraft|product|engine|model|operator|fleet|part|serial)"),
    ("applicability", r"\baffected\s+by\s+this\b"),
    ("applicability", r"\baffects?\s+(?:you|your|my)\b"),
    ("applicability", r"\b(?:your|my)\s+(?:aircraft|airplane|helicopter|rotorcraft|engine|fleet|operation|model|product|serial)"),
    ("applicability", r"\b(?:subject\s+to|covered\s+by|included\s+in)\s+(?:this|the|these)\s+(?:ad|proposed|nprm|applicability)"),
    ("applicability", r"\b(?:does|do|would|will)\s+not\s+apply\b"),
    ("applicability", r"\bcover(?:s|ed|ing)?\b[^.;]{0,60}\b(?:models?|serials?|s/ns?|msns?|airplanes?|aircraft|helicopters?|rotorcraft|engines?|propellers?)\b"),
    ("revision", r"\bsupersed\w*"),
    ("revision", r"\bwithdr(?:aw|ew)\w*"),
    ("revision", r"\brescind\w*"),
    ("revision", r"\brevok\w*"),
    ("revision", r"\b(?:revis|amend|replac|cancel|terminat|retract)\w*\s+(?:the\s+|this\s+|that\s+|an?\s+|existing\s+|proposed\s+)*%s\b" % _R),
    ("revision", r"\b(?:revis|amend|replac|cancel|terminat|retract)\w*\s+(?:ad\s+)?\d{4}-\d{2}-\d{2}"),
    ("revision", r"\b%s\b[^.;]{0,40}\b(?:is|are|was|were|has\s+been|have\s+been|been|be|being|became|become|becomes|remains?)\s+(?:\w+\s+)?%s\b" % (_R, _DOCV)),
    ("finality", r"\bfinal\s+(?:rule|ad|action|decision)\b"),
    ("finality", r"\bfinali[sz]\w*"),
    ("finality", r"\b(?:is|was|became|become|becomes|remains?)\s+(?:now\s+|already\s+)?(?:final|effective)\b"),
    ("status", r"\b(?:currently|presently|at\s+present|as\s+of\s+(?:now|today)|no\s+longer|remains?\s+in\s+(?:effect|force)|"
              r"in\s+(?:effect|force)|still\s+(?:valid|active|effective|required|apply|applies)|"
              r"(?:current|latest|most\s+recent|newest)\s+(?:status|version|revision|amendment|requirement|ad|directive|rule)|"
              r"up[- ]to[- ]date|legally|airworthy|airworthiness\s+status|compliance\s+status|is\s+compliant)\b"),
]
_RESERVED_RX = [(k, re.compile(p)) for k, p in RESERVED]
_SB_REV = re.compile(r"\brevision\s+(?:level\s+)?(?:original|[a-z]|\d+|[a-z0-9.-]*\d[a-z0-9.-]*)\b")


def reserved_topic(claim_n: str) -> Optional[str]:
    t = _SB_REV.sub(" ", claim_n)  # "Service Bulletin X, Revision 04" is a citation, not AD status
    for kind, rx in _RESERVED_RX:
        if rx.search(t):
            return kind
    return None


INJECTION_PATTERNS = [re.compile(p) for p in (
    r"\bignore\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above|earlier|preceding)\b",
    r"\bignore\s+(?:all\s+)?(?:instructions|rules)\b",
    r"\bdisregard\b", r"\bsystem\s+prompt\b", r"\byou\s+are\s+now\b", r"\bnew\s+instructions?\b",
    r"\bfrom\s+now\s+on\b", r"\bforget\s+(?:everything|all|previous)\b", r"\bpretend\s+(?:to\s+be|you)\b",
    r"\bjailbreak\b", r"\breveal\s+(?:your|the)\s+(?:system|prompt|instructions)\b",
    r"</?\s*source\b", r"</?\s*(?:system|assistant|user|instructions?)\s*>", r"\[\s*(?:system|inst)\s*\]",
    r"\bassistant\s*:", r"#{2,}\s*(?:system|instruction)", r"\boverride\s+(?:the\s+)?(?:system|safety|previous)\b",
)]


def contains_injection_markers(text: str) -> bool:
    t = normalize(text)
    return any(p.search(t) for p in INJECTION_PATTERNS)


def wrap_sources(chunks) -> str:
    """Render chunks as <source id="...">escaped text</source>. Source text is only escaped."""
    parts = []
    for c in chunks:
        cid = html.escape(c.chunk_id, quote=True)
        parts.append(f'<source id="{cid}">{html.escape(c.text, quote=False)}</source>')
    return "\n".join(parts)


# ---------------------------------------------------------------- V8
_PLAIN = re.compile(r"(?<![\d])(?P<n>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?![\d])")


def numbers(t: str) -> set:
    t2 = t
    for tok in sorted(_idtokens(t), key=len, reverse=True):
        t2 = re.sub(r"(?<![a-z0-9/.-])%s(?![a-z0-9/-])" % re.escape(tok), " ", t2)
    out = {_numstr(m.group("n")) for m in _PLAIN.finditer(t2)}
    for w in _words(t2):
        if w in WORDNUMS:
            out.add(WORDNUMS[w])
        elif w in MAGNITUDES:
            out.add("mag:" + w)
    return out


# ---------------------------------------------------------------- driver
def _reject(claim: DraftClaim, check: str) -> RejectedClaim:
    return RejectedClaim(text=claim.text, failed_check=check)


def _page(chunk: EvidenceChunk, doc_start: int):
    if chunk.page_spans:
        for ds, de, fr, pdf in chunk.page_spans:
            if ds <= doc_start < de:
                return fr, pdf
    return chunk.fr_page_start, chunk.pdf_page_start


def _line_aligned(text: str, s: int, e: int) -> bool:
    return (s == 0 or text[s - 1] == "\n") and (e == len(text) or text[e] == "\n")


def verify_claim(claim: DraftClaim, retrieved: dict, model_index: Optional[set] = None,
                 judge: Optional[Callable[[str, str], bool]] = None):
    pairs = list(claim.quotes) if claim.quotes else []
    if (claim.chunk_id, claim.quote) not in pairs:
        pairs.insert(0, (claim.chunk_id, claim.quote))
    # V1
    for cid, _ in pairs:
        ch = retrieved.get(cid)
        if ch is None or ch.source_tier != "FR_FULL_TEXT":
            return _reject(claim, "V1_PROVENANCE")
    # V2 / V3
    located = []  # (chunk, local_s, local_e)
    for cid, q in pairs:
        ch = retrieved[cid]
        span = find_quote(ch.text, q, _cached(ch.text))
        if span is None:
            return _reject(claim, "V2_QUOTE_NOT_FOUND")
        located.append((ch, span[0], span[1], q))
    for ch, s, e, q in located:
        qn = normalize(q)
        words = [w for w in qn.split() if any(c.isalnum() for c in w)]
        if not (len(words) >= 6 or (" | " in qn and _line_aligned(ch.text, s, e))):
            return _reject(claim, "V3_QUOTE_TOO_SHORT")
    claim_n = normalize(claim.text)
    quote_n = " ".join(normalize(ch.text[s:e]) for ch, s, e, _ in located)
    ctx_n = " ".join(normalize(_sentence_context(ch.text, s, e)) for ch, s, e, _ in located)
    models = {normalize(m) for m in model_index} if model_index else None
    # V4
    bad = check_identifiers(claim_n, quote_n, models)
    if bad:
        return _reject(claim, f"V4_IDENTIFIER_UNSUPPORTED:{bad}")
    # V5
    if not check_polarity(claim_n, ctx_n):
        return _reject(claim, "V5_POLARITY_MISMATCH")
    # V6
    ratio, qfail = coverage(claim_n, quote_n)
    if qfail:
        return _reject(claim, f"V6_LOW_COVERAGE:quantifier={qfail}")
    if ratio < 0.80:
        return _reject(claim, f"V6_LOW_COVERAGE:{ratio:.2f}")
    extra = unsupported_words(claim_n, quote_n)
    if extra:
        return _reject(claim, f"V6_UNSUPPORTED_WORDS:{','.join(sorted(set(extra))[:5])}")
    order = order_agreement(claim_n, quote_n)
    if order is not None and order < 0.85:
        return _reject(claim, f"V6_ORDER_MISMATCH:{order:.2f}")
    # V7
    if any(contains_injection_markers(ch.text[s:e]) for ch, s, e, _ in located):
        return _reject(claim, "V7_RESERVED_TOPIC:injection")
    kind = reserved_topic(claim_n)
    if kind:
        return _reject(claim, "V7_RESERVED_TOPIC")
    # V8
    qnums = numbers(quote_n)
    for n in sorted(numbers(claim_n) - qnums):
        return _reject(claim, f"V8_NUMBER_MISMATCH:{n}")
    # V9 (can only reject; judge failure fails closed)
    if judge is not None:
        try:
            ok = bool(judge(claim.text, " ... ".join(ch.text[s:e] for ch, s, e, _ in located)))
        except Exception:
            ok = False
        if not ok:
            return _reject(claim, "V9_JUDGE_REJECTED")
    cites, seen = [], set()
    for ch, s, e, _ in located:
        ds, de = ch.start_char + s, ch.start_char + e
        if (ch.fr_docnum, ds, de) in seen:
            continue
        seen.add((ch.fr_docnum, ds, de))
        fr, pdf = _page(ch, ds)
        cites.append(CitationRef(
            citation_id=hashlib.sha256(f"{ch.fr_docnum}|{ds}|{de}".encode()).hexdigest()[:12],
            fr_docnum=ch.fr_docnum, section_path=ch.section_path, label=ch.label,
            fr_page=fr, pdf_page=pdf, quote=ch.text[s:e], start=ds, end=de,
            source_tier=SourceTier.FR_FULL_TEXT, pdf_url=ch.pdf_url, xml_url=ch.xml_url))
    return VerifiedClaim(Claim(text=claim.text, citations=cites))
