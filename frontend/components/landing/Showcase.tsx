import Image from "next/image";

/** Positions are percentages of the 1440x900 screenshot (public/landing/workspace.png), so they track the image at any width. */
const CALLOUTS = [
  { label: "Natural-language search", x: 46, y: 17, side: "right" },
  { label: "Publication status", x: 58, y: 51.5, side: "right" },
  { label: "Structured answers", x: 36, y: 58.5, side: "left" },
  { label: "Applicability results", x: 39, y: 79, side: "right" },
  { label: "Evidence cards", x: 88, y: 49, side: "left" },
  { label: "Original PDF citations", x: 88, y: 81, side: "left" },
] as const;

export function Showcase() {
  return (
    <section id="showcase" className="on-light bg-white py-20 text-slate-900 sm:py-28">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center">
          <p className="font-mono text-xs font-medium uppercase tracking-[0.12em] sm:tracking-[0.2em] text-blue-600">EVIDENCE</p>
          <h2 className="mt-4 text-3xl font-semibold tracking-tight text-[#101B30] sm:text-4xl">Every answer, backed by evidence.</h2>
          <p className="mt-4 text-base leading-relaxed text-slate-600 sm:text-lg">
            Explore regulatory information and inspect the exact documents supporting each result.
          </p>
        </div>
        <div className="relative mt-14">
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-[0_30px_80px_-30px_rgba(16,27,48,0.35)]">
            <Image
              src="/landing/workspace.png"
              alt="Screenshot of the AD Trace workspace showing a search form, a structured applicability answer for a proposed rule, publication status cards, and the original Federal Register PDF with the cited quote highlighted."
              width={1440}
              height={900}
              loading="lazy"
              sizes="(min-width: 1152px) 1100px, 100vw"
              className="block h-auto w-full"
            />
          </div>
          <div aria-hidden className="pointer-events-none absolute inset-0">
            {CALLOUTS.map((c, i) => (
              <span key={c.label} className="absolute" style={{ left: `${c.x}%`, top: `${c.y}%` }}>
                <span className="absolute -left-2.5 -top-2.5 grid h-5 w-5 place-items-center rounded-full bg-blue-600 font-mono text-[10px] font-semibold text-white ring-2 ring-white">{i + 1}</span>
                <span
                  className={`absolute top-0 hidden -translate-y-1/2 whitespace-nowrap rounded bg-[#101B30] px-2.5 py-1 text-xs font-medium text-white shadow-lg md:block ${
                    c.side === "right" ? "left-4" : "right-4"
                  }`}
                >
                  {c.label}
                </span>
              </span>
            ))}
          </div>
        </div>
        <ol className="mt-6 grid gap-2 text-sm text-slate-700 sm:grid-cols-2 md:hidden">
          {CALLOUTS.map((c, i) => (
            <li key={c.label} className="flex items-center gap-3">
              <span aria-hidden className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-blue-600 font-mono text-[10px] font-semibold text-white">{i + 1}</span>
              {c.label}
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
