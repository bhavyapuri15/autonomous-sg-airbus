"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ErrorState } from "@/components/ErrorState";
import { EvaluationView } from "@/components/EvaluationView";

export default function Evaluation() {
  const [data, setData] = useState<unknown>(undefined);
  const [err, setErr] = useState<unknown>(null);
  useEffect(() => { api.evaluation().then(setData).catch(setErr); }, []);
  if (err) return <div className="space-y-2"><h1 className="text-lg font-semibold">Evaluation</h1><ErrorState error={err} /><p className="text-sm">No evaluation results yet (API unavailable).</p></div>;
  if (data === undefined) return <p className="text-sm" role="status">Loading…</p>;
  return <EvaluationView data={data} />;
}
