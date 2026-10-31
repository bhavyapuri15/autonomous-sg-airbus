import { isRec, type Rec } from "./loose";

export interface EvalRun { file: string; split: string | null; timestamp: string | null; families: string[]; runtime_s: number | null; metrics: Rec }

export function parseRuns(data: unknown): EvalRun[] {
  if (!Array.isArray(data)) return [];
  return data.filter(isRec).map((r) => ({
    file: String(r.file ?? ""), split: typeof r.split === "string" ? r.split : null, timestamp: typeof r.timestamp === "string" ? r.timestamp : null,
    families: Array.isArray(r.families) ? r.families.map(String) : [], runtime_s: typeof r.runtime_s === "number" ? r.runtime_s : null,
    metrics: isRec(r.metrics) ? r.metrics : {},
  }));
}

/** Walk a path; returns a finite number or null (never a default). */
export function dig(o: unknown, path: string): unknown {
  let cur: unknown = o;
  for (const k of path.split(".")) { if (!isRec(cur)) return null; cur = cur[k]; }
  return cur ?? null;
}
export const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

export interface MetricPick { value: number | null; n: number | null; run: EvalRun | null; passed?: number | null }

/** Most recent run (runs are timestamp-sorted) that has a numeric value at `path`; n read from `nPath`. */
export function latestWith(runs: EvalRun[], path: string, nPath: string): MetricPick {
  for (let i = runs.length - 1; i >= 0; i--) {
    const v = num(dig(runs[i].metrics, path));
    if (v !== null) return { value: v, n: num(dig(runs[i].metrics, nPath)), run: runs[i] };
  }
  return { value: null, n: null, run: null };
}

export const isLocked = (r: EvalRun) => r.split === "locked" || r.file.endsWith("_locked.json");
export const devRuns = (runs: EvalRun[]) => runs.filter((r) => !isLocked(r));
export const lockedRuns = (runs: EvalRun[]) => runs.filter(isLocked);

/** Chart series over runs that contain the family; a run without the value is null (a gap), never interpolated. */
export function seriesOver(runs: EvalRun[], path: string): (number | null)[] {
  return runs.map((r) => num(dig(r.metrics, path)));
}
