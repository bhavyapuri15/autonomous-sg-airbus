// Quote-location helpers: normalise whitespace/hyphenation/case/punctuation, then fuzzy-substring match.

export interface NormIndex { s: string; map: number[] }

/** Keep only letters/digits (lower-cased, NFKC). Hyphens, spaces and line breaks vanish, so
 *  "bracket-\nry" and "brackery" compare equal. `map[i]` is the original index of s[i]. */
export function normIndex(text: string): NormIndex {
  let s = "";
  const map: number[] = [];
  for (let i = 0; i < text.length; i++) {
    const ch = text[i].normalize("NFKC").toLowerCase();
    for (const c of ch) {
      if (/[\p{L}\p{N}]/u.test(c)) { s += c; map.push(i); }
    }
  }
  return { s, map };
}

/** Returns [start, end) in the original haystack text, or null.
 *  1) exact normalised substring; 2) head/tail anchors (handles small OCR/extraction differences). */
export function findQuote(haystack: string, quote: string): [number, number] | null {
  const h = normIndex(haystack);
  const q = normIndex(quote).s;
  if (q.length < 12 || h.s.length === 0) return null;
  const direct = h.s.indexOf(q);
  if (direct >= 0) return [h.map[direct], h.map[direct + q.length - 1] + 1];
  const k = Math.min(30, Math.floor(q.length / 2));
  const head = h.s.indexOf(q.slice(0, k));
  if (head < 0) return null;
  const tail = h.s.indexOf(q.slice(q.length - k), head);
  if (tail < 0) return null;
  const endIdx = tail + k;
  if (endIdx - head > q.length * 1.4 + 20) return null;
  return [h.map[head], h.map[endIdx - 1] + 1];
}

/** For short quotes (< 30 normalised chars, e.g. "AS355NP"): index of the first span whose normalised text contains
 *  the normalised quote, else -1. */
export function findShortQuoteSpan(spans: string[], quote: string): number {
  const q = normIndex(quote).s;
  if (q.length === 0 || q.length >= 30) return -1;
  return spans.findIndex((t) => normIndex(t).s.includes(q));
}
