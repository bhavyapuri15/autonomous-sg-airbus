import { AlertTriangle } from "lucide-react";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui";

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const e = error instanceof ApiError ? error : null;
  return (
    <div role="alert" className="flex items-start gap-2 rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-900">
      <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden />
      <div className="min-w-0 flex-1">
        <div className="font-semibold">API error{e ? ` (${e.kind}${e.status ? ` ${e.status}` : ""})` : ""}</div>
        <div>{e ? e.message : String(error)}</div>
        {e?.detail && <div className="mt-1 break-words font-mono text-xs">{e.detail}</div>}
        {onRetry && <Button size="sm" variant="danger" className="mt-2" onClick={onRetry}>Retry</Button>}
      </div>
    </div>
  );
}
