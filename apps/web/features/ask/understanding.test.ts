import type { Chunk } from "@ai-study-mentor/api-client";
import { describe, expect, it } from "vitest";
import { fromSavedTurn, reducer, toHistoryTurn, type Turn } from "./session";
import { keyDistinction, toPassages } from "./understanding";

const turn = (over: Partial<Turn> = {}): Turn => ({ id: "t1", question: "Why?", answer: "An answer here.", chunks: [], status: "done", ...over });
const chunk = (over: Partial<Chunk> = {}): Chunk => ({ text: "A passage.", doc: "a.pdf", page: 1, score: 0.5, ...over }) as Chunk;

describe("keyDistinction", () => {
  it("prefers the sentence that draws a contrast", () => {
    expect(keyDistinction("A heap is a tree of keys. A stack is last in, whereas a queue is first in. Both are simple.")).toBe("A stack is last in, whereas a queue is first in.");
  });
  it("falls back to the first sentence", () => {
    expect(keyDistinction("A heap is a complete binary tree. It stores keys.")).toBe("A heap is a complete binary tree.");
  });
  it("drops citations, headings, code and list markers", () => {
    const answer = "## Idea\n\n```python\nx = 1 whereas y\n```\n\n- **BFS** uses a queue, but DFS uses a stack [graphs.pdf (page 2)].";
    expect(keyDistinction(answer)).toBe("BFS uses a queue, but DFS uses a stack.");
  });
  it("skips lead-ins and questions, and handles nothing usable", () => {
    expect(keyDistinction("Here is the key point to remember:\nWhy does this matter so much here?\nThe height bounds every swap.")).toBe("The height bounds every swap.");
    expect(keyDistinction("")).toBe("");
  });
  it("clips a long sentence at a word", () => {
    const seed = keyDistinction(`${"word ".repeat(100)}end.`);
    expect(seed.length).toBeLessThanOrEqual(281);
    expect(seed.endsWith("word…")).toBe(true);
  });
});

describe("toPassages", () => {
  it("fits what the API accepts", () => {
    const out = toPassages([chunk({ text: "x".repeat(5000), doc: "d".repeat(400), page: 0, end_page: 0 }), chunk({ text: "   " })]);
    expect(out).toHaveLength(1);
    expect(out[0]!.text).toHaveLength(4000);
    expect(out[0]!.doc).toHaveLength(300);
    expect(out[0]!.page).toBeNull();
    expect(out[0]!.end_page).toBeNull();
    expect(toPassages(Array.from({ length: 14 }, () => chunk()))).toHaveLength(10);
  });
});

describe("understanding state on a turn", () => {
  it("keeps the note, examples and explanations", () => {
    let turns = reducer([turn()], { type: "note", id: "t1", note: "mine" });
    turns = reducer(turns, { type: "saved", id: "t1", serverId: 7 });
    turns = reducer(turns, { type: "similar", id: "t1", example: { question: "Q1", citations: [] } });
    turns = reducer(turns, { type: "similar", id: "t1", example: { question: "Q2", citations: [] } });
    turns = reducer(turns, { type: "explanation", id: "t1", level: "ELI5", explanation: { answer: "simple" } });
    expect(turns[0]).toMatchObject({ note: "mine", serverId: 7, explanations: { ELI5: { answer: "simple" } } });
    expect(turns[0]!.similar!.map((s) => s.question)).toEqual(["Q1", "Q2"]);
    expect(reducer(turns, { type: "note", id: "t1", note: "" })[0]!.note).toBeUndefined();
  });
  it("sends the note to history only when there is one, and restores it", () => {
    expect(toHistoryTurn(turn())).not.toHaveProperty("note");
    expect(toHistoryTurn(turn({ note: "mine" })).note).toBe("mine");
    const restored = fromSavedTurn({ ...toHistoryTurn(turn({ note: "mine" })), id: 4, ts: 1 } as Parameters<typeof fromSavedTurn>[0]);
    expect(restored).toMatchObject({ id: "srv-4", serverId: 4, note: "mine" });
  });
});
