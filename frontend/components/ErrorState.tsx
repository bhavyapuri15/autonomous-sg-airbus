import { ApiError } from "@/lib/api";

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const e = error instanceof ApiError ? error : null;
  return (
    <div role="alert" className="rounded border border-red-500 bg-red-50 p-3 text-sm text-red-900">
      <div className="font-semibold">API error{e ? ` (${e.kind}${e.status ? ` ${e.status}` : ""})` : ""}</div>
      <div>{e ? e.message : String(error)}</div>
      {e?.detail && <div className="mt-1 font-mono text-xs">{e.detail}</div>}
      {onRetry && <button onClick={onRetry} className="mt-2 rounded border border-red-700 px-2 py-0.5 text-xs hover:bg-red-100">Retry</button>}
    </div>
  );
}
