const STOP = new Set(
  "a an the is are was were be of in on at to for from by with and or not as it this that what which how why when where do does can".split(" "),
);

/** Lower-cased query terms worth highlighting (stopwords and 1-2 letter words removed). */
export function queryTerms(query: string): string[] {
  const seen = new Set<string>();
  for (const t of query.toLowerCase().match(/[a-z0-9_]+/g) ?? []) {
    if (t.length > 2 && !STOP.has(t)) seen.add(t);
  }
  return [...seen];
}

export interface TextPart {
  text: string;
  match: boolean;
}

/** Split text into parts, marking whole-word, case-insensitive matches of the given terms. */
export function splitByTerms(text: string, terms: string[]): TextPart[] {
  if (!terms.length || !text) return [{ text, match: false }];
  const escaped = terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const re = new RegExp(`\\b(${escaped.join("|")})\\b`, "gi");
  const parts: TextPart[] = [];
  let last = 0;
  for (const m of text.matchAll(re)) {
    const i = m.index ?? 0;
    if (i > last) parts.push({ text: text.slice(last, i), match: false });
    parts.push({ text: m[0], match: true });
    last = i + m[0].length;
  }
  if (last < text.length) parts.push({ text: text.slice(last), match: false });
  return parts.length ? parts : [{ text, match: false }];
}
