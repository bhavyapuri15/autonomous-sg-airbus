"use client";
import type { FormEvent, KeyboardEvent } from "react";
import { Loader2, Search } from "lucide-react";
import { Button, Card, Input, Textarea } from "@/components/ui";

export interface QueryForm {
  question: string; directiveId: string; model: string; serial: string; make: string; useLlm: boolean;
}

const label = "mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate-500";

export function QueryPanel({ form, setForm, onSubmit, loading }: {
  form: QueryForm; setForm: (f: QueryForm) => void; onSubmit: () => void; loading: boolean;
}) {
  const set = <K extends keyof QueryForm>(k: K, v: QueryForm[K]) => setForm({ ...form, [k]: v });
  const go = () => { if (!loading && form.question.trim()) onSubmit(); };
  const submit = (e: FormEvent) => { e.preventDefault(); go(); };
  const key = (e: KeyboardEvent) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); go(); } };
  return (
    <Card className="p-0">
      <form onSubmit={submit} onKeyDown={key} className="space-y-3 p-4" aria-label="Query">
        <div>
          <label className={label} htmlFor="q">Question</label>
          <Textarea id="q" rows={3} maxLength={2000} required value={form.question} onChange={(e) => set("question", e.target.value)}
            className="text-base" placeholder="e.g. Does this proposed AD apply to my airplane?" />
        </div>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          <div><label className={label} htmlFor="did">Directive ID</label><Input id="did" maxLength={100} placeholder="docket, FR doc, AD no." value={form.directiveId} onChange={(e) => set("directiveId", e.target.value)} className="font-mono" /></div>
          <div><label className={label} htmlFor="md">Model</label><Input id="md" maxLength={100} value={form.model} onChange={(e) => set("model", e.target.value)} className="font-mono" /></div>
          <div><label className={label} htmlFor="sn">Serial (MSN)</label><Input id="sn" maxLength={100} value={form.serial} onChange={(e) => set("serial", e.target.value)} className="font-mono" /></div>
          <div><label className={label} htmlFor="mk">Make</label><Input id="mk" maxLength={200} value={form.make} onChange={(e) => set("make", e.target.value)} /></div>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-700" title="When off, answers are extractive only (verbatim passages). Applicability and revision are never LLM-written.">
            <input type="checkbox" className="h-4 w-4 accent-blue-600" checked={form.useLlm} onChange={(e) => set("useLlm", e.target.checked)} />
            LLM-generated summary
            <span className="text-xs text-slate-500">(off = extractive only)</span>
          </label>
          <span className="ml-auto hidden text-xs text-slate-500 md:inline"><kbd className="rounded border border-slate-300 bg-slate-50 px-1 font-mono">⌘/Ctrl</kbd> + <kbd className="rounded border border-slate-300 bg-slate-50 px-1 font-mono">Enter</kbd></span>
          <Button type="submit" variant="primary" size="lg" disabled={loading || !form.question.trim()}>
            {loading ? <Loader2 size={16} className="animate-spin" aria-hidden /> : <Search size={16} aria-hidden />}
            {loading ? "Searching and verifying…" : "Search & verify"}
          </Button>
        </div>
      </form>
    </Card>
  );
}
