"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { BarChart3, Database, FileSearch, Info, Search } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { isRec } from "@/lib/loose";

const NAV = [
  { href: "/search", label: "Search & verify", icon: Search },
  { href: "/directives", label: "Directives", icon: FileSearch },
  { href: "/evaluation", label: "Evaluation", icon: BarChart3 },
];

const SRC_LABEL: Record<string, string> = { organiser_sheet: "Organiser dataset", fr_final_rule_lookup: "FR final-rule lookup" };

function Corpus() {
  const [db, setDb] = useState<Record<string, unknown> | null | "err">(null);
  useEffect(() => {
    let off = false;
    api.health().then((h) => !off && setDb(isRec(h.db) ? h.db : "err")).catch(() => !off && setDb("err"));
    return () => { off = true; };
  }, []);
  const by = db && db !== "err" && isRec(db.documents_by_source) ? (db.documents_by_source as Record<string, number>) : null;
  const pages = db && db !== "err" && typeof db.pages === "number" ? db.pages : null;
  return (
    <div className="mx-3 rounded-lg border border-white/10 bg-white/5 p-3 text-xs max-[1099px]:hidden" aria-label="Corpus" data-testid="corpus-panel">
      <div className="mb-2 flex items-center gap-1.5 font-semibold uppercase tracking-wide text-slate-400"><Database size={13} aria-hidden /> Corpus</div>
      {db === null && <div className="text-slate-400">Loading…</div>}
      {db === "err" && <div className="text-slate-400">Corpus counts unavailable</div>}
      {by && (
        <dl className="space-y-1 text-slate-300">
          {Object.entries(by).map(([k, v]) => (
            <div key={k} className="flex justify-between gap-2"><dt>{SRC_LABEL[k] ?? k}</dt><dd className="font-mono text-slate-100">{v}</dd></div>
          ))}
          {pages !== null && <div className="flex justify-between gap-2 border-t border-white/10 pt-1"><dt>Pages indexed</dt><dd className="font-mono text-slate-100">{pages}</dd></div>}
        </dl>
      )}
    </div>
  );
}

export function Sidebar() {
  const path = usePathname();
  return (
    <aside className="sidebar-scroll flex h-screen w-[232px] shrink-0 flex-col gap-4 overflow-y-auto bg-navy py-4 text-slate-200 max-[1099px]:w-16" aria-label="Sidebar">
      <div className="px-4 max-[1099px]:px-0 max-[1099px]:text-center">
        <div className="flex items-center gap-2 max-[1099px]:justify-center">
          <span className="grid h-7 w-7 place-items-center rounded-md bg-blue-600 text-xs font-bold text-white" aria-hidden>AD</span>
          <span className="text-base font-semibold tracking-tight text-white max-[1099px]:hidden">AD Trace</span>
        </div>
        <div className="mt-1 text-[11px] leading-tight text-slate-400 max-[1099px]:hidden">FAA AD proposals · Federal Register</div>
      </div>
      <nav aria-label="Main" className="flex flex-col gap-0.5 px-2">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = path.startsWith(href);
          return (
            <Link key={href} href={href} title={label} aria-current={active ? "page" : undefined}
              className={cn("flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium max-[1099px]:justify-center max-[1099px]:px-0", active ? "bg-blue-600/20 text-white ring-1 ring-inset ring-blue-400/40" : "text-slate-300 hover:bg-white/5 hover:text-white")}>
              <Icon size={16} aria-hidden /><span className="max-[1099px]:hidden">{label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="flex-1" />
      <Corpus />
      <div className="mx-3 flex items-start gap-1.5 rounded-lg border border-amber-400/30 bg-amber-400/10 px-2.5 py-2 text-[11px] leading-snug text-amber-100 max-[1099px]:mx-auto max-[1099px]:px-2" title="Decision support only. Not an official determination. Current authoritative status is not verified.">
        <Info size={13} className="mt-0.5 shrink-0" aria-hidden />
        <span className="max-[1099px]:hidden">Decision support only. Not verified against current authoritative status.</span>
      </div>
    </aside>
  );
}
