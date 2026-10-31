"use client";
import Link from "next/link";
import { use, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { str } from "@/lib/loose";
import type { DirectiveDetailResponse, DirectiveRelation } from "@/lib/types";
import { ErrorState } from "@/components/ErrorState";
import { DocClassPill, SourceBadge } from "@/components/Badges";
import { RevisionCard } from "@/components/AnswerPanel";

const card = "rounded-lg border border-slate-300 bg-white p-4 shadow-sm";
const h2 = "mb-2 text-sm font-semibold uppercase text-slate-600";

function Relation({ r }: { r: DirectiveRelation }) {
  const v = r.confidence === "VERIFIED";
  return (
    <li className={`rounded border-2 px-2 py-1 text-sm ${v ? "border-solid border-slate-700" : "border-dashed border-slate-400 text-slate-700"}`} data-confidence={r.confidence}>
      <span className="font-mono">{r.src}</span> <b>{r.type.replaceAll("_", " ")}</b> <span className="font-mono">{r.dst}</span>{" "}
      <span className="text-xs font-semibold">{v ? "[VERIFIED]" : "[CANDIDATE — unverified]"}</span>
      {r.note && <div className="text-xs">{r.note}</div>}
      {(r.evidence_json ?? []).map((e, i) => e.quote ? <blockquote key={i} className="mt-1 border-l-4 border-slate-400 bg-slate-50 p-1 font-mono text-xs">{e.quote}{e.fr_docnum ? <span className="text-slate-600"> (FR {e.fr_docnum})</span> : null}</blockquote> : null)}
    </li>
  );
}

export default function DirectiveDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id: raw } = use(params);
  const id = decodeURIComponent(raw);
  const [data, setData] = useState<DirectiveDetailResponse | null>(null);
  const [err, setErr] = useState<unknown>(null);
  useEffect(() => {
    let off = false;
    api.directive(id).then((d) => !off && setData(d)).catch((e) => !off && setErr(e));
    return () => { off = true; };
  }, [id]);

  if (err) return <div className="space-y-2"><Link href="/directives" className="text-sm underline">← Directives</Link><ErrorState error={err} /></div>;
  if (!data) return <p className="text-sm" role="status">Loading…</p>;

  const docs = data.documents ?? [];
  const sheet = data.sheet_rows ?? [];
  const rels = data.relations ?? [];
  const warnings = data.warnings ?? [];
  const at = data.applicability_text;

  return (
    <div className="space-y-3">
      <Link href="/directives" className="text-sm underline">← Directives</Link>
      <h1 className="text-lg font-semibold">{docs[0]?.title || data.query_id} <span className="font-mono text-sm text-slate-600">{data.query_id}</span></h1>
      {warnings.length > 0 && (
        <section className="rounded-lg border border-amber-500 bg-amber-50 p-3" aria-label="Warnings">
          <h2 className="mb-1 text-sm font-semibold uppercase text-amber-900">Warnings</h2>
          <ul className="list-disc pl-5 text-sm text-amber-950">{warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
        </section>
      )}
      <section className={card}><h2 className={h2}>Documents</h2>
        {docs.length === 0 ? <p className="text-sm text-slate-700">None reported.</p> : (
          <ul className="space-y-2 text-sm">{docs.map((d, i) => (
            <li key={`${d.fr_docnum}-${i}`} className="flex flex-wrap items-center gap-2">
              <Link className="font-mono text-sky-800 underline" href={`/directives/${encodeURIComponent(d.fr_docnum)}`}>{d.fr_docnum}</Link>
              <DocClassPill docClass={d.doc_class} /> <SourceBadge source={d.source} />
              <span>{d.title}</span> <span className="text-slate-600">{d.publication_date}</span>
              {d.pdf_url && <a className="text-xs text-sky-800 underline" href={d.pdf_url} target="_blank" rel="noreferrer">PDF</a>}
            </li>
          ))}</ul>
        )}
      </section>
      <section className={card}><h2 className={h2}>Spreadsheet metadata, not regulatory text</h2>
        {sheet.length === 0 ? <p className="text-sm text-slate-700">No spreadsheet rows (not in the organiser dataset).</p> : (
          <div className="space-y-2">{sheet.map((r, i) => (
            <table key={i} className="w-full text-sm"><tbody>
              {Object.entries(r).filter(([, v]) => v !== null && v !== "" && !(Array.isArray(v) && v.length === 0)).map(([k, v]) => (
                <tr key={k} className="border-t border-slate-200 align-top"><th className="w-44 p-1 text-left font-normal text-slate-600">{k}</th><td className="break-words p-1 font-mono text-xs">{Array.isArray(v) ? v.join(", ") : str(v)}</td></tr>
              ))}
            </tbody></table>
          ))}</div>
        )}
      </section>
      {<RevisionCard revision={data.revision} />}
      <section className={card}><h2 className={h2}>Relations</h2>
        {rels.length === 0 ? <p className="text-sm text-slate-700">None reported.</p> : <ul className="space-y-1">{rels.map((r, i) => <Relation key={r.id ?? i} r={r} />)}</ul>}
      </section>
      {at && (
        <section className={card}><h2 className={h2}>Applicability text</h2>
          <blockquote className="border-l-4 border-slate-500 bg-slate-50 p-2 font-mono text-xs whitespace-pre-wrap">{at.quote}</blockquote>
          <div className="mt-1 text-xs text-slate-700">FR Doc. {at.fr_docnum} · FR p. {at.fr_page ?? "n/a"} · PDF p. {at.pdf_page ?? "n/a"}</div>
        </section>
      )}
    </div>
  );
}
