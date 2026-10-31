// Helpers for endpoints whose response shape is not fixed in schemas.py. Render only what is present.
export type Rec = Record<string, unknown>;
export const isRec = (v: unknown): v is Rec => typeof v === "object" && v !== null && !Array.isArray(v);
export const str = (v: unknown): string => (v === null || v === undefined ? "" : typeof v === "object" ? JSON.stringify(v) : String(v));
export function pickList(data: unknown, keys: string[]): Rec[] {
  if (Array.isArray(data)) return data.filter(isRec);
  if (isRec(data)) for (const k of keys) if (Array.isArray(data[k])) return (data[k] as unknown[]).filter(isRec);
  return [];
}
