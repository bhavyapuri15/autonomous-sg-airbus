"use client";
import { useState } from "react";
import type { QueryResponse } from "@/lib/types";
import { buildFacts, factLabel, isConditionKey, type FactAnswer } from "@/lib/facts";

export function needsFacts(r: QueryResponse): string[] {
  if (!(r.applicability.value === "UNKNOWN" || r.status === "NEEDS_MORE_INFORMATION")) return [];
  return r.applicability.missing.filter(isConditionKey);
}

export function FactsInput({ missing, onRecheck }: { missing: string[]; onRecheck: (facts: Record<string, boolean>) => void }) {
  const [ans, setAns] = useState<Record<string, FactAnswer>>({});
  if (missing.length === 0) return null;
  return (
    <section className="rounded-lg border-2 border-amber-600 bg-amber-50 p-3" aria-label="Configuration facts" data-testid="facts-input">
      <h2 className="mb-1 text-sm font-semibold uppercase text-amber-900">Configuration facts needed</h2>
      <p className="mb-2 text-xs text-amber-950">Answer what you know about this aircraft. Unknown answers are not sent.</p>
      <ul className="space-y-2">
        {missing.map((m) => (
          <li key={m} className="flex flex-wrap items-center gap-3 text-sm">
            <span className="min-w-0 flex-1">{factLabel(m)}</span>
            <div role="radiogroup" aria-label={factLabel(m)} className="flex overflow-hidden rounded border border-slate-500">
              {(["yes", "no", "unknown"] as const).map((o) => (
                <button key={o} type="button" role="radio" aria-checked={(ans[m] ?? "unknown") === o}
                  onClick={() => setAns({ ...ans, [m]: o })}
                  className={`px-3 py-1 text-xs font-semibold capitalize ${(ans[m] ?? "unknown") === o ? "bg-slate-900 text-white" : "bg-white text-slate-800"}`}>
                  {o}
                </button>
              ))}
            </div>
          </li>
        ))}
      </ul>
      <button type="button" onClick={() => onRecheck(buildFacts(ans))} className="mt-3 rounded bg-slate-900 px-3 py-1.5 text-sm font-semibold text-white hover:bg-slate-700">Re-check</button>
    </section>
  );
}
