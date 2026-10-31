import type {
  ApplicabilityResult, CitationRef, DatasetHistory, DirectiveInfo, Enforceability,
  ProposedSupersession, RevisionResult,
} from "@/lib/types";
import { DocClassPill } from "./Badges";

const STAGE_LABEL: Record<string, string> = {
  PROPOSED_RULE: "Proposed rule (NPRM)",
  SUPPLEMENTAL_PROPOSAL: "Supplemental proposed rule (SNPRM)",
  WITHDRAWAL_NOTICE: "Withdrawal notice",
  CORRECTION: "Correction notice",
  FINAL_RULE: "Final rule",
  OTHER: "Other document type",
};
export const stageLabel = (s?: string | null) => (s ? STAGE_LABEL[s] ?? s : "Not reported");

const ENFORCE_LABEL: Record<Enforceability, string> = {
  NOT_VERIFIED: "Not verified",
  PROPOSAL_WITHDRAWN: "Proposal withdrawn — no requirement",
  FINAL_RULE_PUBLISHED_VERIFIED: "Final rule published (verified link) — later amendments not checked",
};

export function StagePill({ stage }: { stage?: string | null }) {
  if (!stage) return null;
  return (
    <span className="inline-block rounded border border-sky-500 bg-sky-50 px-2 py-0.5 text-xs font-semibold text-sky-900" data-testid="stage-pill">
      Regulatory stage: {stageLabel(stage)}
    </span>
  );
}

function applicabilityText(a?: ApplicabilityResult | null): { value: string; label: string } {
  const v = a?.value ?? "NOT_EVALUATED";
  const fallback: Record<string, string> = {
    APPLICABLE: "Applicable under the proposed rule",
    NOT_APPLICABLE: "Not applicable under the proposed rule",
    UNKNOWN: "Applicability not determined",
    NOT_EVALUATED: "Applicability not evaluated",
  };
  // UNKNOWN always reads as "not determined" regardless of backend label.
  const label = v === "UNKNOWN" ? "Applicability not determined" : a?.label || fallback[v] || v;
  return { value: v.replaceAll("_", " "), label };
}

const cell = "rounded-lg border border-slate-300 bg-white p-3";
const cap = "text-xs font-semibold uppercase tracking-wide text-slate-600";

export function StatusStrip({ directive, revision, applicability }: {
  directive?: DirectiveInfo | null; revision?: RevisionResult | null; applicability?: ApplicabilityResult | null;
}) {
  const stage = revision?.regulatory_stage || directive?.regulatory_stage || null;
  const app = applicabilityText(applicability);
  const basis = applicability?.basis;
  const enf = revision?.enforceability;
  const recs = directive?.record_ids ?? [];
  return (
    <section aria-label="Status" className="space-y-2" data-testid="status-strip">
      {(recs.length > 0 || directive?.source_url) && (
        <div className="flex flex-wrap items-center gap-3">
          {recs.length > 0 && <span className="font-mono text-lg font-bold" data-testid="record-ids">Record {recs.join(", ")}</span>}
          {directive?.source_url && <a className="text-sm text-sky-800 underline" href={directive.source_url} target="_blank" rel="noreferrer">Official source (federalregister.gov)</a>}
        </div>
      )}
      <div className="grid gap-2 md:grid-cols-3">
        <div className={`${cell} border-sky-400`} data-testid="cell-stage">
          <div className={cap}>Regulatory stage</div>
          <div className="mt-1 text-base font-bold text-sky-900">{stageLabel(stage)}</div>
          <div className="text-xs text-slate-700">A proposal is not an enforceable AD.</div>
        </div>
        <div className={`${cell} border-slate-400`} data-testid="cell-applicability" data-value={applicability?.value ?? "NOT_EVALUATED"}>
          <div className={cap}>{basis === "FINAL_RULE" ? "Final-rule applicability" : "Proposed applicability"}</div>
          <div className="mt-1 text-base font-bold text-slate-900">{app.value}</div>
          <div className="text-sm text-slate-800">{app.label}</div>
          {basis && <div className="text-xs text-slate-600">Basis: {basis.replaceAll("_", " ").toLowerCase()}</div>}
        </div>
        <div className={`${cell} border-amber-400`} data-testid="cell-enforceability">
          <div className={cap}>Current enforceability</div>
          <div className="mt-1 text-base font-bold text-amber-950">{enf ? ENFORCE_LABEL[enf] ?? enf : ENFORCE_LABEL.NOT_VERIFIED}</div>
        </div>
      </div>
    </section>
  );
}

export function citationLine(c: CitationRef): string {
  const id = c.record_ids?.[0] || c.docket_number || `FR Doc. ${c.fr_docnum}`;
  return [id, c.federal_register_citation, c.section].filter(Boolean).join(" · ");
}

export function CitationLine({ c }: { c: CitationRef }) {
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <span className="font-mono text-xs font-semibold" data-testid="citation-line">{citationLine(c)}</span>
      {c.source_url && <a className="text-xs text-sky-800 underline" href={c.source_url} target="_blank" rel="noreferrer">source</a>}
    </span>
  );
}

const DS_LABEL: Record<string, string> = {
  LATEST_IN_DATASET: "Latest in dataset",
  SUPERSEDED_IN_DATASET: "Superseded in dataset",
  SINGLE_PUBLICATION: "Single publication",
  NOT_IN_DATASET: "Not in dataset",
};

export function HistoryTimeline({ history: h }: { history?: DatasetHistory | null }) {
  if (!h) return null;
  const items = h.history ?? [];
  return (
    <div className="mt-3" data-testid="history">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded border border-slate-500 bg-slate-100 px-2 py-0.5 text-xs font-semibold" data-testid="dataset-status">{DS_LABEL[h.dataset_status] ?? h.dataset_status}</span>
        {h.docket && <span className="font-mono text-xs text-slate-700">Docket {h.docket}</span>}
        {h.versions_total > 1 && <span className="text-xs text-slate-700">version {h.this_version ?? "?"} of {h.versions_total}</span>}
      </div>
      {h.note && <p className="mt-1 text-xs text-slate-700">{h.note}</p>}
      {(h.warnings ?? []).length > 0 && (
        <ul className="mt-1 list-disc pl-5 text-xs text-amber-950">{h.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
      )}
      {items.length > 0 && (
        <ol className="mt-2 space-y-1 border-l-2 border-slate-300 pl-3" aria-label="Dataset history timeline">
          {items.map((e, i) => (
            <li key={`${e.record_id}-${i}`} className={`rounded px-2 py-1 text-sm ${e.is_latest ? "border-2 border-sky-600 bg-sky-50" : "border border-slate-200"}`} data-latest={e.is_latest}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono font-semibold">{e.record_id}</span>
                <span className="text-xs text-slate-700">{e.publish_date ?? "date n/a"}</span>
                {e.doc_class && <DocClassPill docClass={e.doc_class} />}
                {e.fr_docnum && <span className="font-mono text-xs">FR Doc. {e.fr_docnum}</span>}
              </div>
              {e.is_latest && <div className="mt-0.5 text-xs font-semibold text-sky-900">Latest in supplied dataset (not legal status)</div>}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

export function Supersessions({ items }: { items?: ProposedSupersession[] | null }) {
  if (!items || items.length === 0) return null;
  return (
    <ul className="mt-3 space-y-1" aria-label="Proposed supersessions">
      {items.map((s, i) => (
        <li key={i} className="rounded border border-dashed border-slate-400 bg-slate-50 px-2 py-1 text-sm" data-testid="supersession">
          {s.operative_supersession_verified ? (
            <b>Supersession stated in verified final rule: AD {s.ad_number}</b>
          ) : (
            <b>Proposes to supersede AD {s.ad_number} — proposal, not an operative supersession</b>
          )}
          <div className="text-xs text-slate-700">
            Source: {s.source === "organiser_supersedes_ad_field" ? "organiser field" : "document text"}
            {s.evidence?.source_url && <> · <a className="text-sky-800 underline" href={s.evidence.source_url} target="_blank" rel="noreferrer">evidence</a></>}
          </div>
          {s.evidence?.quote && <blockquote className="mt-1 border-l-4 border-slate-400 p-1 font-mono text-xs">{s.evidence.quote}</blockquote>}
        </li>
      ))}
    </ul>
  );
}

export function StatusChips({ flags }: { flags?: string[] | null }) {
  if (!flags || flags.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1" aria-label="Status flags">
      {flags.map((f) => <span key={f} className="rounded-full border border-slate-400 bg-slate-100 px-2 py-0.5 text-xs text-slate-800">{f.replaceAll("_", " ").toLowerCase()}</span>)}
    </div>
  );
}
