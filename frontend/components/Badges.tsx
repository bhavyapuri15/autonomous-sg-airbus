import { CircleHelp, Info, MinusCircle, ShieldCheck, CheckCircle2 } from "lucide-react";
import type { ApplicabilityValue, CitationRef, SourceTier } from "@/lib/types";
import { cn } from "@/lib/cn";
import { Badge } from "@/components/ui";

export function DocClassPill({ docClass }: { docClass?: string | null }) {
  const c = (docClass || "UNKNOWN").toUpperCase();
  const meta: Record<string, { label: string; tone: "blue" | "slate" | "violet" }> = {
    NPRM: { label: "NPRM · Proposed rule (not an enforceable AD)", tone: "blue" },
    SNPRM: { label: "SNPRM · Supplemental proposal (not an enforceable AD)", tone: "blue" },
    WITHDRAWAL: { label: "WITHDRAWAL · Proposal withdrawn", tone: "slate" },
    CORRECTION: { label: "CORRECTION · Correction notice", tone: "slate" },
    FINAL_RULE: { label: "FINAL RULE", tone: "violet" },
    OTHER: { label: "OTHER document type", tone: "slate" },
  };
  const m = meta[c] || { label: `${c} · document class`, tone: "slate" as const };
  return <Badge tone={m.tone} className={cn("font-semibold", m.tone === "blue" && "border-dashed")}>{m.label}</Badge>;
}

export function TierBadge({ tier }: { tier: SourceTier }) {
  if (tier === "FR_FULL_TEXT")
    return <Badge tone="blue"><ShieldCheck size={12} aria-hidden />Official FR text</Badge>;
  return <Badge tone="amber">Spreadsheet metadata, not regulatory text</Badge>;
}

export function ApplicabilityBadge({ value, label, basis }: { value: ApplicabilityValue; label?: string | null; basis?: string | null }) {
  const m: Record<ApplicabilityValue, { Icon: typeof Info; title: string; sub: string; cls: string }> = {
    APPLICABLE: { Icon: CheckCircle2, title: "Applicable under the proposed rule", sub: "Per the proposed rule text and the configuration given. Not an enforceable requirement.", cls: "bg-blue-50 border-blue-600 text-blue-950" },
    NOT_APPLICABLE: { Icon: MinusCircle, title: "Not applicable under the proposed rule", sub: "Per the proposed rule text and the configuration given.", cls: "bg-slate-100 border-slate-500 text-slate-900" },
    UNKNOWN: { Icon: CircleHelp, title: "Applicability not determined", sub: "The evidence available does not settle this. It is NOT a negative result. Review the source text.", cls: "bg-amber-50 border-amber-500 border-dashed text-amber-950" },
    NOT_EVALUATED: { Icon: Info, title: "Applicability not evaluated", sub: "No applicability check was run for this answer", cls: "bg-white border-slate-300 border-dashed text-slate-700" },
  };
  const x = m[value];
  const title = value === "UNKNOWN" ? x.title : label || x.title;
  const isFinal = basis === "FINAL_RULE";
  const sub = isFinal && (value === "APPLICABLE" || value === "NOT_APPLICABLE")
    ? "Per the published final rule text and the configuration given. Later amendments or supersession were not checked."
    : x.sub;
  return (
    <div className={cn("flex items-center gap-3 rounded-lg border-2 px-4 py-3", x.cls)} data-testid="applicability-badge" data-value={value}>
      <x.Icon size={28} aria-hidden className="shrink-0" />
      <div>
        <div className="text-lg font-semibold">{title}</div>
        <div className="text-xs">{sub}{basis && basis !== "UNKNOWN" ? ` Basis: ${basis.replaceAll("_", " ").toLowerCase()}.` : ""}</div>
      </div>
    </div>
  );
}

export const pageLabel = (c: Pick<CitationRef, "fr_page" | "pdf_page">) =>
  `FR p. ${c.fr_page ?? "n/a"} · PDF p. ${c.pdf_page ?? "n/a"}`;

export function SourceBadge({ source }: { source?: string | null }) {
  const organiser = source === "organiser_sheet";
  return <Badge tone={organiser ? "slate" : "violet"}>{organiser ? "Organiser dataset" : "FR final-rule lookup"}</Badge>;
}
