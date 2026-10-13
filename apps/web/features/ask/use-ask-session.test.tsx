import { act, renderHook, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const askStream = vi.fn();
const httpGet = vi.fn();
const httpPost = vi.fn();
const httpDelete = vi.fn();
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
    api: { askStream: (...a: unknown[]) => askStream(...a), http: { GET: (...a: unknown[]) => httpGet(...a), POST: (...a: unknown[]) => httpPost(...a), DELETE: (...a: unknown[]) => httpDelete(...a) } },
    ApiError,
    unwrap: (r: { data?: unknown; error?: unknown }) => {
      if (r.error !== undefined || r.data === undefined) throw new ApiError(500, "x", "failed");
      return r.data;
    },
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
  httpGet.mockReset();
  httpPost.mockReset();
  httpDelete.mockReset();
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

  it("passes show-prompt through and stores the prompt from the stream", async () => {
    askStream.mockImplementation(() => events({ event: "meta", data: { chunks: [], prompt: "PROMPT TEXT" } }, { event: "done", data: {} }));
    const { result } = renderHook(() => useAskSession());
    await act(async () => {
      await result.current.ask({ ...params, showPrompt: true });
    });
    expect(askStream.mock.calls[0]![0]).toMatchObject({ include_prompt: true });
    expect(result.current.turns[0]!.prompt).toBe("PROMPT TEXT");
  });

  it("retrieval-only mode lists passages without calling the model", async () => {
    httpGet.mockResolvedValue({ data: { chunks: [chunk] }, response: { status: 200 } });
    const { result } = renderHook(() => useAskSession());
    await act(async () => {
      await result.current.ask({ ...params, retrievalOnly: true });
    });
    expect(askStream).not.toHaveBeenCalled();
    expect(httpGet).toHaveBeenCalledWith("/api/v1/search", expect.objectContaining({ params: { query: { query: "what is a heap", k: 3 } } }));
    expect(result.current.turns[0]).toMatchObject({ status: "done", answer: "", chunks: [chunk] });
  });

  it("retrieval-only errors become an error turn", async () => {
    httpGet.mockResolvedValue({ error: { error: { code: "x" } }, response: { status: 500 } });
    const { result } = renderHook(() => useAskSession());
    await act(async () => {
      await result.current.ask({ ...params, retrievalOnly: true });
    });
    expect(result.current.turns[0]).toMatchObject({ status: "error" });
  });

  it("carries the citation report and cached flag from the done event, and can bypass the cache", async () => {
    const citations = [{ label: "heaps.pdf (page 1)", doc: "heaps.pdf", page: 1, status: "ok" }];
    askStream.mockImplementation(() =>
      events({ event: "token", data: { text: "x" } }, { event: "done", data: { model: "m", citations, uncited: false, cached: true } }),
    );
    const { result } = renderHook(() => useAskSession());
    await act(async () => {
      await result.current.ask({ ...params, noCache: true });
    });
    expect(askStream.mock.calls[0]![0]).toMatchObject({ no_cache: true });
    expect(result.current.turns[0]).toMatchObject({ citations, uncited: false, cached: true });
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

  describe("server-side history", () => {
    const finish = () => askStream.mockImplementation(() => events({ event: "token", data: { text: "A heap." } }, { event: "done", data: { model: "m" } }));

    it("saves a finished turn on the server, and deleting it there too", async () => {
      finish();
      httpPost.mockResolvedValue({ data: { id: 41 } });
      const { result } = renderHook(() => useAskSession());
      await act(async () => {
        await result.current.ask(params);
      });
      await waitFor(() => expect(httpPost).toHaveBeenCalledTimes(1));
      expect(httpPost.mock.calls[0]![0]).toBe("/api/v1/history");
      expect(httpPost.mock.calls[0]![1].body).toMatchObject({ question: "what is a heap", answer: "A heap.", model: "m" });
      const id = result.current.turns[0]!.id;
      await act(async () => result.current.remove(id));
      expect(httpDelete).toHaveBeenCalledWith("/api/v1/history/{turn_id}", { params: { path: { turn_id: 41 } } });
    });

    it("does not save the same turn twice, nor retrieval-only lookups", async () => {
      finish();
      httpPost.mockResolvedValue({ data: { id: 1 } });
      httpGet.mockResolvedValue({ data: { chunks: [chunk] } });
      const { result } = renderHook(() => useAskSession());
      await act(async () => {
        await result.current.ask({ ...params, retrievalOnly: true });
      });
      await act(async () => {
        await result.current.ask(params);
      });
      await waitFor(() => expect(httpPost).toHaveBeenCalledTimes(1));
    });

    it("restores history from the server when this browser has none", async () => {
      httpGet.mockResolvedValue({ data: { turns: [{ id: 7, ts: 1, question: "old q", answer: "old a", chunks: [], citations: [], cached: false, uncited: false }] } });
      const { result } = renderHook(() => useAskSession());
      await waitFor(() => expect(result.current.turns).toHaveLength(1));
      expect(result.current.turns[0]).toMatchObject({ id: "srv-7", question: "old q", status: "done" });
      expect(httpPost).not.toHaveBeenCalled(); // restored turns are not saved again
      await act(async () => result.current.remove("srv-7"));
      expect(httpDelete).toHaveBeenCalledWith("/api/v1/history/{turn_id}", { params: { path: { turn_id: 7 } } });
    });

    it("keeps working when the server is unreachable", async () => {
      finish();
      httpGet.mockRejectedValue(new TypeError("down"));
      httpPost.mockRejectedValue(new TypeError("down"));
      httpDelete.mockRejectedValue(new TypeError("down"));
      const { result } = renderHook(() => useAskSession());
      await act(async () => {
        await result.current.ask(params);
      });
      expect(result.current.turns[0]!.status).toBe("done");
      await act(async () => result.current.clear());
      expect(result.current.turns).toHaveLength(0);
    });
  });
});
