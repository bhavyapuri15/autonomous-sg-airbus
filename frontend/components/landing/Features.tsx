"use client";
import { FileSearch, History, Search, SlidersHorizontal } from "lucide-react";
import SpotlightCard from "@/components/reactbits/SpotlightCard";

const ITEMS = [
  { icon: Search, title: "Intelligent Document Search", body: "Find relevant FAA directives using natural-language questions, docket identifiers, and document references." },
  { icon: SlidersHorizontal, title: "Configuration-Aware Analysis", body: "Evaluate proposed applicability against aircraft models, serial numbers, and supported equipment conditions." },
  { icon: FileSearch, title: "Source-Level Traceability", body: "Verify every supported claim against original Federal Register documents, pages, and sections." },
  { icon: History, title: "Revision Intelligence", body: "Explore publication histories, proposed supersessions, corrections, and regulatory status." },
];

export function Features() {
  return (
    <section id="features" className="on-light bg-[#F7F9FC] py-20 text-slate-900 sm:py-28">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center">
          <p className="font-mono text-xs font-medium uppercase tracking-[0.12em] sm:tracking-[0.2em] text-blue-600">FEATURES</p>
          <h2 className="mt-4 text-3xl font-semibold tracking-tight text-[#101B30] sm:text-4xl">Everything you need to verify regulatory intelligence.</h2>
          <p className="mt-4 text-base leading-relaxed text-slate-600 sm:text-lg">
            From finding the right directive to understanding its applicability, every step is designed for clarity and traceability.
          </p>
        </div>
        <ul className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {ITEMS.map(({ icon: Icon, title, body }) => (
            <li key={title} className="flex">
              <SpotlightCard theme="light" spotlightColor="#2563EB" intensity={0.5} className="!w-full !rounded-xl !p-6">
                <span className="grid h-10 w-10 place-items-center rounded-lg bg-blue-50 text-blue-600">
                  <Icon size={20} strokeWidth={1.75} aria-hidden />
                </span>
                <h3 className="mt-5 text-lg font-semibold tracking-tight text-[#101B30]">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-600">{body}</p>
              </SpotlightCard>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
