"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { joinModels } from "@/lib/loose";
import type { DirectiveListItem } from "@/lib/types";
import { ErrorState } from "@/components/ErrorState";
import { DocClassPill, SourceBadge } from "@/components/Badges";

const LIMIT = 50;
const inp = "rounded border border-slate-400 bg-white px-2 py-1.5 text-sm";

export default function Directives() {
  const [q, setQ] = useState(""); const [make, setMake] = useState(""); const [dc, setDc] = useState("");
  const [includeFr, setIncludeFr] = useState(false);
  const [offset, setOffset] = useState(0);
  const [rows, setRows] = useState<DirectiveListItem[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [err, setErr] = useState<unknown>(null); const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      const d = await api.directives({ q, make, doc_class: dc, source: includeFr ? undefined : "organiser_sheet", limit: LIMIT, offset });
      setRows(Array.isArray(d.items) ? d.items : []);
      setTotal(typeof d.total === "number" ? d.total : null);
    } catch (e) { setErr(e); setRows([]); } finally { setLoading(false); }
  }, [q, make, dc, includeFr, offset]);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);

  return (
    <div className="space-y-3">
      <h1 className="text-lg font-semibold">Directives browser</h1>
      <div className="flex flex-wrap gap-2" role="search">
        <input aria-label="Search" placeholder="Search title, docket, FR doc…" className={`${inp} w-72`} value={q} onChange={(e) => { setOffset(0); setQ(e.target.value); }} />
        <input aria-label="Make" placeholder="Make (e.g. Airbus)" className={inp} value={make} onChange={(e) => { setOffset(0); setMake(e.target.value); }} />
        <select aria-label="Document class" className={inp} value={dc} onChange={(e) => { setOffset(0); setDc(e.target.value); }}>
          <option value="">All classes</option>
          {["NPRM", "SNPRM", "WITHDRAWAL", "CORRECTION", "FINAL_RULE", "OTHER"].map((c) => <option key={c}>{c}</option>)}
        </select>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={includeFr} onChange={(e) => { setOffset(0); setIncludeFr(e.target.checked); }} />
        Include final rules found via Federal Register lookup (outside organiser dataset)
      </label>
      {err ? <ErrorState error={err} onRetry={load} /> : null}
      {loading && <p className="text-sm" role="status">Loading…</p>}
      {!err && !loading && rows.length === 0 && <p className="text-sm text-slate-700">No directives match.</p>}
      {rows.length > 0 && (
        <table className="w-full border-collapse bg-white text-sm shadow-sm">
          <thead className="bg-slate-200 text-left text-xs uppercase text-slate-700">
            <tr><th className="p-2">FR doc</th><th className="p-2">Docket</th><th className="p-2">Class</th><th className="p-2">Make</th><th className="p-2">Models</th><th className="p-2">Record / sheet row</th><th className="p-2">Title</th><th className="p-2">Date</th></tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={`${r.fr_docnum}-${i}`} className="border-t border-slate-200 align-top hover:bg-slate-50">
                <td className="p-2 font-mono">
                  <Link className="text-sky-800 underline" href={`/directives/${encodeURIComponent(r.fr_docnum)}`}>{r.fr_docnum}</Link>
                  <div className="mt-1"><SourceBadge source={r.source} /></div>
                </td>
                <td className="p-2 font-mono text-xs">{r.docket ?? ""}</td>
                <td className="p-2"><DocClassPill docClass={r.doc_class} /></td>
                <td className="p-2">{(r.make ?? []).join(", ")}</td>
                <td className="p-2 text-xs">{joinModels(r.models)}</td>
                <td className="p-2 font-mono text-xs">
                  {(r.record_ids ?? []).length > 0 && <div className="font-semibold">{(r.record_ids ?? []).join(", ")}</div>}
                  {(r.sheet_rows ?? []).length > 0 && <div>row {(r.sheet_rows ?? []).join(", ")}</div>}
                </td>
                <td className="p-2">{r.title ?? ""}</td>
                <td className="p-2 whitespace-nowrap">{r.publication_date ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="flex items-center gap-3 text-sm">
        <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMIT))} className="rounded border border-slate-500 px-2 py-0.5 disabled:opacity-40">Previous</button>
        <span>Showing {rows.length ? offset + 1 : 0}–{offset + rows.length}{total !== null ? ` of ${total}` : ""}</span>
        <button disabled={rows.length < LIMIT || (total !== null && offset + rows.length >= total)} onClick={() => setOffset(offset + LIMIT)} className="rounded border border-slate-500 px-2 py-0.5 disabled:opacity-40">Next</button>
      </div>
    </div>
  );
}
