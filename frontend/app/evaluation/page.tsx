"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { isRec, pickList, str, type Rec } from "@/lib/loose";
import { ErrorState } from "@/components/ErrorState";

const card = "rounded-lg border border-slate-300 bg-white p-3 shadow-sm";

/** A metric card shows only numbers returned by the API. Nothing is computed or defaulted here. */
function Metric({ name, v }: { name: string; v: unknown }) {
  let main = "", denom = "", extra: Rec = {};
  if (isRec(v)) {
    const val = v.value ?? v.rate ?? v.score ?? v.numerator ?? v.k;
    const den = v.denominator ?? v.n ?? v.total;
    main = val === undefined ? "" : str(val);
    denom = den === undefined ? "" : str(den);
    extra = Object.fromEntries(Object.entries(v).filter(([k]) => !["value", "rate", "score", "numerator", "k", "denominator", "n", "total"].includes(k)));
  } else main = str(v);
  return (
    <div className={card}>
      <div className="text-xs font-semibold uppercase text-slate-600">{name.replaceAll("_", " ")}</div>
      <div className="mt-1 font-mono text-2xl font-bold">{main || "n/a"}</div>
      {denom && <div className="text-xs text-slate-700">denominator (n): <span className="font-mono">{denom}</span></div>}
      {Object.entries(extra).map(([k, x]) => <div key={k} className="text-xs text-slate-700">{k}: <span className="font-mono">{str(x)}</span></div>)}
    </div>
  );
}

export default function Evaluation() {
  const [data, setData] = useState<unknown>(undefined);
  const [err, setErr] = useState<unknown>(null);
  useEffect(() => { api.evaluation().then(setData).catch(setErr); }, []);

  if (err) return <div className="space-y-2"><h1 className="text-lg font-semibold">Evaluation</h1><ErrorState error={err} /><p className="text-sm">No evaluation results yet (API unavailable).</p></div>;
  if (data === undefined) return <p className="text-sm" role="status">Loading…</p>;
  const empty = data === null || (isRec(data) && Object.keys(data).length === 0) || (Array.isArray(data) && data.length === 0);
  if (empty || !isRec(data)) return <div><h1 className="text-lg font-semibold">Evaluation</h1><p className="mt-2 rounded border border-slate-400 bg-white p-4 text-sm" data-testid="no-eval">No evaluation results yet</p></div>;

  const failures = pickList(data, ["failures", "failure_cases", "failed_cases"]);
  const latency = isRec(data.latency) ? data.latency : isRec(data.latency_ms) ? data.latency_ms : null;
  const handled = new Set(["failures", "failure_cases", "failed_cases", "latency", "latency_ms", "metrics"]);
  const metricSrc: Rec = isRec(data.metrics) ? data.metrics : Object.fromEntries(Object.entries(data).filter(([k]) => !handled.has(k)));
  const metrics = Object.entries(metricSrc);

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">Evaluation</h1>
      <p className="text-xs text-slate-700">Values below are exactly as returned by /evaluation/summary.</p>
      <div className="grid grid-cols-4 gap-3">{metrics.map(([k, v]) => <Metric key={k} name={k} v={v} />)}</div>
      {latency && (
        <section className={card}><h2 className="mb-1 text-sm font-semibold uppercase text-slate-600">Latency</h2>
          <div className="flex flex-wrap gap-x-6 font-mono text-sm">{Object.entries(latency).map(([k, v]) => <span key={k}>{k}: {str(v)}</span>)}</div>
        </section>
      )}
      <section className={card}><h2 className="mb-1 text-sm font-semibold uppercase text-slate-600">Failure cases</h2>
        {failures.length === 0 ? <p className="text-sm text-slate-700">No failure cases reported.</p> : (
          <ul className="space-y-1">{failures.map((f, i) => <li key={i} className="rounded bg-slate-50 p-2 font-mono text-xs">{str(f)}</li>)}</ul>
        )}
      </section>
    </div>
  );
}
