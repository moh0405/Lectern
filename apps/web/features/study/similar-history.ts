import type { Turn } from "@/features/ask/session";

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
    for (const example of [...(turn.similar ?? [])].reverse()) {
      const key = sameText(example?.question ?? "");
      if (!key || seen.has(key)) continue;
      seen.add(key);
      entries.push({ question: example.question, from: turn.question, source: example.citations?.[0]?.doc ?? undefined });
      if (entries.length === limit) return entries;
    }
  }
  return entries;
}
