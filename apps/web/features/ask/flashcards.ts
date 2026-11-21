import { toCsvRows } from "@/lib/csv";
import type { Turn } from "./session";

/** Strip Markdown noise so a flashcard back reads cleanly in Anki and spreadsheets. */
export function plainText(markdown: string): string {
  return markdown
    .replace(/```[\s\S]*?```/g, (block) => block.replace(/```\w*\n?/g, "").trim())
    .replace(/[*_`#>]+/g, "")
    .replace(/\[(.*?)\]\((.*?)\)/g, "$1")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

/** Front/back CSV (importable into Anki) from finished, answered turns, oldest first. */
export function toFlashcardsCsv(turns: Turn[]): string {
  const answered = turns.filter((t) => t.status === "done" && t.answer.trim()).reverse();
  return toCsvRows([["front", "back"], ...answered.map((t) => [t.question, plainText(t.answer)])]);
}

/** Study notes in Markdown, written in the browser from finished turns (oldest first); used where the server cannot. */
export function toNotesMarkdown(finished: Turn[]): string {
  const parts = finished.map((t) => `## ${t.question.trim()}\n\n${t.answer.trim()}`);
  return `# Study notes\n\n${parts.join("\n\n")}\n`;
}
