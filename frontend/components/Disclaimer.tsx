import { DISCLAIMER_FALLBACK } from "@/lib/types";

export function Disclaimer({ text }: { text?: string | null }) {
  return (
    <div role="note" data-testid="disclaimer" className="rounded border border-slate-500 bg-slate-200 px-3 py-2 text-sm font-medium text-slate-900">
      {text && text.trim() ? text : DISCLAIMER_FALLBACK}
    </div>
  );
}
