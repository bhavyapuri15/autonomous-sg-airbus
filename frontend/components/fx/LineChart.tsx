"use client";
import { useState } from "react";

export interface LinePoint { x: string; y: number | null; label?: string }
export interface LineSeries { id: string; name: string; color: string; points: LinePoint[] }

const W = 720, H = 300, M = { l: 48, r: 16, t: 16, b: 52 };
const MARKS = ["circle", "square", "diamond"] as const;

function Mark({ shape, cx, cy, color, r = 5 }: { shape: (typeof MARKS)[number]; cx: number; cy: number; color: string; r?: number }) {
  const common = { fill: color, stroke: "#fff", strokeWidth: 2 };
  if (shape === "square") return <rect x={cx - r} y={cy - r} width={2 * r} height={2 * r} {...common} />;
  if (shape === "diamond") return <polygon points={`${cx},${cy - r - 1} ${cx + r + 1},${cy} ${cx},${cy + r + 1} ${cx - r - 1},${cy}`} {...common} />;
  return <circle cx={cx} cy={cy} r={r} {...common} />;
}

/**
 * Accessible SVG line chart. One mark per real data point; null values are gaps (never interpolated).
 * Categories on the x axis are the run timestamps in order. Values on hover/focus; table fallback below.
 */
export function LineChart({ series, xLabels, yLabel, xLabel, title }: { series: LineSeries[]; xLabels: string[]; yLabel: string; xLabel: string; title: string }) {
  const [active, setActive] = useState<{ s: number; i: number } | null>(null);
  const n = xLabels.length;
  const iw = W - M.l - M.r, ih = H - M.t - M.b;
  const px = (i: number) => M.l + (n <= 1 ? iw / 2 : (i / (n - 1)) * iw);
  const py = (v: number) => M.t + (1 - v) * ih;
  const ticks = [0, 0.25, 0.5, 0.75, 1];
  const act = active ? series[active.s]?.points[active.i] : null;
  return (
    <figure className="space-y-2" data-testid="line-chart">
      <figcaption className="text-sm font-semibold text-slate-900">{title}</figcaption>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-700" aria-label="Legend">
        {series.map((s, si) => (
          <li key={s.id} className="inline-flex items-center gap-1.5">
            <svg width="14" height="14" aria-hidden><Mark shape={MARKS[si % 3]} cx={7} cy={7} color={s.color} r={4} /></svg>{s.name}
          </li>
        ))}
      </ul>
      <div className="relative">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={`${title}. ${series.map((s) => `${s.name}: ${s.points.filter((p) => p.y !== null).length} measured runs`).join("; ")}.`}>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={M.l} x2={W - M.r} y1={py(t)} y2={py(t)} stroke="#e2e8f0" strokeWidth={1} />
              <text x={M.l - 8} y={py(t) + 4} textAnchor="end" fontSize="11" fill="#475569">{t.toFixed(2)}</text>
            </g>
          ))}
          <text transform={`translate(12 ${M.t + ih / 2}) rotate(-90)`} textAnchor="middle" fontSize="11" fill="#475569">{yLabel}</text>
          {xLabels.map((x, i) => (
            <text key={x + i} x={px(i)} y={H - M.b + 16} textAnchor="end" fontSize="10" fill="#475569" transform={`rotate(-30 ${px(i)} ${H - M.b + 16})`}>{x}</text>
          ))}
          <text x={M.l + iw / 2} y={H - 4} textAnchor="middle" fontSize="11" fill="#475569">{xLabel}</text>
          {series.map((s, si) => {
            // draw separate segments between consecutive measured points only (a missing run is a gap)
            const segs: { x: number; y: number }[][] = [];
            let cur: { x: number; y: number }[] = [];
            s.points.forEach((p, i) => { if (p.y === null) { if (cur.length) segs.push(cur); cur = []; } else cur.push({ x: px(i), y: py(p.y) }); });
            if (cur.length) segs.push(cur);
            return (
              <g key={s.id} data-series={s.id}>
                {segs.filter((g) => g.length > 1).map((g, k) => (
                  <path key={k} className="linechart-path" pathLength={1} d={g.map((p, j) => `${j ? "L" : "M"}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ")} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
                ))}
                {s.points.map((p, i) => p.y === null ? null : (
                  <g key={i} data-testid="line-point" tabIndex={0} role="img" aria-label={`${s.name}, ${xLabels[i]}: ${p.y.toFixed(4)}${p.label ? `, ${p.label}` : ""}`}
                    onMouseEnter={() => setActive({ s: si, i })} onMouseLeave={() => setActive(null)} onFocus={() => setActive({ s: si, i })} onBlur={() => setActive(null)}>
                    <circle cx={px(i)} cy={py(p.y)} r={12} fill="transparent" />
                    <Mark shape={MARKS[si % 3]} cx={px(i)} cy={py(p.y)} color={s.color} />
                  </g>
                ))}
              </g>
            );
          })}
        </svg>
        {active && act && act.y !== null && (
          <div role="tooltip" className="pointer-events-none absolute rounded-md border border-slate-200 bg-white px-2 py-1 text-xs shadow-card"
            style={{ left: `${(px(active.i) / W) * 100}%`, top: `${(py(act.y) / H) * 100}%`, transform: "translate(-50%, -130%)" }}>
            <div className="font-semibold text-slate-900">{series[active.s].name}: <span className="font-mono">{act.y.toFixed(4)}</span></div>
            <div className="text-slate-600">{xLabels[active.i]}{act.label ? ` · ${act.label}` : ""}</div>
          </div>
        )}
      </div>
      <details className="text-xs text-slate-600">
        <summary className="cursor-pointer">Show as table</summary>
        <table className="mt-1 w-full border-collapse font-mono">
          <thead><tr><th className="p-1 text-left">Run</th>{series.map((s) => <th key={s.id} className="p-1 text-left">{s.name}</th>)}</tr></thead>
          <tbody>{xLabels.map((x, i) => <tr key={x + i} className="border-t border-slate-100"><td className="p-1">{x}</td>{series.map((s) => <td key={s.id} className="p-1">{s.points[i]?.y == null ? "Not measured" : s.points[i].y!.toFixed(4)}</td>)}</tr>)}</tbody>
        </table>
      </details>
    </figure>
  );
}
