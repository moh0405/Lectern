/**
 * Cut a document's pages into passages for retrieval: whole sentences, about `target` words each, with one
 * sentence of overlap so an idea split across a boundary is still findable. The same idea as backend/chunking.py,
 * simpler (no heading or code awareness).
 */

export interface Passage {
  text: string;
  page: number;
  end_page?: number;
}

interface Options {
  target?: number;
  max?: number;
}

const SENTENCE_END = /(?<=[.!?])\s+(?=[A-Z0-9"'(\[])/;
const words = (s: string) => (s.trim() ? s.trim().split(/\s+/).length : 0);

/** Split a sentence that is itself longer than `max` words (tables, run-on text) into word windows. */
function hardSplit(sentence: string, max: number): string[] {
  const w = sentence.split(/\s+/);
  const out: string[] = [];
  for (let i = 0; i < w.length; i += max) out.push(w.slice(i, i + max).join(" "));
  return out;
}

export function chunkPages(pages: string[], { target = 140, max = 220 }: Options = {}): Passage[] {
  const sentences: { text: string; page: number }[] = [];
  pages.forEach((raw, i) => {
    const text = raw.replace(/\s+/g, " ").trim();
    if (!text) return;
    for (const s of text.split(SENTENCE_END)) {
      for (const piece of words(s) > max ? hardSplit(s, max) : [s]) sentences.push({ text: piece, page: i + 1 });
    }
  });

  const out: Passage[] = [];
  let current: typeof sentences = [];
  let count = 0;
  const flush = () => {
    if (!current.length) return;
    const first = current[0]!.page;
    const last = current[current.length - 1]!.page;
    out.push({ text: current.map((s) => s.text).join(" "), page: first, ...(last > first ? { end_page: last } : {}) });
  };
  for (const s of sentences) {
    const n = words(s.text);
    if (count + n > target && current.length) {
      flush();
      const tail = current[current.length - 1]!; // one sentence of overlap
      current = [tail];
      count = words(tail.text);
    }
    current.push(s);
    count += n;
  }
  // Skip a final chunk that holds nothing but the overlap sentence already emitted.
  if (current.length > 1 || out.length === 0) flush();
  return out;
}
