import { plural } from "@/lib/format";
import type { Turn } from "./session";

/** Phrases the model uses when the passages do not answer the question. */
const NOT_FOUND = /\b(could ?n[o']t|can ?n[o']t|cannot|unable to|did ?n[o']t|do(?:es)? ?n[o']t)\s+(?:find|locate|see)\b|\bnot (?:found |mentioned |covered |present )?in (?:your|the) (?:sources|material|passages|documents|notes)\b|\bno (?:relevant |matching )?(?:information|passages?|mention)\b/i;

export type Grounding =
  /** Still streaming, failed, stopped, or a passage-only lookup: no verdict to give. */
  | { kind: "none" }
  /** The answer cites nothing, or says your material does not cover the question. */
  | { kind: "not-found" }
  | { kind: "checked"; total: number; unchecked: number };

/** How well a finished answer is grounded in the retrieved passages, from the server's citation checks. */
export function groundingOf(turn: Turn | undefined): Grounding {
  if (!turn || turn.status !== "done" || !turn.answer.trim()) return { kind: "none" };
  const citations = turn.citations ?? [];
  if (citations.length === 0 || turn.chunks.length === 0 || NOT_FOUND.test(turn.answer)) return { kind: "not-found" };
  return { kind: "checked", total: citations.length, unchecked: citations.filter((c) => c.status !== "ok").length };
}

/** The one-line verdict shown above an answer. */
export function verdictText(g: Grounding): string {
  if (g.kind === "not-found") return "Not found in your material";
  if (g.kind !== "checked") return "";
  if (g.unchecked === 0) return `${plural(g.total, "citation")} checked against your material`;
  return `${g.unchecked} of ${plural(g.total, "citation")} could not be checked`;
}

/** What the status region says when a question finishes. */
export function finishedMessage(turn: Turn): string {
  if (turn.status === "stopped") return "Stopped";
  if (turn.status === "error") return `This question didn't reach your sources. ${turn.error?.message ?? ""}`.trim();
  if (!turn.answer.trim()) return turn.chunks.length ? `Found ${plural(turn.chunks.length, "matching passage")}` : "No matching passages found";
  const g = groundingOf(turn);
  if (g.kind === "checked") return `Answer ready: ${g.total - g.unchecked} ${g.total - g.unchecked === 1 ? "citation" : "citations"} checked, ${g.unchecked} could not be checked`;
  return "Answer ready: not found in your material";
}
