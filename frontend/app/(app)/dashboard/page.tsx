"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, BarChart3, FileSearch, Search, SlidersHorizontal } from "lucide-react";
import { api } from "@/lib/api";
import { isRec } from "@/lib/loose";
import { EXAMPLES, searchHref } from "@/lib/demo";
import { devRuns, latestWith, parseRuns, type EvalRun } from "@/lib/evaluation";
import { Card, CardTitle, Skeleton } from "@/components/ui";

type Health = { records: number | null; organiser: number | null; lookup: number | null; pages: number | null };

function Stat({ label, value, sub }: { label: string; value: string | number | null; sub?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-card" data-testid="dash-stat">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value === null ? <span className="text-sm font-normal text-slate-500">Not available</span> : <span className="font-mono">{value}</span>}</div>
      {sub && <div className="mt-0.5 font-mono text-xs text-slate-500">{sub}</div>}
    </div>
  );
}

const ACTIONS = [
  { href: "/search", title: "AI Search", text: "Ask a question and verify every statement against its source quote.", icon: Search },
  { href: "/directives", title: "Directives", text: "Browse and filter the indexed FAA AD proposals.", icon: FileSearch },
  { href: "/applicability", title: "Applicability", text: "Check whether a proposal, as written, covers your airplane.", icon: SlidersHorizontal },
  { href: "/evaluation", title: "Evaluation", text: "Measured retrieval, citation and abstention results.", icon: BarChart3 },
];

export default function Dashboard() {
  const [h, setH] = useState<Health | null | "err">(null);
  const [runs, setRuns] = useState<EvalRun[] | null | "err">(null);
  useEffect(() => {
    api.health().then((x) => {
      const db = isRec(x.db) ? x.db : {};
      const by = isRec(db.documents_by_source) ? db.documents_by_source : {};
      const n = (v: unknown) => (typeof v === "number" ? v : null);
      setH({ records: n(db.records), organiser: n(by.organiser_sheet), lookup: n(by.fr_final_rule_lookup), pages: n(db.pages) });
    }).catch(() => setH("err"));
    api.evaluationRuns().then((r) => setRuns(parseRuns(r))).catch(() => setRuns("err"));
  }, []);
  const dev = Array.isArray(runs) ? devRuns(runs) : [];
  const recall = latestWith(dev, "F2.doc_recall_at5", "F2.n");
  const mrr = latestWith(dev, "F2.doc_mrr_at10", "F2.n");
  const cite = latestWith(dev, "F3.extractive.citation_validity", "F3.extractive.citations_checked");
  const abst = latestWith(dev, "F7.abstention.f1", "F7.abstention.n");
  const metric = (p: { value: number | null; n: number | null; run: EvalRun | null }, unit = "n") => p.value === null ? { v: null as string | null, sub: undefined } : { v: p.value.toFixed(4), sub: `${unit} = ${p.n ?? "?"} · dev · ${p.run?.timestamp ?? p.run?.file}` };
  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 md:p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-slate-600">Traceable search over FAA Airworthiness Directive proposals in the Federal Register. Most documents are proposals (NPRMs), not enforceable ADs.</p>
      </header>
      <section aria-label="Corpus">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Indexed corpus (live from the API)</h2>
        {h === null ? <Skeleton className="h-20 w-full" /> : h === "err" ? <Card className="text-sm">Corpus counts unavailable (API not reachable).</Card> : (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Organiser records" value={h.records} />
            <Stat label="Organiser FR documents" value={h.organiser} />
            <Stat label="Final-rule lookup docs" value={h.lookup} sub="outside organiser dataset" />
            <Stat label="Pages indexed" value={h.pages} />
          </div>
        )}
      </section>
      <section aria-label="Evaluation headline">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Headline evaluation (most recent dev run measuring each)</h2>
        {runs === null ? <Skeleton className="h-20 w-full" /> : runs === "err" || dev.length === 0 ? <Card className="text-sm">Evaluation results not available.</Card> : (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {([["Recall@5 (F2)", metric(recall)], ["MRR@10 (F2)", metric(mrr)], ["Citation validity (F3)", metric(cite, "citations")], ["Abstention F1 (F7)", metric(abst)]] as const).map(([l, m]) => <Stat key={l} label={l} value={m.v} sub={m.sub} />)}
          </div>
        )}
        <p className="mt-1 text-xs text-slate-500">Split: dev. See the Evaluation page for locked-split results and the full report.</p>
      </section>
      <section aria-label="Quick actions" className="grid gap-3 md:grid-cols-2">
        {ACTIONS.map(({ href, title, text, icon: Icon }) => (
          <Link key={href} href={href} className="group rounded-lg border border-slate-200 bg-white p-4 shadow-card hover:border-blue-400">
            <div className="flex items-center gap-2 font-semibold"><Icon size={16} className="text-blue-600" aria-hidden />{title}<ArrowRight size={14} className="ml-auto text-slate-400 group-hover:text-blue-600" aria-hidden /></div>
            <p className="mt-1 text-sm text-slate-600">{text}</p>
          </Link>
        ))}
      </section>
      <Card aria-label="Demo queries">
        <CardTitle>Try a real query (answers are extractive, no LLM)</CardTitle>
        <ul className="space-y-1.5">
          {EXAMPLES.map((e) => (
            <li key={e.title}>
              <Link href={searchHref(e.form)} className="flex flex-wrap items-baseline gap-x-3 rounded-lg border border-slate-200 px-3 py-2 text-sm hover:border-blue-500 hover:bg-blue-50">
                <span className="font-medium">{e.title}</span><span className="font-mono text-xs text-slate-500">{e.hint}</span>
              </Link>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
