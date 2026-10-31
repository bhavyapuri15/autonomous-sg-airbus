"use client";
import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Group, Panel, Separator, usePanelRef } from "react-resizable-panels";
import { api } from "@/lib/api";
import { useMedia } from "@/lib/useMedia";
import type { CitationRef, QueryRequest, QueryResponse } from "@/lib/types";
import { QueryPanel, type QueryForm } from "@/components/QueryPanel";
import { AnswerPanel } from "@/components/AnswerPanel";
import { Activity } from "@/components/Activity";
import { DocumentViewer } from "@/components/DocumentViewer";
import { ErrorState } from "@/components/ErrorState";
import { EmptyState } from "@/components/EmptyState";
import { ThinkingDots } from "@/components/fx/ThinkingDots";

function Workspace() {
  const params = useSearchParams();
  const [form, setForm] = useState<QueryForm>({ question: "", directiveId: "", model: "", serial: "", make: "", useLlm: false });
  const [resp, setResp] = useState<QueryResponse | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);
  const [cite, setCite] = useState<CitationRef | null>(null);
  const wide = useMedia("(min-width: 768px)");
  const viewerPanel = usePanelRef();
  const autoRan = useRef(false);

  useEffect(() => {
    const m = resp?.applicability.missing ?? [];
    const id = m.includes("serial") ? "sn" : m.includes("model") ? "md" : null;
    if (id) document.getElementById(id)?.focus();
  }, [resp]);

  useEffect(() => {
    if (!wide) return;
    if (cite) viewerPanel.current?.expand(); else viewerPanel.current?.collapse();
  }, [cite, wide, viewerPanel]);

  async function run(f: QueryForm = form, facts: Record<string, boolean> = {}) {
    setLoading(true); setErr(null); setCite(null);
    const t = (s: string) => (s.trim() ? s.trim() : null);
    const aircraft = t(f.model) || t(f.serial) || t(f.make) || Object.keys(facts).length ? { model: t(f.model), serial: t(f.serial), make: t(f.make), facts } : null;
    const body: QueryRequest = { question: f.question.trim(), directive_id: t(f.directiveId), aircraft, use_llm: f.useLlm };
    try { setResp(await api.query(body)); } catch (e) { setErr(e); setResp(null); } finally { setLoading(false); }
  }

  // Deep link: /search?q=&directive=&model=&serial=&make= pre-fills and auto-runs exactly once.
  useEffect(() => {
    if (autoRan.current) return;
    const q = params.get("q");
    if (!q || !q.trim()) return;
    autoRan.current = true;
    const f: QueryForm = { question: q, directiveId: params.get("directive") ?? "", model: params.get("model") ?? "", serial: params.get("serial") ?? "", make: params.get("make") ?? "", useLlm: false };
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setForm(f);
    void run(f);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  const centre = (
    <div className="mx-auto max-w-4xl space-y-4 p-4 md:p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Regulatory Intelligence Workspace</h1>
        <p className="text-sm text-slate-600">Ask a question. Examine the evidence. Verify the result.</p>
      </header>
      <QueryPanel form={form} setForm={setForm} onSubmit={() => run()} loading={loading} />
      {err ? <ErrorState error={err} onRetry={() => run()} /> : null}
      <ThinkingDots pending={loading} />
      {resp && !loading && (
        <>
          <AnswerPanel response={resp} onOpenCitation={setCite} onRecheck={(facts) => run(form, facts)}
            onPickCandidate={(id) => { const nf = { ...form, directiveId: id }; setForm(nf); run(nf); }} />
          <Activity timings={resp.timings_ms} />
        </>
      )}
      {!resp && !err && !loading && <EmptyState onPick={(f) => { setForm(f); run(f); }} />}
    </div>
  );
  // Header metadata belongs to the cited document: the answer's directive only when the citation is its own FR document,
  // FINAL_RULE for the linked final rule; never a title, docket or stage borrowed from the answer's directive.
  const d = resp?.directive;
  const own = !!cite && !!d?.fr_docnum && cite.fr_docnum === d.fr_docnum;
  const finDoc = resp?.final_rule_docnum ?? resp?.final_rule_applicability?.evaluated_document ?? null;
  const fin = !!cite && !!finDoc && cite.fr_docnum === finDoc;
  const viewer = cite && (
    <DocumentViewer key={`${cite.citation_id}`} citation={cite} onClose={() => setCite(null)}
      title={own ? d?.title : null} docket={own ? d?.docket : null}
      stage={own ? resp?.revision?.regulatory_stage || d?.regulatory_stage : fin ? "FINAL_RULE" : null} />
  );

  if (!wide) {
    return (
      <div>
        {centre}
        {viewer && <div className="h-[80vh] p-4 pt-0">{viewer}</div>}
      </div>
    );
  }
  return (
    <Group orientation="horizontal" className="absolute inset-0">
      <Panel id="centre" minSize="35%">
        <div className="h-full overflow-y-auto">{centre}</div>
      </Panel>
      <Separator className={cite ? "w-1.5 bg-slate-200 transition-colors hover:bg-blue-400 data-[separator=active]:bg-blue-500" : "w-0 pointer-events-none"} />
      <Panel id="viewer" panelRef={viewerPanel} collapsible collapsedSize={0} defaultSize="0%" minSize="28%" maxSize="70%">
        <div className="h-full p-3">{viewer}</div>
      </Panel>
    </Group>
  );
}

export default function Home() {
  return <Suspense fallback={null}><Workspace /></Suspense>;
}
