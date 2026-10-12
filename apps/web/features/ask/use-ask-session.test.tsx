import { act, renderHook, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const askStream = vi.fn();
vi.mock("@/lib/api", async () => {
  class ApiError extends Error {
    constructor(
      public status: number,
      public code: string,
      message: string,
    ) {
      super(message);
    }
  }
  return {
    api: { askStream: (...a: unknown[]) => askStream(...a) },
    ApiError,
    errorMessage: (e: unknown) => (e instanceof Error ? e.message : "unknown"),
  };
});

import { ApiError } from "@/lib/api";
import { useAskSession } from "./use-ask-session";

const params = { question: "what is a heap", k: 3, temperature: 0.2 };
const chunk = { text: "a heap is a tree", doc: "heaps.pdf", page: 1, score: 0.8 };

async function* events(...evs: object[]) {
  for (const e of evs) yield e;
}

beforeEach(() => {
  askStream.mockReset();
  localStorage.clear();
});

describe("useAskSession", () => {
  it("streams meta, tokens and done into one turn", async () => {
    askStream.mockImplementation(() =>
      events(
        { event: "meta", data: { chunks: [chunk] } },
        { event: "token", data: { text: "A heap " } },
        { event: "token", data: { text: "is a tree." } },
        { event: "done", data: { model: "gemini-3.8-flash" } },
      ),
    );
    const { result } = renderHook(() => useAskSession());
    await act(async () => {
      await result.current.ask(params);
    });
    expect(result.current.turns).toHaveLength(1);
    expect(result.current.turns[0]).toMatchObject({
      question: "what is a heap",
      answer: "A heap is a tree.",
      status: "done",
      model: "gemini-3.8-flash",
      chunks: [chunk],
    });
    expect(result.current.busy).toBe(false);
    expect(askStream.mock.calls[0]![0]).toMatchObject({ question: "what is a heap", k: 3 });
  });

  it("turns an error event into an error turn but keeps the sources", async () => {
    askStream.mockImplementation(() =>
      events({ event: "meta", data: { chunks: [chunk] } }, { event: "error", data: { code: "llm_unavailable", message: "no key" } }),
    );
    const { result } = renderHook(() => useAskSession());
    await act(async () => {
      await result.current.ask(params);
    });
    expect(result.current.turns[0]).toMatchObject({ status: "error", error: { code: "llm_unavailable" }, chunks: [chunk] });
  });

  it("reports HTTP errors thrown before streaming starts, with the server's code", async () => {
    askStream.mockImplementation(async function* () {
      throw new ApiError(429, "rate_limited", "Rate limit exceeded");
    });
    const { result } = renderHook(() => useAskSession());
    await act(async () => {
      await result.current.ask(params);
    });
    expect(result.current.turns[0]).toMatchObject({ status: "error", error: { code: "rate_limited", message: "Rate limit exceeded" } });
  });

  it("reports a network failure", async () => {
    askStream.mockImplementation(async function* () {
      throw new TypeError("Failed to fetch");
    });
    const { result } = renderHook(() => useAskSession());
    await act(async () => {
      await result.current.ask(params);
    });
    expect(result.current.turns[0]).toMatchObject({ status: "error", error: { code: "network_error" } });
  });

  it("stop aborts the request and marks the turn stopped, keeping partial text", async () => {
    let release!: () => void;
    askStream.mockImplementation(async function* (_body: unknown, signal: AbortSignal) {
      yield { event: "token", data: { text: "partial" } };
      await new Promise<void>((resolve, reject) => {
        release = resolve;
        signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
      });
    });
    const { result } = renderHook(() => useAskSession());
    let pending!: Promise<void>;
    act(() => {
      pending = result.current.ask(params);
    });
    await waitFor(() => expect(result.current.turns[0]?.answer).toBe("partial"));
    expect(result.current.busy).toBe(true);
    await act(async () => {
      result.current.stop(result.current.turns[0]!.id);
      await pending;
    });
    release?.();
    expect(result.current.turns[0]).toMatchObject({ status: "stopped", answer: "partial" });
    expect(result.current.busy).toBe(false);
  });

  it("persists finished turns and restores them", async () => {
    askStream.mockImplementation(() => events({ event: "token", data: { text: "x" } }, { event: "done", data: {} }));
    const first = renderHook(() => useAskSession());
    await act(async () => {
      await first.result.current.ask(params);
    });
    first.unmount();
    const second = renderHook(() => useAskSession());
    await waitFor(() => expect(second.result.current.turns).toHaveLength(1));
    expect(second.result.current.turns[0]!.answer).toBe("x");
  });

  it("does not wipe stored turns on mount, even when effects run twice (StrictMode)", async () => {
    const stored = [{ id: "old", question: "earlier question", answer: "earlier answer", chunks: [], status: "done" }];
    localStorage.setItem("asm.ask.turns.v1", JSON.stringify(stored));
    const { result } = renderHook(() => useAskSession(), { wrapper: StrictMode });
    await waitFor(() => expect(result.current.turns.map((t) => t.id)).toEqual(["old"]));
    expect(JSON.parse(localStorage.getItem("asm.ask.turns.v1")!)).toHaveLength(1);
  });

  it("clear removes everything", async () => {
    askStream.mockImplementation(() => events({ event: "done", data: {} }));
    const { result } = renderHook(() => useAskSession());
    await act(async () => {
      await result.current.ask(params);
    });
    act(() => result.current.clear());
    expect(result.current.turns).toEqual([]);
  });
});
