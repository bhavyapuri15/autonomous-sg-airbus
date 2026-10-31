"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { isRec, pickList, str } from "@/lib/loose";
import { ErrorState } from "@/components/ErrorState";
import { DocClassPill } from "@/components/Badges";

const LIMIT = 50;
const inp = "rounded border border-slate-400 bg-white px-2 py-1.5 text-sm";

export default function Directives() {
  const [q, setQ] = useState(""); const [make, setMake] = useState(""); const [dc, setDc] = useState("");
  const [offset, setOffset] = useState(0);
  const [rows, setRows] = useState<ReturnType<typeof pickList>>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [err, setErr] = useState<unknown>(null); const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      const d = await api.directives({ q, make, doc_class: dc, limit: LIMIT, offset });
      setRows(pickList(d, ["items", "directives", "results", "data"]));
      setTotal(isRec(d) && typeof d.total === "number" ? d.total : null);
    } catch (e) { setErr(e); setRows([]); } finally { setLoading(false); }
  }, [q, make, dc, offset]);
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
      {err ? <ErrorState error={err} onRetry={load} /> : null}
      {loading && <p className="text-sm" role="status">Loading…</p>}
      {!err && !loading && rows.length === 0 && <p className="text-sm text-slate-700">No directives match.</p>}
      {rows.length > 0 && (
        <table className="w-full border-collapse bg-white text-sm shadow-sm">
          <thead className="bg-slate-200 text-left text-xs uppercase text-slate-700">
            <tr><th className="p-2">FR doc</th><th className="p-2">Docket</th><th className="p-2">Class</th><th className="p-2">Make</th><th className="p-2">Title</th><th className="p-2">Date</th></tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const id = str(r.fr_docnum || r.id || r.docket);
              return (
                <tr key={i} className="border-t border-slate-200 align-top hover:bg-slate-50">
                  <td className="p-2 font-mono"><Link className="text-sky-800 underline" href={`/directives/${encodeURIComponent(id)}`}>{id || "(no id)"}</Link></td>
                  <td className="p-2 font-mono text-xs">{str(r.docket)}</td>
                  <td className="p-2"><DocClassPill docClass={str(r.doc_class) || null} /></td>
                  <td className="p-2">{str(r.make)}</td>
                  <td className="p-2">{str(r.title)}</td>
                  <td className="p-2 whitespace-nowrap">{str(r.publication_date || r.date)}</td>
                </tr>
              );
            })}
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
