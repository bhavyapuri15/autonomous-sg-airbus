"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ErrorState } from "@/components/ErrorState";
import { EvaluationView } from "@/components/EvaluationView";
import { EvaluationDashboard } from "@/components/EvaluationDashboard";
import { parseRuns, type EvalRun } from "@/lib/evaluation";
import { Card, Skeleton } from "@/components/ui";

export default function Evaluation() {
  const [data, setData] = useState<unknown>(undefined);
  const [err, setErr] = useState<unknown>(null);
  const [runs, setRuns] = useState<EvalRun[]>([]);
  useEffect(() => { api.evaluation().then(setData).catch(setErr); api.evaluationRuns().then((r) => setRuns(parseRuns(r))).catch(() => setRuns([])); }, []);
  return (
    <div className="mx-auto max-w-[1200px] p-4 md:p-6">
      {err ? (
        <div className="space-y-3"><h1 className="text-xl font-semibold">Evaluation</h1><ErrorState error={err} /><Card className="text-sm">No evaluation results yet (API unavailable).</Card></div>
      ) : data === undefined ? (
        <div className="space-y-3" role="status"><Skeleton className="h-7 w-40" /><Skeleton className="h-20 w-full" /><Skeleton className="h-40 w-full" /><span className="sr-only">Loading…</span></div>
      ) : (
        <div className="space-y-8">
          <div><h1 className="text-xl font-semibold">Evaluation</h1><p className="text-sm text-slate-600">Measured results from the evaluation harness. Every value is read from the stored result files.</p></div>
          <EvaluationDashboard runs={runs} />
          <section aria-label="Full report" className="space-y-3"><EvaluationView data={data} /></section>
        </div>
      )}
    </div>
  );
}
