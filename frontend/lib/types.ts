// Mirrors backend/api/schemas.py exactly. Do not diverge; report ambiguities instead.

export const DISCLAIMER_FALLBACK =
  "Decision support only. Not a certified airworthiness or compliance determination. Verify against the official FAA source.";

export type AnswerStatus = "ANSWERED" | "ABSTAINED" | "NEEDS_MORE_INFORMATION";
export type ApplicabilityValue = "APPLICABLE" | "NOT_APPLICABLE" | "UNKNOWN" | "NOT_EVALUATED";
export type RevisionStatus = "WITHDRAWN" | "SUPPLEMENTED" | "FINALIZED" | "PROPOSAL_STATUS_UNVERIFIED";
export type SourceTier = "FR_FULL_TEXT" | "SHEET_METADATA" | "SHEET_EMBEDDED_TEXT";

export interface CitationRef {
  citation_id: string;
  fr_docnum: string;
  section_path?: string | null;
  label?: string | null;
  fr_page?: number | null;
  pdf_page?: number | null;
  quote: string;
  start?: number | null;
  end?: number | null;
  source_tier: SourceTier;
  pdf_url?: string | null;
  xml_url?: string | null;
  sheet_row?: number | null;
}

export interface Claim {
  text: string;
  citations: CitationRef[];
}

export type StepOutcome = "TRUE" | "FALSE" | "UNKNOWN" | "INFO";

export interface ExplanationStep {
  step: string;
  outcome: StepOutcome;
  detail: string;
  evidence: CitationRef[];
}

export type RuleParseStatus = "FULL" | "PARTIAL" | "FAILED";

export interface ApplicabilityResult {
  value: ApplicabilityValue;
  template_text?: string | null;
  explanation: ExplanationStep[];
  missing: string[];
  rule_parse_status?: RuleParseStatus | null;
  evaluated_document?: string | null;
  applicability_text?: CitationRef | null;
}

export type EdgeType =
  | "WITHDRAWS" | "SUPPLEMENTS" | "CORRECTS" | "FINALIZES"
  | "PROPOSES_TO_SUPERSEDE" | "SUPERSEDES" | "SAME_DOCKET";
export type EdgeConfidence = "VERIFIED" | "CANDIDATE";

export interface RevisionEdge {
  src: string;
  dst: string;
  type: EdgeType;
  confidence: EdgeConfidence;
  evidence: CitationRef[];
  note?: string | null;
}

export interface RevisionResult {
  status: RevisionStatus;
  current_authoritative_status_verified: boolean;
  edges: RevisionEdge[];
  template_text?: string | null;
  latest_in_dataset?: string | null;
}

export interface DirectiveInfo {
  fr_docnum?: string | null;
  docket?: string | null;
  doc_class?: string | null;
  title?: string | null;
  publication_date?: string | null;
  citation?: string | null;
  sheet_rows: number[];
  pdf_url?: string | null;
}

export interface RejectedClaim {
  text: string;
  failed_check: string;
}

export interface VerificationInfo {
  mode: "llm" | "extractive" | "none";
  claims_generated: number;
  claims_verified: number;
  claims_rejected: RejectedClaim[];
}

export interface Timings {
  retrieval: number;
  engines: number;
  generation: number;
  verification: number;
  total: number;
}

export interface AircraftConfig {
  model?: string | null;
  serial?: string | null;
  make?: string | null;
  facts: Record<string, boolean>;
}

export interface QueryRequest {
  question: string;
  directive_id?: string | null;
  aircraft?: AircraftConfig | null;
  use_llm: boolean;
}

export interface QueryResponse {
  status: AnswerStatus;
  answer_claims: Claim[];
  applicability: ApplicabilityResult;
  revision?: RevisionResult | null;
  directive?: DirectiveInfo | null;
  candidates: DirectiveInfo[];
  citations: CitationRef[];
  warnings: string[];
  abstention_reason?: string | null;
  missing_information: string[];
  verification: VerificationInfo;
  timings_ms: Timings;
  disclaimer: string;
}

export interface SearchRequest {
  query: string;
  top_k?: number;
  filters?: Record<string, string>;
}

export interface SearchHit {
  chunk_id: string;
  fr_docnum: string;
  docket?: string | null;
  title?: string | null;
  doc_class?: string | null;
  section_path?: string | null;
  text: string;
  score: number;
  match_sources: string[];
  citation: CitationRef;
}

export interface SearchResponse {
  hits: SearchHit[];
  timings_ms: Timings;
}

export interface ApplicabilityCheckRequest {
  directive_id: string;
  aircraft: AircraftConfig;
}

export interface ApplicabilityCheckResponse {
  directive?: DirectiveInfo | null;
  applicability: ApplicabilityResult;
  revision?: RevisionResult | null;
  warnings: string[];
  disclaimer: string;
}

export interface ErrorResponse {
  error: string;
  detail?: string | null;
}

// ---- Endpoints whose shapes are NOT fixed in schemas.py. Deliberately loose; the UI renders defensively. ----
export type LooseRecord = Record<string, unknown>;

export interface DirectiveListResponseLoose {
  items?: LooseRecord[];
  total?: number;
  [k: string]: unknown;
}

export interface PageTextResponseLoose {
  text?: string;
  fr_page?: number | null;
  pdf_page?: number;
  [k: string]: unknown;
}

export type EvaluationSummary = LooseRecord;
