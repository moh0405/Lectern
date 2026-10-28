import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const askStream = vi.fn();
const httpGet = vi.fn();
vi.mock("@/lib/api", async () => {
  class ApiError extends Error {
    constructor(public status: number, public code: string, message: string) {
      super(message);
    }
  }
  return {
    api: { askStream: (...a: unknown[]) => askStream(...a), http: { GET: (...a: unknown[]) => httpGet(...a), POST: vi.fn(), DELETE: vi.fn() } },
    ApiError,
    unwrap: (r: { data?: unknown }) => r.data,
    errorMessage: (e: unknown) => (e instanceof Error ? e.message : "unknown"),
  };
});
const retrieveLocal = vi.fn();
vi.mock("@/lib/browser-rag/retrieve", () => ({ retrieveLocal: (...a: unknown[]) => retrieveLocal(...a) }));

import { DemoContext } from "@/lib/demo";
import { useAskSession } from "./use-ask-session";

// This feature exists for the public demo, so the hook runs in demo mode.
const inDemo = () => renderHook(() => useAskSession(), { wrapper: ({ children }) => <DemoContext.Provider value={true}>{children}</DemoContext.Provider> });

const params = { question: "what is a treap", k: 3, temperature: 0.2, local: true };
const mine = { text: "A treap is a randomized BST.", doc: "my-notes.pdf", page: 3, score: 0.9 };

async function* events(...evs: object[]) {
  for (const e of evs) yield e;
}

beforeEach(() => {
  askStream.mockReset();
  httpGet.mockReset();
  retrieveLocal.mockReset();
  localStorage.clear();
});

describe("asking about the visitor's own documents", () => {
  it("retrieves in the browser and sends only those passages as the question's context", async () => {
    retrieveLocal.mockResolvedValue([mine]);
    askStream.mockImplementation(() => events({ event: "meta", data: { chunks: [mine] } }, { event: "token", data: { text: "A treap" } }, { event: "done", data: {} }));
    const { result } = inDemo();
    await act(async () => {
      await result.current.ask(params);
    });
    expect(retrieveLocal).toHaveBeenCalledWith("what is a treap", 3);
    expect(askStream.mock.calls[0]![0]).toMatchObject({ question: "what is a treap", context: [mine] });
    expect(result.current.turns[0]!.status).toBe("done");
  });

  it("never falls back to the shared index when nothing matches", async () => {
    retrieveLocal.mockResolvedValue([]);
    const { result } = inDemo();
    await act(async () => {
      await result.current.ask(params);
    });
    expect(askStream).not.toHaveBeenCalled();
    expect(httpGet).not.toHaveBeenCalled();
    expect(result.current.turns[0]).toMatchObject({ status: "error" });
    expect(result.current.turns[0]!.error?.message).toMatch(/Nothing in your documents/);
  });

  it("'only show matching passages' lists the local passages without any server call", async () => {
    retrieveLocal.mockResolvedValue([mine]);
    const { result } = inDemo();
    await act(async () => {
      await result.current.ask({ ...params, retrievalOnly: true });
    });
    expect(askStream).not.toHaveBeenCalled();
    expect(httpGet).not.toHaveBeenCalled();
    expect(result.current.turns[0]!.chunks).toEqual([mine]);
  });

  it("does not use the browser documents unless asked to", async () => {
    askStream.mockImplementation(() => events({ event: "done", data: {} }));
    const { result } = inDemo();
    await act(async () => {
      await result.current.ask({ ...params, local: false });
    });
    expect(retrieveLocal).not.toHaveBeenCalled();
    expect(askStream.mock.calls[0]![0].context).toBeUndefined();
  });
});
