import Link from "next/link";
import { Logo } from "./Logo";

const LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/search", label: "AI Search" },
  { href: "/directives", label: "Directives" },
  { href: "/applicability", label: "Applicability" },
  { href: "/evaluation", label: "Evaluation" },
];

export function Footer() {
  return (
    <footer className="border-t border-white/10 bg-[#060f20] py-12">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-8 md:flex-row md:items-start md:justify-between">
          <div>
            <Logo />
            <p className="mt-4 text-sm text-slate-300">Airbus Challenge #4 · Autonomous SG 2026</p>
            <p className="mt-1 text-sm text-slate-400">Independent hackathon prototype.</p>
          </div>
          <nav aria-label="Footer">
            <ul className="flex flex-wrap gap-x-6 gap-y-2">
              {LINKS.map((l) => (
                <li key={l.href}>
                  <Link href={l.href} className="rounded text-sm text-slate-300 hover:text-white">{l.label}</Link>
                </li>
              ))}
            </ul>
          </nav>
        </div>
        <div className="mt-10 border-t border-white/10 pt-6 text-xs leading-relaxed text-slate-400">
          <p>Decision-support prototype. Not a certified airworthiness or regulatory compliance determination.</p>
          <p className="mt-2">
            Animations: <a href="https://reactbits.dev" className="underline hover:text-white" rel="noreferrer">React Bits</a> (MIT + Commons Clause)
          </p>
        </div>
      </div>
    </footer>
  );
}
