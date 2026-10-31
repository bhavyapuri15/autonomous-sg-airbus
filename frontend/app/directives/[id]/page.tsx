"use client";
import Link from "next/link";
import { use, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { isRec, pickList, str, type Rec } from "@/lib/loose";
import { ErrorState } from "@/components/ErrorState";
import { DocClassPill } from "@/components/Badges";

const card = "rounded-lg border border-slate-300 bg-white p-4 shadow-sm";

function KV({ data, skip = [] }: { data: Rec; skip?: string[] }) {
  const entries = Object.entries(data).filter(([k, v]) => !skip.includes(k) && v !== null && v !== "" && !(Array.isArray(v) && v.length === 0));
  return (
    <dl className="grid grid-cols-[180px_1fr] gap-x-3 gap-y-1 text-sm">
      {entries.map(([k, v]) => (
        <div key={k} className="contents"><dt className="text-slate-600">{k}</dt><dd className="break-words font-mono text-xs">{str(v)}</dd></div>
      ))}
    </dl>
  );
}

export default function DirectiveDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id: raw } = use(params);
  const id = decodeURIComponent(raw);
  const [data, setData] = useState<Rec | null>(null);
  const [err, setErr] = useState<unknown>(null);
  useEffect(() => {
    let off = false;
    api.directive(id).then((d) => !off && setData(d)).catch((e) => !off && setErr(e));
    return () => { off = true; };
  }, [id]);

  if (err) return <div className="space-y-2"><Link href="/directives" className="text-sm underline">← Directives</Link><ErrorState error={err} /></div>;
  if (!data) return <p className="text-sm" role="status">Loading…</p>;

  const docs = pickList(data, ["documents", "docket_documents", "same_docket", "related_documents"]);
  const edges = pickList(data, ["edges", "revision_edges"]);
  const rev = isRec(data.revision) ? pickList(data.revision, ["edges"]) : [];
  const allEdges = edges.length ? edges : rev;
  const sheet = pickList(data, ["sheet_rows", "rows", "sheet"]);
  const meta = isRec(data.directive) ? data.directive : isRec(data.metadata) ? data.metadata : data;

  return (
    <div className="space-y-3">
      <Link href="/directives" className="text-sm underline">← Directives</Link>
      <h1 className="text-lg font-semibold">{str(meta.title) || id}</h1>
      <DocClassPill docClass={str(meta.doc_class) || null} />
      <section className={card}><h2 className="mb-2 text-sm font-semibold uppercase text-slate-600">Metadata</h2>
        <KV data={meta} skip={["documents", "edges", "revision", "sheet_rows", "revision_edges", "docket_documents", "same_docket", "related_documents", "rows"]} />
      </section>
      {sheet.length > 0 && (
        <section className={card}><h2 className="mb-2 text-sm font-semibold uppercase text-slate-600">Spreadsheet rows (metadata, not regulatory text)</h2>
          <div className="space-y-2">{sheet.map((r, i) => <div key={i} className="rounded bg-slate-50 p-2"><KV data={r} /></div>)}</div>
        </section>
      )}
      {Array.isArray(data.sheet_rows) && sheet.length === 0 && (
        <p className="text-xs text-slate-700">Sheet rows: <span className="font-mono">{str(data.sheet_rows)}</span></p>
      )}
      <section className={card}><h2 className="mb-2 text-sm font-semibold uppercase text-slate-600">Documents in the same docket</h2>
        {docs.length === 0 ? <p className="text-sm text-slate-700">None reported.</p> : (
          <ul className="space-y-1 text-sm">{docs.map((d, i) => (
            <li key={i}><Link className="font-mono text-sky-800 underline" href={`/directives/${encodeURIComponent(str(d.fr_docnum || d.id))}`}>{str(d.fr_docnum || d.id)}</Link>{" "}
              <DocClassPill docClass={str(d.doc_class) || null} /> {str(d.title)} <span className="text-slate-600">{str(d.publication_date)}</span></li>
          ))}</ul>
        )}
      </section>
      <section className={card}><h2 className="mb-2 text-sm font-semibold uppercase text-slate-600">Revision edges</h2>
        {allEdges.length === 0 ? <p className="text-sm text-slate-700">None reported.</p> : (
          <ul className="space-y-1">{allEdges.map((e, i) => {
            const v = str(e.confidence) === "VERIFIED";
            return (
              <li key={i} className={`rounded border-2 px-2 py-1 text-sm ${v ? "border-solid border-slate-700" : "border-dashed border-slate-400 text-slate-700"}`}>
                <span className="font-mono">{str(e.src)}</span> <b>{str(e.type).replaceAll("_", " ")}</b> <span className="font-mono">{str(e.dst)}</span>{" "}
                <span className="text-xs font-semibold">{v ? "[verified]" : "[unverified]"}</span>
              </li>
            );
          })}</ul>
        )}
      </section>
    </div>
  );
}
