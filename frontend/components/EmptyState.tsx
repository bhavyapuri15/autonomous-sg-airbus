import { FileSearch, Sparkles } from "lucide-react";
import type { QueryForm } from "@/components/QueryPanel";
import { Card } from "@/components/ui";
import { EXAMPLES } from "@/lib/demo";


export function EmptyState({ onPick }: { onPick: (f: QueryForm) => void }) {
  return (
    <Card className="border-dashed p-6" data-testid="empty-state">
      <div className="flex items-center gap-2 text-slate-900">
        <FileSearch size={20} className="text-blue-600" aria-hidden />
        <h2 className="text-base font-semibold">Search FAA AD proposed rules, with the source for every statement</h2>
      </div>
      <p className="mt-2 max-w-2xl text-sm text-slate-600">
        Ask a question about an FAA Airworthiness Directive proposal. Every statement is shown with its source quote and page.
        Documents in this dataset are mostly <b>proposals</b> (NPRMs), which are not enforceable ADs.
      </p>
      <div className="mt-4 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500"><Sparkles size={13} aria-hidden />Try an example</div>
      <div className="mt-2 flex flex-wrap gap-2">
        {EXAMPLES.map((e) => (
          <button key={e.title} type="button" onClick={() => onPick(e.form)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-left text-sm hover:border-blue-500 hover:bg-blue-50">
            <span className="block font-medium text-slate-900">{e.title}</span>
            <span className="block font-mono text-xs text-slate-500">{e.hint}</span>
          </button>
        ))}
      </div>
    </Card>
  );
}
