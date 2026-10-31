import { Card, Skeleton } from "@/components/ui";

export function ResultSkeleton() {
  return (
    <div className="space-y-4" role="status" aria-label="Searching and verifying">
      <Skeleton className="h-12 w-full" />
      <Card><Skeleton className="h-4 w-40" /><Skeleton className="mt-3 h-6 w-3/4" /><Skeleton className="mt-3 h-4 w-1/2" /></Card>
      <div className="grid gap-3 md:grid-cols-3"><Skeleton className="h-24" /><Skeleton className="h-24" /><Skeleton className="h-24" /></div>
      <Card><Skeleton className="h-4 w-48" /><Skeleton className="mt-3 h-14 w-full" /><Skeleton className="mt-2 h-14 w-full" /></Card>
      <span className="sr-only">Working…</span>
    </div>
  );
}
