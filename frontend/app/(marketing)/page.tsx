import { FinalCta } from "@/components/landing/FinalCta";
import { Features } from "@/components/landing/Features";
import { Footer } from "@/components/landing/Footer";
import { Hero } from "@/components/landing/Hero";
import { Nav } from "@/components/landing/Nav";
import { PipelineFlow } from "@/components/landing/PipelineFlow";
import { Showcase } from "@/components/landing/Showcase";

export default function Landing() {
  return (
    <div className="landing-root">
      <Nav />
      <main>
        <Hero />
        <Features />
        <section id="how-it-works" className="relative bg-[#0a1730] py-20 sm:py-28">
          <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
            <div className="mx-auto max-w-3xl text-center">
              <p className="font-mono text-xs font-medium uppercase tracking-[0.12em] sm:tracking-[0.2em] text-cyan-300">WORKFLOW</p>
              <h2 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-4xl">From complex documents to verifiable answers.</h2>
              <p className="mt-4 text-base leading-relaxed text-slate-300 sm:text-lg">
                A transparent workflow that keeps source evidence at the centre of every result.
              </p>
            </div>
            <PipelineFlow />
          </div>
        </section>
        <Showcase />
        <FinalCta />
      </main>
      <Footer />
    </div>
  );
}
