"use client";
import { useState } from "react";
import answered from "@/fixtures/answered.json";
import needs from "@/fixtures/needs_info.json";
import abstained from "@/fixtures/abstained.json";
import { AnswerPanel } from "@/components/AnswerPanel";
import { DocumentViewer } from "@/components/DocumentViewer";
import type { CitationRef, QueryResponse } from "@/lib/types";

const sets: Record<string, QueryResponse> = {
  answered: answered as unknown as QueryResponse,
  needs_info: needs as unknown as QueryResponse,
  abstained: abstained as unknown as QueryResponse,
};

export default function FixturePage() {
  const [k, setK] = useState("answered");
  const [cite, setCite] = useState<CitationRef | null>(null);
  return (
    <div className="space-y-3">
      <div role="alert" className="rounded border-2 border-fuchsia-700 bg-fuchsia-100 p-3 text-center font-bold text-fuchsia-950">
        SYNTHETIC FIXTURE — invented data for UI development. Not real FAA content.
      </div>
      <div className="flex gap-2">{Object.keys(sets).map((n) => (
        <button key={n} onClick={() => setK(n)} className={`rounded border px-3 py-1 text-sm ${k === n ? "bg-slate-900 text-white" : "bg-white"}`}>{n}</button>
      ))}</div>
      <div className={`grid gap-4 ${cite ? "grid-cols-2" : "grid-cols-1"}`}>
        <AnswerPanel response={sets[k]} onOpenCitation={setCite} />
        {cite && <DocumentViewer citation={cite} onClose={() => setCite(null)} />}
      </div>
    </div>
  );
}
