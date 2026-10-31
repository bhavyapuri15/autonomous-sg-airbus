"use client";
import { useState } from "react";
import { isRec, str, type Rec } from "@/lib/loose";
import { Badge, Card, Tabs } from "@/components/ui";

const label = (k: string) => k.replaceAll("_", " ");
const isScalar = (v: unknown) => v === null || ["string", "number", "boolean"].includes(typeof v);

function Scalar({ v }: { v: unknown }) {
  if (v === null || v === undefined || v === "") return <span className="text-sm font-normal text-slate-400" data-testid="not-measured">Not measured</span>;
  return <span className="font-mono">{String(v)}</span>;
}

function ObjectTable({ rows }: { rows: Rec[] }) {
  const cols = Array.from(new Set(rows.flatMap((r) => Object.keys(r))));
  return (
    <div className="overflow-auto">
      <table className="w-full border-collapse text-xs">
        <thead className="bg-slate-50 text-left text-slate-500"><tr>{cols.map((c) => <th key={c} className="p-1.5 font-semibold">{label(c)}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => (
          <tr key={i} className="border-t border-slate-100 align-top">{cols.map((c) => <td key={c} className="p-1.5 font-mono">{r[c] === undefined ? "" : str(r[c])}</td>)}</tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function ArrayView({ name, v }: { name: string; v: unknown[] }) {
  const allObj = v.length > 0 && v.every(isRec);
  const isFail = /fail|false_|invalid|reject/i.test(name);
  return (
    <details className="col-span-full rounded-lg border border-slate-200 bg-white p-3" data-testid={isFail ? "failure-list" : undefined}>
      <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-slate-500">{label(name)} ({v.length})</summary>
      <div className="mt-2">
        {v.length === 0 ? <p className="text-xs text-slate-600">Empty.</p>
          : allObj ? <ObjectTable rows={v as Rec[]} />
          : <p className="break-words font-mono text-xs">{v.map((x) => (isScalar(x) ? String(x) : str(x))).join(", ")}</p>}
      </div>
    </details>
  );
}

function Metric({ name, v, n }: { name: string; v: unknown; n?: number }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-card">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label(name)}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-900"><Scalar v={v} /></div>
      {typeof n === "number" && <div className="mt-0.5 font-mono text-xs text-slate-500">n = {n}</div>}
    </div>
  );
}

function Node({ name, v, depth }: { name: string; v: unknown; depth: number }) {
  if (Array.isArray(v)) return <ArrayView name={name} v={v} />;
  if (!isRec(v)) return <Metric name={name} v={v} />;
  const scalars = Object.entries(v).filter(([k, x]) => isScalar(x) && k !== "n" && k !== "denominator" && k !== "total");
  const rest = Object.entries(v).filter(([, x]) => !isScalar(x));
  const n = v.n ?? v.denominator ?? v.total;
  const notes = scalars.filter(([, x]) => typeof x === "string");
  const nums = scalars.filter(([, x]) => typeof x !== "string");
  const Wrap = depth === 0 ? Card : "div";
  return (
    <Wrap className={depth === 0 ? "col-span-full space-y-3" : "col-span-full space-y-2 rounded-lg border border-slate-200 bg-slate-50/50 p-3"} aria-label={label(name)}>
      <h2 className={depth === 0 ? "flex items-center gap-2 text-sm font-semibold text-slate-900" : "text-xs font-semibold uppercase tracking-wide text-slate-600"}>
        {depth === 0 ? <Badge tone="blue" className="font-mono">{label(name)}</Badge> : label(name)}
        {typeof n === "number" ? <span className="font-mono text-xs font-normal normal-case text-slate-500">(n = {n})</span> : null}
      </h2>
      {nums.length > 0 && (
        <div className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-4">
          {nums.map(([k, x]) => <Metric key={k} name={k} v={x} n={typeof n === "number" ? n : undefined} />)}
        </div>
      )}
      {notes.map(([k, x]) => <p key={k} className="text-xs text-slate-600"><span className="font-semibold">{label(k)}:</span> {String(x)}</p>)}
      {rest.length > 0 && <div className="grid grid-cols-1 gap-2 xl:grid-cols-2">{rest.map(([k, x]) => <Node key={k} name={k} v={x} depth={depth + 1} />)}</div>}
    </Wrap>
  );
}

function Report({ data }: { data: Rec }) {
  const head = Object.entries(data).filter(([k, v]) => isScalar(v) || /git/i.test(k) || (Array.isArray(v) && v.every(isScalar)));
  const headKeys = new Set(head.map(([k]) => k));
  const sections = Object.entries(data).filter(([k]) => !headKeys.has(k));
  const ordered = [...head.filter(([k]) => ["split", "timestamp"].includes(k)), ...head.filter(([k]) => !["split", "timestamp"].includes(k))];
  return (
    <div className="space-y-4">
      <Card className="py-3" data-testid="eval-header">
        <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
          {ordered.map(([k, v]) => <span key={k}><span className="text-slate-500">{label(k)}:</span> <span className="font-mono">{Array.isArray(v) ? v.join(", ") : isScalar(v) ? String(v) : str(v)}</span></span>)}
        </div>
      </Card>
      <p className="text-xs text-slate-500">Values below are exactly as returned by /evaluation/summary. Unavailable values are shown as &quot;Not measured&quot;.</p>
      <div className="grid grid-cols-1 gap-4">{sections.map(([k, v]) => <Node key={k} name={k} v={v} depth={0} />)}</div>
    </div>
  );
}

export function EvaluationView({ data }: { data: unknown }) {
  const [tab, setTab] = useState<string>("dev");
  const empty = data === null || data === undefined || (isRec(data) && Object.keys(data).length === 0) || (Array.isArray(data) && data.length === 0);
  const title = (
    <div>
      <h1 className="text-xl font-semibold">Evaluation</h1>
      <p className="text-sm text-slate-600">Measured results from the evaluation harness.</p>
    </div>
  );
  if (empty || !isRec(data)) return <div className="space-y-3">{title}<Card className="p-4 text-sm" data-testid="no-eval">No evaluation results yet</Card></div>;
  // Dev vs locked tabs only when the summary actually carries both splits.
  const splits = (["dev", "locked"] as const).filter((k) => isRec(data[k]));
  if (splits.length === 2) {
    const active = splits.includes(tab as "dev" | "locked") ? tab : "dev";
    return (
      <div className="space-y-4">{title}
        <Tabs label="Evaluation split" value={active} onChange={setTab} tabs={splits.map((s) => ({ id: s, label: s === "dev" ? "Dev" : "Locked" }))} />
        <Report data={data[active] as Rec} />
      </div>
    );
  }
  return <div className="space-y-4">{title}<Report data={data} /></div>;
}
