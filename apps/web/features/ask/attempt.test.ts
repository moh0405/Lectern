import { describe, expect, it } from "vitest";
import { feedbackMessage, passagesFor, tally, verdictOf } from "./attempt";
import { reducer } from "./session";
import type { AttemptFeedback, AttemptItem } from "./session";

const chunks = [
  { text: "Insert sifts the key up, swapping with its parent.", doc: "heaps.pdf", page: 2, score: 0.8 },
  { text: "A priority queue is built on a heap.", doc: "queues.md", score: 0.5 },
];
const ok = (label: string, doc: string, page: number | null = null) => ({ label, doc, page, status: "ok" as const });
const item = (over: Partial<AttemptItem>): AttemptItem => ({ unit: 1, ref: "Step 1", verdict: "supported", note: "", citations: [], checked: true, ...over });
const feedback: AttemptFeedback = {
  format: "steps",
  units: ["Put it at the bottom.", "Swap it down.", "Heaps are blue."],
  items: [
    item({ citations: [ok("heaps.pdf (page 2)", "heaps.pdf", 2)] }),
    item({ unit: 2, ref: "Step 2", verdict: "contradicted", citations: [ok("heaps.pdf (page 2)", "heaps.pdf", 2)] }),
    item({ unit: 3, ref: "Step 3", verdict: "not_covered", checked: false }),
  ],
  summary: "Look at step 2.",
  chunks,
  unverified_citations: 0,
  withheld: 0,
};

describe("verdictOf", () => {
  it("only shows a verdict as confirmed when it has a verified citation", () => {
    expect(verdictOf({ verdict: "supported", checked: true }).kind).toBe("supported");
    expect(verdictOf({ verdict: "contradicted", checked: true })).toMatchObject({ kind: "contradicted", long: "Contradicted by your sources" });
    expect(verdictOf({ verdict: "supported", checked: false })).toEqual({ kind: "unchecked", label: "Looks right, unchecked", long: "Looks right, but not checked against your sources" });
    expect(verdictOf({ verdict: "contradicted", checked: false }).long).toBe("Looks wrong, but not checked against your sources");
    expect(verdictOf({ verdict: "not_covered", checked: false }).kind).toBe("not_covered");
  });
});

describe("verdicts reasoned from the problem", () => {
  it("are labelled apart from source-checked verdicts, and a wrong step is still flagged", () => {
    const right = verdictOf({ verdict: "supported", checked: false, basis: "problem" });
    const wrong = verdictOf({ verdict: "contradicted", checked: false, basis: "problem" });
    expect(right).toMatchObject({ kind: "reasoned", label: "Works for this problem" });
    expect(wrong).toMatchObject({ kind: "reasoned_wrong", label: "Does not hold for this problem" });
    expect(right.long).toContain("Reasoned from the problem, not from your sources");
    expect(wrong.long).toContain("Reasoned from the problem, not from your sources");
  });

  it("never outrank the basis, even if an item claims to be checked", () => {
    expect(verdictOf({ verdict: "supported", checked: true, basis: "problem" }).kind).toBe("reasoned");
  });

  it("leave saved feedback without a basis as it was", () => {
    expect(verdictOf({ verdict: "supported", checked: true }).kind).toBe("supported");
    expect(verdictOf({ verdict: "supported", checked: true, basis: "sources" }).kind).toBe("supported");
  });

  it("are counted on their own", () => {
    const items = [item({ checked: false, basis: "problem" }), item({ checked: false, basis: "problem", verdict: "contradicted" })];
    expect(tally({ items })).toBe("reasoned from the problem: 1 fine, 1 to re-check");
  });
});

describe("passagesFor", () => {
  it("maps verified citations to passages, once each, and ignores unverified ones", () => {
    const it_ = item({ citations: [ok("heaps.pdf (page 2)", "heaps.pdf", 2), ok("queues.md", "queues.md"), ok("heaps.pdf", "heaps.pdf"),
      { label: "x.pdf (page 1)", doc: "x.pdf", page: 1, status: "unknown_source" }] });
    expect(passagesFor(it_, chunks, "swap up")).toEqual([0, 1]);
    expect(passagesFor(item({ citations: [ok("heaps.pdf (page 9)", "heaps.pdf", 9)] }), chunks, "")).toEqual([]);
  });
});

describe("tally", () => {
  it("counts each kind of verdict", () => {
    expect(tally(feedback)).toBe("1 supported · 1 to re-check · 1 not in your sources");
    expect(tally({ items: [item({ checked: false })] })).toBe("1 not checked against your sources");
    expect(tally({ items: [] })).toMatch(/No part of your attempt/);
    expect(feedbackMessage(feedback)).toBe("Feedback ready on 3 steps: 1 supported · 1 to re-check · 1 not in your sources.");
  });
});

describe("session reducer for Try first", () => {
  const params = { question: "why log n", k: 3, temperature: 0.2 };
  const start = { type: "start", id: "a", question: "why log n", attempt: { params, text: "x", format: "steps", evidenceStarted: false } } as const;

  it("stores feedback with its passages, then keeps those passages after the answer's own", () => {
    let s = reducer([], start);
    s = reducer(s, { type: "feedback", id: "a", feedback });
    expect(s[0]).toMatchObject({ status: "done", chunks, answer: "", attempt: { feedback, evidenceStarted: false } });
    s = reducer(s, { type: "resume", id: "a", evidence: true });
    expect(s[0]).toMatchObject({ status: "streaming", chunks: [], attempt: { evidenceStarted: true, feedback } });
    const other = { text: "Other.", doc: "b.pdf", page: 1, score: 0.9 };
    s = reducer(s, { type: "meta", id: "a", chunks: [other, chunks[0]!] });
    expect(s[0]!.chunks).toEqual([other, chunks[0], chunks[1]]);
  });

  it("does not merge passages for a turn without an attempt", () => {
    let s = reducer([], { type: "start", id: "a", question: "q" });
    s = reducer(s, { type: "meta", id: "a", chunks: [chunks[0]!] });
    expect(s[0]!.chunks).toEqual([chunks[0]]);
  });
});
