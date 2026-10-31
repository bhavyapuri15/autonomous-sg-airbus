import Link from "next/link";
import type { ReactNode } from "react";

const base = "inline-flex items-center justify-center gap-2 rounded px-5 py-3 text-sm font-medium transition-colors";
export function PrimaryLink({ href, children }: { href: string; children: ReactNode }) {
  return <Link href={href} className={`${base} bg-blue-600 text-white shadow-[0_0_0_1px_rgba(255,255,255,0.08)_inset] hover:bg-blue-500`}>{children}</Link>;
}
export function SecondaryLink({ href, children }: { href: string; children: ReactNode }) {
  return <Link href={href} className={`${base} border border-white/20 bg-white/[0.04] text-slate-100 hover:bg-white/10`}>{children}</Link>;
}
