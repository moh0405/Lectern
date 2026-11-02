import { describe, expect, it } from "vitest";
import { idle, runReducer, type RunState } from "./trace";

const ev = (event: string, data: object) => ({ type: "event", event: { event, data } }) as never;
const apply = (...actions: unknown[]) => actions.reduce<RunState>((s, a) => runReducer(s, a as never), idle);
const start = { type: "start", task: "what is a heap" };

describe("runReducer", () => {
  it("starts a clean run", () => {
    expect(apply(start)).toMatchObject({ status: "running", task: "what is a heap", trace: [], answer: "" });
  });

  it("pairs each tool call with its result, in order", () => {
    const s = apply(
      start,
      ev("tool_call", { name: "search_documents", arguments: { query: "heap" } }),
      ev("tool_call", { name: "solve_math", arguments: { expression: "x" } }),
      ev("tool_result", { name: "solve_math", summary: "x^2/2", error: false }),
      ev("tool_result", { name: "search_documents", summary: "3 passages from heaps.pdf", error: false }),
    );
    expect(s.trace).toEqual([
      { kind: "tool", name: "search_documents", arguments: { query: "heap" }, status: "ok", summary: "3 passages from heaps.pdf" },
      { kind: "tool", name: "solve_math", arguments: { expression: "x" }, status: "ok", summary: "x^2/2" },
    ]);
  });

  it("repeated calls to one tool are matched first-come first-served", () => {
    const s = apply(
      start,
      ev("tool_call", { name: "search_documents", arguments: { query: "a" } }),
      ev("tool_call", { name: "search_documents", arguments: { query: "b" } }),
      ev("tool_result", { name: "search_documents", summary: "first", error: false }),
    );
    expect(s.trace.map((t) => (t.kind === "tool" ? [t.status, t.summary] : null))).toEqual([["ok", "first"], ["running", undefined]]);
  });

  it("marks a failed tool and keeps going", () => {
    const s = apply(start, ev("tool_call", { name: "read_page", arguments: {} }), ev("tool_result", { name: "read_page", summary: "Unknown document", error: true }));
    expect(s.trace[0]).toMatchObject({ status: "failed", summary: "Unknown document" });
    expect(s.status).toBe("running");
  });

  it("keeps thoughts in the trace, then sources, answer and the cost", () => {
    const s = apply(
      start,
      ev("thought", { text: "I should search." }),
      ev("meta", { chunks: [{ doc: "heaps.pdf", page: 1, text: "t", score: 0.5 }] }),
      ev("token", { text: "A heap is " }),
      ev("token", { text: "a tree." }),
      ev("done", { steps: 2, tool_calls: 1, llm_calls: 2, citations: [], unverified_citations: 0, uncited: false, wrapped_up: false }),
    );
    expect(s.trace[0]).toEqual({ kind: "thought", text: "I should search." });
    expect(s).toMatchObject({ status: "done", answer: "A heap is a tree.", chunks: [{ doc: "heaps.pdf" }], done: { llm_calls: 2 } });
  });

  it("an error event ends the run but keeps what was already shown", () => {
    const s = apply(start, ev("tool_call", { name: "search_documents", arguments: {} }), ev("error", { code: "quota_exhausted", message: "quota used up" }));
    expect(s).toMatchObject({ status: "error", error: { code: "quota_exhausted" } });
    expect(s.trace).toHaveLength(1);
  });

  it("stop only affects a running run; a new start clears the old one", () => {
    expect(apply(start, { type: "stop" }).status).toBe("stopped");
    expect(apply(start, ev("done", {}), { type: "stop" }).status).toBe("done");
    expect(apply(start, ev("token", { text: "x" }), start).answer).toBe("");
  });

  it("a result with no matching call is ignored", () => {
    expect(apply(start, ev("tool_result", { name: "solve_math", summary: "?", error: false })).trace).toEqual([]);
  });
});
