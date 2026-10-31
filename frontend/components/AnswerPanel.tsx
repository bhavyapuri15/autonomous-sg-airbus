"use client";
import { useState } from "react";
import type { CitationRef, QueryResponse, RevisionEdge, RevisionResult, StepOutcome } from "@/lib/types";
import { ApplicabilityBadge, DocClassPill, TierBadge, pageLabel } from "./Badges";
import { Disclaimer } from "./Disclaimer";
import { FactsInput, needsFacts } from "./FactsInput";

type Open = (c: CitationRef) => void;

const card = "rounded-lg border border-slate-300 bg-white p-4 shadow-sm";
const h2 = "mb-2 text-sm font-semibold uppercase tracking-wide text-slate-600";

function StatusBanner({ r, onPick }: { r: QueryResponse; onPick?: (id: string) => void }) {
  if (r.status === "ANSWERED")
    return (
      <div role="status" className="rounded-lg border-2 border-emerald-600 bg-emerald-50 p-3 text-emerald-900" data-testid="status-banner">
        <b>ANSWERED</b> — every statement below is backed by a verified quote from the source.
      </div>
    );
  if (r.status === "NEEDS_MORE_INFORMATION")
    return (
      <div role="status" className="rounded-lg border-2 border-amber-600 bg-amber-50 p-3 text-amber-950" data-testid="status-banner">
        <b>NEEDS MORE INFORMATION</b> — a determination cannot be made yet.
        {r.missing_information.length > 0 && (
          <ul className="mt-1 list-disc pl-5" data-testid="missing-info">
            {r.missing_information.map((m, i) => <li key={i}>{m}</li>)}
          </ul>
        )}
        <div className="mt-1 text-sm">Provide these in the aircraft configuration inputs on the left and submit again.</div>
        {r.candidates.length > 0 && <Candidates r={r} onPick={onPick} label="Matching directives (pick the one you mean)" />}
      </div>
    );
  return (
    <div role="status" className="rounded-lg border-2 border-slate-600 bg-slate-200 p-3 text-slate-900" data-testid="status-banner">
      <b>ABSTAINED</b> — the system declined to answer rather than guess.
      {r.abstention_reason && <div className="mt-1">Reason: {r.abstention_reason}</div>}
      {r.candidates.length > 0 && <Candidates r={r} onPick={onPick} label="Did you mean (these are DIFFERENT directives, not the one you asked for)" />}
    </div>
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
              className="rounded-full border border-slate-500 bg-white px-3 py-1 text-left text-xs hover:bg-slate-50">
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
  return (
    <section className={card} aria-label="Directive">
      <div className="flex flex-wrap items-center gap-2">
        <DocClassPill docClass={d.doc_class} />
        {d.fr_docnum && <span className="font-mono text-sm">FR Doc. {d.fr_docnum}</span>}
        {d.docket && <span className="font-mono text-sm text-slate-700">Docket {d.docket}</span>}
      </div>
      {d.title && <h3 className="mt-1 text-base font-semibold">{d.title}</h3>}
      <div className="mt-1 flex flex-wrap gap-x-4 text-xs text-slate-700">
        {d.publication_date && <span>Published {d.publication_date}</span>}
        {d.citation && <span className="font-mono">{d.citation}</span>}
        {d.pdf_url && <a className="text-sky-800 underline" href={d.pdf_url} target="_blank" rel="noreferrer">Official FR PDF</a>}
      </div>
    </section>
  );
}

const OUT: Record<StepOutcome, { icon: string; label: string; cls: string }> = {
  TRUE: { icon: "✔", label: "TRUE", cls: "text-emerald-800" },
  FALSE: { icon: "✖", label: "FALSE", cls: "text-slate-800" },
  UNKNOWN: { icon: "?", label: "UNKNOWN", cls: "text-violet-800" },
  INFO: { icon: "i", label: "INFO", cls: "text-sky-800" },
};

function EvidenceLink({ c, onOpen }: { c: CitationRef; onOpen: Open }) {
  return (
    <button type="button" onClick={() => onOpen(c)} className="rounded border border-slate-400 bg-slate-50 px-1.5 py-0.5 text-xs text-sky-900 underline hover:bg-slate-100">
      evidence: {c.fr_docnum} · {pageLabel(c)}
    </button>
  );
}

function ApplicabilityCard({ r, onOpen }: { r: QueryResponse; onOpen: Open }) {
  const a = r.applicability;
  return (
    <section className={card} aria-label="Applicability">
      <h2 className={h2}>Applicability</h2>
      <ApplicabilityBadge value={a.value} />
      {a.template_text && <p className="mt-2 text-sm">{a.template_text}</p>}
      <div className="mt-1 flex flex-wrap gap-x-4 text-xs text-slate-700">
        {a.rule_parse_status && <span>Rule parse status: <b className="font-mono">{a.rule_parse_status}</b>{a.rule_parse_status !== "FULL" && " (rule text was not fully machine-readable)"}</span>}
        {a.evaluated_document && <span>Evaluated document: <span className="font-mono">{a.evaluated_document}</span></span>}
      </div>
      {a.explanation.length > 0 && (
        <ol className="mt-3 space-y-2" aria-label="Explanation steps">
          {a.explanation.map((s, i) => {
            const o = OUT[s.outcome];
            return (
              <li key={i} className="flex gap-2 text-sm">
                <span className={`w-16 shrink-0 font-semibold ${o.cls}`}><span aria-hidden>{o.icon}</span> {o.label}</span>
                <div>
                  <div className="font-medium">{s.step}</div>
                  <div className="text-slate-700">{s.detail}</div>
                  {s.evidence.length > 0 && <div className="mt-0.5 flex flex-wrap gap-1">{s.evidence.map((c, j) => <EvidenceLink key={j} c={c} onOpen={onOpen} />)}</div>}
                </div>
              </li>
            );
          })}
        </ol>
      )}
      {a.missing.length > 0 && (
        <div className="mt-3 rounded border border-amber-500 bg-amber-50 p-2 text-sm text-amber-950">
          <b>Missing facts:</b> <span className="font-mono">{a.missing.join(", ")}</span>
        </div>
      )}
      {a.applicability_text && (
        <figure className="mt-3">
          <figcaption className="text-xs font-semibold uppercase text-slate-600">Source text for human review</figcaption>
          <blockquote className="mt-1 border-l-4 border-slate-500 bg-slate-50 p-2 font-mono text-xs whitespace-pre-wrap">{a.applicability_text.quote}</blockquote>
          <div className="mt-1"><EvidenceLink c={a.applicability_text} onOpen={onOpen} /></div>
        </figure>
      )}
    </section>
  );
}

function Edge({ e }: { e: RevisionEdge }) {
  const verified = e.confidence === "VERIFIED";
  return (
    <li className={`rounded border-2 px-2 py-1 text-sm ${verified ? "border-solid border-slate-700 bg-white" : "border-dashed border-slate-400 bg-slate-50 text-slate-700"}`} data-confidence={e.confidence}>
      <span className="font-mono">{e.src}</span> <b>{e.type.replaceAll("_", " ")}</b> <span className="font-mono">{e.dst}</span>{" "}
      {verified ? <span className="text-xs font-semibold text-emerald-800">[verified]</span> : <span className="text-xs font-semibold text-amber-900">[unverified — relationship not confirmed by text]</span>}
      {e.note && <div className="text-xs">{e.note}</div>}
    </li>
  );
}

export function RevisionCard({ revision: v }: { revision?: RevisionResult | null }) {
  if (!v) return null;
  return (
    <section className={card} aria-label="Revision status">
      <h2 className={h2}>Revision status (within dataset)</h2>
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded border border-slate-600 bg-slate-100 px-2 py-0.5 font-mono text-sm font-semibold">{v.status}</span>
        {!v.current_authoritative_status_verified && (
          <span className="rounded border-2 border-amber-600 bg-amber-50 px-2 py-0.5 text-xs font-bold text-amber-950" data-testid="not-verified-badge">
            Current authoritative status NOT verified
          </span>
        )}
      </div>
      {v.template_text && <p className="mt-2 text-sm">{v.template_text}</p>}
      {v.edges.length > 0 && <ul className="mt-2 space-y-1" aria-label="Revision edges">{v.edges.map((e, i) => <Edge key={i} e={e} />)}</ul>}
      {v.latest_in_dataset && (
        <p className="mt-2 text-xs text-slate-700">Latest document in dataset: <span className="font-mono">{v.latest_in_dataset}</span> (a dataset fact, not a statement of current legal status)</p>
      )}
    </section>
  );
}

function Verification({ r }: { r: QueryResponse }) {
  const v = r.verification, t = r.timings_ms;
  const [open, setOpen] = useState(false);
  return (
    <footer className={`${card} text-sm`} aria-label="Verification">
      <div className="flex flex-wrap gap-x-6 gap-y-1">
        <span>Mode: <b className="font-mono">{v.mode}</b></span>
        <span>Claims generated: <b>{v.claims_generated}</b></span>
        <span>Verified: <b>{v.claims_verified}</b></span>
        <span>Rejected: <b>{v.claims_rejected.length}</b></span>
        <span className="font-mono text-xs text-slate-700">
          retrieval {t.retrieval}ms · engines {t.engines}ms · generation {t.generation}ms · verification {t.verification}ms · total {t.total}ms
        </span>
      </div>
      {v.claims_rejected.length > 0 && (
        <div className="mt-2">
          <button className="text-xs text-sky-900 underline" aria-expanded={open} onClick={() => setOpen(!open)}>
            {open ? "Hide" : "Show"} rejected claims ({v.claims_rejected.length})
          </button>
          {open && (
            <ul className="mt-1 space-y-1">
              {v.claims_rejected.map((c, i) => (
                <li key={i} className="rounded bg-slate-50 p-1.5 text-xs"><span className="font-mono text-red-800">{c.failed_check}</span>: {c.text}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </footer>
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
    <div className="space-y-3" data-testid="answer-panel">
      <StatusBanner r={r} onPick={onPickCandidate} />
      <DirectiveHeader r={r} />
      <ApplicabilityCard r={r} onOpen={onOpenCitation} />
      {onRecheck && factKeys.length > 0 && <FactsInput key={factKeys.join("|")} missing={factKeys} onRecheck={onRecheck} />}
      <RevisionCard revision={r.revision} />
      {claims.length > 0 && (
        <section className={card} aria-label="Answer claims">
          <h2 className={h2}>Answer (verified statements)</h2>
          <ul className="space-y-2">
            {claims.map(({ cl, nums }, i) => (
              <li key={i} className="text-sm">
                {cl.text}
                {nums.map(({ c, n }, j) => (
                  <sup key={j}>
                    <button type="button" aria-label={`Open citation ${n}`} onClick={() => onOpenCitation(c)} className="ml-0.5 font-semibold text-sky-800 underline">[{n}]</button>
                  </sup>
                ))}
              </li>
            ))}
          </ul>
        </section>
      )}
      {all.length > 0 && (
        <section className={card} aria-label="Citations">
          <h2 className={h2}>Citations</h2>
          <ol className="space-y-3">
            {all.map((c, i) => (
              <li key={c.citation_id} className="text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold">[{i + 1}]</span>
                  <span className="font-mono text-xs">FR Doc. {c.fr_docnum}</span>
                  {(c.label || c.section_path) && <span className="text-xs text-slate-700">{c.label || c.section_path}</span>}
                  <span className="text-xs text-slate-700">{c.source_tier === "FR_FULL_TEXT" ? pageLabel(c) : `Sheet row ${c.sheet_row ?? "n/a"}`}</span>
                  <TierBadge tier={c.source_tier} />
                </div>
                <blockquote className="mt-1 border-l-4 border-slate-400 bg-slate-50 p-2 font-mono text-xs whitespace-pre-wrap">{c.quote}</blockquote>
                {c.source_tier === "FR_FULL_TEXT" && (
                  <button type="button" onClick={() => onOpenCitation(c)} className="mt-1 text-xs text-sky-900 underline">View in source document</button>
                )}
              </li>
            ))}
          </ol>
        </section>
      )}
      {r.warnings.length > 0 && (
        <section className="rounded-lg border border-amber-500 bg-amber-50 p-3" aria-label="Warnings">
          <h2 className="mb-1 text-sm font-semibold uppercase text-amber-900">Warnings</h2>
          <ul className="list-disc pl-5 text-sm text-amber-950">{r.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
        </section>
      )}
      <Verification r={r} />
      <Disclaimer text={r.disclaimer} />
    </div>
  );
}
