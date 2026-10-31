"use client";
import { useState, type FormEvent } from "react";
import Link from "next/link";
import { AlertTriangle, Loader2, SlidersHorizontal } from "lucide-react";
import { api } from "@/lib/api";
import type { CitationRef, QueryRequest, QueryResponse } from "@/lib/types";
import { ApplicabilityLegend } from "@/components/ApplicabilityLegend";
import { ApplicabilityCard, StatusBanner } from "@/components/AnswerPanel";
import { FactsInput, needsFacts } from "@/components/FactsInput";
import { ErrorState } from "@/components/ErrorState";
import { ThinkingDots } from "@/components/fx/ThinkingDots";
import { StagePill, StatusStrip } from "@/components/Provenance";
import { Disclaimer } from "@/components/Disclaimer";
import { Button, Card, CardTitle, Input } from "@/components/ui";
import { APPLICABILITY_QUESTION, searchHref } from "@/lib/demo";

const label = "mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate-500";
const openSource = (c: CitationRef) => { const u = c.source_url || c.pdf_url; if (u) window.open(u, "_blank", "noopener,noreferrer"); };

export default function Applicability() {
  const [f, setF] = useState({ directiveId: "", model: "", serial: "", make: "" });
  const [resp, setResp] = useState<QueryResponse | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);
  // inputs of the request that produced `resp`: re-checks and the AI Search link use these, not later edits
  const [sent, setSent] = useState(f);

  async function run(facts: Record<string, boolean> = {}, form = f) {
    setLoading(true); setErr(null); setSent(form);
    const t = (s: string) => (s.trim() ? s.trim() : null);
    const body: QueryRequest = {
      question: APPLICABILITY_QUESTION, directive_id: t(form.directiveId), use_llm: false,
      aircraft: t(form.model) || t(form.serial) || t(form.make) || Object.keys(facts).length ? { model: t(form.model), serial: t(form.serial), make: t(form.make), facts } : null,
    };
    try { setResp(await api.query(body)); } catch (e) { setErr(e); setResp(null); } finally { setLoading(false); }
  }
  const submit = (e: FormEvent) => { e.preventDefault(); if (f.directiveId.trim() && !loading) run(); };
  const factKeys = resp ? needsFacts(resp) : [];
  const d = resp?.directive;

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-4 md:p-6">
      <header>
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight"><SlidersHorizontal size={22} className="text-blue-600" aria-hidden />Applicability Checker</h1>
        <p className="text-sm text-slate-600">Check whether a proposed AD, as written, covers a specific airplane. Stage (proposal vs final rule) is shown separately from applicability.</p>
      </header>
      <Card className="p-0">
        <form onSubmit={submit} className="space-y-3 p-4" aria-label="Applicability check">
          <div className="grid gap-2 md:grid-cols-4">
            <div className="md:col-span-2"><label className={label} htmlFor="ap-did">Directive ID (required)</label>
              <Input id="ap-did" required maxLength={100} placeholder="Record ID (NPRM-001), docket, or FR doc" className="font-mono" value={f.directiveId} onChange={(e) => setF({ ...f, directiveId: e.target.value })} /></div>
            <div><label className={label} htmlFor="ap-md">Aircraft model</label><Input id="ap-md" maxLength={100} className="font-mono" value={f.model} onChange={(e) => setF({ ...f, model: e.target.value })} /></div>
            <div><label className={label} htmlFor="ap-sn">Serial number</label><Input id="ap-sn" maxLength={100} className="font-mono" value={f.serial} onChange={(e) => setF({ ...f, serial: e.target.value })} /></div>
            <div><label className={label} htmlFor="ap-mk">Make (optional)</label><Input id="ap-mk" maxLength={200} value={f.make} onChange={(e) => setF({ ...f, make: e.target.value })} /></div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <p className="max-w-xl text-xs text-slate-600">Equipment configuration is supported only as asserted condition facts: if the proposal depends on one, you will be asked to answer it yes, no or unknown. It is never inferred.</p>
            <Button type="submit" variant="primary" size="lg" className="ml-auto" disabled={loading || !f.directiveId.trim()}>
              {loading ? <Loader2 size={16} className="animate-spin" aria-hidden /> : null}Check applicability
            </Button>
          </div>
        </form>
      </Card>
      <ApplicabilityLegend />
      {err ? <ErrorState error={err} onRetry={() => run()} /> : null}
      <ThinkingDots pending={loading} />
      {resp && !loading && (
        <div className="space-y-4" data-testid="applicability-result">
          {resp.status !== "ANSWERED" && <StatusBanner r={resp} onPick={(id) => { const nf = { ...f, directiveId: id }; setF(nf); run({}, nf); }} />}
          {d && (
            <Card aria-label="Directive">
              <div className="flex flex-wrap items-center gap-2">
                {d.record_ids?.length ? <span className="font-mono text-sm font-semibold">Record {d.record_ids.join(", ")}</span> : null}
                <StagePill stage={d.fr_docnum ? resp.revision?.regulatory_stage || d.regulatory_stage : null} />
                {d.docket && <span className="font-mono text-xs text-slate-600">Docket {d.docket}</span>}
              </div>
              {d.title && <div className="mt-1 text-sm font-medium">{d.title}</div>}
            </Card>
          )}
          <StatusStrip directive={resp.directive} revision={resp.revision} applicability={resp.applicability} finalApplicability={resp.final_rule_applicability} finalDocnum={resp.final_rule_docnum} />
          {resp.final_rule_applicability ? (
            <div className="grid gap-4 xl:grid-cols-2" data-testid="applicability-pair">
              <ApplicabilityCard a={resp.applicability} title="Proposed rule" testId="card-proposed" onOpen={openSource} />
              <ApplicabilityCard a={resp.final_rule_applicability} title={`Published final rule (FR ${resp.final_rule_docnum ?? resp.final_rule_applicability.evaluated_document ?? ""})`.replace(" )", ")")} testId="card-final" onOpen={openSource} />
            </div>
          ) : (
            <ApplicabilityCard a={resp.applicability} title="Applicability" testId="card-proposed" onOpen={openSource} />
          )}
          {factKeys.length > 0 && <FactsInput key={factKeys.join("|")} missing={factKeys} onRecheck={(facts) => run(facts, sent)} />}
          {resp.applicability.missing.length > 0 && (
            <Card className="border-amber-300 bg-amber-50 text-sm text-amber-950" aria-label="Missing inputs" data-testid="missing-inputs">
              <b>Missing inputs:</b> <span className="font-mono text-xs">{resp.applicability.missing.join(", ")}</span>
            </Card>
          )}
          {resp.warnings.length > 0 && (
            <Card className="border-amber-300 bg-amber-50" aria-label="Warnings">
              <CardTitle className="text-amber-900" icon={<AlertTriangle size={14} aria-hidden />}>Warnings</CardTitle>
              <ul className="list-disc pl-5 text-sm text-amber-950">{resp.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
            </Card>
          )}
          <Disclaimer text={resp.disclaimer} />
          <Link href={searchHref({ question: APPLICABILITY_QUESTION, directiveId: sent.directiveId.trim(), model: sent.model.trim(), serial: sent.serial.trim(), make: sent.make.trim() })}
            className="inline-flex h-9 items-center rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-slate-800 hover:bg-slate-50">Open in AI Search</Link>
        </div>
      )}
    </div>
  );
}
