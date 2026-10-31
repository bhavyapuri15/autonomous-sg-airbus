"""Model / make normalization. Deterministic, no fuzzy matching."""
import re

_DASHES = "‐‑‒–—―−"


def normalize_model(s: str) -> str:
    s = s.strip()
    for d in _DASHES:
        s = s.replace(d, "-")
    s = s.upper()
    s = re.sub(r"\s*-\s*", "-", s)
    return re.sub(r"\s+", " ", s)


def compact(s: str) -> str:
    return re.sub(r"[\s]", "", normalize_model(s))


def expand_shorthand(prev_norm: str, token: str):
    """'A310-203' + '-204' -> 'A310-204'. None if prev has no hyphen."""
    if "-" not in prev_norm or not token.startswith("-"):
        return None
    base = prev_norm[: prev_norm.rfind("-") + 1]
    return base + normalize_model(token)[1:]


def _slash_variants(ref: str):
    out = {ref}
    if "/" in ref:
        parts = ref.split("/")
        head = parts[0]
        m = re.match(r"^(.*?)(\d+)$", head)
        for p in parts[1:]:
            if m:
                out.add(m.group(1) + p)
            out.add(p)
    return out


def match_model(cfg: str, ref: str, is_series: bool = False) -> str:
    """Return 'T', 'U' or 'F' for config model vs one rule model (both pre-normalized)."""
    if cfg == ref:
        return "T"
    cc, rc = cfg.replace(" ", ""), ref.replace(" ", "")
    if cc == rc:
        return "U"                       # differs only by spaces: cannot verify
    if cc.startswith(rc) or rc.startswith(cc) or cc.endswith(rc) or rc.endswith(cc):
        return "U"                       # series / family / sub-variant relation
    if cfg in _slash_variants(ref) or any(cc == v.replace(" ", "") for v in _slash_variants(ref)):
        return "U"
    return "F"


_LEGAL = {"INC", "LLC", "LTD", "LIMITED", "CORPORATION", "CORP", "COMPANY", "CO", "THE", "SAS", "S.A.S.",
          "GMBH", "KG", "SA", "S.A.", "PLC", "AG", "BV", "B.V.", "SPA", "S.P.A.", "LP", "AND", "&"}
_MAKE_ALIASES = {"BOEING": {"BOEING", "BOEING COMPANY"}}


def normalize_make(s: str) -> str:
    s = re.sub(r"\([^)]*\)", " ", s.upper())
    toks = [t for t in re.split(r"[\s,]+", s) if t and t.strip(".") not in _LEGAL and t not in _LEGAL]
    return " ".join(toks)


def make_matches(a: str, b: str) -> bool:
    return bool(a and b and normalize_make(a) == normalize_make(b))
