import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const askStream = vi.fn();
const askAgentStream = vi.fn();
vi.mock("@/lib/api", async () => {
  class ApiError extends Error {
    constructor(public status: number, public code: string, message: string) {
      super(message);
    }
  }
  return {
    api: {
      askStream: (...a: unknown[]) => askStream(...a),
      askAgentStream: (...a: unknown[]) => askAgentStream(...a),
      http: { GET: vi.fn(async () => ({ data: { turns: [] } })), POST: vi.fn(async () => ({ data: { id: 1 } })), DELETE: vi.fn() },
    },
    ApiError,
    unwrap: (r: { data?: unknown }) => r.data,
    errorMessage: (e: unknown) => (e instanceof Error ? e.message : "unknown"),
  };
});
const retrieveLocal = vi.fn();
vi.mock("@/lib/browser-rag/retrieve", () => ({ retrieveLocal: (...a: unknown[]) => retrieveLocal(...a) }));

import { useAskSession } from "./use-ask-session";

const params = { question: "what is a heap", k: 3, temperature: 0.2 };
const chunk = { text: "a heap is a tree", doc: "heaps.pdf", page: 1, score: 0.8 };

async function* events(...evs: object[]) {
  for (const e of evs) yield e;
}

beforeEach(() => {
  askStream.mockReset();
  askAgentStream.mockReset();
  retrieveLocal.mockReset();
  localStorage.clear();
});

describe("useAskSession in agentic mode", () => {
  it("uses the agent stream and turns its events into steps, an answer and the cost", async () => {
    askAgentStream.mockImplementation(() =>
      events(
        { event: "step", data: { name: "rewrite", detail: "Searching for: heap" } },
        { event: "meta", data: { chunks: [chunk] } },
        { event: "token", data: { text: "A heap" } },
        { event: "step", data: { name: "verify", detail: "Every citation is in the retrieved passages" } },
        { event: "done", data: { model: "m", citations: [], uncited: false, llm_calls: 3, regenerated: false, unverified_citations: 0, cached: false } },
      ),
    );
    const { result } = renderHook(() => useAskSession());
    await act(async () => {
      await result.current.ask({ ...params, agent: true });
    });
    expect(askStream).not.toHaveBeenCalled();
    expect(askAgentStream.mock.calls[0]![0]).toMatchObject({ question: "what is a heap", k: 3 });
    expect(result.current.turns[0]).toMatchObject({ agent: true, answer: "A heap", status: "done", llmCalls: 3, chunks: [chunk] });
    expect(result.current.turns[0]!.steps!.map((s) => s.name)).toEqual(["rewrite", "verify"]);
  });

  it("a replace event swaps the first answer for the corrected one", async () => {
    askAgentStream.mockImplementation(() =>
      events(
        { event: "token", data: { text: "Draft [Ghost.pdf]" } },
        { event: "replace", data: { reason: "bad citation" } },
        { event: "token", data: { text: "Final" } },
        { event: "done", data: { model: "m", citations: [], uncited: false, llm_calls: 4, regenerated: true } },
      ),
    );
    const { result } = renderHook(() => useAskSession());
    await act(async () => {
      await result.current.ask({ ...params, agent: true });
    });
    expect(result.current.turns[0]).toMatchObject({ answer: "Final", rewritten: true });
  });

  it("reports a failure as an error turn", async () => {
    askAgentStream.mockImplementation(() => events({ event: "error", data: { code: "quota_exhausted", message: "quota used up" } }));
    const { result } = renderHook(() => useAskSession());
    await act(async () => {
      await result.current.ask({ ...params, agent: true });
    });
    expect(result.current.turns[0]).toMatchObject({ status: "error", error: { code: "quota_exhausted" } });
  });

  it("is ignored for the visitor's own documents and for passage-only lookups", async () => {
    retrieveLocal.mockResolvedValue([chunk]);
    askStream.mockImplementation(() => events({ event: "done", data: {} }));
    const { result } = renderHook(() => useAskSession());
    await act(async () => {
      await result.current.ask({ ...params, agent: true, local: true });
    });
    expect(askAgentStream).not.toHaveBeenCalled();
    expect(result.current.turns[0]).not.toHaveProperty("agent");
  });

  it("plain questions still use the plain stream", async () => {
    askStream.mockImplementation(() => events({ event: "done", data: {} }));
    const { result } = renderHook(() => useAskSession());
    await act(async () => {
      await result.current.ask(params);
    });
    expect(askAgentStream).not.toHaveBeenCalled();
  });
});
