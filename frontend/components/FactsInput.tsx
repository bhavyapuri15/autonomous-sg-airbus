"use client";
import { useState } from "react";
import { Button, Card } from "@/components/ui";
import { cn } from "@/lib/cn";
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
    <Card className="border-amber-400 bg-amber-50" aria-label="Configuration facts" data-testid="facts-input">
      <h2 className="mb-1 text-sm font-semibold text-amber-950">Configuration facts needed</h2>
      <p className="mb-3 text-xs text-amber-900">Answer what you know about this aircraft. Unknown answers are not sent.</p>
      <ul className="space-y-2">
        {missing.map((m) => (
          <li key={m} className="flex flex-wrap items-center gap-3 text-sm">
            <span className="min-w-0 flex-1">{factLabel(m)}</span>
            <div role="radiogroup" aria-label={factLabel(m)} className="flex overflow-hidden rounded-lg border border-slate-300 bg-white">
              {(["yes", "no", "unknown"] as const).map((o) => (
                <button key={o} type="button" role="radio" aria-checked={(ans[m] ?? "unknown") === o}
                  onClick={() => setAns({ ...ans, [m]: o })}
                  className={cn("px-3 py-1 text-xs font-medium capitalize", (ans[m] ?? "unknown") === o ? "bg-blue-600 text-white" : "text-slate-700 hover:bg-slate-50")}>
                  {o}
                </button>
              ))}
            </div>
          </li>
        ))}
      </ul>
      <Button variant="primary" className="mt-3" onClick={() => onRecheck(buildFacts(ans))}>Re-check</Button>
    </Card>
  );
}
