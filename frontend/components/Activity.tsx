"use client";
import { Activity as ActivityIcon } from "lucide-react";
import AnimatedList from "@/components/reactbits/AnimatedList";
import { Card, CardTitle } from "@/components/ui";
import type { Timings } from "@/lib/types";

/** Real pipeline stages with the real durations returned in response.timings_ms. Nothing here is simulated. */
export function Activity({ timings }: { timings: Timings }) {
  const stages: [string, number][] = [
    ["Retrieval", timings.retrieval], ["Engines (applicability, revision)", timings.engines], ["Generation", timings.generation],
    ["Verification", timings.verification], ["Total", timings.total],
  ];
  const items = stages.filter(([, ms]) => typeof ms === "number").map(([title, ms]) => ({ id: title, title, meta: `${ms} ms` }));
  return (
    <Card aria-label="Activity" data-testid="activity">
      <CardTitle icon={<ActivityIcon size={14} aria-hidden />}>Activity (measured stage timings)</CardTitle>
      <AnimatedList items={items} theme="light" frame={false} showGradients={false} width="100%" maxHeight={260} enableArrowNavigation={false} selectOnHover={false}
        renderItem={(it) => {
          const e = it as { title: string; meta: string };
          return <div className="flex items-center justify-between gap-3 px-3 py-1.5 text-sm"><span>{e.title}</span><span className="font-mono text-xs text-slate-600">{e.meta}</span></div>;
        }} />
    </Card>
  );
}
