import type {
  ApplicabilityResult, CitationRef, DatasetHistory, DirectiveInfo, Enforceability,
  ProposedSupersession, RevisionResult,
} from "@/lib/types";
import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/cn";
import { Badge, Mono } from "@/components/ui";
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

const CLASS_STAGE: Record<string, string> = {
  NPRM: "PROPOSED_RULE", SNPRM: "SUPPLEMENTAL_PROPOSAL", WITHDRAWAL: "WITHDRAWAL_NOTICE", CORRECTION: "CORRECTION", FINAL_RULE: "FINAL_RULE", OTHER: "OTHER",
};
export const stageFromDocClass = (c?: string | null) => (c ? CLASS_STAGE[c.toUpperCase()] ?? null : null);

export function StagePill({ stage, compact }: { stage?: string | null; compact?: boolean }) {
  if (!stage) return null;
  return (
    <Badge tone={stage === "FINAL_RULE" ? "violet" : stage === "PROPOSED_RULE" || stage === "SUPPLEMENTAL_PROPOSAL" ? "blue" : "slate"} className="font-semibold" data-testid="stage-pill">
      {compact ? "" : "Regulatory stage: "}{stageLabel(stage)}
    </Badge>
  );
}

export function applicabilityText(a?: ApplicabilityResult | null): { value: string; label: string } {
  const v = a?.value ?? "NOT_EVALUATED";
  const fallback: Record<string, string> = {
    APPLICABLE: a?.basis === "FINAL_RULE" ? "Applicable under the published final rule" : "Applicable under the proposed rule",
    NOT_APPLICABLE: a?.basis === "FINAL_RULE" ? "Not applicable under the published final rule" : "Not applicable under the proposed rule",
    UNKNOWN: "Applicability not determined",
    NOT_EVALUATED: "Applicability not evaluated",
  };
  // UNKNOWN always reads as "not determined" regardless of backend label.
  const label = v === "UNKNOWN" ? "Applicability not determined" : a?.label || fallback[v] || v;
  return { value: v.replaceAll("_", " "), label };
}

export function conditionCount(a?: ApplicabilityResult | null): { met: number; total: number } | null {
  const steps = (a?.explanation ?? []).filter((s) => s.outcome !== "INFO");
  if (steps.length === 0) return null;
  return { met: steps.filter((s) => s.outcome === "TRUE").length, total: steps.length };
}

const cell = "flex flex-col rounded-lg border bg-white p-3 shadow-card";
const cap = "text-[11px] font-semibold uppercase tracking-wide text-slate-500";

function AppCell({ a, title, testId }: { a?: ApplicabilityResult | null; title: string; testId: string }) {
  const app = applicabilityText(a);
  const basis = a?.basis;
  const v = a?.value ?? "NOT_EVALUATED";
  const tone = v === "UNKNOWN" ? "border-amber-400 bg-amber-50/60 border-dashed" : v === "APPLICABLE" ? "border-blue-500 bg-blue-50/60" : "border-slate-300";
  return (
    <div className={cn(cell, tone)} data-testid={testId} data-value={v}>
      <div className={cap}>{title}</div>
      <div className="mt-1 font-mono text-xs font-semibold text-slate-600">{app.value}</div>
      <div className={cn("text-base font-semibold", v === "UNKNOWN" ? "text-amber-950" : v === "APPLICABLE" ? "text-blue-900" : "text-slate-900")}>{app.label}</div>
      {basis && <div className="mt-auto pt-2 text-xs text-slate-600">Basis: {basis.replaceAll("_", " ").toLowerCase()}</div>}
    </div>
  );
}

export function StatusStrip({ directive, revision, applicability, finalApplicability, finalDocnum }: {
  directive?: DirectiveInfo | null; revision?: RevisionResult | null; applicability?: ApplicabilityResult | null;
  finalApplicability?: ApplicabilityResult | null; finalDocnum?: string | null;
}) {
  // metadata-only record (no FR document): the backend's stage is a default, not a determination
  const metaOnly = !!directive && !directive.fr_docnum;
  const stage = metaOnly ? null : revision?.regulatory_stage || directive?.regulatory_stage || null;
  const enf = revision?.enforceability;
  return (
    <section aria-label="Status" data-testid="status-strip">
      <div className={`grid gap-3 ${finalApplicability ? "md:grid-cols-2 xl:grid-cols-4" : "md:grid-cols-3"}`}>
        <div className={cn(cell, "border-slate-300")} data-testid="cell-stage">
          <div className={cap}>Regulatory stage</div>
          <div className="mt-1 text-base font-semibold text-slate-900">{metaOnly ? "Not determined" : stageLabel(stage)}</div>
          {metaOnly && <div className="mt-auto pt-2 text-xs text-slate-600">No Federal Register text for this record; stage not verified.</div>}
          {(stage === "PROPOSED_RULE" || stage === "SUPPLEMENTAL_PROPOSAL") && <div className="mt-auto pt-2 text-xs text-slate-600">A proposal is not an enforceable AD.</div>}
          {stage === "WITHDRAWAL_NOTICE" && <div className="mt-auto pt-2 text-xs text-slate-600">A withdrawal notice imposes no requirement.</div>}
        </div>
        {finalApplicability ? (
          <>
            <AppCell a={applicability} title="Proposed rule" testId="cell-applicability" />
            <AppCell a={finalApplicability} title={`Published final rule (FR ${finalDocnum ?? finalApplicability.evaluated_document ?? ""})`.replace(" )", ")")} testId="cell-final-applicability" />
          </>
        ) : (
          <AppCell a={applicability} title={applicability?.basis === "FINAL_RULE" ? "Final-rule applicability" : "Proposed applicability"} testId="cell-applicability" />
        )}
        <div className={cn(cell, "border-amber-400 bg-amber-50/60")} data-testid="cell-enforceability">
          <div className={cap}>Current enforceability</div>
          <div className="mt-1 flex items-start gap-1.5 text-base font-semibold text-amber-950"><AlertTriangle size={16} className="mt-1 shrink-0" aria-hidden />{enf ? ENFORCE_LABEL[enf] ?? enf : ENFORCE_LABEL.NOT_VERIFIED}</div>
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
      <span className="rounded-md border border-slate-200 bg-slate-50 px-1.5 py-0.5 font-mono text-xs font-medium text-slate-800" data-testid="citation-line">{citationLine(c)}</span>
      {c.source_url && <a className="text-xs text-blue-600 underline hover:text-blue-700" href={c.source_url} target="_blank" rel="noreferrer">source</a>}
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
        <Badge tone="slate" className="font-semibold" data-testid="dataset-status">{DS_LABEL[h.dataset_status] ?? h.dataset_status}</Badge>
        {h.docket && <Mono className="text-xs text-slate-700">Docket {h.docket}</Mono>}
        {h.versions_total > 1 && <span className="text-xs text-slate-700">version {h.this_version ?? "?"} of {h.versions_total}</span>}
      </div>
      {h.note && <p className="mt-1 text-xs text-slate-600">{h.note}</p>}
      {(h.warnings ?? []).length > 0 && (
        <ul className="mt-1 list-disc pl-5 text-xs text-amber-900">{h.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
      )}
      {items.length > 0 && (
        <ol className="mt-3 space-y-2 border-l-2 border-slate-200 pl-4" aria-label="Dataset history timeline">
          {items.map((e, i) => (
            <li key={`${e.record_id}-${i}`} className={cn("relative rounded-lg border px-3 py-2 text-sm", e.is_latest ? "border-blue-300 bg-blue-50/50" : "border-slate-200 bg-white")} data-latest={e.is_latest}>
              <span aria-hidden className={cn("absolute -left-[22px] top-3.5 h-2.5 w-2.5 rounded-full border-2 border-white", e.is_latest ? "bg-blue-600" : "bg-slate-400")} />
              <div className="flex flex-wrap items-center gap-2">
                <Mono className="font-semibold">{e.record_id}</Mono>
                <span className="text-xs text-slate-600">{e.publish_date ?? "date n/a"}</span>
                {e.doc_class && <DocClassPill docClass={e.doc_class} />}
                {e.fr_docnum && <Mono className="text-xs text-slate-700">FR Doc. {e.fr_docnum}</Mono>}
              </div>
              {e.is_latest && <div className="mt-0.5 text-xs font-medium text-blue-800">Latest in supplied dataset (not legal status)</div>}
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
    <ul className="mt-3 space-y-2" aria-label="Proposed supersessions">
      {items.map((s, i) => (
        <li key={i} className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-3 py-2 text-sm" data-testid="supersession">
          {s.operative_supersession_verified ? (
            <b>Supersession stated in verified final rule: AD {s.ad_number}</b>
          ) : (
            <b>Proposes to supersede AD {s.ad_number} — proposal, not an operative supersession</b>
          )}
          <div className="text-xs text-slate-600">
            Source: {s.source === "organiser_supersedes_ad_field" ? "organiser field" : "document text"}
            {s.evidence?.source_url && <> · <a className="text-blue-600 underline" href={s.evidence.source_url} target="_blank" rel="noreferrer">evidence</a></>}
          </div>
          {s.evidence?.quote && <blockquote className="mt-1 border-l-4 border-slate-300 pl-2 font-mono text-xs">{s.evidence.quote}</blockquote>}
        </li>
      ))}
    </ul>
  );
}

export function StatusChips({ flags }: { flags?: string[] | null }) {
  if (!flags || flags.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1" aria-label="Status flags">
      {flags.map((f) => <Badge key={f} tone="outline" className="rounded-full">{f.replaceAll("_", " ").toLowerCase()}</Badge>)}
    </div>
  );
}
