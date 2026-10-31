"use client";
import type { FormEvent } from "react";

export interface QueryForm {
  question: string; directiveId: string; model: string; serial: string; make: string; useLlm: boolean;
}

const input = "w-full rounded border border-slate-400 bg-white px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-600";
const label = "mb-0.5 block text-xs font-semibold text-slate-700";

export function QueryPanel({ form, setForm, onSubmit, loading }: {
  form: QueryForm; setForm: (f: QueryForm) => void; onSubmit: () => void; loading: boolean;
}) {
  const set = <K extends keyof QueryForm>(k: K, v: QueryForm[K]) => setForm({ ...form, [k]: v });
  const submit = (e: FormEvent) => { e.preventDefault(); if (!loading && form.question.trim()) onSubmit(); };
  return (
    <form onSubmit={submit} className="space-y-3 rounded-lg border border-slate-300 bg-white p-4 shadow-sm" aria-label="Query">
      <div>
        <label className={label} htmlFor="q">Question</label>
        <textarea id="q" rows={4} maxLength={2000} required value={form.question} onChange={(e) => set("question", e.target.value)} className={input}
          placeholder="e.g. Does this proposed rule apply to my aircraft?" />
      </div>
      <div>
        <label className={label} htmlFor="did">Directive ID (optional: docket, FR doc number or AD number)</label>
        <input id="did" maxLength={100} value={form.directiveId} onChange={(e) => set("directiveId", e.target.value)} className={`${input} font-mono`} />
      </div>
      <fieldset className="rounded border border-slate-300 p-2">
        <legend className="px-1 text-xs font-semibold text-slate-700">Aircraft configuration (optional)</legend>
        <div className="grid grid-cols-2 gap-2">
          <div><label className={label} htmlFor="mk">Make</label><input id="mk" maxLength={200} value={form.make} onChange={(e) => set("make", e.target.value)} className={input} /></div>
          <div><label className={label} htmlFor="md">Model</label><input id="md" maxLength={100} value={form.model} onChange={(e) => set("model", e.target.value)} className={`${input} font-mono`} /></div>
          <div className="col-span-2"><label className={label} htmlFor="sn">Serial number (MSN)</label><input id="sn" maxLength={100} value={form.serial} onChange={(e) => set("serial", e.target.value)} className={`${input} font-mono`} /></div>
        </div>
      </fieldset>
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" className="mt-1" checked={form.useLlm} onChange={(e) => set("useLlm", e.target.checked)} />
        <span>LLM-generated summary<span className="block text-xs text-slate-600">When off, answers are extractive only (verbatim passages). Applicability and revision are never LLM-written.</span></span>
      </label>
      <button type="submit" disabled={loading || !form.question.trim()} className="w-full rounded bg-slate-900 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50">
        {loading ? "Searching and verifying…" : "Search & verify"}
      </button>
    </form>
  );
}
