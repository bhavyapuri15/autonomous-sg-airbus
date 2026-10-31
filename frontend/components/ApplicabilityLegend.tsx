import { CircleHelp, MinusCircle, Target } from "lucide-react";
import { cn } from "@/lib/cn";

/** Legend for the three applicability outcomes, worded as the API labels them. Stage is a separate field.
 *  Never green, and no check-mark for "applicable": coverage is not a pass or an approval. */
export const OUTCOMES = [
  { key: "APPLICABLE", text: "Applicable under the proposed rule", Icon: Target, cls: "border-blue-600 bg-blue-50 text-blue-950", note: "The proposal text and the configuration given point to this airplane being covered. Not an enforceable requirement." },
  { key: "NOT_APPLICABLE", text: "Not applicable under the proposed rule", Icon: MinusCircle, cls: "border-slate-500 bg-slate-100 text-slate-900", note: "The proposal text and the configuration given exclude this airplane." },
  { key: "UNKNOWN", text: "Applicability not determined", Icon: CircleHelp, cls: "border-amber-500 border-dashed bg-amber-50 text-amber-950", note: "The evidence does not settle it. This is not a negative result." },
] as const;

export function ApplicabilityLegend() {
  return (
    <ul className="grid gap-2 md:grid-cols-3" aria-label="Applicability outcomes" data-testid="applicability-legend">
      {OUTCOMES.map(({ key, text, Icon, cls, note }) => (
        <li key={key} data-outcome={key} className={cn("flex items-start gap-2 rounded-lg border-2 p-2.5 text-xs", cls)}>
          <Icon size={16} className="mt-0.5 shrink-0" aria-hidden />
          <div><div className="text-sm font-semibold">{text}</div><div>{note}</div></div>
        </li>
      ))}
    </ul>
  );
}
