import "./globals.css";
import Link from "next/link";
import type { ReactNode } from "react";

export const metadata = { title: "AD Trace - traceable search for FAA AD proposed rules" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="bg-slate-900 text-slate-100">
          <div className="mx-auto flex max-w-[1400px] items-center gap-6 px-4 py-2.5">
            <span className="font-semibold tracking-tight">AD Trace</span>
            <nav className="flex gap-4 text-sm" aria-label="Main">
              <Link className="hover:underline" href="/">Search &amp; verify</Link>
              <Link className="hover:underline" href="/directives">Directives</Link>
              <Link className="hover:underline" href="/evaluation">Evaluation</Link>
            </nav>
            <span className="ml-auto text-xs text-slate-300">FAA AD proposed rules (Federal Register)</span>
          </div>
        </header>
        <main className="mx-auto max-w-[1400px] px-4 py-4">{children}</main>
      </body>
    </html>
  );
}
