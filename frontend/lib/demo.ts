import type { QueryForm } from "@/components/QueryPanel";

// Real demo queries against the live dataset (not mock data): they are submitted to the API like any other query.
export const EXAMPLES: { title: string; hint: string; form: QueryForm }[] = [
  {
    title: "Does this proposed AD apply to my airplane?",
    hint: "FAA-2022-0222 · PA-34-200 · s/n 34-7250001",
    form: { question: "Does this proposed AD apply to my airplane?", directiveId: "FAA-2022-0222", model: "PA-34-200", serial: "34-7250001", make: "", useLlm: false },
  },
  {
    title: "What unsafe condition does this proposed AD address?",
    hint: "NPRM-001",
    form: { question: "What unsafe condition does this proposed AD address?", directiveId: "NPRM-001", model: "", serial: "", make: "", useLlm: false },
  },
  {
    title: "Which AD is the most dangerous?",
    hint: "No directive ID: expect the system to abstain",
    form: { question: "Which AD is the most dangerous?", directiveId: "", model: "", serial: "", make: "", useLlm: false },
  },
  {
    title: "Near-miss directive ID",
    hint: "FAA-2026-11844 · expect abstention with did-you-mean",
    form: { question: "What unsafe condition does this proposed AD address?", directiveId: "FAA-2026-11844", model: "", serial: "", make: "", useLlm: false },
  },
  {
    title: "Metadata-only record",
    hint: "NPRM-409 · source text unavailable",
    form: { question: "What unsafe condition does this proposed AD address?", directiveId: "NPRM-409", model: "", serial: "", make: "", useLlm: false },
  },
];

/** Deep link into the AI Search workspace; the workspace pre-fills and runs once. */
export function searchHref(f: { question: string; directiveId?: string; model?: string; serial?: string; make?: string }): string {
  const u = new URLSearchParams();
  u.set("q", f.question);
  if (f.directiveId) u.set("directive", f.directiveId);
  if (f.model) u.set("model", f.model);
  if (f.serial) u.set("serial", f.serial);
  if (f.make) u.set("make", f.make);
  return `/search?${u.toString()}`;
}

export const APPLICABILITY_QUESTION = "Does this proposed AD apply to my airplane?";
