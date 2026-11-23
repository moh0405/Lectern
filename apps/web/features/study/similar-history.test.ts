import { describe, expect, it } from "vitest";
import type { SimilarExample, Turn } from "@/features/ask/session";
import { similarHistory } from "./similar-history";

const example = (question: string, doc?: string): SimilarExample => ({
  question,
  citations: doc ? [{ label: doc, doc, page: 1, status: "ok" } as SimilarExample["citations"][number]] : [],
});
const turn = (question: string, similar?: SimilarExample[]): Turn => ({ id: question, question, answer: "a", chunks: [], status: "done", similar });

describe("similarHistory", () => {
  it("lists the newest example first, across turns", () => {
    const entries = similarHistory([turn("newer", [example("n1"), example("n2", "heaps.pdf")]), turn("older", [example("o1")])]);
    expect(entries.map((e) => e.question)).toEqual(["n2", "n1", "o1"]);
    expect(entries[0]).toMatchObject({ from: "newer", source: "heaps.pdf" });
  });

  it("drops repeats that differ only in case or spacing, and blank questions", () => {
    const entries = similarHistory([turn("a", [example("What is  a heap?"), example("   ")]), turn("b", [example("what is a heap?")])]);
    expect(entries).toHaveLength(1);
  });

  it("ignores damaged saved data instead of crashing the page", () => {
    const damaged = [
      { ...turn("a"), similar: { question: "not a list" } },
      { ...turn("b"), similar: [null, 7, { question: 3 }, { question: "kept", citations: "nope" }] },
    ] as unknown as Turn[];
    expect(similarHistory(damaged)).toEqual([{ question: "kept", from: "b", source: undefined }]);
  });

  it("stops at the limit and handles turns with no examples", () => {
    expect(similarHistory([turn("none"), turn("a", [example("1"), example("2"), example("3")])], 2)).toHaveLength(2);
    expect(similarHistory([turn("none")])).toEqual([]);
  });
});
