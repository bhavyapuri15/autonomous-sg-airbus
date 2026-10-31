"use client";
import Link from "next/link";
import { Menu, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Logo } from "./Logo";

const LINKS = [
  { href: "#top", label: "Home" },
  { href: "#features", label: "Features" },
  { href: "#how-it-works", label: "How It Works" },
  { href: "/directives", label: "Explore Directives" },
];

export function Nav() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 24);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);
  const link = "rounded px-3 py-2 text-sm text-slate-300 transition-colors hover:text-white";
  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 border-b transition-colors ${
        scrolled || open ? "border-white/10 bg-[#081328]" : "border-white/[0.06] bg-[#081328]/40 backdrop-blur-md"
      }`}
    >
      <nav aria-label="Primary" className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Logo />
        <div className="hidden items-center gap-1 md:flex">
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href} className={link}>{l.label}</Link>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <Link href="/dashboard" className="hidden rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-500 sm:inline-flex">
            Launch Workspace
          </Link>
          <button
            type="button"
            className="grid h-10 w-10 place-items-center rounded text-slate-200 hover:bg-white/10 md:hidden"
            aria-expanded={open}
            aria-controls="mobile-menu"
            aria-label={open ? "Close menu" : "Open menu"}
            onClick={() => setOpen((o) => !o)}
          >
            {open ? <X size={20} aria-hidden /> : <Menu size={20} aria-hidden />}
          </button>
        </div>
      </nav>
      {open && (
        <div id="mobile-menu" className="border-t border-white/10 px-4 pb-4 pt-2 md:hidden">
          <div className="flex flex-col">
            {LINKS.map((l) => (
              <Link key={l.href} href={l.href} className={`${link} py-3`} onClick={() => setOpen(false)}>{l.label}</Link>
            ))}
            <Link href="/dashboard" className="mt-2 rounded bg-blue-600 px-4 py-3 text-center text-sm font-medium text-white" onClick={() => setOpen(false)}>
              Launch Workspace
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}
