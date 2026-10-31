"use client";
import Link from "next/link";
import { use, useEffect, useState } from "react";
import { ArrowLeft, ExternalLink, FileText, Link2, PanelRightOpen, Table2 } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { str } from "@/lib/loose";
import type { CitationRef, DirectiveDetailResponse, DirectiveRelation } from "@/lib/types";
import { ErrorState } from "@/components/ErrorState";
import { DocClassPill, SourceBadge } from "@/components/Badges";
import { RevisionCard } from "@/components/AnswerPanel";
import { DocumentViewer } from "@/components/DocumentViewer";
import { HistoryTimeline, StagePill, Supersessions } from "@/components/Provenance";
import { Badge, Button, Card, CardTitle, Skeleton } from "@/components/ui";

function Relation({ r }: { r: DirectiveRelation }) {
  const v = r.confidence === "VERIFIED";
  return (
    <li className={cn("rounded-lg border px-3 py-2 text-sm", v ? "border-slate-300" : "border-dashed border-slate-300 text-slate-700")} data-confidence={r.confidence}>
      <span className="font-mono">{r.src}</span> <b>{r.type.replaceAll("_", " ")}</b> <span className="font-mono">{r.dst}</span>{" "}
      <Badge tone={v ? "blue" : "amber"}>{v ? "VERIFIED" : "CANDIDATE — unverified"}</Badge>
      {r.note && <div className="text-xs">{r.note}</div>}
      {(r.evidence_json ?? []).map((e, i) => e.quote ? <blockquote key={i} className="mt-1 border-l-4 border-slate-300 pl-2 font-mono text-xs">{e.quote}{e.fr_docnum ? <span className="text-slate-500"> (FR {e.fr_docnum})</span> : null}</blockquote> : null)}
    </li>
  );
}

export default function DirectiveDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id: raw } = use(params);
  const id = decodeURIComponent(raw);
  const [data, setData] = useState<DirectiveDetailResponse | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [cite, setCite] = useState<CitationRef | null>(null);
  useEffect(() => {
    let off = false;
    api.directive(id).then((d) => !off && setData(d)).catch((e) => !off && setErr(e));
    return () => { off = true; };
  }, [id]);

  const back = <Link href="/directives" className="inline-flex items-center gap-1 text-sm text-blue-600 hover:underline"><ArrowLeft size={14} aria-hidden />Directives</Link>;
  if (err) return <div className="mx-auto max-w-4xl space-y-3 p-6">{back}<ErrorState error={err} /></div>;
  if (!data) return (
    <div className="mx-auto max-w-4xl space-y-3 p-6" role="status"><Skeleton className="h-6 w-1/2" /><Skeleton className="h-24 w-full" /><Skeleton className="h-40 w-full" /><span className="sr-only">Loading…</span></div>
  );

  const docs = data.documents ?? [];
  const sheet = data.sheet_rows ?? [];
  const rels = data.relations ?? [];
  const warnings = data.warnings ?? [];
  const at = data.applicability_text;
  const rev = data.revision;
  const recIds = Array.from(new Set([
    ...(data.candidates ?? []).flatMap((c) => c.record_ids ?? []),
    ...(rev?.dataset_history?.history ?? []).filter((e) => e.fr_docnum === docs[0]?.fr_docnum).map((e) => e.record_id),
    ...docs.flatMap((d) => (Array.isArray(d.record_ids) ? (d.record_ids as string[]) : [])),
  ]));
  const stage = rev?.regulatory_stage || (data.candidates ?? []).find((c) => c.regulatory_stage)?.regulatory_stage;
  const hasHist = (rev?.dataset_history?.history ?? []).length > 0 || (rev?.proposed_supersedes ?? []).length > 0;

  return (
    <div className={cn("mx-auto grid max-w-[1500px] gap-4 p-4 md:p-6", cite && "lg:grid-cols-[minmax(0,1fr)_minmax(0,520px)]")}>
      <div className="min-w-0 space-y-4">
        {back}
        <Card>
          <div className="flex flex-wrap items-center gap-2">
            {recIds.length > 0 && <Badge tone="outline" className="px-2 py-1 font-mono text-sm font-semibold text-slate-900" data-testid="record-ids">Record {recIds.join(", ")}</Badge>}
            <StagePill stage={stage} />
            {docs[0]?.pdf_url && <a className="ml-auto inline-flex items-center gap-1 text-sm text-blue-600 hover:underline" href={docs[0].pdf_url} target="_blank" rel="noreferrer">Official source<ExternalLink size={13} aria-hidden /></a>}
          </div>
          <h1 className="mt-2 text-xl font-semibold leading-snug">{docs[0]?.title || data.query_id}</h1>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Badge tone="slate" className="font-mono">{data.query_id}</Badge>
            {docs[0]?.publication_date && <Badge tone="slate">Published {docs[0].publication_date}</Badge>}
          </div>
        </Card>
        {warnings.length > 0 && (
          <Card className="border-amber-300 bg-amber-50" aria-label="Warnings">
            <CardTitle className="text-amber-900">Warnings</CardTitle>
            <ul className="list-disc pl-5 text-sm text-amber-950">{warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
          </Card>
        )}
        <Card><CardTitle icon={<FileText size={14} aria-hidden />}>Documents</CardTitle>
          {docs.length === 0 ? <p className="text-sm text-slate-600">None reported.</p> : (
            <ul className="space-y-2 text-sm">{docs.map((d, i) => (
              <li key={`${d.fr_docnum}-${i}`} className="flex flex-wrap items-center gap-2">
                <Link className="font-mono text-blue-600 hover:underline" href={`/directives/${encodeURIComponent(d.fr_docnum)}`}>{d.fr_docnum}</Link>
                <DocClassPill docClass={d.doc_class} /> <SourceBadge source={d.source} />
                <span>{d.title}</span> <span className="text-slate-500">{d.publication_date}</span>
                {d.pdf_url && <a className="text-xs text-blue-600 hover:underline" href={d.pdf_url} target="_blank" rel="noreferrer">PDF</a>}
              </li>
            ))}</ul>
          )}
        </Card>
        {at && (
          <Card><CardTitle>Applicability text</CardTitle>
            <blockquote className="whitespace-pre-wrap rounded-lg border-l-4 border-yellow-300 bg-slate-50 p-2 font-mono text-xs">{at.quote}</blockquote>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-600">
              <span className="font-mono">FR Doc. {at.fr_docnum} · FR p. {at.fr_page ?? "n/a"} · PDF p. {at.pdf_page ?? "n/a"}</span>
              {at.source_tier === "FR_FULL_TEXT" && <Button size="sm" variant="primary" onClick={() => setCite(at)}><PanelRightOpen size={12} aria-hidden />Open in source viewer</Button>}
            </div>
          </Card>
        )}
        <RevisionCard revision={rev} />
        {hasHist && (
          <Card aria-label="Dataset history and supersessions"><CardTitle>Dataset history and proposed supersessions</CardTitle>
            <HistoryTimeline history={rev?.dataset_history} />
            <Supersessions items={rev?.proposed_supersedes} />
          </Card>
        )}
        <Card><CardTitle icon={<Link2 size={14} aria-hidden />}>Relations</CardTitle>
          {rels.length === 0 ? <p className="text-sm text-slate-600">None reported.</p> : <ul className="space-y-2">{rels.map((r, i) => <Relation key={r.id ?? i} r={r} />)}</ul>}
        </Card>
        <Card><CardTitle icon={<Table2 size={14} aria-hidden />}>Spreadsheet metadata, not regulatory text</CardTitle>
          {sheet.length === 0 ? <p className="text-sm text-slate-600">No spreadsheet rows (not in the organiser dataset).</p> : (
            <div className="space-y-3">{sheet.map((r, i) => (
              <table key={i} className="w-full text-sm"><tbody>
                {Object.entries(r).filter(([, v]) => v !== null && v !== "" && !(Array.isArray(v) && v.length === 0)).map(([k, v]) => (
                  <tr key={k} className="border-t border-slate-100 align-top"><th className="w-44 p-1.5 text-left text-xs font-normal text-slate-500">{k}</th><td className="break-words p-1.5 font-mono text-xs">{Array.isArray(v) ? v.join(", ") : str(v)}</td></tr>
                ))}
              </tbody></table>
            ))}</div>
          )}
        </Card>
      </div>
      {cite && <div className="sticky top-4 h-[calc(100vh-5rem)] min-w-0 self-start"><DocumentViewer key={cite.citation_id} citation={cite} onClose={() => setCite(null)} stage={stage} /></div>}
    </div>
  );
}
