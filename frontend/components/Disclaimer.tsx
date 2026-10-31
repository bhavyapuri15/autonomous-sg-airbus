import { Info } from "lucide-react";
import { DISCLAIMER_FALLBACK } from "@/lib/types";

export function Disclaimer({ text }: { text?: string | null }) {
  return (
    <div role="note" data-testid="disclaimer" className="flex items-start gap-2 rounded-lg border border-slate-300 bg-slate-100 px-3 py-2 text-sm text-slate-800">
      <Info size={15} className="mt-0.5 shrink-0 text-slate-500" aria-hidden />
      <span>{text && text.trim() ? text : DISCLAIMER_FALLBACK}</span>
    </div>
  );
}
