import type { Chunk } from "@ai-study-mentor/api-client";
import { toPassages, type ContextPassage } from "@/features/ask/understanding";

export interface TryFirstProblem { pid: string; title: string; description: string }

const MAX_QUESTION = 2000;
const MAX_PASSAGE = 4000;
const MAX_DOC = 300;
/** Passages from the library, alongside the problem statement. */
export const LIBRARY_PASSAGES = 3;

export const attemptQuestion = (p: TryFirstProblem) => `Solve LeetCode problem ${p.pid}: ${p.title}`.slice(0, MAX_QUESTION);

/** What to search the library for: the problem's name, which carries its idea better than the full statement. */
export const librarySearch = (p: TryFirstProblem) => p.title.slice(0, MAX_QUESTION);

/** LeetCode statements describe no method, so reasoning is judged against the statement, when there is one to judge against. */
export const attemptJudge = (p: TryFirstProblem): "problem" | "sources" => (p.description.trim() ? "problem" : "sources");

/** The passages an attempt is judged against: the problem statement first, then what the library holds on it. */
export function attemptContext(p: TryFirstProblem, library: Chunk[]): ContextPassage[] {
  const text = p.description.trim().slice(0, MAX_PASSAGE);
  const statement: ContextPassage[] = text ? [{ text, doc: `LeetCode ${p.pid}. ${p.title}`.slice(0, MAX_DOC), page: null, end_page: null, score: 1 }] : [];
  return [...statement, ...toPassages(library).slice(0, LIBRARY_PASSAGES)];
}
