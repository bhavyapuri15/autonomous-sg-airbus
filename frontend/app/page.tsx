"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CitationRef, QueryRequest, QueryResponse } from "@/lib/types";
import { QueryPanel, type QueryForm } from "@/components/QueryPanel";
import { AnswerPanel } from "@/components/AnswerPanel";
import { DocumentViewer } from "@/components/DocumentViewer";
import { ErrorState } from "@/components/ErrorState";
import { Disclaimer } from "@/components/Disclaimer";

export default function Home() {
  const [form, setForm] = useState<QueryForm>({ question: "", directiveId: "", model: "", serial: "", make: "", useLlm: true });
  const [resp, setResp] = useState<QueryResponse | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);
  const [cite, setCite] = useState<CitationRef | null>(null);

  useEffect(() => {
    const m = resp?.applicability.missing ?? [];
    const id = m.includes("serial") ? "sn" : m.includes("model") ? "md" : null;
    if (id) document.getElementById(id)?.focus();
  }, [resp]);

  async function run(f: QueryForm = form, facts: Record<string, boolean> = {}) {
    setLoading(true); setErr(null); setCite(null);
    const t = (s: string) => (s.trim() ? s.trim() : null);
    const aircraft = t(f.model) || t(f.serial) || t(f.make) || Object.keys(facts).length ? { model: t(f.model), serial: t(f.serial), make: t(f.make), facts } : null;
    const body: QueryRequest = { question: f.question.trim(), directive_id: t(f.directiveId), aircraft, use_llm: f.useLlm };
    try { setResp(await api.query(body)); } catch (e) { setErr(e); setResp(null); } finally { setLoading(false); }
  }

  return (
    <div className={`grid gap-4 ${cite ? "grid-cols-[320px_minmax(0,1fr)_minmax(0,1fr)]" : "grid-cols-[320px_minmax(0,1fr)]"}`}>
      <div className="self-start">
        <QueryPanel form={form} setForm={setForm} onSubmit={() => run()} loading={loading} />
      </div>
      <div className="min-w-0">
        {err ? <ErrorState error={err} onRetry={() => run()} /> : null}
        {loading && <p className="rounded border border-slate-300 bg-white p-3 text-sm" role="status">Working…</p>}
        {resp && !loading && (
          <AnswerPanel response={resp} onOpenCitation={setCite} onRecheck={(facts) => run(form, facts)}
            onPickCandidate={(id) => { const nf = { ...form, directiveId: id }; setForm(nf); run(nf); }} />
        )}
        {!resp && !err && !loading && (
          <div className="space-y-3">
            <div className="rounded-lg border border-dashed border-slate-400 bg-white p-4 text-sm text-slate-700">
              Ask a question about an FAA Airworthiness Directive proposed rule. Every statement is shown with its source quote and page.
              Documents in this dataset are mostly <b>proposals</b> (NPRMs), which are not enforceable ADs.
            </div>
            <Disclaimer />
          </div>
        )}
      </div>
      {cite && (
        <div className="sticky top-2 h-[calc(100vh-1.5rem)] min-w-0">
          <DocumentViewer citation={cite} onClose={() => setCite(null)} stage={resp?.revision?.regulatory_stage || resp?.directive?.regulatory_stage} />
        </div>
      )}
    </div>
  );
}
