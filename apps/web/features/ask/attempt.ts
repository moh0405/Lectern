import type { Chunk } from "@ai-study-mentor/api-client";
import { plural } from "@/lib/format";
import { chunkForCitation } from "./citations";
import type { AttemptFeedback, AttemptFormat, AttemptItem } from "./session";

/** The attempt formats, with the copy each one shows. Order is the picker's order. */
export const ATTEMPT_FORMATS: { value: AttemptFormat; label: string; hint: string; unit: string }[] = [
  { value: "steps", label: "Steps", hint: "Show your working, one step per line.", unit: "step" },
  { value: "code", label: "Code", hint: "Write or paste your code. Feedback points at line numbers.", unit: "line" },
  { value: "short_answer", label: "Short answer", hint: "A sentence or a short paragraph in your own words.", unit: "sentence" },
];

export const CODE_LANGUAGES = ["Python", "JavaScript", "TypeScript", "Java", "C++", "C", "Go", "Pseudocode"];

/** The longest attempt the server accepts. */
export const MAX_ATTEMPT = 6000;

export const UNCHECKED = "not checked against your sources";

/** How a verdict judged from the problem statement is labelled, so it never reads as source-checked. */
export const REASONED = "Reasoned from the problem, not from your sources";

export type VerdictKind = "supported" | "contradicted" | "reasoned" | "reasoned_wrong" | "unchecked" | "not_covered";

/**
 * How to show a verdict. A supported or contradicted verdict with no verified citation is never shown as if it were
 * confirmed: it reads "not checked against your sources", because a wrong "supported" is worse than none.
 */
export function verdictOf(item: Pick<AttemptItem, "verdict" | "checked"> & { basis?: AttemptItem["basis"] }): { kind: VerdictKind; label: string; long: string } {
  if (item.verdict === "not_covered") return { kind: "not_covered", label: "Not in your sources", long: "Not covered by your sources" };
  if (item.basis === "problem") {
    return item.verdict === "supported"
      ? { kind: "reasoned", label: "Works for this problem", long: `Works for this problem. ${REASONED}` }
      : { kind: "reasoned_wrong", label: "Does not hold for this problem", long: `Does not hold for this problem. ${REASONED}` };
  }
  if (!item.checked) {
    const said = item.verdict === "supported" ? "Looks right" : "Looks wrong";
    return { kind: "unchecked", label: `${said}, unchecked`, long: `${said}, but ${UNCHECKED}` };
  }
  return item.verdict === "supported"
    ? { kind: "supported", label: "Supported", long: "Supported by your sources" }
    : { kind: "contradicted", label: "Re-check this", long: "Contradicted by your sources" };
}

/** Which of the turn's passages a verdict points to, in citation order, without repeats (verified citations only). */
export function passagesFor(item: AttemptItem, chunks: Chunk[], unitText: string): number[] {
  const found: number[] = [];
  for (const c of item.citations) {
    const i = chunkForCitation(c, chunks, `${unitText} ${item.note}`);
    if (i !== null && !found.includes(i)) found.push(i);
  }
  return found;
}

/** One line that sums up the feedback, e.g. "2 supported · 1 to re-check · 1 not in your sources". */
export function tally(feedback: Pick<AttemptFeedback, "items">): string {
  const counts: Record<VerdictKind, number> = { supported: 0, contradicted: 0, reasoned: 0, reasoned_wrong: 0, unchecked: 0, not_covered: 0 };
  for (const item of feedback.items) counts[verdictOf(item).kind]++;
  const reasoned = [counts.reasoned ? `${counts.reasoned} fine` : "", counts.reasoned_wrong ? `${counts.reasoned_wrong} to re-check` : ""].filter(Boolean).join(", ");
  const parts = [
    counts.supported ? `${counts.supported} supported` : "",
    counts.contradicted ? `${counts.contradicted} to re-check` : "",
    reasoned ? `reasoned from the problem: ${reasoned}` : "",
    counts.unchecked ? `${counts.unchecked} ${UNCHECKED}` : "",
    counts.not_covered ? `${counts.not_covered} not in your sources` : "",
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : "No part of your attempt could be judged against your sources.";
}

/** What the status region says when feedback arrives. */
export function feedbackMessage(feedback: AttemptFeedback): string {
  const unit = ATTEMPT_FORMATS.find((f) => f.value === feedback.format)?.unit ?? "step";
  return `Feedback ready on ${plural(feedback.units.length, unit)}: ${tally(feedback)}.`;
}
