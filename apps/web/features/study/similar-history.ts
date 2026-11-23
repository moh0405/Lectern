import type { SimilarExample, Turn } from "@/features/ask/session";

export interface SimilarEntry {
  question: string;
  /** The question it was written from. */
  from: string;
  /** The passage it was written from, when known. */
  source?: string;
}

export const MAX_SIMILAR_HISTORY = 10;

const sameText = (text: string) => text.trim().replace(/\s+/g, " ").toLowerCase();

/** Practice questions the Understanding step already saved on each turn, newest first, without repeats. */
export function similarHistory(turns: Turn[], limit = MAX_SIMILAR_HISTORY): SimilarEntry[] {
  const seen = new Set<string>();
  const entries: SimilarEntry[] = [];
  for (const turn of turns) {
    // Read from browser storage, which may hold an older or damaged shape.
    const saved: unknown[] = Array.isArray(turn.similar) ? turn.similar : [];
    for (const raw of [...saved].reverse()) {
      const example = raw as Partial<SimilarExample> | null;
      if (typeof example?.question !== "string") continue;
      const key = sameText(example.question);
      if (!key || seen.has(key)) continue;
      seen.add(key);
      const doc = Array.isArray(example.citations) ? example.citations[0]?.doc : undefined;
      entries.push({ question: example.question, from: turn.question, source: typeof doc === "string" ? doc : undefined });
      if (entries.length === limit) return entries;
    }
  }
  return entries;
}
