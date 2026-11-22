import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { IDLE_TIMEOUT, IDLE_TIMEOUT_MS, STREAM_ENDED, idle, idleWatchdog, runReducer, stepLabel, type RunState } from "./trace";

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

describe("stepLabel", () => {
  it("describes each tool call in plain language", () => {
    expect(stepLabel("search_documents", { query: "binary heap" })).toBe("Searched your material for “binary heap”");
    expect(stepLabel("search_documents", { query: "binary heap" }, true)).toBe("Searching your material for “binary heap”");
    expect(stepLabel("list_documents", {})).toBe("Listed the documents in your library");
    expect(stepLabel("read_page", { document: "heaps.pdf", page: 3 })).toBe("Read heaps.pdf, page 3");
    expect(stepLabel("solve_math", { expression: "integrate x^2" })).toBe("Worked out “integrate x^2”");
    expect(stepLabel("find_leetcode_problem", { query: "hash table", difficulty: "Easy" })).toBe("Looked for an easy LeetCode problem about “hash table”");
    expect(stepLabel("find_leetcode_problem", { query: "graphs", difficulty: "Medium" })).toBe("Looked for a medium LeetCode problem about “graphs”");
    expect(stepLabel("find_leetcode_problem", {})).toBe("Looked for a LeetCode problem");
    expect(stepLabel("brand_new_tool", {})).toBe("Used brand new tool");
  });
  it("shortens very long arguments", () => {
    expect(stepLabel("search_documents", { query: "x".repeat(200) }).length).toBeLessThan(110);
  });
});

describe("a run always ends visibly", () => {
  it("a stream that closes without done or error becomes an error, with Run enabled again", () => {
    const s = apply(start, ev("tool_call", { name: "search_documents", arguments: { query: "heap" } }), { type: "end" });
    expect(s.status).toBe("error");
    expect(s.error).toEqual(STREAM_ENDED);
    expect(s.trace[0]).toMatchObject({ status: "failed", summary: "did not finish" }); // no spinner left behind
  });

  it("end after done or a server error changes nothing", () => {
    const done = apply(start, ev("done", { steps: 1, tool_calls: 0, llm_calls: 1, citations: [], unverified_citations: 0, uncited: false, wrapped_up: false }), { type: "end" });
    expect(done.status).toBe("done");
    const err = apply(start, ev("error", { code: "timeout", message: "took too long" }), { type: "end" });
    expect(err.error).toEqual({ code: "timeout", message: "took too long" });
  });

  it("a server error settles tool steps that never got a result", () => {
    const s = apply(start, ev("tool_call", { name: "search_documents", arguments: {} }), ev("error", { code: "quota_exhausted", message: "Out of quota" }));
    expect(s).toMatchObject({ status: "error", error: { code: "quota_exhausted" } });
    expect(s.trace[0]).toMatchObject({ status: "failed" });
  });

  it("the client timeout is reported as an error that says how long it waited", () => {
    const s = apply(start, { type: "fail", ...IDLE_TIMEOUT });
    expect(s.status).toBe("error");
    expect(s.error?.message).toContain(`${IDLE_TIMEOUT_MS / 1000} seconds`);
    expect(IDLE_TIMEOUT_MS).toBeGreaterThan(145_000); // longer than the server's 100 s deadline plus a cold start
  });
});

describe("idleWatchdog", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("fires once after the quiet period, and each event restarts the clock", () => {
    const onIdle = vi.fn();
    const w = idleWatchdog(1000, onIdle);
    vi.advanceTimersByTime(900);
    w.poke();
    vi.advanceTimersByTime(900);
    expect(onIdle).not.toHaveBeenCalled();
    vi.advanceTimersByTime(200);
    expect(onIdle).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(5000);
    expect(onIdle).toHaveBeenCalledTimes(1);
  });

  it("cancel disarms it", () => {
    const onIdle = vi.fn();
    idleWatchdog(1000, onIdle).cancel();
    vi.advanceTimersByTime(5000);
    expect(onIdle).not.toHaveBeenCalled();
  });
});
