"""Abstention reason codes and response builders (spec section 5)."""
from __future__ import annotations

from backend.api.schemas import AnswerStatus, CitationRef, DirectiveInfo, QueryResponse, SourceTier

OUT_OF_SCOPE_INSTRUCTION = "OUT_OF_SCOPE_INSTRUCTION"
DIRECTIVE_NOT_FOUND = "DIRECTIVE_NOT_FOUND"
SOURCE_TEXT_UNAVAILABLE = "SOURCE_TEXT_UNAVAILABLE"
COMPLIANCE_DETERMINATION_OUT_OF_SCOPE = "COMPLIANCE_DETERMINATION_OUT_OF_SCOPE"
UNSUPPORTED_QUESTION = "UNSUPPORTED_QUESTION"
DIRECTIVE_AMBIGUOUS = "DIRECTIVE_AMBIGUOUS"
MISSING_MODEL = "MISSING_MODEL"
NO_SUPPORTING_EVIDENCE = "NO_SUPPORTING_EVIDENCE"
NO_VERIFIED_CLAIMS = "NO_VERIFIED_CLAIMS"
VERIFICATION_UNAVAILABLE = "VERIFICATION_UNAVAILABLE"

MESSAGES = {
    OUT_OF_SCOPE_INSTRUCTION: "Request outside scope: instructions that change the system's role or checks are not followed.",
    DIRECTIVE_NOT_FOUND: "Not in indexed dataset. Any suggestions below are different IDs, not substitutions.",
    SOURCE_TEXT_UNAVAILABLE: "Source text unavailable; only spreadsheet metadata exists for this record.",
    COMPLIANCE_DETERMINATION_OUT_OF_SCOPE: "Compliance sign-off, certification and airworthiness determinations are out of scope.",
    UNSUPPORTED_QUESTION: "Unsupported question: superlative/comparative judgements across the corpus cannot be supported by cited text.",
    DIRECTIVE_AMBIGUOUS: "Several directives match; please choose one (directive_id).",
    MISSING_MODEL: "Enter the aircraft model (and serial if relevant) in the aircraft fields.",
    NO_SUPPORTING_EVIDENCE: "No supporting evidence found in the indexed documents.",
    NO_VERIFIED_CLAIMS: "No statement could be verified against the source text.",
    VERIFICATION_UNAVAILABLE: "The verification module is unavailable, so no statement can be returned.",
}


def abstain(code: str, *, status: AnswerStatus = AnswerStatus.ABSTAINED, candidates: list[DirectiveInfo] | None = None,
            warnings: list[str] | None = None, missing: list[str] | None = None, citations: list[CitationRef] | None = None,
            directive: DirectiveInfo | None = None, **extra) -> QueryResponse:
    w = [MESSAGES[code]] + list(warnings or [])
    return QueryResponse(status=status, abstention_reason=code, candidates=candidates or [], warnings=w,
                         missing_information=missing or [], citations=citations or [], directive=directive, **extra)


def sheet_citations(rec: dict) -> list[CitationRef]:
    """SHEET_METADATA citations for a metadata-only record (metadata only, never technical claims)."""
    import hashlib
    out = []
    for label, key in (("docket", "docket_raw"), ("subject", "subject"), ("status", "status_raw"), ("make", "make_raw"),
                       ("publish_date", "publish_date")):
        v = rec.get(key)
        if not v:
            continue
        cid = hashlib.sha256(f"sheet|{rec['row']}|{key}".encode()).hexdigest()[:12]
        out.append(CitationRef(citation_id=cid, fr_docnum="", section_path=f"sheet/{label}", label=label,
                               quote=f"{label}: {v}", source_tier=SourceTier.SHEET_METADATA, sheet_row=rec["row"]))
    return out
