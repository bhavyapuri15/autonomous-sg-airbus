import type {
  ApplicabilityCheckRequest, ApplicabilityCheckResponse, DirectiveDetailResponse, DirectiveListResponse, LooseRecord, QueryRequest,
  QueryResponse, SearchRequest, SearchResponse,
} from "./types";

export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  kind: "network" | "timeout" | "http" | "parse";
  status?: number;
  detail?: string;
  constructor(kind: ApiError["kind"], message: string, status?: number, detail?: string) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init: RequestInit = {}, timeoutMs = 30000): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init.headers || {}) },
      signal: ctrl.signal,
      cache: "no-store",
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") {
      throw new ApiError("timeout", `Request to ${path} timed out after ${timeoutMs / 1000}s`);
    }
    throw new ApiError("network", `Cannot reach the API at ${API_BASE}`, undefined, (e as Error).message);
  } finally {
    clearTimeout(timer);
  }
  if (!res.ok) {
    let detail: string | undefined;
    try {
      const b = await res.json();
      detail = b?.detail ? (typeof b.detail === "string" ? b.detail : JSON.stringify(b.detail)) : b?.error;
    } catch { /* ignore */ }
    throw new ApiError("http", `API returned HTTP ${res.status} for ${path}`, res.status, detail);
  }
  try {
    return (await res.json()) as T;
  } catch {
    throw new ApiError("parse", `API returned invalid JSON for ${path}`, res.status);
  }
}

const qs = (p: Record<string, string | number | undefined | null>) => {
  const u = new URLSearchParams();
  Object.entries(p).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") u.set(k, String(v)); });
  const s = u.toString();
  return s ? `?${s}` : "";
};

export const api = {
  health: () => request<LooseRecord>("/health", {}, 5000),
  search: (b: SearchRequest) => request<SearchResponse>("/search", { method: "POST", body: JSON.stringify(b) }),
  query: (b: QueryRequest) => request<QueryResponse>("/query", { method: "POST", body: JSON.stringify(b) }, 90000),
  applicability: (b: ApplicabilityCheckRequest) =>
    request<ApplicabilityCheckResponse>("/applicability/check", { method: "POST", body: JSON.stringify(b) }),
  directives: (p: { q?: string; make?: string; doc_class?: string; source?: string; limit?: number; offset?: number }) =>
    request<DirectiveListResponse>(`/directives${qs(p)}`),
  directive: (id: string) => request<DirectiveDetailResponse>(`/directives/${encodeURIComponent(id)}`),
  document: (docnum: string) => request<LooseRecord>(`/documents/${encodeURIComponent(docnum)}`),
  page: (docnum: string, pdfPage: number) =>
    request<LooseRecord>(`/documents/${encodeURIComponent(docnum)}/pages/${pdfPage}`),
  pdfUrl: (docnum: string) => `${API_BASE}/documents/${encodeURIComponent(docnum)}/pdf`,
  evaluationRuns: () => request<unknown>("/evaluation/runs"),
  evaluation: () => request<unknown>("/evaluation/summary"),
};
