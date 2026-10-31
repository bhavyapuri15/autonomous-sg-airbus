"use client";
import { isRec, str, type Rec } from "@/lib/loose";

const card = "rounded-lg border border-slate-300 bg-white p-3 shadow-sm";
const label = (k: string) => k.replaceAll("_", " ");
const isScalar = (v: unknown) => v === null || ["string", "number", "boolean"].includes(typeof v);

function Scalar({ v }: { v: unknown }) {
  if (typeof v === "number") return <span className="font-mono">{v}</span>;
  if (typeof v === "boolean") return <span className="font-mono">{String(v)}</span>;
  return <span className="font-mono">{v === null ? "null" : String(v)}</span>;
}

function ObjectTable({ rows }: { rows: Rec[] }) {
  const cols = Array.from(new Set(rows.flatMap((r) => Object.keys(r))));
  return (
    <div className="overflow-auto">
      <table className="w-full border-collapse text-xs">
        <thead className="bg-slate-200 text-left"><tr>{cols.map((c) => <th key={c} className="p-1">{label(c)}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => (
          <tr key={i} className="border-t border-slate-200 align-top">{cols.map((c) => <td key={c} className="p-1 font-mono">{r[c] === undefined ? "" : str(r[c])}</td>)}</tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function ArrayView({ name, v }: { name: string; v: unknown[] }) {
  const allObj = v.length > 0 && v.every(isRec);
  const isFail = /fail|false_|invalid|reject/i.test(name);
  return (
    <details className={`${card} col-span-full`} data-testid={isFail ? "failure-list" : undefined}>
      <summary className="cursor-pointer text-xs font-semibold uppercase text-slate-600">{label(name)} ({v.length})</summary>
      <div className="mt-2">
        {v.length === 0 ? <p className="text-xs text-slate-700">Empty.</p>
          : allObj ? <ObjectTable rows={v as Rec[]} />
          : <p className="break-words font-mono text-xs">{v.map((x) => (isScalar(x) ? String(x) : str(x))).join(", ")}</p>}
      </div>
    </details>
  );
}

function Metric({ name, v }: { name: string; v: unknown }) {
  return (
    <div className={card}>
      <div className="text-xs font-semibold uppercase text-slate-600">{label(name)}</div>
      <div className="mt-1 text-xl font-bold"><Scalar v={v} /></div>
    </div>
  );
}

function Node({ name, v, depth }: { name: string; v: unknown; depth: number }) {
  if (Array.isArray(v)) return <ArrayView name={name} v={v} />;
  if (!isRec(v)) return <Metric name={name} v={v} />;
  const scalars = Object.entries(v).filter(([, x]) => isScalar(x));
  const rest = Object.entries(v).filter(([, x]) => !isScalar(x));
  const n = v.n ?? v.denominator ?? v.total;
  return (
    <section className={`${card} col-span-full space-y-2`} aria-label={label(name)}>
      <h2 className={`font-semibold uppercase text-slate-700 ${depth === 0 ? "text-sm" : "text-xs"}`}>
        {label(name)}{typeof n === "number" ? <span className="ml-2 font-mono normal-case text-slate-600">(n = {n})</span> : null}
      </h2>
      {scalars.length > 0 && (
        <div className="grid grid-cols-4 gap-2">
          {scalars.map(([k, x]) => (
            <div key={k} className="rounded border border-slate-200 bg-slate-50 p-2">
              <div className="text-xs text-slate-600">{label(k)}</div>
              <div className="text-lg font-bold"><Scalar v={x} /></div>
            </div>
          ))}
        </div>
      )}
      {rest.length > 0 && (
        <div className="grid grid-cols-2 gap-2">{rest.map(([k, x]) => <Node key={k} name={k} v={x} depth={depth + 1} />)}</div>
      )}
    </section>
  );
}

export function EvaluationView({ data }: { data: unknown }) {
  const empty = data === null || data === undefined || (isRec(data) && Object.keys(data).length === 0) || (Array.isArray(data) && data.length === 0);
  if (empty || !isRec(data)) return <div><h1 className="text-lg font-semibold">Evaluation</h1><p className="mt-2 rounded border border-slate-400 bg-white p-4 text-sm" data-testid="no-eval">No evaluation results yet</p></div>;
  const head = Object.entries(data).filter(([k, v]) => isScalar(v) || /git/i.test(k) || (Array.isArray(v) && v.every(isScalar)));
  const headKeys = new Set(head.map(([k]) => k));
  const sections = Object.entries(data).filter(([k]) => !headKeys.has(k));
  const ordered = [...head.filter(([k]) => ["split", "timestamp"].includes(k)), ...head.filter(([k]) => !["split", "timestamp"].includes(k))];
  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">Evaluation</h1>
      <header className={card} data-testid="eval-header">
        <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
          {ordered.map(([k, v]) => <span key={k}><span className="text-slate-600">{label(k)}:</span> <span className="font-mono">{Array.isArray(v) ? v.join(", ") : isScalar(v) ? String(v) : str(v)}</span></span>)}
        </div>
      </header>
      <p className="text-xs text-slate-700">Values below are exactly as returned by /evaluation/summary.</p>
      <div className="grid grid-cols-1 gap-3">{sections.map(([k, v]) => <Node key={k} name={k} v={v} depth={0} />)}</div>
    </div>
  );
}

