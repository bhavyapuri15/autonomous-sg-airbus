"use client";
import { useState } from "react";
import { Info } from "lucide-react";
import { Badge, Card, Tabs } from "@/components/ui";
import { LineChart, type LineSeries } from "@/components/fx/LineChart";
import { dig, devRuns, latestWith, lockedRuns, num, seriesOver, type EvalRun, type MetricPick } from "@/lib/evaluation";

const fmt = (v: number, d = 4) => v.toFixed(d);
const runLabel = (r: EvalRun) => `${r.timestamp ?? r.file} (${r.split ?? "?"})`;

function MetricCard({ name, value, n, nLabel = "n", run, extra, note }: { name: string; value: string | null; n?: number | null; nLabel?: string; run?: EvalRun | null; extra?: string; note?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-card" data-testid="metric-card" aria-label={name}>
      <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{name}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-900">
        {value === null ? <span className="text-sm font-normal text-slate-500" data-testid="not-measured">Not measured</span> : <span className="font-mono">{value}</span>}
      </div>
      {value !== null && (
        <div className="mt-0.5 font-mono text-xs text-slate-500">
          {typeof n === "number" ? `${nLabel} = ${n}` : null}{extra ? ` ${extra}` : null}
        </div>
      )}
      {run && value !== null && <div className="mt-0.5 text-[11px] text-slate-500">from run {runLabel(run)}</div>}
      {note && <div className="mt-1 text-[11px] text-slate-600">{note}</div>}
    </div>
  );
}

const rate = (p: MetricPick) => (p.value === null ? null : fmt(p.value));

export function EvaluationDashboard({ runs }: { runs: EvalRun[] }) {
  const [tab, setTab] = useState<"dev" | "locked">("dev");
  const dev = devRuns(runs), locked = lockedRuns(runs);
  const set = tab === "dev" ? dev : locked;
  if (runs.length === 0) return <Card className="text-sm" data-testid="no-runs">No timestamped evaluation runs available.</Card>;

  const recall = latestWith(set, "F2.doc_recall_at5", "F2.n");
  const mrr = latestWith(set, "F2.doc_mrr_at10", "F2.n");
  const cite = latestWith(set, "F3.extractive.citation_validity", "F3.extractive.citations_checked");
  const f1acc = latestWith(set, "F1.acc_at1", "F1.n");
  const f6 = latestWith(set, "F6.status_accuracy", "F6.n");
  const f11 = latestWith(set, "F11.status_acc", "F11.n");
  const abst = latestWith(set, "F7.abstention.f1", "F7.abstention.n");
  const f8 = latestWith(set, "F8.passed", "F8.n");
  const p50 = latestWith(set, "latency.answer.warm.p50_ms", "latency.answer.warm.n");
  const p95 = latestWith(set, "latency.answer.warm.p95_ms", "latency.answer.warm.n");
  const idxDocs = latestWith(set, "latency.index.documents", "latency.index.pages");
  const pages = num(dig(idxDocs.run?.metrics, "latency.index.pages"));

  // chart over dev runs only; a run lacking the metric is a gap
  const x = dev.map((r) => (r.timestamp ?? r.file).replace("T", " ").slice(5, 19));
  const mk = (id: string, name: string, color: string, path: string): LineSeries => ({
    id, name, color, points: seriesOver(dev, path).map((y, i) => ({ x: x[i], y, label: `n=${num(dig(dev[i].metrics, path.split(".")[0] + ".n")) ?? "?"}` })),
  });
  const chart: LineSeries[] = [
    mk("recall", "F2 Recall@5", "#2563eb", "F2.doc_recall_at5"),
    mk("mrr", "F2 MRR@10", "#c2410c", "F2.doc_mrr_at10"),
    mk("acc", "F1 exact-ID acc@1", "#0e9aa7", "F1.acc_at1"),
  ];
  const plotted = chart.map((s) => ({ ...s })).filter((s) => s.points.some((p) => p.y !== null));
  // keep only runs where at least one series was measured (a run with none is not a point on this chart)
  const keep = dev.map((_, i) => plotted.some((s) => s.points[i].y !== null));
  const cx = x.filter((_, i) => keep[i]);
  const cs = plotted.map((s) => ({ ...s, points: s.points.filter((_, i) => keep[i]) }));

  return (
    <div className="space-y-4">
      <Tabs label="Evaluation split" value={tab} onChange={setTab} tabs={[{ id: "dev", label: `Dev (${dev.length} runs)` }, { id: "locked", label: `Locked (${locked.length})` }]} />
      {tab === "locked" && (
        <p className="flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 p-2 text-xs text-amber-950" data-testid="locked-note">
          <Info size={14} className="mt-0.5 shrink-0" aria-hidden />Locked-split results were measured on the pre-fix corpus (before the 31 Oct corpus fix). They are shown as recorded and are not comparable one-to-one with the latest dev run.
        </p>
      )}
      {set.length === 0 ? <Card className="text-sm">No {tab} runs available. Not measured.</Card> : (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4" data-testid="metric-grid">
          <MetricCard name="Indexed documents" value={idxDocs.value === null ? null : String(idxDocs.value)} extra={pages !== null ? `${pages} pages` : undefined} run={idxDocs.run} />
          <MetricCard name="Recall@5 (F2, document)" value={rate(recall)} n={recall.n} run={recall.run} />
          <MetricCard name="MRR@10 (F2, document)" value={rate(mrr)} n={mrr.n} run={mrr.run} />
          <MetricCard name="Citation validity (F3, extractive)" value={rate(cite)} n={cite.n} nLabel="citations" run={cite.run} />
          <MetricCard name="Exact-ID acc@1 (F1)" value={rate(f1acc)} n={f1acc.n} run={f1acc.run} />
          <MetricCard name="Revision status acc. (F6)" value={rate(f6)} n={f6.n} run={f6.run} />
          <MetricCard name="Revision chains acc. (F11)" value={rate(f11)} n={f11.n} run={f11.run} />
          <MetricCard name="Abstention F1 (F7)" value={rate(abst)} n={abst.n} run={abst.run} />
          <MetricCard name="Adversarial (F8) passed" value={f8.value === null ? null : `${f8.value} / ${f8.n ?? "?"}`} run={f8.run} />
          <MetricCard name="Answer latency p50 (warm)" value={p50.value === null ? null : `${p50.value} ms`} n={p50.n} run={p50.run} />
          <MetricCard name="Answer latency p95 (warm)" value={p95.value === null ? null : `${p95.value} ms`} n={p95.n} run={p95.run} />
          <MetricCard name="Applicability accuracy" value={null} note="No evaluation family measures it. A hand audit is described in docs/evaluation_report.md section 6." />
        </div>
      )}
      <Card>
        <LineChart title="Retrieval across dev runs" series={cs} xLabels={cx} xLabel="Dev run (MM-DD HH:MM, timestamp order)" yLabel="Score (0 to 1)" />
        <p className="mt-2 text-xs text-slate-600">One point per run that measured the metric; runs that did not include a family are omitted, never interpolated. Corpus and case files changed between runs, so differences are not a like-for-like trend.</p>
      </Card>
      <p className="text-xs text-slate-600" data-testid="corpus-note">
        <Badge tone="blue">Note</Badge> The most recent dev run was measured on the fixed corpus with case files regenerated for it (gold correction; the locked split was not re-run). The run before it used the fixed corpus with the older, frozen case files. See docs/evaluation_report.md, sections 9 and 9.1.
      </p>
    </div>
  );
}
