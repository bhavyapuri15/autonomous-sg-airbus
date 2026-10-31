"use client";
import { useEffect, useState } from "react";
import { Group, Panel, Separator, usePanelRef } from "react-resizable-panels";
import { api } from "@/lib/api";
import { useMedia } from "@/lib/useMedia";
import type { CitationRef, QueryRequest, QueryResponse } from "@/lib/types";
import { QueryPanel, type QueryForm } from "@/components/QueryPanel";
import { AnswerPanel } from "@/components/AnswerPanel";
import { DocumentViewer } from "@/components/DocumentViewer";
import { ErrorState } from "@/components/ErrorState";
import { EmptyState } from "@/components/EmptyState";
import { ResultSkeleton } from "@/components/ResultSkeleton";

export default function Home() {
  const [form, setForm] = useState<QueryForm>({ question: "", directiveId: "", model: "", serial: "", make: "", useLlm: true });
  const [resp, setResp] = useState<QueryResponse | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);
  const [cite, setCite] = useState<CitationRef | null>(null);
  const wide = useMedia("(min-width: 768px)");
  const viewerPanel = usePanelRef();

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

  const centre = (
    <div className="mx-auto max-w-4xl space-y-4 p-4 md:p-6">
      <QueryPanel form={form} setForm={setForm} onSubmit={() => run()} loading={loading} />
      {err ? <ErrorState error={err} onRetry={() => run()} /> : null}
      {loading && <ResultSkeleton />}
      {resp && !loading && (
        <AnswerPanel response={resp} onOpenCitation={setCite} onRecheck={(facts) => run(form, facts)}
          onPickCandidate={(id) => { const nf = { ...form, directiveId: id }; setForm(nf); run(nf); }} />
      )}
      {!resp && !err && !loading && <EmptyState onPick={(f) => { setForm(f); run(f); }} />}
    </div>
  );
  const viewer = cite && (
    <DocumentViewer key={`${cite.citation_id}`} citation={cite} onClose={() => setCite(null)} stage={resp?.directive && !resp.directive.fr_docnum ? null : resp?.revision?.regulatory_stage || resp?.directive?.regulatory_stage} />
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
