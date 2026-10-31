"""Deterministic applicability engine (spec: docs/applicability_spec.md).

Extraction consumes text spans; everything not consumed is residue -> PARTIAL -> UNKNOWN.
No LLM. All literals carry offsets into doc_text.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass, field, asdict
from typing import Optional

from backend.api.schemas import (AircraftConfig, ApplicabilityResult, ApplicabilityValue,
                                 CitationRef, ExplanationStep, SourceTier)
from backend.config import DB_PATH
from backend.rules import serials as S
from backend.rules.models_norm import (expand_shorthand, make_matches, match_model, normalize_model)

PARSER_VERSION = "1.0"

# ----------------------------------------------------------------- dataclasses


@dataclass
class Lit:
    text: str
    start: int
    end: int


@dataclass
class ModelRef:
    value: str
    start: int
    end: int
    normalized: str
    is_series: bool = False
    expanded_from_shorthand: bool = False
    base_span: Optional[tuple] = None
    is_alias: bool = False


@dataclass
class SRange:
    lo: Optional[str]
    hi: Optional[str]
    lo_incl: Optional[bool]
    hi_incl: Optional[bool]
    start: int
    end: int
    text: str


@dataclass
class SerialSpec:
    id_kind: str = "serial"          # serial | line_number | engine_serial
    all_serials: bool = False
    ranges: list = field(default_factory=list)
    serial_list: list = field(default_factory=list)       # [Lit]
    excluded: list = field(default_factory=list)   # [Lit]
    subject: str = "aircraft"        # aircraft | component
    component: Optional[Lit] = None
    spans: list = field(default_factory=list)


@dataclass
class Condition:
    kind: str                        # part_number_installed|modification_incorporated|service_bulletin_accomplished|free_text
    values: list                     # [Lit]
    polarity: str
    start: int
    end: int
    text: str

    @property
    def key(self) -> str:
        return f"{self.kind}:{'|'.join(sorted(_normv(v.text) for v in self.values))}"


def _normv(t: str) -> str:
    return re.sub(r"\s+", " ", t.strip().upper())


@dataclass
class Clause:
    models: list = field(default_factory=list)      # [ModelRef]
    all_models: bool = False
    make: Optional[Lit] = None
    serial: Optional[SerialSpec] = None             # None == NOT_STATED
    conditions: list = field(default_factory=list)
    exclusions: list = field(default_factory=list)
    span: tuple = (0, 0)


@dataclass
class ApplicabilityRule:
    fr_docnum: str
    section_id: Optional[str] = None
    span: tuple = (0, 0)
    doc_class: Optional[str] = None
    product_kind: str = "unknown"
    make: Optional[Lit] = None
    clauses: list = field(default_factory=list)
    global_conditions: list = field(default_factory=list)
    global_exclusions: list = field(default_factory=list)
    external_refs: list = field(default_factory=list)
    benign: list = field(default_factory=list)
    residue: list = field(default_factory=list)
    parse_status: str = "FAILED"
    parser_version: str = PARSER_VERSION
    failure_reason: Optional[str] = None

    def to_dict(self):
        return asdict(self)


# ----------------------------------------------------------------- regexes
NOUN = (r"(?:airplanes?|helicopters?|rotorcraft|(?:turbofan\s+|turboprop\s+|turboshaft\s+)?engines?|"
        r"propellers?|gliders?|aircraft|appliances?|balloons?)")
NOUN_RX = re.compile(r"\b(?:(?P<series>series)\s+)?(?P<noun>" + NOUN + r")\b", re.I)
WORD = r"-?[A-Za-z0-9][A-Za-z0-9.+/]*(?:[-‐-―]\s?[A-Za-z0-9][A-Za-z0-9.+/]*)*"
WORD2 = r"[A-Z0-9][A-Za-z0-9.+/]*(?:[-‐-―]\s?[A-Za-z0-9][A-Za-z0-9.+/]*)*"
MODEL_TOK = re.compile(r"(?P<m>" + WORD + r"(?: " + WORD2 + r"){0,3})")
LIST_SEP = re.compile(r"\s*,\s*(?:and\s+|or\s+)?|\s+(?:and|or)\s+")
TC_PAREN = re.compile(r"\((?:type\s+certificate|TC)\s+previously\s+held\s+by\b(?:[^()]|\([^()]*\))*\)", re.I)
LEADIN = re.compile(r"(?:This\s+(?:proposed\s+)?AD\s+(?:applies\s+to|affects)|the\s+following(?=[\s:])|\(c\)(?=\s)|Applicability\b:?)", re.I)
BENIGN = re.compile(r"(?:(?:are\s+)?(?:certificated|certified)\s+in\s+any\s+category|all\s+certificated\s+models|as\s+applicable)\b", re.I)
SERIAL_INTRO = re.compile(
    r"(?:(?:having|with)\s+)?(?:(?P<all>all|any)\s+)?(?:(?P<k>manufacturer(?:'s)?\s+serial|engine\s+serial|serial|line)\s+numbers?|"
    r"(?P<a>S/Ns?|MSNs?|ESNs?|L/Ns?))(?:\s*\((?:S/Ns?|MSNs?|ESNs?|L/Ns?|line\s+numbers?)\))?", re.I)
SERTOK = re.compile(r"(?:\d{1,3}(?:,\d{3})+|[A-Za-z0-9](?:[A-Za-z0-9/\-]*[A-Za-z0-9])?)(?![A-Za-z0-9])")
EXCL_SER = re.compile(r"\s*,?\s*(?:except(?:\s+for)?|excluding)\s+(?:(?:serial|line)\s+numbers?\s*|S/Ns?\s*)?", re.I)
PNTOK = r"(?=[A-Z0-9\-./]*\d)[A-Z0-9]+(?:[-./][A-Z0-9]+)*"
PN_RX = re.compile(
    r"(?:(?:that\s+are\s+|which\s+are\s+)?(?:now\s+or\s+at\s+any\s+time\s+)?(?:equipped\s+with|having|with)\s+)"
    r"(?P<desc>[^;.]{0,100}?)\b(?:part\s+numbers?(?:\s*\(P/Ns?\))?|P/Ns?)\s*"
    r"(?P<pns>" + PNTOK + r"(?:(?:\s*,\s*(?:or\s+|and\s+)?|\s+(?:or|and)\s+)" + PNTOK + r")*)"
    r"(?:\s*,)?(?:\s+(?:installed|incorporated))?", re.S)
SB_RX = re.compile(
    r"(?P<excl>(?:excluding|except(?:\s+for)?)\s+(?:those\s+)?(?:airplanes|helicopters|aircraft|engines|propellers)\s+)?"
    r"(?:on\s+which|that\s+have|in\s+which)\s+(?P<what>[^;]{3,200}?)\s+(?:has|have)\s+(?P<neg>not\s+)?been\s+"
    r"(?:incorporated|accomplished|done|performed|installed|embodied|completed)\b", re.I)
EXT_RX = re.compile(r"(?:as\s+)?(?:identified|listed|specified|defined|described)\s+(?:in|by)\s+"
                    r"(?!paragraphs?\s*\(c\))(?!table)(?P<doc>[^;]+)", re.I)
INTREF_RX = re.compile(r"(?:as\s+)?(?:identified|listed|specified|described)\s+in\s+paragraphs?\s+\(c\)[^;:]*?of\s+this\s+AD", re.I)
FREE_RX = re.compile(r"(?P<kw>(?:(?:that|which)\s+(?:are\s+)?)?(?:now\s+or\s+at\s+any\s+time\s+)?equipped\s+with)\s+(?P<body>[^;]+)", re.I)
FREE_BAD = re.compile(r"\b(identified|listed|specified|defined|shown|table|paragraph|bulletin|dated|AD)\b|\d{4}-\d", re.I)
NOTE_RX = re.compile(r"Note\s+1:\s*\n+This\s+AD\s+applies\s+to\s+each\s+\w+\s+identified\s+in\s+the\s+preceding\s+applicability\s+"
                     r"provision,\s+regardless\s+of\s+whether.*?specific\s+proposed\s+actions\s+to\s+address\s+it\.", re.S)
SMALL = {"the", "of", "and", "de", "du", "van", "von", "la", "di", "plc", "a"}
STOP = {"and", "or", "the"}
KIND_MAP = {"serial": "serial", "manufacturer serial": "serial", "msn": "serial", "s/n": "serial", "line": "line_number",
            "l/n": "line_number", "engine serial": "engine_serial", "esn": "engine_serial"}


def _kind(m) -> str:
    k = (m.group("k") or m.group("a") or "").lower().replace("'s", "")
    k = re.sub(r"\s+", " ", k).rstrip("s")
    return KIND_MAP.get(k, "other")


# ----------------------------------------------------------------- parser
class _Group:
    def __init__(self):
        self.make = None
        self.models = []
        self.product = "unknown"
        self.all_flag = False
        self.serial = None
        self.conds = []
        self.excls = []
        self.quals = []        # (start,end) of qualifier spans
        self.last_pn = None
        self.start = 0


class _Seg:
    def __init__(self, intro=False):
        self.intro = intro
        self.groups = []
        self.pre = _Group()


class _P:
    def __init__(self, T, ps, pe):
        self.T, self.ps, self.pe = T, ps, pe
        self.cons = []
        self.forced = []
        self.benign = []
        self.ext = []
        self.product = "unknown"
        self.has_items = False

    def eat(self, a, b):
        self.cons.append((a, b))

    def lit(self, a, b):
        return Lit(self.T[a:b], a, b)

    # ---- make validation
    def make_ok(self, a, b):
        txt = self.T[a:b]
        txt2 = TC_PAREN.sub(" ", txt)
        if not txt2.strip():
            return True
        if len(txt) > 160 or re.search(r"[;:]|\bModels?\b", txt2, re.I):
            return False
        txt3 = re.sub(r"\([^()]*\)", " ", txt2)
        for w in re.split(r"[\s,]+", txt3.strip()):
            if not w:
                continue
            if w.lower() in SMALL:
                continue
            if not re.match(r"^[A-Z0-9][A-Za-z0-9.&'’\-/]*$", w) and w != "&":
                return False
        return True

    # ---- model list
    def parse_models(self, a, b, is_series, prev_full=None):
        """Tokenize T[a:b] as model list. Returns list[ModelRef] or None."""
        T = self.T
        out = []
        i = a
        prev = prev_full
        while True:
            m = MODEL_TOK.match(T, i, b)
            if not m:
                return None
            tok = m.group("m")
            if re.match(r"(?i)models?\b", tok):
                return None
            s0, e0 = m.start("m"), m.end("m")
            if tok.startswith("-"):
                exp = expand_shorthand(prev, tok) if prev else None
                if exp is None:
                    return None
                out.append(ModelRef(tok, s0, e0, exp, is_series, True, None))
            else:
                out.append(ModelRef(tok, s0, e0, normalize_model(tok), is_series))
                prev = normalize_model(tok)
            if tok.startswith("-") and out[-1].expanded_from_shorthand:
                out[-1].base_span = None
            i = e0
            pm = re.compile(r"\s*\(([^()]*)\)").match(T, i, b)
            if pm:
                inner = self.parse_models(pm.start(1), pm.end(1), is_series, None)
                if inner is None or any(r.expanded_from_shorthand for r in inner):
                    return None
                for r in inner:
                    r.is_alias = True
                out.extend(inner)
                i = pm.end()
            sep = LIST_SEP.match(T, i, b)
            if sep and sep.end() < b:
                i = sep.end()
                continue
            if T[i:b].strip():
                return None
            return out

    def m_group(self, seg, p, e, bare=False):
        T = self.T
        q = p
        allf = False
        m = re.compile(r"all\s+", re.I).match(T, q, e)
        if m:
            allf, q = True, m.end()
        m = re.compile(r"the\s+", re.I).match(T, q, e)
        if m:
            q = m.end()
        kw = re.compile(r"\bModels?\b", re.I).search(T, q, e)
        nm = NOUN_RX.search(T, q, e)
        if bare:
            if not seg.groups:
                return None
            k = q - 1
            while k > self.ps and T[k - 1].isspace():
                k -= 1
            if T[k - 1:k] != ";":
                return None
            nm = NOUN_RX.search(T, q, e)
            if not nm:
                return None
            ms = parse_ms = q
            models = self.parse_models(q, nm.start(), bool(nm.group("series")), self._prev_full(seg))
            if not models:
                return None
            g = _Group()
            g.start = p
            g.models, g.product = models, nm.group("noun").lower()
            seg.groups.append(g)
            self.eat(p, nm.end())
            self.product = g.product
            return nm.end()
        if kw:
            if not self.make_ok(q, kw.start()):
                return None
            ls = kw.end()
            while ls < e and T[ls].isspace():
                ls += 1
            nm2 = NOUN_RX.search(T, ls, e)
            if not nm2:
                return None
            models = []
            if nm2.start() > ls:
                models = self.parse_models(ls, nm2.start(), bool(nm2.group("series")), None)
                if models is None:
                    return None
                models = models
            g = _Group()
            g.start = p
            g.all_flag = allf
            g.models = models
            g.product = nm2.group("noun").lower()
            mk = T[q:kw.start()].strip()
            if TC_PAREN.sub("", mk).strip():
                a0 = q
                while T[a0].isspace():
                    a0 += 1
                g.make = self.lit(a0, kw.start()).__class__(TC_PAREN.sub("", T[a0:kw.start()]).strip(), a0, a0 + len(T[a0:kw.start()].rstrip()))
                g.make = self._make_lit(a0, kw.start())
            seg.groups.append(g)
            self.eat(p, nm2.end())
            self.product = g.product
            return nm2.end()
        # make-only / intro group: "Bombardier, Inc., airplanes" or "all Airbus Helicopters,"
        if nm and T[nm.start()].islower() and (seg.intro or allf):
            if self.make_ok(q, nm.start()) and not nm.group("series"):
                g = _Group()
                g.start = p
                g.all_flag = allf
                g.product = nm.group("noun").lower()
                if self.T[q:nm.start()].strip(" ,"):
                    g.make = self._make_lit(q, nm.start())
                seg.groups.append(g)
                self.eat(p, nm.end())
                self.product = g.product
                return nm.end()
        if allf and seg.intro:
            m2 = re.compile(r"([^,;:]+?)(?=\s*,\s*(?:certificated|certified|identified))").match(T, q, e)
            if m2 and self.make_ok(m2.start(1), m2.end(1)):
                g = _Group()
                g.start = p
                g.all_flag = True
                g.make = self._make_lit(q, m2.end(1))
                seg.groups.append(g)
                self.eat(p, m2.end(1))
                return m2.end(1)
        return None

    def _make_lit(self, a, b):
        T = self.T
        while a < b and (T[a].isspace() or T[a] == ","):
            a += 1
        while b > a and (T[b - 1].isspace() or T[b - 1] == ","):
            b -= 1
        return self.lit(a, b)

    def _prev_full(self, seg):
        for g in reversed(seg.groups):
            for r in reversed(g.models):
                if not r.is_alias:
                    return r.normalized
        return None

    # ---- serials
    def _ser_item(self, p, e, kind):
        T = self.T
        m = re.compile(r"up\s+to\s+and\s+including\s+", re.I).match(T, p, e)
        if m:
            t = SERTOK.match(T, m.end(), e)
            if t and re.search(r"\d", t.group()):
                return (SRange(None, t.group(), None, True, p, t.end(), T[p:t.end()]), t.end())
            return None
        m = re.compile(r"(?:up\s+to|prior\s+to|before)\s+", re.I).match(T, p, e)
        if m:
            t = SERTOK.match(T, m.end(), e)
            if t and re.search(r"\d", t.group()):
                return (SRange(None, t.group(), None, None, p, t.end(), T[p:t.end()]), t.end())
            return None
        t = SERTOK.match(T, p, e)
        if not t or not re.search(r"\d", t.group()):
            return None
        a = t.group()
        m = re.compile(r"\s+and\s+(?:subsequent|on)\b", re.I).match(T, t.end(), e)
        if m:
            return (SRange(a, None, True, None, p, m.end(), T[p:m.end()]), m.end())
        m = re.compile(r"\s+(through|thru|to)\s+", re.I).match(T, t.end(), e)
        if m:
            t2 = SERTOK.match(T, m.end(), e)
            if t2 and re.search(r"\d", t2.group()):
                inc = re.compile(r"\s+inclusive\b", re.I).match(T, t2.end(), e)
                end = inc.end() if inc else t2.end()
                word = m.group(1).lower()
                hi_incl = True if (word != "to" or inc) else None
                x, y = S.parse_serial(a), S.parse_serial(t2.group())
                if x.number is not None and y.number is not None and x.prefix == y.prefix \
                        and x.suffix == y.suffix and x.number > y.number:
                    return None
                return (SRange(a, t2.group(), True, hi_incl, p, end, T[p:end]), end)
            return None
        dd = re.fullmatch(r"(\d+)-(\d+)", a)
        if dd:
            inc = re.compile(r"\s+inclusive\b", re.I).match(T, t.end(), e)
            if inc and len(dd.group(1)) == len(dd.group(2)) and int(dd.group(1)) <= int(dd.group(2)):
                return (SRange(dd.group(1), dd.group(2), True, True, p, inc.end(), T[p:inc.end()]), inc.end())
            return None
        return (self.lit(p, t.end()), t.end())

    def m_serial(self, seg, p, e):
        T = self.T
        m = SERIAL_INTRO.match(T, p, e)
        if not m:
            return None
        kind = _kind(m)
        tgt = seg.groups[-1] if seg.groups else seg.pre
        spec = SerialSpec(id_kind=kind)
        q = m.end()
        if m.group("all"):
            spec.all_serials = True
        else:
            q2 = re.compile(r"\s*:?\s*(?:from\s+)?", re.I).match(T, q, e).end()
            it = self._ser_item(q2, e, kind)
            if not it:
                return None
            q = q2
            while it:
                obj, end = it
                (spec.serial_list if isinstance(obj, Lit) else spec.ranges).append(obj)
                q = end
                sep = re.compile(r"\s*,\s*(?:and\s+)?|\s+and\s+|\s+or\s+").match(T, q, e)
                if not sep:
                    break
                q3 = sep.end()
                im = SERIAL_INTRO.match(T, q3, e)
                if im and _kind(im) == kind and not im.group("all"):
                    q3 = re.compile(r"\s*:?\s*(?:from\s+)?").match(T, im.end(), e).end()
                it2 = self._ser_item(q3, e, kind)
                if not it2:
                    break
                it = it2
                q = q  # separator is trivia
            # exclusions
            em = EXCL_SER.match(T, q, e)
            if em:
                q4 = em.end()
                ex = []
                while True:
                    t = SERTOK.match(T, q4, e)
                    if not t or not re.search(r"\d", t.group()):
                        break
                    ex.append(self.lit(q4, t.end()))
                    q4 = t.end()
                    sep = re.compile(r"\s*,\s*(?:and\s+)?|\s+and\s+").match(T, q4, e)
                    if not sep or not SERTOK.match(T, sep.end(), e):
                        break
                    q4 = sep.end()
                if ex:
                    spec.excluded = ex
                    q = q4
        if tgt.serial is not None:
            self.forced.append((p, q))
            return q
        if tgt.last_pn is not None and not spec.all_serials:
            spec.subject, spec.component = "component", tgt.last_pn
        tgt.serial = spec
        tgt.quals.append((p, q, "all" if spec.all_serials else "serial"))
        self.eat(p, q)
        return q

    # ---- conditions
    def m_cond(self, seg, p, e):
        T = self.T
        tgt = seg.groups[-1] if seg.groups else seg.pre
        m = SB_RX.match(T, p, e)
        if m and re.search(r"\d", m.group("what")):
            what = m.group("what")
            kind = "modification_incorporated" if re.search(r"\b(modification|mod\b|STC|amendment)", what, re.I) \
                else "service_bulletin_accomplished"
            ids = [self.lit(m.start("what") + x.start(), m.start("what") + x.end())
                   for x in re.finditer(r"(?=[A-Za-z0-9\-]*\d)[A-Za-z0-9]+(?:-[A-Za-z0-9]+)+|\b\d{3,}\b", what)]
            if not ids:
                return None
            pol = "-" if m.group("neg") else "+"
            c = Condition(kind, ids, pol, p, m.end(), T[p:m.end()])
            (tgt.excls if m.group("excl") else tgt.conds).append(c)
            tgt.quals.append((p, m.end(), "cond"))
            self.eat(p, m.end())
            return m.end()
        m = PN_RX.match(T, p, e)
        if m and not re.search(r"\b(with|modified|STC|Supplemental|installed|equipped|having)\b|[()]", m.group("desc"), re.I) \
                and m.group("desc").count(",") <= 1:
            vals = [self.lit(m.start("pns") + x.start(), m.start("pns") + x.end())
                    for x in re.finditer(PNTOK, m.group("pns"))]
            c = Condition("part_number_installed", vals, "+", p, m.end(), T[p:m.end()])
            tgt.conds.append(c)
            tgt.last_pn = self.lit(p, m.end())
            tgt.quals.append((p, m.end(), "cond"))
            self.eat(p, m.end())
            return m.end()
        m = FREE_RX.match(T, p, e)
        if m:
            body = m.group("body")
            # cut at first comma-terminator
            cut = re.search(r",\s*(?:certificated|certified|serial|all\s+serial|line|as\s+(?:identified|listed))|\s+(?:certificated|certified)\s+in\s+any", body, re.I)
            if cut:
                body = body[:cut.start()]
            body = body.rstrip(" .,")
            if body and len(body) < 160 and not FREE_BAD.search(body) and not re.search(r"\b(not|or|and)\b", body, re.I):
                bs = m.start("body")
                c = Condition("free_text", [self.lit(bs, bs + len(body))], "+", p, bs + len(body), T[p:bs + len(body)])
                tgt.conds.append(c)
                tgt.quals.append((p, c.end, "cond"))
                self.eat(p, c.end)
                return c.end
        return None

    def m_ext(self, seg, p, e):
        T = self.T
        if self.has_items:
            m = INTREF_RX.match(T, p, e)
            if m:
                self.benign.append(self.lit(p, m.end()))
                self.eat(p, m.end())
                return m.end()
        m = EXT_RX.match(T, p, e)
        if m:
            end = m.end()
            while end > p and T[end - 1] in " .\n,":
                end -= 1
            self.ext.append(self.lit(p, end))
            self.eat(p, end)
            return end
        return None

    def m_benign(self, p, e):
        T = self.T
        for rx in (LEADIN, BENIGN, TC_PAREN):
            m = rx.match(T, p, e)
            if m:
                self.benign.append(self.lit(p, m.end()))
                self.eat(p, m.end())
                return m.end()
        return None

    def parse_segment(self, s, e, intro=False):
        T = self.T
        seg = _Seg(intro)
        p = s
        skip = re.compile(r"[\s,;:]+")
        while p < e:
            m = skip.match(T, p, e)
            if m:
                p = m.end()
                continue
            q = (self.m_benign(p, e) or self.m_group(seg, p, e) or self.m_group(seg, p, e, bare=True)
                 or self.m_serial(seg, p, e) or self.m_cond(seg, p, e) or self.m_ext(seg, p, e))
            if q:
                p = q
                continue
            w = re.compile(r"\S+").match(T, p, e)
            p = w.end()
        return seg

    def build_clauses(self, seg, allow_all_models=False):
        """Return clauses from a segment (forced residue on ambiguous qualifiers)."""
        clauses = []
        groups = [g for g in seg.groups]
        multi = len(groups) >= 2
        pre = seg.pre
        for g in groups:
            quals = g.quals
            if multi:
                for (a, b, k) in quals:
                    if k != "all":
                        self.forced.append((a, b))
                g_serial = g.serial if (g.serial and g.serial.all_serials) else None
                g_conds, g_ex = [], []
            else:
                g_serial, g_conds, g_ex = g.serial, g.conds, g.excls
            c = Clause(models=g.models, make=g.make, span=(g.start, g.start))
            if not g.models:
                if g.all_flag and g.make and allow_all_models and len(groups) == 1:
                    c.all_models = True
                else:
                    self.forced.append((g.start, g.start + 5))
                    continue
            c.serial = g_serial or pre.serial
            c.conditions = list(g_conds) + list(pre.conds)
            c.exclusions = list(g_ex) + list(pre.excls)
            clauses.append(c)
        return clauses


# ----------------------------------------------------------------- paragraph extraction
def _residue(T, ps, pe, cons, forced):
    mask = [False] * (pe - ps)
    for a, b in cons:
        for i in range(max(a, ps), min(b, pe)):
            mask[i - ps] = True
    for a, b in forced:
        for i in range(max(a, ps), min(b, pe)):
            mask[i - ps] = False
    runs = []
    i = 0
    n = pe - ps
    while i < n:
        if mask[i]:
            i += 1
            continue
        j = i
        while j < n and not mask[j]:
            j += 1
        txt = T[ps + i:ps + j]
        toks = [t for t in re.split(r"[\s,;:.|()\-—]+", txt) if t and t.lower() not in STOP]
        if toks:
            a = ps + i + (len(txt) - len(txt.lstrip(" \n,;:.|")))
            b = ps + j - (len(txt) - len(txt.rstrip(" \n,;:.|")))
            runs.append(Lit(T[a:b], a, b))
        i = j
    return runs


def extract_rule_from_text(T: str, ps: int, pe: int, fr_docnum: str, doc_class=None, section_id=None,
                           has_table_hint=False) -> ApplicabilityRule:
    rule = ApplicabilityRule(fr_docnum=fr_docnum, section_id=section_id, span=(ps, pe), doc_class=doc_class)
    P = _P(T, ps, pe)
    # trailing heading junk
    body = T[ps:pe]
    last = body.rfind("\n\n")
    if last >= 0:
        tail = body[last:].strip()
        if tail and len(tail.split()) <= 8 and not re.search(r"[.;:|]$", tail) and not tail.startswith(("(", "Note", "Table")) \
                and " | " not in tail:
            pe = ps + last
            P.pe = pe
            rule.span = (ps, pe)
    # standard Note boilerplate
    nm = NOTE_RX.search(T, ps, pe)
    pe_main = pe
    if nm:
        P.benign.append(P.lit(nm.start(), nm.end()))
        P.eat(nm.start(), nm.end())
        pe_main = nm.start()
    # tables: unsupported in v1 -> residue (never consumed)
    # items
    item_rx = re.compile(r"(?m)^[ \t]*\((\d+)\)[ \t]")
    ms = [m for m in item_rx.finditer(T, ps, pe_main)]
    nums = [int(m.group(1)) for m in ms]
    items = []
    if ms and nums == list(range(nums[0], nums[0] + len(nums))) and nums[0] == 1:
        for i, m in enumerate(ms):
            items.append((m.start(1) - 1, m.end(), ms[i + 1].start() if i + 1 < len(ms) else pe_main))
    intro_end = items[0][0] if items else pe_main
    P.has_items = bool(items)
    clauses = []
    seg0 = P.parse_segment(ps, intro_end, intro=bool(items))
    conj = bool(items) and re.search(r"\bthat(?:\s+are)?\s*:\s*$", T[ps:intro_end].rstrip())
    if items:
        if conj:
            pass  # conjunctive items stay residue (v1): never consumed
        else:
            # intro qualifiers are global
            if any(g.models for g in seg0.groups):
                for g in seg0.groups:
                    if g.models:
                        P.forced.append((g.start, g.start + 5))
            for g in seg0.groups + [seg0.pre]:
                if g.serial and not g.serial.all_serials:
                    for (a, b, k) in g.quals:
                        if k == "serial":
                            P.forced.append((a, b))
                rule.global_conditions += g.conds
                rule.global_exclusions += g.excls
            introgroups = [g for g in seg0.groups if g.make]
            intro_make = introgroups[0].make if introgroups else None
            for (ls, le, ie) in items:
                P.eat(ls, le)
                sg = P.parse_segment(le, ie)
                cl = P.build_clauses(sg)
                for c in cl:
                    if c.make is None:
                        c.make = intro_make
                clauses += cl
                if not cl:
                    pass
    else:
        clauses = P.build_clauses(seg0, allow_all_models=True)
    rule.clauses = clauses
    rule.make = next((c.make for c in clauses if c.make), None)
    rule.external_refs = P.ext
    rule.benign = P.benign
    rule.product_kind = P.product if P.product in ("airplane", "helicopter", "rotorcraft", "engine", "propeller", "glider") else (
        {"airplanes": "airplane", "helicopters": "helicopter", "engines": "engine", "propellers": "propeller", "gliders": "glider",
         "airplane": "airplane", "helicopter": "helicopter", "engine": "engine"}.get(P.product, "unknown"))
    rule.residue = _residue(T, ps, pe, P.cons, P.forced)
    if not clauses:
        rule.parse_status, rule.failure_reason = "FAILED", "NO_CLAUSES"
    elif rule.residue:
        rule.parse_status = "PARTIAL"
    else:
        rule.parse_status = "FULL"
    return rule


# ----------------------------------------------------------------- DB access
def _connect():
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=30)


def _retry(fn, tries=5):
    import time
    for i in range(tries):
        try:
            return fn()
        except sqlite3.OperationalError:
            if i == tries - 1:
                raise
            time.sleep(0.5)


def load_doc(fr_docnum: str):
    def go():
        c = _connect()
        try:
            t = c.execute("select text from doc_text where fr_docnum=?", (fr_docnum,)).fetchone()
            d = c.execute("select doc_class, publication_date, pdf_url, xml_url from documents where fr_docnum=?", (fr_docnum,)).fetchone()
            secs = c.execute("select id,seq,section_path,kind,label,heading,top_path,start_char,end_char,fr_page_start,fr_page_end,"
                             "pdf_page_start,pdf_page_end from sections where fr_docnum=? order by seq", (fr_docnum,)).fetchall()
            return t[0] if t else None, d, secs
        finally:
            c.close()
    return _retry(go)


def locate_paragraph(secs):
    cands = [s for s in secs if s[3] == "proposed_ad_paragraph" and s[5] and re.fullmatch(r"\s*Applicability\s*", s[5], re.I)]
    if not cands:
        return None
    pick = next((s for s in cands if s[4] == "(c)"), cands[0])
    start, end = pick[7], pick[8]
    if pick[6]:
        i = secs.index(pick)
        for s in secs[i + 1:]:
            if s[3] == "proposed_ad_paragraph" and s[6] == pick[6] and s[7] >= end:
                end = s[8]
            else:
                break
    return pick, start, end


def extract_rule(fr_docnum: str) -> ApplicabilityRule:
    T, d, secs = load_doc(fr_docnum)
    doc_class = d[0] if d else None
    if T is None:
        r = ApplicabilityRule(fr_docnum=fr_docnum, doc_class=doc_class, failure_reason="NO_DOC_TEXT")
        return r
    loc = locate_paragraph(secs)
    if not loc:
        return ApplicabilityRule(fr_docnum=fr_docnum, doc_class=doc_class, failure_reason="NO_APPLICABILITY_PARAGRAPH")
    pick, a, b = loc
    return extract_rule_from_text(T, a, b, fr_docnum, doc_class, pick[0])


def all_lits(rule: ApplicabilityRule):
    """Yield every (text,start,end) literal for the round-trip test."""
    def conds(cs):
        for c in cs:
            yield (c.text, c.start, c.end)
            for v in c.values:
                yield (v.text, v.start, v.end)
    for l in [rule.make] + rule.external_refs + rule.benign + rule.residue:
        if l:
            yield (l.text, l.start, l.end)
    yield from conds(rule.global_conditions)
    yield from conds(rule.global_exclusions)
    for c in rule.clauses:
        if c.make:
            yield (c.make.text, c.make.start, c.make.end)
        for m in c.models:
            yield (m.value, m.start, m.end)
        yield from conds(c.conditions)
        yield from conds(c.exclusions)
        sp = c.serial
        if sp:
            for l in sp.serial_list + sp.excluded + ([sp.component] if sp.component else []):
                yield (l.text, l.start, l.end)
            for r in sp.ranges:
                yield (r.text, r.start, r.end)


# ----------------------------------------------------------------- evaluation
@dataclass
class Step:
    step: str
    outcome: str      # TRUE FALSE UNKNOWN INFO
    detail: str
    evidence: list = field(default_factory=list)   # [Lit]


@dataclass
class Evaluation:
    value: str                       # T F U
    steps: list
    missing: list
    warnings: list
    reason: str = ""
    reason_code: str = ""


def _and(a, b):
    if a == "F" or b == "F":
        return "F"
    if a == "U" or b == "U":
        return "U"
    return "T"


def _not(a):
    return {"T": "F", "F": "T", "U": "U"}[a]


def _cond_label(c: Condition) -> str:
    return f"{c.key} ({c.text.strip()[:80]})"


def _eval_cond(c, facts, miss):
    k = c.key
    if k not in facts:
        miss.append(_cond_label(c))
        return "U"
    v = bool(facts[k])
    return "T" if (v if c.polarity == "+" else not v) else "F"


def _eval_serial(spec: SerialSpec, cfg_serial, steps, miss, ev_cl):
    if spec.all_serials:
        steps.append(Step("serial", "TRUE", "Rule applies to all serial numbers.", ev_cl))
        return "T"
    if spec.subject == "component":
        steps.append(Step("serial", "UNKNOWN", "SERIAL_SUBJECT_IS_COMPONENT: serial limits refer to a component, not the aircraft.",
                          [spec.component] if spec.component else []))
        miss.append("component_serial")
        return "U"
    ev = [Lit(r.text, r.start, r.end) for r in spec.ranges] + list(spec.serial_list)
    if spec.id_kind != "serial":
        steps.append(Step("serial", "UNKNOWN", f"SERIAL_KIND_UNSUPPORTED: limits are by {spec.id_kind}, which this engine does not compare.", ev))
        miss.append(spec.id_kind)
        return "U"
    if cfg_serial is None:
        steps.append(Step("serial", "UNKNOWN", "Serial number not provided.", ev))
        miss.append("serial")
        return "U"
    # excluded
    ex = "F"
    for l in spec.excluded:
        r = S.equal_elem(cfg_serial, l.text)
        if r == "T":
            steps.append(Step("serial", "FALSE", f"Serial {cfg_serial} is explicitly excluded.", [l]))
            return "F"
        if r == "U":
            ex = "U"
    sel = "F"
    reasons = []
    for r in spec.ranges:
        v, why = S.in_range(cfg_serial, r.lo, r.hi, r.lo_incl, r.hi_incl)
        reasons.append((v, why, r))
        sel = "T" if v == "T" or sel == "T" else ("U" if v == "U" or sel == "U" else "F")
    for l in spec.serial_list:
        v = S.equal_elem(cfg_serial, l.text)
        reasons.append((v, "LIST", l))
        sel = "T" if v == "T" or sel == "T" else ("U" if v == "U" or sel == "U" else "F")
    res = _and(sel, _not(ex))
    ev_hit = [Lit(x.text, x.start, x.end) for (v, w, x) in reasons if v == sel] or ev
    why = ", ".join(sorted({w for (v, w, x) in reasons if v == sel}))
    steps.append(Step("serial", {"T": "TRUE", "F": "FALSE", "U": "UNKNOWN"}[res],
                      f"Serial {cfg_serial}: {why or 'excluded-list not comparable'}.", ev_hit))
    return res


def evaluate(rule: ApplicabilityRule, cfg: AircraftConfig, revision_overlay: Optional[list] = None) -> Evaluation:
    warnings = list(revision_overlay or [])
    steps, miss = [], []

    def done(v, reason, code):
        return Evaluation(v, steps, list(dict.fromkeys(miss)), warnings, reason, code)
    if rule.parse_status != "FULL":
        ev = rule.residue[:3]
        q = "; ".join(f'"{r.text[:80]}"' for r in ev)
        steps.append(Step("parse", "UNKNOWN", f"RULE_NOT_FULLY_PARSED ({rule.parse_status}). Unparsed text: {q}" if q else
                          f"RULE_NOT_FULLY_PARSED ({rule.parse_status}): {rule.failure_reason}", ev))
        return done("U", f"the applicability paragraph could not be fully parsed ({rule.failure_reason or 'unparsed text'})", "RULE_NOT_FULLY_PARSED")
    if not cfg.model or not cfg.model.strip():
        miss.append("model")
        steps.append(Step("model", "UNKNOWN", "No aircraft model provided.", []))
        return done("U", "no aircraft model was provided", "MODEL_REQUIRED")
    cm = normalize_model(cfg.model)
    clause_vals = []
    for ci, cl in enumerate(rule.clauses):
        cm_miss = []
        # model
        if cl.all_models:
            v = "T" if (cfg.make and cl.make and make_matches(cfg.make, cl.make.text)) else "U"
            steps.append(Step("model", {"T": "TRUE", "U": "UNKNOWN"}[v], "Rule covers all models of the make.", [cl.make] if cl.make else []))
            if v == "U":
                cm_miss.append("make")
            mv = v
        else:
            mv = "F"
            hit = None
            for r in cl.models:
                x = match_model(cm, r.normalized, r.is_series)
                if x == "T":
                    mv, hit = "T", r
                    break
                if x == "U" and mv != "T":
                    mv, hit = "U", r
            ev = [Lit(r.value, r.start, r.end) for r in cl.models[:12]]
            if mv == "T":
                ev = [Lit(hit.value, hit.start, hit.end)]
                if hit.expanded_from_shorthand:
                    warnings.append(f"Model {hit.value.strip()} was expanded from shorthand in the source; verify.")
                steps.append(Step("model", "TRUE", f"Model {cfg.model} equals listed model {hit.normalized}.", ev))
            elif mv == "U":
                ev = [Lit(hit.value, hit.start, hit.end)]
                steps.append(Step("model", "UNKNOWN", f"Model {cfg.model} is related to listed {hit.normalized} (series/variant); membership cannot be verified from text.", ev))
            else:
                steps.append(Step("model", "FALSE", f"Model {cfg.model} is not among the listed models.", ev))
        if mv == "F":
            clause_vals.append(("F", [], ci))
            continue
        # serial
        if cl.serial is None:
            sv = "T"
            steps.append(Step("serial", "INFO", "No serial restriction stated for this clause.", []))
        else:
            sv = _eval_serial(cl.serial, cfg.serial, steps, cm_miss, [])
        v = _and(mv, sv)
        for c in cl.conditions:
            r = _eval_cond(c, cfg.facts, cm_miss)
            steps.append(Step("condition", {"T": "TRUE", "F": "FALSE", "U": "UNKNOWN"}[r], f"Condition {_cond_label(c)} polarity {c.polarity}.", [Lit(c.text, c.start, c.end)]))
            v = _and(v, r)
        for c in cl.exclusions:
            r = _eval_cond(c, cfg.facts, cm_miss)
            steps.append(Step("exclusion", {"T": "FALSE", "F": "TRUE", "U": "UNKNOWN"}[r], f"Exclusion {_cond_label(c)}.", [Lit(c.text, c.start, c.end)]))
            v = _and(v, _not(r))
        clause_vals.append((v, cm_miss, ci))
    rv = "F"
    for v, _, _ in clause_vals:
        rv = "T" if (v == "T" or rv == "T") else ("U" if (v == "U" or rv == "U") else "F")
    gm = []
    for c in rule.global_conditions:
        rv = _and(rv, _eval_cond(c, cfg.facts, gm))
    for c in rule.global_exclusions:
        rv = _and(rv, _not(_eval_cond(c, cfg.facts, gm)))
    # Opus review decision: "as identified in <external document>" can only NARROW the models/serials the
    # paragraph itself lists, so it is an unknown AND-condition (Kleene): a definite FALSE from the paragraph
    # stays FALSE; anything else becomes UNKNOWN until the external document is checked.
    ext_code = ""
    if rule.external_refs and rv != "F":
        rv = "U"
        ext_code = "EXTERNAL_DOCUMENT_REQUIRED"
        miss.append("external document: " + rule.external_refs[0].text[:120])
        steps.append(Step("external", "UNKNOWN", "EXTERNAL_DOCUMENT_REQUIRED: scope depends on " + rule.external_refs[0].text[:120],
                          rule.external_refs))
    elif rule.external_refs:
        steps.append(Step("external", "INFO", "Paragraph also references " + rule.external_refs[0].text[:120]
                          + "; it can only narrow scope, so the definite exclusion above stands.", rule.external_refs))
    if rv == "U":
        for v, m, _ in clause_vals:
            if v == "U":
                miss.extend(m)
        miss.extend(gm)
    steps.append(Step("rule", {"T": "TRUE", "F": "FALSE", "U": "UNKNOWN"}[rv], "Combined result over clauses and global conditions.", []))
    reason = _reason(steps)
    return done(rv, reason, ext_code)


def _reason(steps):
    keep = [s for s in steps if s.step in ("model", "serial", "condition", "exclusion") and s.outcome != "INFO"]
    sel = [s for s in keep if s.outcome in ("UNKNOWN", "FALSE")] or keep[:3]
    out = []
    for s in sel[:3]:
        q = f' [“{s.evidence[0].text[:80]}”]' if s.evidence else ""
        out.append(s.detail.rstrip(".") + q)
    return "; ".join(out)


# ----------------------------------------------------------------- rendering
class _Pages:
    def __init__(self, fr_docnum, secs, d):
        self.doc, self.secs, self.d = fr_docnum, secs or [], d

    def cite(self, text, start, end, label=None) -> CitationRef:
        best = None
        for s in self.secs:
            if s[7] is not None and s[7] <= start < s[8] and end <= s[8] + 1:
                if best is None or (s[8] - s[7]) < (best[8] - best[7]):
                    best = s
        cid = hashlib.sha256(f"{self.doc}|{start}|{end}".encode()).hexdigest()[:12]
        return CitationRef(citation_id=cid, fr_docnum=self.doc, section_path=best[2] if best else None,
                           label=best[4] if best else label, fr_page=best[9] if best else None,
                           pdf_page=best[11] if best else None, quote=text, start=start, end=end,
                           source_tier=SourceTier.FR_FULL_TEXT, pdf_url=self.d[2] if self.d else None,
                           xml_url=self.d[3] if self.d else None)


def render(rule: ApplicabilityRule, cfg: AircraftConfig, ev: Evaluation, T: Optional[str] = None,
           pages: Optional[_Pages] = None) -> ApplicabilityResult:
    pages = pages or _Pages(rule.fr_docnum, [], None)
    value = {"T": ApplicabilityValue.APPLICABLE, "F": ApplicabilityValue.NOT_APPLICABLE, "U": ApplicabilityValue.UNKNOWN}[ev.value]
    steps = [ExplanationStep(step=s.step, outcome=s.outcome, detail=s.detail,
                             evidence=[pages.cite(l.text, l.start, l.end) for l in s.evidence]) for s in ev.steps]
    for w in ev.warnings:
        steps.append(ExplanationStep(step="warning", outcome="INFO", detail=w, evidence=[]))
    mdl = cfg.model or "(model not given)"
    ser = cfg.serial or "(serial not given)"
    ap = None
    if T is not None:
        ap = pages.cite(T[rule.span[0]:rule.span[1]], rule.span[0], rule.span[1], "(c)")
    first = next((e for s in steps for e in s.evidence), None)
    page = first.fr_page if first and first.fr_page else (ap.fr_page if ap else None)
    vol, final = None, False
    try:
        row = _retry(lambda: _connect().execute("select volume, doc_class from documents where fr_docnum=?",
                                                (rule.fr_docnum,)).fetchone())
        if row:
            vol, final = row[0], row[1] == "FINAL_RULE"
    except Exception:
        pass
    cite_s = f"{vol} FR {page}" if vol and page else (f"FR page {page}" if page else "applicability paragraph")
    would, would_not = (("the AD as published in this final rule applies to", "the AD as published in this final rule does not apply to")
                        if final else ("the proposed AD would apply to", "the proposed AD would not apply to"))
    if ev.value == "T":
        txt = (f"Based on paragraph (c) of FR {rule.fr_docnum} ({cite_s}), {would} {mdl} S/N {ser}: {ev.reason}.")
    elif ev.value == "F":
        txt = (f"Based on paragraph (c) of FR {rule.fr_docnum} ({cite_s}), {would_not} {mdl} S/N {ser}: {ev.reason}.")
    else:
        txt = f"Applicability cannot be determined from the source: {ev.reason}. Needed: {', '.join(ev.missing) if ev.missing else 'n/a'}."
    return ApplicabilityResult(value=value, template_text=txt, explanation=steps, missing=ev.missing,
                               rule_parse_status=rule.parse_status, evaluated_document=rule.fr_docnum, applicability_text=ap)


def evaluate_document(fr_docnum: str, cfg: AircraftConfig, revision_overlay: Optional[list] = None) -> ApplicabilityResult:
    """Full path: extract -> evaluate -> render. Overlay strings are appended as warnings."""
    T, d, secs = load_doc(fr_docnum)
    rule = extract_rule(fr_docnum)
    ev = evaluate(rule, cfg, revision_overlay)
    return render(rule, cfg, ev, T, _Pages(fr_docnum, secs, d))


def evaluate_text(paragraph: str, cfg: AircraftConfig, docnum: str = "SYN-0"):
    """Synthetic path used by tests: same extract->evaluate->render code."""
    rule = extract_rule_from_text(paragraph, 0, len(paragraph), docnum)
    ev = evaluate(rule, cfg)
    return rule, ev, render(rule, cfg, ev, paragraph)
