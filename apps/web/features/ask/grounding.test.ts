import { describe, expect, it } from "vitest";
import { finishedMessage, groundingOf, verdictText } from "./grounding";
import type { Turn } from "./session";

const chunks = [{ text: "heap text", doc: "heaps.pdf", page: 1, score: 0.7 }];
const ok = { label: "heaps.pdf (page 1)", doc: "heaps.pdf", page: 1, status: "ok" as const };
const bad = { label: "Invented.pdf (page 9)", doc: "Invented.pdf", page: 9, status: "unknown_source" as const };
const turn = (over: Partial<Turn>): Turn => ({ id: "1", question: "q", answer: "A heap [heaps.pdf (page 1)].", chunks, citations: [ok], status: "done", ...over });

describe("grounding verdict", () => {
  it("counts checked citations", () => {
    expect(verdictText(groundingOf(turn({ citations: [ok, ok] })))).toBe("2 citations checked against your material");
    expect(verdictText(groundingOf(turn({ citations: [ok, bad] })))).toBe("1 of 2 citations could not be checked");
  });

  it("says not found when nothing is cited or the answer says so", () => {
    expect(groundingOf(turn({ citations: [] })).kind).toBe("not-found");
    expect(groundingOf(turn({ answer: "I could not find that in your sources." })).kind).toBe("not-found");
    expect(groundingOf(turn({ chunks: [] })).kind).toBe("not-found");
  });

  it("gives no verdict before an answer is finished", () => {
    for (const status of ["streaming", "error", "stopped"] as const) expect(groundingOf(turn({ status })).kind).toBe("none");
    expect(groundingOf(turn({ answer: "" })).kind).toBe("none");
  });

  it("phrases the status message for each ending", () => {
    expect(finishedMessage(turn({ citations: [ok, bad] }))).toBe("Answer ready: 1 citation checked, 1 could not be checked");
    expect(finishedMessage(turn({ status: "stopped" }))).toBe("Stopped");
    expect(finishedMessage(turn({ status: "error", error: { code: "x", message: "Busy." } }))).toBe("This question didn't reach your sources. Busy.");
    expect(finishedMessage(turn({ answer: "" }))).toBe("Found 1 matching passage");
  });
});
