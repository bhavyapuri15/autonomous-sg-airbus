/**
 * PipelineFlow: custom component (React Bits has no free equivalent of a "center flow" diagram).
 * Four numbered nodes joined by a connector rail with a travelling pulse (pure CSS, see landing.css).
 * Horizontal at lg+, vertical below. Animations are disabled under prefers-reduced-motion.
 */
const STEPS = [
  { n: "01", title: "Ask", body: "Describe your regulatory question or specify an aircraft configuration." },
  { n: "02", title: "Retrieve", body: "Search the indexed Federal Register document corpus for relevant evidence." },
  { n: "03", title: "Analyse", body: "Evaluate applicable conditions and publication relationships using deterministic rules." },
  { n: "04", title: "Verify", body: "Inspect supporting citations directly in the original source documents." },
];

export function PipelineFlow() {
  return (
    <div className="relative mt-16">
      <span aria-hidden className="pf-rail pf-rail-v lg:hidden" />
      <span aria-hidden className="pf-rail pf-rail-h hidden lg:block" />
      <ol className="relative grid gap-10 lg:grid-cols-4 lg:gap-6">
      {STEPS.map((s, i) => (
        <li key={s.n} className="relative flex gap-5 lg:flex-col lg:items-center lg:gap-0 lg:text-center">
          <span
            className="pf-node relative z-10 grid h-14 w-14 shrink-0 place-items-center rounded-full border border-cyan-400/40 bg-[#0d1f3d] font-mono text-sm font-medium text-cyan-300"
            style={{ animationDelay: `${i * 1.2}s` }}
          >
            {s.n}
          </span>
          <div className="lg:mt-6">
            <h3 className="text-lg font-semibold text-white">{s.title}</h3>
            <p className="mt-2 max-w-xs text-sm leading-relaxed text-slate-300">{s.body}</p>
          </div>
        </li>
      ))}
      </ol>
    </div>
  );
}
