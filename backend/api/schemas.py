"""API contract. Single source of truth for backend responses and frontend types.

See docs/verification_spec.md section 4 for semantics.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field

DISCLAIMER = (
    "Decision support only. Not a certified airworthiness or compliance determination. "
    "Verify against the official FAA source."
)


class AnswerStatus(str, Enum):
    ANSWERED = "ANSWERED"
    ABSTAINED = "ABSTAINED"
    NEEDS_MORE_INFORMATION = "NEEDS_MORE_INFORMATION"


class ApplicabilityValue(str, Enum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"
    NOT_EVALUATED = "NOT_EVALUATED"


class RevisionStatus(str, Enum):
    WITHDRAWN = "WITHDRAWN"
    SUPPLEMENTED = "SUPPLEMENTED"
    FINALIZED = "FINALIZED"
    PROPOSAL_STATUS_UNVERIFIED = "PROPOSAL_STATUS_UNVERIFIED"


class SourceTier(str, Enum):
    FR_FULL_TEXT = "FR_FULL_TEXT"
    SHEET_METADATA = "SHEET_METADATA"
    SHEET_EMBEDDED_TEXT = "SHEET_EMBEDDED_TEXT"


class CitationRef(BaseModel):
    citation_id: str  # sha256(fr_docnum|start|end)[:12]
    fr_docnum: str
    section_path: Optional[str] = None
    label: Optional[str] = None
    fr_page: Optional[int] = None
    pdf_page: Optional[int] = None
    quote: str
    start: Optional[int] = None  # offsets into doc_text
    end: Optional[int] = None
    source_tier: SourceTier
    pdf_url: Optional[str] = None
    xml_url: Optional[str] = None
    sheet_row: Optional[int] = None  # for SHEET_* tiers


class Claim(BaseModel):
    text: str
    citations: list[CitationRef]


class ExplanationStep(BaseModel):
    step: str
    outcome: Literal["TRUE", "FALSE", "UNKNOWN", "INFO"]
    detail: str
    evidence: list[CitationRef] = []


class ApplicabilityResult(BaseModel):
    value: ApplicabilityValue = ApplicabilityValue.NOT_EVALUATED
    template_text: Optional[str] = None
    explanation: list[ExplanationStep] = []
    missing: list[str] = []
    rule_parse_status: Optional[Literal["FULL", "PARTIAL", "FAILED"]] = None
    evaluated_document: Optional[str] = None
    applicability_text: Optional[CitationRef] = None  # verbatim (c) paragraph for human review


class RevisionEdge(BaseModel):
    src: str
    dst: str
    type: Literal[
        "WITHDRAWS", "SUPPLEMENTS", "CORRECTS", "FINALIZES",
        "PROPOSES_TO_SUPERSEDE", "SUPERSEDES", "SAME_DOCKET",
    ]
    confidence: Literal["VERIFIED", "CANDIDATE"]
    evidence: list[CitationRef] = []
    note: Optional[str] = None


class RevisionResult(BaseModel):
    status: RevisionStatus = RevisionStatus.PROPOSAL_STATUS_UNVERIFIED
    current_authoritative_status_verified: bool = False
    edges: list[RevisionEdge] = []
    template_text: Optional[str] = None
    latest_in_dataset: Optional[str] = None


class DirectiveInfo(BaseModel):
    fr_docnum: Optional[str] = None
    docket: Optional[str] = None
    doc_class: Optional[str] = None
    title: Optional[str] = None
    publication_date: Optional[str] = None
    citation: Optional[str] = None
    sheet_rows: list[int] = []
    pdf_url: Optional[str] = None


class RejectedClaim(BaseModel):
    text: str
    failed_check: str


class VerificationInfo(BaseModel):
    mode: Literal["llm", "extractive", "none"] = "none"
    claims_generated: int = 0
    claims_verified: int = 0
    claims_rejected: list[RejectedClaim] = []


class Timings(BaseModel):
    retrieval: float = 0.0
    engines: float = 0.0
    generation: float = 0.0
    verification: float = 0.0
    total: float = 0.0


class AircraftConfig(BaseModel):
    model: Optional[str] = Field(None, max_length=100)
    serial: Optional[str] = Field(None, max_length=100)
    make: Optional[str] = Field(None, max_length=200)
    facts: dict[str, bool] = {}  # condition_key -> asserted value; absent = unknown


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    directive_id: Optional[str] = Field(None, max_length=100)  # docket, FR docnum or AD number
    aircraft: Optional[AircraftConfig] = None
    use_llm: bool = True


class QueryResponse(BaseModel):
    status: AnswerStatus
    answer_claims: list[Claim] = []
    applicability: ApplicabilityResult = ApplicabilityResult()
    revision: Optional[RevisionResult] = None
    directive: Optional[DirectiveInfo] = None
    candidates: list[DirectiveInfo] = []  # when ambiguous / did-you-mean
    citations: list[CitationRef] = []
    warnings: list[str] = []
    abstention_reason: Optional[str] = None
    missing_information: list[str] = []
    verification: VerificationInfo = VerificationInfo()
    timings_ms: Timings = Timings()
    disclaimer: str = DISCLAIMER


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(10, ge=1, le=50)
    filters: dict[str, str] = {}  # make, model, doc_class, docket, date_from, date_to


class SearchHit(BaseModel):
    chunk_id: str
    fr_docnum: str
    docket: Optional[str] = None
    title: Optional[str] = None
    doc_class: Optional[str] = None
    section_path: Optional[str] = None
    text: str
    score: float
    match_sources: list[str] = []  # exact_id, bm25, dense
    citation: CitationRef


class SearchResponse(BaseModel):
    hits: list[SearchHit]
    timings_ms: Timings = Timings()


class ApplicabilityCheckRequest(BaseModel):
    directive_id: str = Field(..., max_length=100)
    aircraft: AircraftConfig


class ApplicabilityCheckResponse(BaseModel):
    directive: Optional[DirectiveInfo] = None
    applicability: ApplicabilityResult
    revision: Optional[RevisionResult] = None
    warnings: list[str] = []
    disclaimer: str = DISCLAIMER


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


# --- added by API agent ---
class HealthResponse(BaseModel):
    status: str
    db: dict = {}
    modules: dict = {}
    llm_configured: bool = False


class DirectiveListItem(BaseModel):
    fr_docnum: Optional[str] = None
    docket: Optional[str] = None
    doc_class: Optional[str] = None
    title: Optional[str] = None
    publication_date: Optional[str] = None
    source: Optional[str] = None
    make: list[str] = []
    models: list[str] = []
    ad_number: Optional[str] = None
    sheet_rows: list[int] = []


class DirectiveListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[DirectiveListItem]


class DocumentMeta(BaseModel):
    fr_docnum: str
    title: Optional[str] = None
    fr_type: Optional[str] = None
    doc_class: Optional[str] = None
    publication_date: Optional[str] = None
    volume: Optional[int] = None
    start_page: Optional[int] = None
    end_page: Optional[int] = None
    dockets: list[str] = []
    pdf_url: Optional[str] = None
    xml_url: Optional[str] = None
    html_url: Optional[str] = None
    source: Optional[str] = None
    extraction_status: Optional[str] = None
    pdf_cached: bool = False
    page_count: int = 0


class SheetRow(BaseModel):
    row: int
    docket: Optional[str] = None
    fr_docnum: Optional[str] = None
    subject: Optional[str] = None
    status_raw: Optional[str] = None
    publish_date: Optional[str] = None
    make: Optional[str] = None
    models: list[str] = []
    ad_number: Optional[str] = None
    citation: Optional[str] = None
    summary: Optional[str] = None


class DirectiveDetail(BaseModel):
    query_id: str
    documents: list[DocumentMeta] = []
    sheet_rows: list[SheetRow] = []
    revision: Optional[RevisionResult] = None
    relations: list[dict] = []
    applicability_text: Optional[CitationRef] = None
    warnings: list[str] = []
    candidates: list[DirectiveInfo] = []


class PageResponse(BaseModel):
    fr_docnum: str
    pdf_page: int
    fr_page: Optional[int] = None
    text: str
    is_image_only: bool = False
