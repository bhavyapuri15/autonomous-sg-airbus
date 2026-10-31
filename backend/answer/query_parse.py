"""Query parsing: intent classification and hints. Aircraft config is NEVER taken from free text."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.api.schemas import QueryRequest

_APPLIC = re.compile(r"\b(applies|apply|applicable|applicability|affect(?:s|ed)?|does .{0,60}\bapply)\b", re.I)
# Applicability intent only for an explicit "does it apply to MY/THIS/a specific aircraft" question (fix 2b).
_APPLIC_SPECIFIC = re.compile(
    r"\b(?:appl(?:y|ies)|applicable|applicability)\s+to\s+(?:my|our|this|that|a\s+specific|an?\s+specific|s/?n\b|serial)"
    r"|\bis\s+(?:my|our|this|that)\b.{0,60}\b(?:affected|covered|subject)\b"
    r"|\b(?:am\s+i|are\s+we)\s+(?:required|subject|obligated|affected)\b"
    r"|\bdoes\s+(?:this|the|that|it)\b.{0,60}\b(?:affect|apply\s+to)\s+(?:my|our)\b", re.I)
_APPLIC_MODELQ = re.compile(r"^\s*(?:does|do|is|are|will|would|can)\b.{0,80}\b(?:appl(?:y|ies)|applicable|affect(?:s|ed)?)\b", re.I)
# comparison of two directives / vague reference (fix 5)
_COMPARE = re.compile(
    r"\b(?:vs\.?|versus|compare[ds]?|comparison|difference between|differs?\s+from|differences?)\b"
    r"|\bthe\s+\w+\s+one\s+or\s+the\s+\w+\s+one\b", re.I)
_VAGUE = re.compile(r"\bwhichever\b.{0,30}\b(?:you|i)\b|\bwhichever one\b", re.I)
_PRONOUN_ONLY = re.compile(r"\b(?:it|this one|that one)\b", re.I)
_REVISION = re.compile(r"\b(supersed\w*|withdr[ae]w\w*|final(?:ized|ised)?|latest|revis\w*|amend\w*|current(?:ly)?|status)\b", re.I)
_INJECTION = re.compile(
    r"(ignore|disregard|forget|override|bypass)\b.{0,40}\b(previous|prior|above|earlier|all|any|your|the)\b.{0,40}"
    r"\b(instruction|prompt|rule|guideline|polic|constraint|verification|check)s?"
    r"|\byou are now\b|\bact as\b|\bpretend (to be|you)\b|\bsystem prompt\b|\bdeveloper mode\b|\bjailbreak\b"
    r"|\bdo anything now\b|\bnew instructions?\b|\breveal (your|the) (prompt|instructions)\b", re.I)
_COMPLIANCE = re.compile(
    r"\b(certify|certification of|sign[- ]?off|approve (?:my|the) aircraft|release to service|return to service)\b"
    r"|\bis (?:my|our|the|this) .{0,40}\b(airworthy|legal|compliant|safe to fly|in compliance)\b"
    r"|\bam i (?:compliant|legal|in compliance)\b|\bcan i (?:legally )?fly\b", re.I)
_SUPERLATIVE = re.compile(
    r"\b(most|least|worst|best|biggest|largest|smallest|highest|lowest|top \d+|ranking|rank)\b.{0,40}"
    r"\b(dangerous|critical|severe|important|serious|urgent|risky|safe|costly|expensive|common|AD|ADs|directive|directives)\b"
    r"|\b(worst|best|most dangerous|most critical|more dangerous|safer than|compare .{0,40} (?:to|with|and))\b", re.I)
# model/serial-like tokens in free text (hints only)
_MODEL_TOK = re.compile(r"\b(?:[A-Z]{1,4}-?\d{2,4}[A-Z0-9-]*|[A-Z]{2,4}\d{3,}[A-Z0-9]*)\b")
_SERIAL = re.compile(r"\b(?:s/?n|serial(?: number| no\.?)?)\b[:\s#]*([A-Z0-9-]{3,})", re.I)
_IDLIKE = re.compile(r"^(?:\d{4}-\d{4,5}|\d{4}-\d{2}-\d{2}|FAA-\d{4}-\d+|MCAI-.*|R\d-.*|[A-Z]\d-\d+|\d{1,3}-[A-Z]{2}-\d+.*)$", re.I)


@dataclass
class ParsedQuery:
    intent: str                      # applicability | revision | factual
    injection: bool = False
    compliance: bool = False
    superlative: bool = False
    hints: list[str] = field(default_factory=list)   # missing_information hints (never auto-filled)
    suggested_tokens: list[str] = field(default_factory=list)
    comparison: bool = False         # compares two directives / vague reference (needs an explicit directive)


def is_injection(text: str) -> bool:
    return bool(_INJECTION.search(text))


def parse(req: QueryRequest) -> ParsedQuery:
    q = req.question
    ac = req.aircraft
    has_fields = bool(ac and (ac.model or ac.serial or ac.make or ac.facts))
    model_q = bool(_APPLIC_MODELQ.search(q)) and any(
        not _IDLIKE.match(t) and re.search(r"\d", t) for t in _MODEL_TOK.findall(q))
    if has_fields or _APPLIC_SPECIFIC.search(q) or model_q:
        intent = "applicability"
    elif _REVISION.search(q):
        intent = "revision"
    else:
        intent = "factual"
    pq = ParsedQuery(intent=intent, injection=is_injection(q), compliance=bool(_COMPLIANCE.search(q)),
                     superlative=bool(_SUPERLATIVE.search(q)),
                     comparison=bool(_COMPARE.search(q) or _VAGUE.search(q)
                                     or (_PRONOUN_ONLY.search(q) and len(q.split()) <= 12 and not re.search(r"\d{3,}", q))))
    toks = [t for t in _MODEL_TOK.findall(q) if not _IDLIKE.match(t) and re.search(r"\d", t)]
    ser = _SERIAL.findall(q)
    if toks and not (ac and ac.model):
        pq.suggested_tokens = sorted(set(toks))
        pq.hints.append(f"Model/serial must be entered in the aircraft fields (detected in text: {', '.join(pq.suggested_tokens)}); "
                        "it was not used automatically.")
    if ser and not (ac and ac.serial):
        pq.hints.append("Serial number must be entered in the aircraft fields; text mentions are not used automatically.")
    return pq
