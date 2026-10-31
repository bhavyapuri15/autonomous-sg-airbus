"use client";
import Image from "next/image";
import Aurora from "@/components/reactbits/Aurora";
import BlurText from "@/components/reactbits/BlurText";
import StarBorder from "@/components/reactbits/StarBorder";
import { PrimaryLink, SecondaryLink } from "./Buttons";
import { useHydrated, useReducedMotion } from "./useReducedMotion";

const HEADLINE = "Aerospace Intelligence. Verified.";

export function Hero() {
  const reduce = useReducedMotion();
  const hydrated = useHydrated();
  return (
    <section id="top" className="relative isolate overflow-hidden pt-16">
      {/* Static gradient is always rendered: it is the base, the reduced-motion version and the WebGL fallback. */}
      <div aria-hidden className="hero-gradient absolute inset-0 -z-30" />
      {hydrated && !reduce && (
        <div aria-hidden className="absolute inset-x-0 top-0 -z-20 h-[640px] opacity-70">
          <Aurora colorStops={["#0B3A8F", "#2563EB", "#22B8CF"]} amplitude={0.9} blend={0.6} speed={0.6} height={0.6} glow={0.5} mouseInteraction={false} opacity={0.8} />
        </div>
      )}
      <div aria-hidden className="dot-grid absolute inset-0 -z-10" />
      <div aria-hidden className="absolute inset-x-0 bottom-0 -z-10 h-40 bg-gradient-to-b from-transparent to-[#081328]" />

      <div className="mx-auto max-w-5xl px-4 pb-10 pt-20 text-center sm:px-6 sm:pt-28 lg:pt-32">
        <p className="font-mono text-xs font-medium uppercase tracking-[0.12em] sm:tracking-[0.2em] text-cyan-300">AEROSPACE REGULATORY INTELLIGENCE</p>
        {reduce ? (
          <h1 className="mt-6 text-5xl font-semibold leading-[1.05] tracking-tight text-white sm:text-6xl lg:text-7xl">
            Aerospace Intelligence. <span className="grad-text">Verified.</span>
          </h1>
        ) : (
          <>
            {/* BlurText renders a <p>, which is not valid inside <h1>: the h1 carries the text for assistive tech
                and the animated copy is a decorative sibling. */}
            <h1 className="sr-only">{HEADLINE}</h1>
            <div aria-hidden className="mt-6 text-5xl font-semibold leading-[1.05] tracking-tight text-white sm:text-6xl lg:text-7xl flex flex-col items-center sm:block">
              <BlurText text="Aerospace Intelligence." trigger="load" delay={110} className="justify-center" />
              <BlurText text="Verified." trigger="load" delay={200} className="grad-text justify-center sm:inline-flex sm:ml-[0.25em]" />
            </div>
          </>
        )}
        <p className="mx-auto mt-6 max-w-2xl text-lg text-slate-200 sm:text-xl">
          Find, understand, and verify aviation regulatory information with evidence-backed AI.
        </p>
        <p className="mx-auto mt-4 max-w-2xl text-base leading-relaxed text-slate-400">
          Built for engineers who need precise answers, configuration-aware analysis, and direct access to the original regulatory evidence.
        </p>
        <div className="mt-9 flex flex-col items-stretch justify-center gap-3 sm:flex-row sm:items-center">
          <PrimaryLink href="/directives">Explore Directives</PrimaryLink>
          <SecondaryLink href="/search">Open AI Search</SecondaryLink>
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-4 pb-20 sm:px-6 lg:pb-28">
        <StarBorder
          as="div"
          theme="dark"
          backgroundColor="#0c1a33"
          color="#22B8CF"
          trailColor="#2563EB"
          thickness={1}
          radius={14}
          stars={1}
          glow={0.25}
          sparkle={false}
          hover="none"
          className="!block !w-full !p-1.5 shadow-[0_30px_80px_-20px_rgba(37,99,235,0.45)]"
        >
          <div className="overflow-hidden rounded-[10px] border border-white/10 bg-white">
            <div className="flex items-center gap-2 border-b border-slate-200 bg-slate-100 px-4 py-2.5">
              <span aria-hidden className="flex gap-1.5">
                <i className="h-2.5 w-2.5 rounded-full bg-slate-300" />
                <i className="h-2.5 w-2.5 rounded-full bg-slate-300" />
                <i className="h-2.5 w-2.5 rounded-full bg-slate-300" />
              </span>
              <span className="ml-3 truncate rounded bg-white px-3 py-0.5 font-mono text-[11px] text-slate-500">AD Trace · Search &amp; verify</span>
            </div>
            <Image
              src="/landing/workspace.png"
              alt="AD Trace workspace: a question and aircraft configuration form, a proposed-rule applicability answer with publication status and conditions, and a side panel showing the cited quote in the original Federal Register PDF."
              width={1440}
              height={900}
              priority
              sizes="(min-width: 1152px) 1100px, 100vw"
              className="block h-auto w-full"
            />
          </div>
        </StarBorder>
      </div>
    </section>
  );
}
