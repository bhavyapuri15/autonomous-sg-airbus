"use client";
import { useState } from "react";
import type { ApplicabilityResult, CitationRef, QueryResponse, RevisionEdge, RevisionResult, StepOutcome } from "@/lib/types";
import type { ReactNode } from "react";
import { AlertTriangle, BookOpen, Quote, Ban, CheckCircle2, Copy, ExternalLink, HelpCircle, History, Info, ListChecks, ShieldCheck, XCircle } from "lucide-react";
import { cn } from "@/lib/cn";
import { Badge, Button, Card, CardTitle } from "@/components/ui";
import { ApplicabilityBadge, DocClassPill, TierBadge, pageLabel } from "./Badges";
import { Disclaimer } from "./Disclaimer";
import { FactsInput, needsFacts } from "./FactsInput";
import { CitationLine, citationLine, conditionCount, HistoryTimeline, StagePill, StatusChips, StatusStrip, Supersessions } from "./Provenance";

type Open = (c: CitationRef) => void;

function Banner({ tone, icon: Icon, children, testId = "status-banner" }: { tone: "blue" | "amber" | "red"; icon: typeof Info; children: ReactNode; testId?: string }) {
  const cls = { blue: "border-blue-300 bg-blue-50 text-blue-950", amber: "border-amber-400 bg-amber-50 text-amber-950", red: "border-red-300 bg-red-50 text-red-950" }[tone];
  return (
    <div role="status" className={cn("flex items-start gap-3 rounded-lg border p-3 text-sm", cls)} data-testid={testId}>
      <Icon size={18} className="mt-0.5 shrink-0" aria-hidden />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

function StatusBanner({ r, onPick }: { r: QueryResponse; onPick?: (id: string) => void }) {
  if (r.status === "ANSWERED")
    return (
      <Banner tone="blue" icon={ShieldCheck}>
        <b className="tracking-wide">ANSWERED</b> — every statement below is backed by a verified quote from the source.
      </Banner>
    );
  if (r.status === "NEEDS_MORE_INFORMATION")
    return (
      <Banner tone="amber" icon={HelpCircle}>
        <b className="tracking-wide">NEEDS MORE INFORMATION</b> — a determination cannot be made yet.
        {r.missing_information.length > 0 && (
          <ul className="mt-1 list-disc pl-5" data-testid="missing-info">
            {r.missing_information.map((m, i) => <li key={i}>{m}</li>)}
          </ul>
        )}
        <div className="mt-1 text-xs">Provide these in the aircraft configuration inputs above and submit again.</div>
        {r.candidates.length > 0 && <Candidates r={r} onPick={onPick} label="Matching directives (pick the one you mean)" />}
      </Banner>
    );
  return (
    <Banner tone="red" icon={Ban}>
      <b className="tracking-wide">ABSTAINED</b> — the system declined to answer rather than guess.
      {r.abstention_reason && <div className="mt-1">Reason: {r.abstention_reason}</div>}
      {r.abstention_reason === "SOURCE_TEXT_UNAVAILABLE" && (
        <div className="mt-1" data-testid="source-unavailable">Source text unavailable: the full Federal Register text for this directive is not in the indexed dataset, so no statement could be verified against a quote. Only spreadsheet metadata is shown below (not regulatory text).</div>
      )}
      {r.candidates.length > 0 && <Candidates r={r} onPick={onPick} label="Did you mean (these are DIFFERENT directives, not the one you asked for)" />}
    </Banner>
  );
}

function Candidates({ r, onPick, label }: { r: QueryResponse; onPick?: (id: string) => void; label: string }) {
  return (
    <div className="mt-2" data-testid="candidates">
      <div className="text-sm font-semibold">{label}</div>
      <div className="mt-1 flex flex-wrap gap-2">
        {r.candidates.map((c, i) => {
          const id = c.fr_docnum || c.docket || "";
          return (
            <button key={i} type="button" onClick={() => onPick?.(id)} title={c.title || ""}
              className="max-w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-left text-xs text-slate-800 hover:border-blue-500 hover:bg-blue-50">
              <span className="font-mono">{id}</span> {c.doc_class && <span className="text-slate-600">· {c.doc_class}</span>}
              {c.title && <span className="block max-w-[28rem] truncate text-slate-600">{c.title}</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function DirectiveHeader({ r }: { r: QueryResponse }) {
  const d = r.directive;
  if (!d) return null;
  const recs = d.record_ids ?? [];
  const src = d.source_url || d.pdf_url;
  return (
    <Card aria-label="Directive">
      <div className="flex flex-wrap items-center gap-2">
        {recs.length > 0 && <Badge tone="outline" className="px-2 py-1 font-mono text-sm font-semibold text-slate-900" data-testid="record-ids">Record {recs.join(", ")}</Badge>}
        <DocClassPill docClass={d.doc_class} />
        <StagePill stage={r.revision?.regulatory_stage || d.regulatory_stage} />
        {src && <a className="ml-auto inline-flex items-center gap-1 text-sm text-blue-600 hover:underline" href={src} target="_blank" rel="noreferrer">Official source<ExternalLink size={13} aria-hidden /></a>}
      </div>
      {d.title && <h3 className="mt-2 text-lg font-semibold leading-snug">{d.title}</h3>}
      <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
        {d.fr_docnum && <Badge tone="slate" className="font-mono">FR Doc. {d.fr_docnum}</Badge>}
        {d.docket && <Badge tone="slate" className="font-mono">Docket {d.docket}</Badge>}
        {d.citation && <Badge tone="slate" className="font-mono">{d.citation}</Badge>}
        {d.publication_date && <Badge tone="slate">Published {d.publication_date}</Badge>}
        {d.pdf_url && d.source_url && <a className="inline-flex items-center gap-1 px-1 text-blue-600 hover:underline" href={d.pdf_url} target="_blank" rel="noreferrer">Official FR PDF</a>}
      </div>
    </Card>
  );
}

const OUT: Record<StepOutcome, { Icon: typeof Info; label: string; cls: string }> = {
  TRUE: { Icon: CheckCircle2, label: "TRUE", cls: "text-blue-700" },
  FALSE: { Icon: XCircle, label: "FALSE", cls: "text-red-700" },
  UNKNOWN: { Icon: HelpCircle, label: "UNKNOWN", cls: "text-amber-700" },
  INFO: { Icon: Info, label: "INFO", cls: "text-slate-500" },
};

function EvidenceLink({ c, onOpen }: { c: CitationRef; onOpen: Open }) {
  return (
    <button type="button" onClick={() => onOpen(c)} className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-slate-50 px-1.5 py-0.5 font-mono text-xs text-slate-800 hover:border-blue-400 hover:bg-blue-50">
      evidence: {c.fr_docnum} · {pageLabel(c)}<ExternalLink size={11} aria-hidden />
    </button>
  );
}

function ApplicabilityCard({ a, title, testId, onOpen }: { a: ApplicabilityResult; title: string; testId: string; onOpen: Open }) {
  const cnt = conditionCount(a);
  return (
    <Card aria-label={title} data-testid={testId}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <CardTitle className="mb-0" icon={<ListChecks size={14} aria-hidden />}>{title}</CardTitle>
        {cnt && <Badge tone={a.value === "UNKNOWN" ? "amber" : "blue"} className="font-mono" data-testid="condition-count">{cnt.met}/{cnt.total} conditions met</Badge>}
      </div>
      <ApplicabilityBadge value={a.value} label={a.label} basis={a.basis} />
      {a.template_text && <p className="mt-2 text-sm">{a.template_text}</p>}
      <div className="mt-1 flex flex-wrap gap-x-4 text-xs text-slate-600">
        {a.rule_parse_status && <span>Rule parse status: <b className="font-mono">{a.rule_parse_status}</b>{a.rule_parse_status !== "FULL" && " (rule text was not fully machine-readable)"}</span>}
        {a.evaluated_document && <span>Evaluated document: <span className="font-mono">{a.evaluated_document}</span></span>}
      </div>
      {a.explanation.length > 0 && (
        <ol className="mt-3 space-y-2" aria-label="Explanation steps">
          {a.explanation.map((s, i) => {
            const o = OUT[s.outcome];
            return (
              <li key={i} className="flex gap-3 rounded-lg border border-slate-200 bg-slate-50/60 p-2.5 text-sm">
                <span className={cn("flex w-24 shrink-0 items-start gap-1 text-xs font-semibold", o.cls)}><o.Icon size={15} aria-hidden /> {o.label}</span>
                <div className="min-w-0">
                  <div className="font-medium">{s.step}</div>
                  <div className="text-slate-600">{s.detail}</div>
                  {s.evidence.length > 0 && <div className="mt-1 flex flex-wrap gap-1">{s.evidence.map((c, j) => <EvidenceLink key={j} c={c} onOpen={onOpen} />)}</div>}
                </div>
              </li>
            );
          })}
        </ol>
      )}
      {a.missing.length > 0 && (
        <div className="mt-3 rounded-lg border border-amber-300 bg-amber-50 p-2 text-sm text-amber-950">
          <b>Missing facts:</b> <span className="break-words font-mono text-xs">{a.missing.join(", ")}</span>
        </div>
      )}
      {a.applicability_text && (
        <figure className="mt-3">
          <figcaption className="text-xs font-semibold uppercase tracking-wide text-slate-500">Source text for human review</figcaption>
          <blockquote className="mt-1 whitespace-pre-wrap rounded-lg border-l-4 border-yellow-300 bg-slate-50 p-2 font-mono text-xs">{a.applicability_text.quote}</blockquote>
          <div className="mt-1"><EvidenceLink c={a.applicability_text} onOpen={onOpen} /></div>
        </figure>
      )}
    </Card>
  );
}

function Edge({ e }: { e: RevisionEdge }) {
  const verified = e.confidence === "VERIFIED";
  return (
    <li className={cn("rounded-lg border px-3 py-1.5 text-sm", verified ? "border-slate-300 bg-white" : "border-dashed border-slate-300 bg-slate-50 text-slate-700")} data-confidence={e.confidence}>
      <span className="font-mono">{e.src}</span> <b>{e.type.replaceAll("_", " ")}</b> <span className="font-mono">{e.dst}</span>{" "}
      {verified ? <span className="text-xs font-semibold text-blue-800">[verified]</span> : <span className="text-xs font-semibold text-amber-800">[unverified — relationship not confirmed by text]</span>}
      {e.note && <div className="text-xs">{e.note}</div>}
    </li>
  );
}

export function RevisionCard({ revision: v }: { revision?: RevisionResult | null }) {
  if (!v) return null;
  return (
    <Card aria-label="Revision status">
      <CardTitle icon={<History size={14} aria-hidden />}>Revision status (within dataset)</CardTitle>
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="slate" className="font-mono text-sm font-semibold">{v.status}</Badge>
        {!v.current_authoritative_status_verified && (
          <Badge tone="amber" className="border-2 font-semibold" data-testid="not-verified-badge">
            Current authoritative status NOT verified
          </Badge>
        )}
      </div>
      {v.template_text && <p className="mt-2 text-sm">{v.template_text}</p>}
      {v.edges.length > 0 && <ul className="mt-2 space-y-1" aria-label="Revision edges">{v.edges.map((e, i) => <Edge key={i} e={e} />)}</ul>}
      <StatusChips flags={v.status_flags} />
      <HistoryTimeline history={v.dataset_history} />
      <Supersessions items={v.proposed_supersedes} />
      {v.latest_in_dataset && (
        <p className="mt-2 text-xs text-slate-600">Latest document in dataset: <span className="font-mono">{v.latest_in_dataset}</span> (a dataset fact, not a statement of current legal status)</p>
      )}
    </Card>
  );
}

function Verification({ r }: { r: QueryResponse }) {
  const v = r.verification, t = r.timings_ms;
  const [open, setOpen] = useState(false);
  return (
    <Card aria-label="Verification" className="text-sm">
      <CardTitle icon={<ShieldCheck size={14} aria-hidden />}>Verification</CardTitle>
      <div className="flex flex-wrap gap-x-6 gap-y-1">
        <span>Mode: <b className="font-mono">{v.mode}</b></span>
        <span>Claims generated: <b>{v.claims_generated}</b></span>
        <span>Verified: <b>{v.claims_verified}</b></span>
        <span>Rejected: <b>{v.claims_rejected.length}</b></span>
      </div>
      <div className="mt-1 font-mono text-xs text-slate-500">
        retrieval {t.retrieval}ms · engines {t.engines}ms · generation {t.generation}ms · verification {t.verification}ms · total {t.total}ms
      </div>
      {v.claims_rejected.length > 0 && (
        <div className="mt-2">
          <button className="text-xs text-blue-600 underline" aria-expanded={open} onClick={() => setOpen(!open)}>
            {open ? "Hide" : "Show"} rejected claims ({v.claims_rejected.length})
          </button>
          {open && (
            <ul className="mt-1 space-y-1">
              {v.claims_rejected.map((c, i) => (
                <li key={i} className="rounded-md bg-slate-50 p-1.5 text-xs"><span className="font-mono text-slate-700">{c.failed_check}</span>: {c.text}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Card>
  );
}

function CopyButton({ text }: { text: string }) {
  const [done, setDone] = useState(false);
  return (
    <Button size="sm" onClick={() => { navigator.clipboard?.writeText(text).then(() => { setDone(true); setTimeout(() => setDone(false), 1500); }).catch(() => {}); }}>
      <Copy size={12} aria-hidden />{done ? "Copied" : "Copy citation"}
    </Button>
  );
}

export function AnswerPanel({ response: r, onOpenCitation, onPickCandidate, onRecheck }: {
  response: QueryResponse; onOpenCitation: Open; onPickCandidate?: (id: string) => void;
  onRecheck?: (facts: Record<string, boolean>) => void;
}) {
  const factKeys = onRecheck ? needsFacts(r) : [];
  // Global citation numbering: response.citations first, then any claim citations not already listed.
  const all: CitationRef[] = [...r.citations];
  const idx = (c: CitationRef) => {
    let i = all.findIndex((x) => x.citation_id === c.citation_id);
    if (i < 0) { all.push(c); i = all.length - 1; }
    return i + 1;
  };
  const claims = r.answer_claims.map((cl) => ({ cl, nums: cl.citations.map((c) => ({ c, n: idx(c) })) }));

  return (
    <div className="space-y-4" data-testid="answer-panel">
      <StatusBanner r={r} onPick={onPickCandidate} />
      <DirectiveHeader r={r} />
      <StatusStrip directive={r.directive} revision={r.revision} applicability={r.applicability} finalApplicability={r.final_rule_applicability} finalDocnum={r.final_rule_docnum} />
      {r.final_rule_applicability ? (
        <div className="grid gap-4 2xl:grid-cols-2" data-testid="applicability-pair">
          <ApplicabilityCard a={r.applicability} title="Proposed rule" testId="card-proposed" onOpen={onOpenCitation} />
          <ApplicabilityCard a={r.final_rule_applicability} title={`Published final rule (FR ${r.final_rule_docnum ?? r.final_rule_applicability.evaluated_document ?? ""})`.replace(" )", ")")} testId="card-final" onOpen={onOpenCitation} />
        </div>
      ) : (
        <ApplicabilityCard a={r.applicability} title="Applicability" testId="card-proposed" onOpen={onOpenCitation} />
      )}
      {onRecheck && factKeys.length > 0 && <FactsInput key={factKeys.join("|")} missing={factKeys} onRecheck={onRecheck} />}
      <RevisionCard revision={r.revision} />
      {claims.length > 0 && (
        <Card aria-label="Answer claims">
          <CardTitle icon={<Quote size={14} aria-hidden />}>Answer (verified statements)</CardTitle>
          <ul className="space-y-2">
            {claims.map(({ cl, nums }, i) => (
              <li key={i} className="text-sm leading-relaxed">
                {cl.text}
                {nums.map(({ c, n }, j) => (
                  <sup key={j}>
                    <button type="button" aria-label={`Open citation ${n}`} onClick={() => onOpenCitation(c)} className="ml-0.5 rounded px-0.5 font-semibold text-blue-600 hover:bg-blue-50 hover:underline">[{n}]</button>
                  </sup>
                ))}
              </li>
            ))}
          </ul>
        </Card>
      )}
      {all.length > 0 && (
        <Card aria-label="Citations">
          <CardTitle icon={<BookOpen size={14} aria-hidden />}>Citations</CardTitle>
          <ol className="space-y-3">
            {all.map((c, i) => (
              <li key={c.citation_id} className="rounded-lg border border-slate-200 p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold">[{i + 1}]</span>
                  <CitationLine c={c} />
                  <span className="font-mono text-xs text-slate-500">FR Doc. {c.fr_docnum}</span>
                  {!c.section && (c.label || c.section_path) && <span className="text-xs text-slate-600">{c.label || c.section_path}</span>}
                  <span className="text-xs text-slate-600">{c.source_tier === "FR_FULL_TEXT" ? pageLabel(c) : `Sheet row ${c.sheet_row ?? "n/a"}`}</span>
                  <TierBadge tier={c.source_tier} />
                </div>
                <blockquote className="mt-2 whitespace-pre-wrap rounded-lg border-l-4 border-yellow-300 bg-slate-50 p-2 font-mono text-xs">{c.quote}</blockquote>
                <div className="mt-2 flex flex-wrap gap-2">
                  {c.source_tier === "FR_FULL_TEXT" && (
                    <Button size="sm" variant="primary" onClick={() => onOpenCitation(c)}>View in source document</Button>
                  )}
                  <CopyButton text={citationLine(c)} />
                  {(c.source_url || c.pdf_url) && (
                    <a href={c.source_url || c.pdf_url || "#"} target="_blank" rel="noreferrer" className="inline-flex h-7 items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-2 text-xs font-medium text-slate-800 hover:bg-slate-50">
                      <ExternalLink size={12} aria-hidden />Open source
                    </a>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </Card>
      )}
      {r.warnings.length > 0 && (
        <Card className="border-amber-300 bg-amber-50" aria-label="Warnings">
          <CardTitle className="text-amber-900" icon={<AlertTriangle size={14} aria-hidden />}>Warnings</CardTitle>
          <ul className="list-disc pl-5 text-sm text-amber-950">{r.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
        </Card>
      )}
      <Verification r={r} />
      <Disclaimer text={r.disclaimer} />
    </div>
  );
}
