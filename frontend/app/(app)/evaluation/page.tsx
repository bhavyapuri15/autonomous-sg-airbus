"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ErrorState } from "@/components/ErrorState";
import { EvaluationView } from "@/components/EvaluationView";
import { Card, Skeleton } from "@/components/ui";

export default function Evaluation() {
  const [data, setData] = useState<unknown>(undefined);
  const [err, setErr] = useState<unknown>(null);
  useEffect(() => { api.evaluation().then(setData).catch(setErr); }, []);
  return (
    <div className="mx-auto max-w-[1200px] p-4 md:p-6">
      {err ? (
        <div className="space-y-3"><h1 className="text-xl font-semibold">Evaluation</h1><ErrorState error={err} /><Card className="text-sm">No evaluation results yet (API unavailable).</Card></div>
      ) : data === undefined ? (
        <div className="space-y-3" role="status"><Skeleton className="h-7 w-40" /><Skeleton className="h-20 w-full" /><Skeleton className="h-40 w-full" /><span className="sr-only">Loading…</span></div>
      ) : <EvaluationView data={data} />}
    </div>
  );
}
