"use client";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { createColumnHelper, flexRender, getCoreRowModel, getSortedRowModel, useReactTable, type SortingState } from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, ExternalLink, Search } from "lucide-react";
import { api } from "@/lib/api";
import { joinModels } from "@/lib/loose";
import type { DirectiveListItem } from "@/lib/types";
import { ErrorState } from "@/components/ErrorState";
import { SourceBadge } from "@/components/Badges";
import { stageFromDocClass, StagePill } from "@/components/Provenance";
import { Button, Card, Input, Skeleton } from "@/components/ui";

const PAGE_SIZES = [25, 50, 100];
const CLASSES = ["NPRM", "SNPRM", "WITHDRAWAL", "CORRECTION", "FINAL_RULE", "OTHER"];
const col = createColumnHelper<DirectiveListItem>();
const mono = "font-mono text-xs";

const columns = [
  col.accessor((r) => (r.record_ids ?? []).join(", "), { id: "record", header: "Record ID", cell: (c) => <span className={`${mono} font-semibold`}>{c.getValue() || <span className="text-slate-400">—</span>}</span> }),
  col.accessor((r) => r.docket ?? "", { id: "docket", header: "Docket", cell: (c) => <span className={mono}>{c.getValue()}</span> }),
  col.accessor((r) => (r.make ?? []).join(", "), { id: "make", header: "Make", cell: (c) => <span className="text-xs">{c.getValue()}</span> }),
  col.accessor((r) => joinModels(r.models), { id: "models", header: "Models", enableSorting: false, cell: (c) => <span className="text-xs text-slate-600">{c.getValue()}</span> }),
  col.accessor((r) => stageFromDocClass(r.doc_class) ?? "", { id: "stage", header: "Regulatory stage", cell: (c) => <StagePill stage={c.getValue()} compact /> }),
  col.accessor((r) => r.publication_date ?? "", { id: "date", header: "Publication date", cell: (c) => <span className="whitespace-nowrap text-xs">{c.getValue()}</span> }),
  col.display({
    id: "source", header: "Source",
    cell: (c) => (
      <div className="flex flex-col items-start gap-1">
        <SourceBadge source={c.row.original.source} />
        {c.row.original.fr_docnum ? <span className={`${mono} text-blue-700`}>FR Doc. {c.row.original.fr_docnum}</span> : <span className="text-xs text-slate-500">No FR text</span>}
        {c.row.original.fr_docnum && <a href={`https://www.federalregister.gov/d/${encodeURIComponent(c.row.original.fr_docnum)}`} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}
          className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline">Official <ExternalLink size={11} aria-hidden /></a>}
      </div>
    ),
  }),
];

export default function Directives() {
  const router = useRouter();
  const [q, setQ] = useState(""); const [make, setMake] = useState(""); const [dc, setDc] = useState("");
  const [includeFr, setIncludeFr] = useState(false);
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(50);
  const [rows, setRows] = useState<DirectiveListItem[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [err, setErr] = useState<unknown>(null); const [loading, setLoading] = useState(false);
  const [sorting, setSorting] = useState<SortingState>([]);

  const load = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      const d = await api.directives({ q, make, doc_class: dc, source: includeFr ? undefined : "organiser_sheet", limit, offset });
      setRows(Array.isArray(d.items) ? d.items : []);
      setTotal(typeof d.total === "number" ? d.total : null);
    } catch (e) { setErr(e); setRows([]); } finally { setLoading(false); }
  }, [q, make, dc, includeFr, offset, limit]);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);

  const data = useMemo(() => rows, [rows]);
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({ data, columns, state: { sorting }, onSortingChange: setSorting, getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel() });
  const open = (r: DirectiveListItem) => {
    const id = r.fr_docnum ?? r.record_ids?.[0] ?? r.docket;   // metadata-only rows have no FR docnum
    if (id) router.push(`/directives/${encodeURIComponent(id)}`);
  };

  return (
    <div className="mx-auto max-w-[1400px] space-y-4 p-4 md:p-6">
      <div>
        <h1 className="text-xl font-semibold">Directives</h1>
        <p className="text-sm text-slate-600">Browse the indexed FAA AD proposals. Select a row to open its record.</p>
      </div>
      <Card className="p-3">
        <div className="flex flex-wrap items-center gap-2" role="search">
          <div className="relative min-w-[220px] flex-1">
            <Search size={14} className="pointer-events-none absolute left-2.5 top-2.5 text-slate-400" aria-hidden />
            <Input aria-label="Search" placeholder="Search title, docket, FR doc…" className="pl-8" value={q} onChange={(e) => { setOffset(0); setQ(e.target.value); }} />
          </div>
          <Input aria-label="Make" placeholder="Make (e.g. Airbus)" className="w-44" value={make} onChange={(e) => { setOffset(0); setMake(e.target.value); }} />
          <select aria-label="Document class" className="h-9 rounded-lg border border-slate-300 bg-white px-2 text-sm focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-600/30" value={dc} onChange={(e) => { setOffset(0); setDc(e.target.value); }}>
            <option value="">All classes / stages</option>
            {CLASSES.map((c) => <option key={c}>{c}</option>)}
          </select>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" className="h-4 w-4 accent-blue-600" checked={includeFr} onChange={(e) => { setOffset(0); setIncludeFr(e.target.checked); }} />
            Include final rules found via Federal Register lookup (outside organiser dataset)
          </label>
        </div>
      </Card>
      {err ? <ErrorState error={err} onRetry={load} /> : null}
      <Card className="overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm" aria-label="Directives">
            <thead className="bg-slate-50 text-left text-[11px] uppercase tracking-wide text-slate-500">
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id}>
                  {hg.headers.map((h) => {
                    const dir = h.column.getIsSorted();
                    return (
                      <th key={h.id} className="whitespace-nowrap border-b border-slate-200 px-3 py-2 font-semibold" aria-sort={dir ? (dir === "asc" ? "ascending" : "descending") : undefined}>
                        {h.column.getCanSort() ? (
                          <button type="button" onClick={h.column.getToggleSortingHandler()} className="inline-flex items-center gap-1 uppercase hover:text-slate-900">
                            {flexRender(h.column.columnDef.header, h.getContext())}
                            {dir === "asc" ? <ArrowUp size={12} aria-hidden /> : dir === "desc" ? <ArrowDown size={12} aria-hidden /> : <ArrowUpDown size={12} className="text-slate-300" aria-hidden />}
                          </button>
                        ) : flexRender(h.column.columnDef.header, h.getContext())}
                      </th>
                    );
                  })}
                </tr>
              ))}
            </thead>
            <tbody>
              {loading && rows.length === 0 && Array.from({ length: 6 }).map((_, i) => (
                <tr key={i} className="border-t border-slate-100"><td colSpan={columns.length} className="px-3 py-2"><Skeleton className="h-5 w-full" /></td></tr>
              ))}
              {table.getRowModel().rows.map((r) => (
                <tr key={r.id} tabIndex={0} onClick={() => open(r.original)} onKeyDown={(e) => { if (e.key === "Enter") open(r.original); }}
                  className="cursor-pointer border-t border-slate-100 align-top hover:bg-blue-50/40 focus-visible:bg-blue-50/60">
                  {r.getVisibleCells().map((c) => <td key={c.id} className="px-3 py-2">{flexRender(c.column.columnDef.cell, c.getContext())}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!err && !loading && rows.length === 0 && <p className="p-4 text-sm text-slate-600">No directives match these filters. Clear the search or filters, or include final-rule lookup documents.</p>}
        <div className="flex items-center gap-3 border-t border-slate-200 px-3 py-2 text-sm text-slate-600">
          <Button size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}><ChevronLeft size={14} aria-hidden />Previous</Button>
          <span role="status">{loading ? "Loading…" : `Showing ${rows.length ? offset + 1 : 0}–${offset + rows.length}${total !== null ? ` of ${total}` : ""}`}</span>
          <Button size="sm" disabled={rows.length < limit || (total !== null && offset + rows.length >= total)} onClick={() => setOffset(offset + limit)}>Next<ChevronRight size={14} aria-hidden /></Button>
          <label className="ml-auto flex items-center gap-1.5 text-xs">Rows per page
            <select aria-label="Rows per page" className="h-7 rounded-lg border border-slate-300 bg-white px-1 text-xs" value={limit} onChange={(e) => { setOffset(0); setLimit(Number(e.target.value)); }}>
              {PAGE_SIZES.map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
          <span className="hidden text-xs text-slate-500 md:inline">Sorting applies to the rows on this page.</span>
        </div>
      </Card>
    </div>
  );
}
