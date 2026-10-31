"""Serial parsing and comparison. Never lexicographic."""
import re
from dataclasses import dataclass
from typing import Optional

_OK = re.compile(r"^[A-Za-z0-9/\-]+$")


@dataclass
class PSerial:
    raw: str
    prefix: str = ""
    number: Optional[int] = None
    digits: str = ""
    width: int = 0
    suffix: str = ""


def parse_serial(raw: str) -> PSerial:
    r = raw.strip().replace(",", "") if re.fullmatch(r"\d{1,3}(,\d{3})+", raw.strip()) else raw.strip()
    ps = PSerial(raw=raw)
    if not r or not _OK.match(r):
        return ps
    m = re.match(r"^(.*?)(\d+)([^\d]*)$", r)
    if not m:
        return ps
    ps.prefix, ps.digits, ps.suffix = m.group(1).upper(), m.group(2), m.group(3).upper()
    ps.number, ps.width = int(m.group(2)), len(m.group(2))
    return ps


def _same_shape(a: PSerial, b: PSerial) -> bool:
    return (a.number is not None and b.number is not None and a.prefix == b.prefix and a.suffix == b.suffix)


def _padded(p: PSerial) -> bool:
    return len(p.digits) > 1 and p.digits.startswith("0")


def _width_ok(cfg: PSerial, bounds) -> bool:
    ps = [b for b in bounds if b is not None]
    if any(_padded(b) for b in ps):
        if len({b.width for b in ps}) != 1:
            return False
        if _padded(cfg) and cfg.width != ps[0].width:
            return False
        return True
    if _padded(cfg):
        return False
    return True


def equal_elem(cfg_raw: str, elem_raw: str) -> str:
    """T exact (case-insens) match, F definitively different, U not comparable."""
    c, e = parse_serial(cfg_raw), parse_serial(elem_raw)
    if cfg_raw.strip().upper() == elem_raw.strip().upper() and c.number is not None:
        return "T"
    if not _same_shape(c, e) or not _width_ok(c, [e]):
        return "U"
    return "T" if c.number == e.number else "F"


def in_range(cfg_raw: str, lo_raw, hi_raw, lo_incl, hi_incl):
    """Return ('T'|'F'|'U', reason)."""
    c = parse_serial(cfg_raw)
    lo = parse_serial(lo_raw) if lo_raw else None
    hi = parse_serial(hi_raw) if hi_raw else None
    if c.number is None:
        return "U", "SERIAL_FORMAT_NOT_COMPARABLE"
    for b in (lo, hi):
        if b is not None and not _same_shape(c, b):
            return "U", "SERIAL_FORMAT_NOT_COMPARABLE"
    if not _width_ok(c, [lo, hi]):
        return "U", "SERIAL_FORMAT_NOT_COMPARABLE"
    res = "T"
    for b, incl, side in ((lo, lo_incl, "lo"), (hi, hi_incl, "hi")):
        if b is None:
            continue
        if side == "lo":
            r = "F" if c.number < b.number else ("T" if c.number > b.number else _bd(incl))
        else:
            r = "F" if c.number > b.number else ("T" if c.number < b.number else _bd(incl))
        if r == "F":
            return "F", "OUTSIDE_RANGE"
        if r == "U":
            res = "U"
    return res, ("BOUNDARY_AMBIGUOUS" if res == "U" else "IN_RANGE")


def _bd(incl):
    return "T" if incl is True else ("F" if incl is False else "U")
