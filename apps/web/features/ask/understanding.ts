import type { Chunk, components } from "@ai-study-mentor/api-client";
import { plainText } from "./flashcards";

export type ContextPassage = components["schemas"]["ContextPassage"];
export type EliLevel = components["schemas"]["AdaptiveRequest"]["level"] & string;

export const EXPLAIN_LEVELS: { value: EliLevel; label: string }[] = [
  { value: "ELI5", label: "Like I'm five" },
  { value: "ELI10", label: "Middle school" },
  { value: "Undergrad", label: "Undergraduate" },
  { value: "Grad", label: "Graduate" },
  { value: "Expert", label: "Expert" },
];

/** A note must fit on a flashcard back without being cut. */
export const MAX_NOTE = 1200;
export const MAX_CARD_FRONT = 1200;
const MAX_SEED = 280;
const MAX_PASSAGES = 10;
const MAX_PASSAGE_TEXT = 4000;
const MAX_DOC = 300;

const CONTRAST = /\b(whereas|unlike|in contrast|rather than|instead of|instead|however|while|but|differs?|difference|compared (?:to|with)|not .{1,40} but)\b/i;

/** The answer as plain sentences: no code blocks, headings, citations or list markers. */
function sentences(answer: string): string[] {
  const text = answer
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/^\s{0,3}#{1,6}\s.*$/gm, " ")
    .replace(/\[[^\]\n]*\]\([^)\n]*\)/g, (link) => link.slice(1, link.indexOf("]")))
    .replace(/\[[^\]\n]*\]/g, "")
    .replace(/\(\*[^)\n]*\*,?[^)\n]*\)/g, "")
    .replace(/^\s*(?:[-*+]|\d+[.)])\s+/gm, "");
  return plainText(text)
    .split(/(?<=[.!?])\s+|\n+/)
    .map((s) => s.replace(/\s+/g, " ").replace(/\s+([.,;:!?])/g, "$1").trim())
    .filter((s) => s.length >= 20 && !s.endsWith(":") && !s.endsWith("?"));
}

/**
 * A starting point for the learner's note, with no model call: the answer's first sentence that draws a contrast, or
 * else its first sentence. It is only a seed; the learner is asked to rewrite it.
 */
export function keyDistinction(answer: string): string {
  const all = sentences(answer);
  const picked = all.find((s) => CONTRAST.test(s)) ?? all[0] ?? "";
  if (picked.length <= MAX_SEED) return picked;
  const cut = picked.slice(0, MAX_SEED);
  return `${cut.slice(0, Math.max(cut.lastIndexOf(" "), 1)).trimEnd()}…`;
}

/** The turn's passages in the shape the API accepts back, so follow-ups use exactly what the learner just read. */
export function toPassages(chunks: Chunk[]): ContextPassage[] {
  return chunks
    .filter((c) => c.text.trim() && c.doc)
    .slice(0, MAX_PASSAGES)
    .map((c) => ({
      text: c.text.slice(0, MAX_PASSAGE_TEXT),
      doc: c.doc.slice(0, MAX_DOC),
      page: c.page && c.page >= 1 ? c.page : null,
      end_page: c.end_page && c.end_page >= 1 ? c.end_page : null,
      score: c.score,
    }));
}
