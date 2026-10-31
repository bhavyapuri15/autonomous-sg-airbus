// Configuration-fact helpers. Backend `applicability.missing` entries are either bare tokens ("serial", "model")
// or "<condition_key> (<condition text>)" where condition_key is the key accepted in aircraft.facts.

export type FactAnswer = "yes" | "no" | "unknown";

/** Split "KEY (TEXT)" into key + text. TEXT is the trailing balanced/unclosed parenthesised group. */
export function parseMissing(raw: string): { key: string; text: string } {
  // Preferred backend format: "<key> :: <label>" (unambiguous). The bracket heuristic below is a fallback.
  const sep = raw.indexOf(" :: ");
  if (sep > 0) return { key: raw.slice(0, sep).trim(), text: raw.slice(sep + 4).trim() };
  const open: number[] = [];
  let lastTop = -1;
  for (let i = 0; i < raw.length; i++) {
    if (raw[i] === "(") { if (open.length === 0 && i > 0 && raw[i - 1] === " ") lastTop = i; open.push(i); }
    else if (raw[i] === ")") open.pop();
  }
  // Unclosed group (backend truncates text to 80 chars): its outermost opener starts the text.
  let start = lastTop;
  if (open.length > 0) start = raw[open[0] - 1] === " " ? open[0] : lastTop;
  if (start < 1 || raw[start - 1] !== " ") return { key: raw.trim(), text: "" };
  let text = raw.slice(start).trim();
  if (text.startsWith("(")) text = text.slice(1);
  if (text.endsWith(")") && (text.match(/\(/g)?.length ?? 0) < (text.match(/\)/g)?.length ?? 0)) text = text.slice(0, -1);
  return { key: raw.slice(0, start - 1).trim(), text };
}

export function isConditionKey(raw: string): boolean {
  return /^[a-z_]+:/.test(raw);
}

export function factLabel(raw: string): string {
  const { key, text } = parseMissing(raw);
  const i = key.indexOf(":");
  const kind = i > 0 ? key.slice(0, i) : "";
  const body = i > 0 ? key.slice(i + 1) : key;
  const kinds: Record<string, string> = {
    part_number_installed: "Part number installed",
    modification_incorporated: "Modification incorporated",
    free_text: "Condition",
  };
  const k = kinds[kind] ?? (kind ? kind.replaceAll("_", " ") : "Condition");
  return `${k}: ${text || body}`;
}

/** Only non-Unknown answers are sent; keys are the parsed condition keys. */
export function buildFacts(answers: Record<string, FactAnswer>): Record<string, boolean> {
  const out: Record<string, boolean> = {};
  for (const [raw, a] of Object.entries(answers)) {
    if (a === "unknown") continue;
    out[parseMissing(raw).key] = a === "yes";
  }
  return out;
}
