import type { ApplicabilityValue, CitationRef, SourceTier } from "@/lib/types";

export function DocClassPill({ docClass }: { docClass?: string | null }) {
  const c = (docClass || "UNKNOWN").toUpperCase();
  const meta: Record<string, { label: string; cls: string }> = {
    NPRM: { label: "NPRM · Proposed rule (not an enforceable AD)", cls: "bg-sky-100 text-sky-900 border-sky-400 border-dashed" },
    SNPRM: { label: "SNPRM · Supplemental proposal (not an enforceable AD)", cls: "bg-sky-100 text-sky-900 border-sky-400 border-dashed" },
    WITHDRAWAL: { label: "WITHDRAWAL · Proposal withdrawn", cls: "bg-slate-200 text-slate-900 border-slate-500" },
    CORRECTION: { label: "CORRECTION · Correction notice", cls: "bg-slate-100 text-slate-900 border-slate-400" },
    FINAL_RULE: { label: "FINAL RULE", cls: "bg-emerald-100 text-emerald-900 border-emerald-500" },
    OTHER: { label: "OTHER document type", cls: "bg-slate-100 text-slate-800 border-slate-400" },
  };
  const m = meta[c] || { label: `${c} · document class`, cls: "bg-slate-100 text-slate-800 border-slate-400" };
  return <span className={`inline-block rounded border px-2 py-0.5 text-xs font-semibold ${m.cls}`}>{m.label}</span>;
}

export function TierBadge({ tier }: { tier: SourceTier }) {
  if (tier === "FR_FULL_TEXT")
    return <span className="rounded border border-emerald-600 bg-emerald-50 px-1.5 py-0.5 text-xs font-medium text-emerald-900">Official FR text</span>;
  return (
    <span className="rounded border border-amber-600 bg-amber-50 px-1.5 py-0.5 text-xs font-medium text-amber-900">
      Spreadsheet metadata, not regulatory text
    </span>
  );
}

export function ApplicabilityBadge({ value }: { value: ApplicabilityValue }) {
  const m: Record<ApplicabilityValue, { icon: string; label: string; sub: string; cls: string }> = {
    APPLICABLE: { icon: "✔", label: "Applicable", sub: "Per the proposed rule text and the configuration given", cls: "bg-emerald-50 border-emerald-600 text-emerald-900" },
    NOT_APPLICABLE: { icon: "✖", label: "Not applicable", sub: "Per the proposed rule text and the configuration given", cls: "bg-slate-100 border-slate-600 text-slate-900" },
    UNKNOWN: { icon: "?", label: "Not determined", sub: "Unknown: the evidence available does not settle this. It is NOT a negative result. Review the source text.", cls: "bg-violet-50 border-violet-600 border-dashed text-violet-900" },
    NOT_EVALUATED: { icon: "–", label: "Not evaluated", sub: "No applicability check was run for this answer", cls: "bg-white border-slate-400 border-dashed text-slate-700" },
  };
  const x = m[value];
  return (
    <div className={`flex items-center gap-3 rounded-lg border-2 px-4 py-3 ${x.cls}`} data-testid="applicability-badge" data-value={value}>
      <span aria-hidden className="text-3xl font-bold">{x.icon}</span>
      <div>
        <div className="text-xl font-bold uppercase tracking-wide">{x.label}</div>
        <div className="text-xs">{x.sub}</div>
      </div>
    </div>
  );
}

export const pageLabel = (c: Pick<CitationRef, "fr_page" | "pdf_page">) =>
  `FR p. ${c.fr_page ?? "n/a"} · PDF p. ${c.pdf_page ?? "n/a"}`;

export function SourceBadge({ source }: { source?: string | null }) {
  const organiser = source === "organiser_sheet";
  return (
    <span className={`inline-block rounded border px-1.5 py-0.5 text-xs font-medium ${organiser ? "border-slate-500 bg-slate-100 text-slate-900" : "border-violet-500 border-dashed bg-violet-50 text-violet-900"}`}>
      {organiser ? "Organiser dataset" : "FR final-rule lookup"}
    </span>
  );
}
