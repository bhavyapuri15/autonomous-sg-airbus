"""Parse FR full_text.xml into canonical text + sections with char offsets and FR page spans.

Canonical text (`ParsedDoc.text`, stored as doc_text.text) rules, deterministic:
  * The XML is walked in document order. Each BLOCK element (P, HD, FP, AMDPAR, SECTNO, SUBJECT, AGENCY, ...,
    GPOTABLE) becomes one block; stray text in container elements becomes its own block.
  * Inside a block all descendant text is concatenated (inline tags such as <E> are transparent) and every run
    of whitespace (incl. NBSP) collapses to one space. The pretty-printing artifact "</E>\\n ." is repaired by
    dropping whitespace that sits between an inline element end and one of . , ; : ) ] .
  * GPOTABLE: lines "TTITLE", "CHED | CHED ...", one line per ROW "ENT | ENT ..." joined with "\\n".
  * Blocks are joined with "\\n\\n". ALL offsets refer to this string.
  * <PRTPAGE P="N"/> records (offset, N): characters at/after offset are on FR page N. Characters before the
    first marker are on start_page.
"""
import bisect, re
from dataclasses import dataclass, field
from lxml import etree

BLOCK_TAGS = {"P", "HD", "FP", "AMDPAR", "SECTNO", "SUBJECT", "AGENCY", "SUBAGY", "CFR", "DEPDOC", "RIN",
              "DATED", "NAME", "TITLE", "BILCOD", "FRDOC", "EDNOTE", "LI", "HED", "DATE", "PARTNO", "TTITLE"}
TABLE_TAG = "GPOTABLE"
SKIP_TAGS = {"STARS", "GPH", "MATH"}   # no text content
PREAMB_HEADER_TAGS = {"AGENCY", "SUBAGY", "CFR", "DEPDOC", "RIN", "SUBJECT"}
PUNCT_FIX = re.compile(r"\s+[.,;:)\]]")


class TextBuilder:
    def __init__(self):
        self.parts, self.n, self.pending, self.markers = [], 0, False, []

    def _put(self, s):
        self.parts.append(s); self.n += len(s)

    def add(self, piece, boundary=False):
        if not piece:
            return
        if boundary and PUNCT_FIX.match(piece):
            piece = piece.lstrip()
        words = piece.split()
        if not words:
            if self.n:
                self.pending = True
            return
        lead, trail = piece[0].isspace(), piece[-1].isspace()
        if (self.pending or lead) and self.n and not self.parts[-1].endswith("\n"):
            self._put(" ")
        self._put(" ".join(words))
        self.pending = trail

    def newline(self):
        self._put("\n"); self.pending = False

    def marker(self, page):
        self.markers.append((self.n, page))

    def result(self):
        return "".join(self.parts).rstrip(), self.markers


def _local(el):
    return el.tag if isinstance(el.tag, str) else None


def _flatten(el, tb, info, is_root=True):
    """Add el's content to tb. info collects lead_em."""
    if el.tag is etree.Comment or el.tag is etree.ProcessingInstruction:
        return
    tag = _local(el)
    if tag == "PRTPAGE":
        tb.marker(int(el.get("P")))
        return
    if tag in SKIP_TAGS:
        for e in el.iter("PRTPAGE"):
            tb.marker(int(e.get("P")))
        return
    if tag == "E" and tb.n == 0 and not tb.parts and "lead_em" not in info:
        info["lead_em"] = " ".join("".join(el.itertext()).split())
        info["lead_em_t"] = el.get("T")
    tb.add(el.text, boundary=False)
    for ch in el:
        _flatten(ch, tb, info, False)
        tb.add(ch.tail, boundary=True)


def _render_table(el, tb):
    """Deterministic table text: TTITLE line; header line of CHED joined ' | '; one line per ROW with ENT joined ' | '.
    PRTPAGE anywhere inside the table is recorded at the current position (they occur inside ROW, not only in ENT)."""
    st = {"first": True}

    def nl():
        if not st["first"]:
            tb.newline()
        st["first"] = False

    def cells(parent, cell_tags):
        i = 0
        for ch in parent.iter():
            if ch is parent:
                continue
            if ch.tag == "PRTPAGE":
                tb.marker(int(ch.get("P")))
            elif ch.tag in cell_tags:
                if i: tb.add(" | ")
                _flatten(ch, tb, {}); i += 1

    def walk(e):
        for ch in e:
            if ch.tag is etree.Comment or ch.tag is etree.ProcessingInstruction:
                continue
            if ch.tag == "PRTPAGE":
                tb.marker(int(ch.get("P")))
            elif ch.tag in ("TTITLE", "TNOTE", "TDESC"):
                nl(); _flatten(ch, tb, {})
            elif ch.tag == "BOXHD":
                nl(); cells(ch, ("CHED",))
            elif ch.tag == "ROW":
                nl(); cells(ch, ("ENT",))
            else:
                walk(ch)
    walk(el)


@dataclass
class Block:
    tag: str
    text: str
    start: int = 0
    end: int = 0
    anc: tuple = ()
    cont: int = 0            # id of nearest non-block container ancestor (for grouping)
    hd_source: str = ""
    lead_em: str = ""
    lead_em_t: str = ""
    has_table: bool = False
    markers: list = field(default_factory=list)   # (offset_in_block, page)


@dataclass
class ParsedDoc:
    text: str
    blocks: list
    markers: list            # global (offset, page), sorted by offset
    sections: list
    start_page: int
    warnings: list

    def page_at(self, c):
        i = bisect.bisect_right([m[0] for m in self.markers], c) - 1
        return self.markers[i][1] if i >= 0 else self.start_page


def _blocks_from_xml(root):
    blocks, pending, ctr = [], [], [0]

    def emit(tag, tb_result, anc, cont, hd_source="", info=None, table=False, extra_markers=()):
        text, markers = tb_result
        markers = list(extra_markers) + [m for m in markers]
        if not text:
            pending.extend(p for _, p in markers); return
        b = Block(tag, text, anc=anc, cont=cont, hd_source=hd_source, has_table=table)
        if info:
            b.lead_em, b.lead_em_t = info.get("lead_em", ""), info.get("lead_em_t", "")
        b.markers = [(min(o, len(text)), p) for o, p in markers]
        if pending:
            b.markers = [(0, p) for p in pending] + b.markers
            pending.clear()
        blocks.append(b)

    def stray(s, anc, cont):
        if s and s.strip():
            tb = TextBuilder(); tb.add(s); emit("#text", tb.result(), anc, cont)

    def walk(el, anc, cont):
        if el.tag is etree.Comment or el.tag is etree.ProcessingInstruction:
            return
        tag = el.tag
        if tag == "PRTPAGE":
            pending.append(int(el.get("P"))); return
        if tag in SKIP_TAGS:
            for e in el.iter("PRTPAGE"):
                pending.append(int(e.get("P")))
            return
        if tag == TABLE_TAG:
            tb = TextBuilder(); _render_table(el, tb); emit(tag, tb.result(), anc, cont, table=True); return
        if tag in BLOCK_TAGS:
            tb = TextBuilder(); info = {}; _flatten(el, tb, info)
            emit(tag, tb.result(), anc, cont, hd_source=el.get("SOURCE", ""), info=info); return
        ctr[0] += 1
        my = ctr[0]
        anc2 = anc + (tag,)
        stray(el.text, anc2, my)
        for ch in el:
            walk(ch, anc2, my)
            stray(ch.tail, anc2, my)

    walk(root, (), 0)
    return blocks


def _clean_hd(t):
    return t.strip().rstrip(":").strip()


LABEL_HD = re.compile(r"^\(([a-z]{1,2})\)\s*(.*)$")
SUBLABEL = re.compile(r"^\(([0-9]+|[a-zA-Z]{1,4})\)\s")
LEAD_LABELED = re.compile(r"^\(([a-z]{1,2})\)\s*(.+?)\s*[:.]?$")
LEAD_UNLABELED = re.compile(r"^([A-Z][A-Za-z ,/&'’-]{2,60}):$")


def _sub_level(lbl):
    if lbl.isdigit(): return 2
    if lbl.islower(): return 3
    return 4


def _ad_sections(blocks, idxs, prefix, used):
    """idxs: block indices in one EXTRACT. Returns list of section dicts (block-index spans, inclusive)."""
    out = []
    modern = any(blocks[i].tag == "HD" and LABEL_HD.match(blocks[i].text) for i in idxs)
    cur_top = None      # dict
    stack = []          # open sub sections [(level, sec)]
    header_idx = []
    pending_hd = None
    last_letter = None

    def uniq(path):
        n = used.get(path, 0) + 1; used[path] = n
        return path if n == 1 else f"{path}#{n}"

    def close_to(level, i):
        while stack and stack[-1][0] >= level:
            stack.pop()[1]["end_i"] = i - 1

    def close_all(i):
        close_to(0, i)
        nonlocal cur_top
        if cur_top: cur_top["end_i"] = i - 1; cur_top = None

    def open_top(i, start_i, label, heading):
        nonlocal cur_top
        close_all(i)
        path = uniq(f"{prefix}/{label}" if label else f"{prefix}/{heading}")
        cur_top = dict(kind="proposed_ad_paragraph", path=path, label=label, heading=heading, start_i=start_i,
                       end_i=None, ancestor="", top=path, level=1)
        out.append(cur_top)
        return cur_top

    for i in idxs:
        b = blocks[i]
        top_started = False
        if b.tag == "HD" and LABEL_HD.match(b.text):
            m = LABEL_HD.match(b.text); open_top(i, i, "(" + m.group(1) + ")", m.group(2).strip().rstrip(":") or None)
            last_letter = m.group(1); top_started = True; pending_hd = None
        elif b.tag == "P" and b.lead_em and LEAD_LABELED.match(b.lead_em) and b.text.startswith(b.lead_em[:3]) and b.lead_em_t in ("03", "02", "04", ""):
            m = LEAD_LABELED.match(b.lead_em)
            open_top(i, i, "(" + m.group(1) + ")", m.group(2).strip().rstrip(":")); last_letter = m.group(1); top_started = True; pending_hd = None
        elif b.tag == "P" and b.lead_em and LEAD_UNLABELED.match(b.lead_em) and b.text.startswith(b.lead_em):
            rest = b.text[len(b.lead_em):].strip()
            ml = re.match(r"\(([a-z]{1,2})\)\s", rest)
            open_top(i, i, "(" + ml.group(1) + ")" if ml else None, b.lead_em.rstrip(":"))
            if ml: last_letter = ml.group(1)
            top_started = True; pending_hd = None
        elif b.tag == "P" and not modern and SUBLABEL.match(b.text) and re.match(r"\([a-z]\)", b.text) and \
                (last_letter is None and b.text.startswith("(a)") or
                 last_letter is not None and b.text[1] == chr(ord(last_letter[-1]) + 1) and len(last_letter) == 1):
            lbl = b.text[1]
            open_top(i, pending_hd if pending_hd is not None else i, "(" + lbl + ")",
                     blocks[pending_hd].text.strip().rstrip(":") if pending_hd is not None else None)
            last_letter = lbl; top_started = True; pending_hd = None
        elif b.tag == "HD" and not modern:
            pending_hd = i
            continue
        if top_started:
            continue
        if pending_hd is not None:
            pending_hd = None   # heading becomes part of the current section's text (continuation)
        if cur_top is None:
            header_idx.append(i); continue
        m = SUBLABEL.match(b.text) if b.tag == "P" else None
        if m:
            lbl = m.group(1); lv = _sub_level(lbl)
            close_to(lv, i)
            parent = stack[-1][1] if stack else cur_top
            path = uniq(f"{parent['path']}/({lbl})")
            sec = dict(kind="proposed_ad_paragraph", path=path, label=f"({lbl})", heading=None, start_i=i, end_i=None,
                       ancestor=parent["path"], top=cur_top["path"], level=lv)
            stack.append((lv, sec)); out.append(sec)
    close_all(idxs[-1] + 1)
    if header_idx:
        out.append(dict(kind="other", path=uniq(f"{prefix}/header"), label=None, heading="header",
                        start_i=header_idx[0], end_i=header_idx[-1], ancestor="", top="", level=0))
    if not any(s["kind"] == "proposed_ad_paragraph" for s in out):
        out.append(dict(kind="other", path=uniq(f"{prefix}/unparsed"), label=None, heading="unparsed",
                        start_i=idxs[0], end_i=idxs[-1], ancestor="", top="", level=0))
    return out


def parse_fr_xml(xml_bytes, start_page, end_page=None, pdf_pages=None):
    root = etree.fromstring(xml_bytes)
    blocks = _blocks_from_xml(root)
    warnings = []
    pos, parts = 0, []
    markers = []
    for b in blocks:
        b.start, b.end = pos, pos + len(b.text)
        for o, p in b.markers:
            markers.append((b.start + o, p))
        parts.append(b.text); pos = b.end + 2
    text = "\n\n".join(parts)
    markers.sort(key=lambda m: m[0])
    n_xml = sum(1 for _ in root.iter("PRTPAGE"))
    if n_xml != len(markers):
        warnings.append(f"prtpage_count_mismatch_xml{n_xml}_recorded{len(markers)}")
    pages = [p for _, p in markers]
    if pages != sorted(pages):
        warnings.append("non_monotonic_prtpage")
    if markers and markers[0][1] < start_page:
        warnings.append("prtpage_before_start_page")
    if end_page and pages and max(pages) > end_page:
        warnings.append("prtpage_beyond_end_page")
    repaired = []
    if pdf_pages and end_page:
        markers, repaired = _repair_missing_markers(text, markers, start_page, end_page, pdf_pages)
        if repaired:
            warnings.append("prtpage_repaired_from_pdf:" + ",".join(map(str, repaired)))
    doc = ParsedDoc(text, blocks, markers, [], start_page, warnings)
    doc.repaired_pages = repaired

    # ---- classify blocks into sections -------------------------------------------------------------------
    secs = []          # dicts with start_i,end_i inclusive block indexes
    n = len(blocks)
    amend_mode = False
    in_extract_groups = {}   # extract container id -> list of block idx
    kinds = [None] * n       # (kind, group key, path)
    stack = {}               # heading level -> text, for SUPLINF
    cur = None               # current non-AD section

    def start_sec(kind, path, i, **kw):
        nonlocal cur
        cur = dict(kind=kind, path=path, label=None, heading=kw.get("heading"), start_i=i, end_i=i, ancestor="", top="", level=0)
        secs.append(cur)

    ad_gid = -1
    for i, b in enumerate(blocks):
        a = b.anc
        in_ext = "EXTRACT" in a
        if b.tag == "HD" and b.hd_source.startswith("HD") and "SUPLINF" in a and re.match(r"(The Proposed Amendment|Adoption of the Amendment|The Amendment)", b.text.strip(), re.I):
            amend_mode = True
        if in_ext and (amend_mode or "REGTEXT" in a or "SECTION" in a or "PART" in a):
            # container id of the EXTRACT: nearest cont is some descendant; use position of EXTRACT in anc and a run-id
            gid = ad_gid if (i > 0 and kinds[i - 1] == "AD") else i
            ad_gid = gid
            in_extract_groups.setdefault(gid, []).append(i)
            cur = None
            kinds[i] = "AD"
            continue
        if i > 0 and kinds[i - 1] == "AD" and "SECTION" in a and "EXTRACT" not in a:
            # AD text that continues after a (short) EXTRACT inside the same SECTION (seen in 2004-2005 NPRMs)
            in_extract_groups.setdefault(ad_gid, []).append(i)
            cur = None
            kinds[i] = "AD"
            continue
        # non AD
        if "PREAMB" in a:
            k = a.index("PREAMB")
            direct_child = a[k + 1] if len(a) > k + 1 else None
            if b.tag in PREAMB_HEADER_TAGS and direct_child is None:
                key, path = ("hdr",), "preamble/header"
            else:
                hed = b.text if b.tag == "HD" else None
                key = ("pre", b.cont)
                path = None
                if cur is None or cur.get("key") != key:
                    # heading of the group is the first HD block in the group
                    j = i
                    while j < n and blocks[j].cont == b.cont and blocks[j].tag != "HD" and j - i < 3:
                        j += 1
                    h = _clean_hd(blocks[j].text) if j < n and blocks[j].cont == b.cont and blocks[j].tag == "HD" else (_clean_hd(b.text)[:40])
                    path = f"preamble/{h}"
            if cur is None or cur.get("key") != key:
                start_sec("preamble", path, i); cur["key"] = key
            else:
                cur["end_i"] = i
            continue
        if "SUPLINF" in a and not amend_mode:
            if b.tag == "HD" and b.hd_source.startswith("HD") and b.hd_source[2:].isdigit():
                lvl = int(b.hd_source[2:])
                for l in [l for l in stack if l >= lvl]: del stack[l]
                stack[lvl] = _clean_hd(b.text)
                path = "preamble/SUPPLEMENTARY INFORMATION/" + "/".join(stack[l] for l in sorted(stack))
                start_sec("preamble", path, i); cur["heading"] = stack[lvl]; cur["key"] = ("sup", i)
            elif b.tag == "HD" and b.hd_source == "HED":
                stack.clear()
                start_sec("preamble", "preamble/" + _clean_hd(b.text), i); cur["key"] = ("suphead", i)
            else:
                if cur is not None and cur.get("key", ("",))[0] in ("sup", "suphead"):
                    cur["end_i"] = i
                else:
                    start_sec("preamble", "preamble/SUPPLEMENTARY INFORMATION", i); cur["key"] = ("suphead", i)
            continue
        if amend_mode:
            has_ext_after = any(blocks[j].anc and "EXTRACT" in blocks[j].anc for j in range(i, n))
            key = ("reg",) if has_ext_after else ("close",)
            if cur is None or cur.get("key") != key:
                start_sec("regtext" if has_ext_after else "other", "regtext/amendment" if has_ext_after else "closing", i)
                cur["key"] = key
            else:
                cur["end_i"] = i
            continue
        # anything else (REGTEXT outside extract, corrections, trailing docs...)
        top = a[1] if len(a) > 1 else (a[0] if a else "root")
        key = ("other", top, b.cont if "REGTEXT" in a else 0)
        kind = "regtext" if "REGTEXT" in a else "other"
        if cur is None or cur.get("key") != key:
            start_sec(kind, f"{'regtext' if kind == 'regtext' else 'body'}/{top}", i); cur["key"] = key
        else:
            cur["end_i"] = i

    used = {}
    for n_ext, (_, idxs) in enumerate(sorted(in_extract_groups.items())):
        prefix = "proposed_ad" if n_ext == 0 else f"proposed_ad#{n_ext + 1}"
        secs.extend(_ad_sections(blocks, idxs, prefix, used))

    # make paths unique among non-AD sections
    seen = {}
    for s in secs:
        if s["kind"] in ("preamble", "regtext", "other") and not s["path"].startswith("proposed_ad"):
            c = seen.get(s["path"], 0) + 1; seen[s["path"]] = c
            if c > 1: s["path"] = f"{s['path']}#{c}"
    secs.sort(key=lambda s: (blocks[s["start_i"]].start, -blocks[s["end_i"]].end, s["level"]))
    for seq, s in enumerate(secs):
        s0, s1 = blocks[s["start_i"]], blocks[s["end_i"]]
        s["seq"] = seq
        s["start_char"], s["end_char"] = s0.start, s1.end
        s["text"] = text[s0.start:s1.end]
        s["has_table"] = any(blocks[j].has_table for j in range(s["start_i"], s["end_i"] + 1))
        s["fr_page_start"] = doc.page_at(s["start_char"])
        s["fr_page_end"] = doc.page_at(max(s["start_char"], s["end_char"] - 1))
        s.pop("key", None)
    doc.sections = secs
    return doc


def _norm_idx(text):
    """Normalised text (identical rules to pdf_parser.norm_for_match) plus map normalised index -> original index."""
    from backend.ingestion.pdf_parser import strip_marks
    keep, idx = [], []
    for i, ch in enumerate(text):
        for c2 in strip_marks(ch).lower():
            if "a" <= c2 <= "z" or "0" <= c2 <= "9":
                keep.append(c2); idx.append(i)
    return "".join(keep), idx


def _page_body(pdf_text):
    lines = pdf_text.split("\n")
    for k, ln in enumerate(lines[:4]):
        if "Federal Register /" in ln or "Federal Register/" in ln:
            return "\n".join(lines[k + 1:])
    return pdf_text


def _repair_missing_markers(text, markers, start_page, end_page, pdf_pages, probe=60):
    """Some FR XML files omit a <PRTPAGE> (seen when a page break falls next to a heading/table).
    For every page in (start_page, end_page] lacking a marker, locate the first words of the PDF page body in the
    XML text, strictly between the neighbouring markers. Pages that cannot be located are left missing (never guessed)."""
    from backend.ingestion.pdf_parser import norm_for_match
    have = {p for _, p in markers}
    missing = [p for p in range(start_page + 1, end_page + 1) if p not in have]
    if not missing:
        return markers, []
    ntext, idx = _norm_idx(text)
    markers = list(markers); fixed = []
    for p in missing:
        k = p - start_page
        if k >= len(pdf_pages):
            continue
        body = norm_for_match(_page_body(pdf_pages[k]))
        lo = max([o for o, q in markers if q < p], default=0)
        hi = min([o for o, q in markers if q > p], default=len(text))
        # normalised index range corresponding to (lo, hi)
        import bisect
        a, b = bisect.bisect_left(idx, lo), bisect.bisect_left(idx, hi)
        pos = ntext.find(body[:probe], a, b) if len(body) >= 20 else -1
        if pos >= 0:
            markers.append((idx[pos], p)); fixed.append(p)
    markers.sort(key=lambda m: m[0])
    return markers, fixed


def _ext_run(blocks, i):
    """Identify which EXTRACT element block i belongs to: contiguous run of blocks having EXTRACT in anc
    (consecutive EXTRACT runs separated by non-EXTRACT blocks are distinct)."""
    j = i
    while j > 0 and "EXTRACT" in blocks[j - 1].anc:
        j -= 1
    return j
