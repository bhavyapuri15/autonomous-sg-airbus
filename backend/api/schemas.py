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
    # Organiser citation format (update 31 Oct): record_id + FR citation and page + section.
    record_ids: list[str] = []                       # stable organiser record_id(s) (NPRM-NNN) mapped to fr_docnum
    docket_number: Optional[str] = None
    federal_register_citation: Optional[str] = None  # e.g. "91 FR 66022" (volume FR printed page of the quote)
    section: Optional[str] = None                    # human label, e.g. "(c) Applicability"
    source_url: Optional[str] = None                 # official federalregister.gov document URL


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
    basis: Literal["PROPOSED_RULE", "FINAL_RULE", "UNKNOWN"] = "UNKNOWN"
    label: Optional[str] = None   # e.g. "Applicable under the proposed rule" / "Not applicable under the proposed rule"


class RegulatoryStage(str, Enum):
    PROPOSED_RULE = "PROPOSED_RULE"                  # NPRM
    SUPPLEMENTAL_PROPOSAL = "SUPPLEMENTAL_PROPOSAL"  # SNPRM
    WITHDRAWAL_NOTICE = "WITHDRAWAL_NOTICE"
    CORRECTION = "CORRECTION"
    FINAL_RULE = "FINAL_RULE"                        # FR final-rule document (found by the verified lookup)
    OTHER = "OTHER"


class Enforceability(str, Enum):
    NOT_VERIFIED = "NOT_VERIFIED"                                    # default for every proposal
    PROPOSAL_WITHDRAWN = "PROPOSAL_WITHDRAWN"                        # VERIFIED withdrawal: imposes no requirement
    FINAL_RULE_PUBLISHED_VERIFIED = "FINAL_RULE_PUBLISHED_VERIFIED"  # VERIFIED final rule cites this proposal;
    #                                                                 later amendments/supersession NOT checked


class DatasetVersionEntry(BaseModel):
    record_id: str
    fr_docnum: Optional[str] = None
    publish_date: Optional[str] = None
    doc_class: Optional[str] = None
    version: Optional[int] = None
    is_latest: bool = False


class DatasetHistory(BaseModel):
    """Organiser revision_chains view: versions of one docket inside the supplied dataset (not legal currency)."""
    docket: Optional[str] = None
    versions_total: int = 1
    this_version: Optional[int] = None
    dataset_status: Literal["LATEST_IN_DATASET", "SUPERSEDED_IN_DATASET", "SINGLE_PUBLICATION", "NOT_IN_DATASET"] = "NOT_IN_DATASET"
    latest_record_id: Optional[str] = None
    history: list[DatasetVersionEntry] = []          # chronological (publish_date, version)
    source: str = "organiser revision_chains worksheet (challenge4_ad_index.xlsx)"
    note: str = "Latest publish date = latest version in the supplied dataset; this does not establish legal enforceability."
    warnings: list[str] = []                         # ties, missing dates, disagreement with evidence graph


class ProposedSupersession(BaseModel):
    ad_number: str
    source: Literal["organiser_supersedes_ad_field", "document_text"]
    evidence: Optional[CitationRef] = None
    operative_supersession_verified: bool = False    # True only if a VERIFIED final rule's text supersedes it
    sources: list[str] = []                          # every source that lists this AD (after de-duplication)
    additional_evidence: list[CitationRef] = []      # evidence from the other source(s); `evidence` is the preferred one
    operative_final_rule: Optional[str] = None       # fr_docnum of the VERIFIED final rule whose text supersedes it


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
    regulatory_stage: RegulatoryStage = RegulatoryStage.OTHER
    enforceability: Enforceability = Enforceability.NOT_VERIFIED
    status_flags: list[str] = []   # subset of LATEST_IN_DATASET, SUPERSEDED_IN_DATASET, WITHDRAWN_IN_DATASET, CORRECTED,
    #                                FINAL_RULE_VERIFIED, CURRENT_AUTHORITATIVE_STATUS_UNKNOWN
    dataset_history: Optional[DatasetHistory] = None
    proposed_supersedes: list[ProposedSupersession] = []


class DirectiveInfo(BaseModel):
    fr_docnum: Optional[str] = None
    docket: Optional[str] = None
    doc_class: Optional[str] = None
    title: Optional[str] = None
    publication_date: Optional[str] = None
    citation: Optional[str] = None
    sheet_rows: list[int] = []
    pdf_url: Optional[str] = None
    record_ids: list[str] = []
    regulatory_stage: Optional[str] = None
    source_url: Optional[str] = None


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
    final_rule_applicability: Optional[ApplicabilityResult] = None
    final_rule_docnum: Optional[str] = None
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
    final_rule_applicability: Optional[ApplicabilityResult] = None
    final_rule_docnum: Optional[str] = None
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
    record_ids: list[str] = []


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
    record_id: Optional[str] = None


class DirectiveDetail(BaseModel):
    query_id: str
    documents: list[DocumentMeta] = []
    sheet_rows: list[SheetRow] = []
    revision: Optional[RevisionResult] = None
    relations: list[dict] = []
    applicability_text: Optional[CitationRef] = None
    warnings: list[str] = []
    candidates: list[DirectiveInfo] = []
    record_ids: list[str] = []


class PageResponse(BaseModel):
    fr_docnum: str
    pdf_page: int
    fr_page: Optional[int] = None
    text: str
    is_image_only: bool = False
