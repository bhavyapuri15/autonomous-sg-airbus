"use client";
import Aurora from "@/components/reactbits/Aurora";
import { PrimaryLink, SecondaryLink } from "./Buttons";
import { useHydrated, useReducedMotion } from "./useReducedMotion";

export function FinalCta() {
  const reduce = useReducedMotion();
  const hydrated = useHydrated();
  return (
    <section aria-labelledby="cta-heading" className="relative isolate overflow-hidden py-24 sm:py-32">
      <div aria-hidden className="cta-gradient absolute inset-0 -z-20" />
      {hydrated && !reduce && (
        <div aria-hidden className="absolute inset-0 -z-10 opacity-40">
          <Aurora colorStops={["#0B3A8F", "#2563EB", "#22B8CF"]} amplitude={0.7} blend={0.6} speed={0.5} height={0.5} glow={0.35} mouseInteraction={false} opacity={0.7} />
        </div>
      )}
      <div className="mx-auto max-w-3xl px-4 text-center sm:px-6">
        <h2 id="cta-heading" className="text-3xl font-semibold tracking-tight text-white sm:text-5xl">Regulatory clarity starts with reliable evidence.</h2>
        <p className="mx-auto mt-5 max-w-2xl text-base leading-relaxed text-slate-300 sm:text-lg">
          Explore FAA regulatory proposals, evaluate documented applicability, and trace answers to their original sources.
        </p>
        <div className="mt-9 flex flex-col items-stretch justify-center gap-3 sm:flex-row sm:items-center">
          <PrimaryLink href="/search">Launch Regulatory Workspace</PrimaryLink>
          <SecondaryLink href="/directives">Browse Directives</SecondaryLink>
        </div>
      </div>
    </section>
  );
}
