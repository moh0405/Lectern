import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const askStream = vi.fn();
const httpPost = vi.fn();
vi.mock("@/lib/api", async () => {
  class ApiError extends Error {
    constructor(public status: number, public code: string, message: string) {
      super(message);
    }
  }
  return {
    api: { askStream: (...a: unknown[]) => askStream(...a), http: { GET: vi.fn(async () => ({ data: { turns: [] } })), POST: (...a: unknown[]) => httpPost(...a), DELETE: vi.fn() } },
    ApiError,
    unwrap: (r: { data?: unknown; error?: { error?: { code: string; message: string } } }) => {
      if (r.error !== undefined) throw new ApiError(429, r.error.error?.code ?? "x", r.error.error?.message ?? "failed");
      return r.data;
    },
    errorMessage: (e: unknown) => (e instanceof Error ? e.message : "unknown"),
  };
});
const retrieveLocal = vi.fn();
vi.mock("@/lib/browser-rag/retrieve", () => ({ retrieveLocal: (...a: unknown[]) => retrieveLocal(...a) }));

import { useAskSession } from "./use-ask-session";

const chunk = { text: "Insert sifts up.", doc: "heaps.pdf", page: 2, score: 0.8 };
const feedback = { format: "steps", units: ["Swap down."], items: [], summary: "Look again.", chunks: [chunk], model: "m", unverified_citations: 0, withheld: 0 };
const params = { question: "why log n", k: 3, temperature: 0.2, model: "gemini-2.5-flash-lite", attempt: { text: "Swap down.", format: "steps" as const } };

async function* events(...evs: object[]) {
  for (const e of evs) yield e;
}

beforeEach(() => {
  askStream.mockReset();
  httpPost.mockReset();
  retrieveLocal.mockReset();
  localStorage.clear();
});

describe("useAskSession Try first", () => {
  it("makes one feedback call, then the cited answer only on Show me the evidence", async () => {
    httpPost.mockImplementation(async (path: string) => (path === "/api/v1/attempt/feedback" ? { data: feedback } : { data: { id: 1 } }));
    askStream.mockImplementation(() => events({ event: "meta", data: { chunks: [chunk] } }, { event: "token", data: { text: "Sift up [heaps.pdf (page 2)]." } }, { event: "done", data: { model: "m" } }));
    const { result } = renderHook(() => useAskSession());
    await act(async () => {
      await result.current.ask(params);
    });
    const feedbackCalls = httpPost.mock.calls.filter(([p]) => p === "/api/v1/attempt/feedback");
    expect(feedbackCalls).toHaveLength(1);
    expect(feedbackCalls[0]![1].body).toEqual({ question: "why log n", attempt: "Swap down.", format: "steps", k: 3, temperature: 0.2, model: "gemini-2.5-flash-lite", context: undefined, language: undefined });
    expect(askStream).not.toHaveBeenCalled();
    const turn = result.current.turns[0]!;
    expect(turn).toMatchObject({ status: "done", answer: "", chunks: [chunk], attempt: { feedback, evidenceStarted: false, text: "Swap down." } });

    // Asking again for the same turn never refetches feedback.
    await act(async () => {
      await result.current.retryFeedback(turn);
    });
    expect(httpPost.mock.calls.filter(([p]) => p === "/api/v1/attempt/feedback")).toHaveLength(1);

    await act(async () => {
      await result.current.showEvidence(result.current.turns[0]!);
    });
    expect(askStream).toHaveBeenCalledTimes(1);
    expect(askStream.mock.calls[0]![0]).toMatchObject({ question: "why log n", k: 3, model: "gemini-2.5-flash-lite" });
    expect(result.current.turns).toHaveLength(1);
    expect(result.current.turns[0]).toMatchObject({ answer: "Sift up [heaps.pdf (page 2)].", status: "done", attempt: { evidenceStarted: true, feedback } });
    await act(async () => {
      await result.current.showEvidence(result.current.turns[0]!);
    });
    expect(askStream).toHaveBeenCalledTimes(1);
  });

  it("sends browser passages as context and keeps the shared index out of it", async () => {
    retrieveLocal.mockResolvedValue([chunk]);
    httpPost.mockResolvedValue({ data: feedback });
    const { result } = renderHook(() => useAskSession());
    await act(async () => {
      await result.current.ask({ ...params, local: true, attempt: { text: "def f(): pass", format: "code", language: "Python" } });
    });
    expect(httpPost.mock.calls[0]![1].body).toMatchObject({ context: [chunk], format: "code", language: "Python", attempt: "def f(): pass" });
  });

  it("an error keeps the turn and allows one retry", async () => {
    httpPost.mockResolvedValueOnce({ error: { error: { code: "daily_limit", message: "Daily limit" } }, response: new Response() });
    const { result } = renderHook(() => useAskSession());
    await act(async () => {
      await result.current.ask(params);
    });
    expect(result.current.turns[0]).toMatchObject({ status: "error", error: { code: "daily_limit" } });
    httpPost.mockResolvedValueOnce({ data: feedback });
    await act(async () => {
      await result.current.retryFeedback(result.current.turns[0]!);
    });
    expect(result.current.turns).toHaveLength(1);
    expect(result.current.turns[0]).toMatchObject({ status: "done", attempt: { feedback } });
  });
});
