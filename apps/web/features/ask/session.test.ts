import { beforeEach, describe, expect, it } from "vitest";
import { loadTurns, reducer, saveTurns, type Turn } from "./session";

const chunk = { text: "t", doc: "d.pdf", page: 1, score: 0.7 };
const start = (id: string, q = "what is x") => ({ type: "start", id, question: q }) as const;

describe("reducer", () => {
  it("adds new turns first and streams tokens into the answer", () => {
    let s = reducer([], start("a"));
    s = reducer(s, start("b", "second"));
    expect(s.map((t) => t.id)).toEqual(["b", "a"]);
    s = reducer(s, { type: "meta", id: "a", chunks: [chunk] });
    s = reducer(s, { type: "token", id: "a", text: "Hel" });
    s = reducer(s, { type: "token", id: "a", text: "lo" });
    s = reducer(s, { type: "done", id: "a", model: "m" });
    const a = s.find((t) => t.id === "a")!;
    expect(a).toMatchObject({ answer: "Hello", status: "done", model: "m", chunks: [chunk] });
    expect(s.find((t) => t.id === "b")!.answer).toBe("");
  });

  it("records errors and keeps the sources that arrived before them", () => {
    let s = reducer([], start("a"));
    s = reducer(s, { type: "meta", id: "a", chunks: [chunk] });
    s = reducer(s, { type: "error", id: "a", code: "llm_unavailable", message: "no key" });
    expect(s[0]).toMatchObject({ status: "error", error: { code: "llm_unavailable" }, chunks: [chunk] });
  });

  it("stop only affects a streaming turn", () => {
    let s = reducer([], start("a"));
    s = reducer(s, { type: "done", id: "a" });
    expect(reducer(s, { type: "stop", id: "a" })[0]!.status).toBe("done");
    const streaming = reducer([], start("b"));
    expect(reducer(streaming, { type: "stop", id: "b" })[0]!.status).toBe("stopped");
  });

  it("removes and clears", () => {
    const s = reducer(reducer([], start("a")), start("b"));
    expect(reducer(s, { type: "remove", id: "a" }).map((t) => t.id)).toEqual(["b"]);
    expect(reducer(s, { type: "clear" })).toEqual([]);
  });
});

describe("persistence", () => {
  beforeEach(() => localStorage.clear());
  const turn = (id: string, status: Turn["status"]): Turn => ({ id, question: "q", answer: "a", chunks: [], status });

  it("saves finished turns only", () => {
    saveTurns([turn("1", "streaming"), turn("2", "done"), turn("3", "error")]);
    expect(loadTurns().map((t) => t.id)).toEqual(["2", "3"]);
  });

  it("keeps at most 20 turns", () => {
    saveTurns(Array.from({ length: 30 }, (_, i) => turn(String(i), "done")));
    expect(loadTurns()).toHaveLength(20);
  });

  it("ignores corrupt or wrongly shaped storage", () => {
    localStorage.setItem("asm.ask.turns.v1", "{not json");
    expect(loadTurns()).toEqual([]);
    localStorage.setItem("asm.ask.turns.v1", JSON.stringify([{ id: 1 }, { id: "ok", question: "q", answer: "a", chunks: [] }]));
    expect(loadTurns().map((t) => t.id)).toEqual(["ok"]);
  });
});
