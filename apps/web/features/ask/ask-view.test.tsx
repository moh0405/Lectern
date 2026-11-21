import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Turn } from "./session";

const get = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { http: { GET: (path: string, ...rest: unknown[]) => get(path, ...rest), POST: vi.fn(), DELETE: vi.fn() } },
  unwrap: (r: { data?: unknown; error?: unknown }) => {
    if (r.error !== undefined) throw new Error("unreachable");
    return r.data;
  },
  errorMessage: (e: unknown) => (e instanceof Error ? e.message : "unknown"),
}));
vi.mock("@/lib/browser-rag/use-local-docs", () => ({ useLocalDocs: () => ({ data: [] }) }));
const url = vi.hoisted(() => ({ search: "" }));
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(url.search) }));

const session = { turns: [] as Turn[], ask: vi.fn(), stop: vi.fn(), remove: vi.fn(), clear: vi.fn(), busy: false };
vi.mock("./use-ask-session", () => ({ useAskSession: () => session }));

import { AskView } from "./ask-view";

const chunks = [{ text: "A heap keeps the smallest key on top.", doc: "heaps.pdf", page: 1, score: 0.7 }];
const done: Turn = {
  id: "t1",
  question: "What is a binary heap used for?",
  answer: "A heap keeps the smallest key on top [heaps.pdf (page 1)].",
  chunks,
  citations: [{ label: "heaps.pdf (page 1)", doc: "heaps.pdf", page: 1, status: "ok" }],
  status: "done",
};

function serve({ chunks: n = 2, offline = false } = {}) {
  get.mockImplementation(async (path: string) => {
    if (offline) throw new TypeError("Failed to fetch");
    if (path === "/api/v1/stats") return { data: { chunks: n, documents: 1 } };
    if (path === "/api/v1/documents") return { data: { documents: [] } };
    if (path === "/api/v1/suggestions") return { data: { questions: [] } };
    if (path === "/api/v1/models") return { data: { default: "m", models: ["m"] } };
    return { data: {} };
  });
}

const view = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AskView /></QueryClientProvider>);
const status = () => document.querySelector('p[role="status"].sr-only');

beforeEach(() => {
  get.mockReset();
  session.turns = [];
  session.busy = false;
  url.search = "";
  Object.values(session).forEach((v) => typeof v === "function" && "mockReset" in v && v.mockReset());
});

describe("AskView opening state", () => {
  it("shows the empty state only when the stats say there is no material", async () => {
    serve({ chunks: 0 });
    view();
    expect(await screen.findByText("No study material yet")).toBeInTheDocument();
    expect(screen.queryByText(/Can't reach Lectern/)).toBeNull();
  });

  it("says the server is unreachable, not that the library is empty, and disables asking", async () => {
    serve({ offline: true });
    view();
    expect(await screen.findByText("Can't reach Lectern right now")).toBeInTheDocument();
    expect(screen.queryByText("No study material yet")).toBeNull();
    await userEvent.type(screen.getByLabelText("Your question"), "What is a heap?");
    expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Explain dynamic programming/ })).toBeDisabled();
    serve();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(screen.queryByText("Can't reach Lectern right now")).toBeNull());
  });

  it("keeps the composer compact: a hidden label, and Style and Passages inside Advanced", async () => {
    serve();
    view();
    expect(screen.getByLabelText("Your question")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask" })).toBeInTheDocument();
    expect(screen.getByLabelText("Style").closest("details")).not.toBeNull();
    expect(screen.getByLabelText("Passages").closest("details")).not.toBeNull();
  });

  it("explains the passage-search limit and refuses longer questions", async () => {
    serve();
    view();
    await userEvent.click(screen.getByText("Advanced"));
    await userEvent.click(screen.getByLabelText(/Only show matching passages/));
    const box = screen.getByLabelText("Your question") as HTMLTextAreaElement;
    expect(box.maxLength).toBe(500);
  });

  it("prefills and focuses the composer from ?q= without sending it, then drops q from the address", async () => {
    serve();
    url.search = "?q=What%20is%20a%20heap%3F";
    window.history.replaceState(null, "", "/ask?q=What%20is%20a%20heap%3F");
    view();
    const box = screen.getByLabelText("Your question");
    await waitFor(() => expect(box).toHaveValue("What is a heap?"));
    await waitFor(() => expect(box).toHaveFocus());
    expect(session.ask).not.toHaveBeenCalled();
    expect(window.location.search).toBe("");
  });
});

describe("AskView with a session", () => {
  it("asks before clearing all history, and Escape cancels", async () => {
    serve();
    session.turns = [done];
    view();
    await userEvent.click(screen.getByRole("button", { name: "Clear history" }));
    expect(session.clear).not.toHaveBeenCalled();
    expect(screen.getByRole("group", { name: "Clear history?" })).toHaveTextContent(/Delete all 1 question/);
    expect(screen.getByRole("button", { name: "Confirm clear" })).toHaveFocus();
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.getByRole("button", { name: "Clear history" })).toHaveFocus());
    await userEvent.click(screen.getByRole("button", { name: "Clear history" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirm clear" }));
    expect(session.clear).toHaveBeenCalledTimes(1);
  });

  it("announces a finished answer and an opened passage through one status region", async () => {
    serve();
    session.turns = [{ ...done, status: "streaming", answer: "", citations: undefined }];
    const { rerender } = view();
    session.turns = [done];
    rerender(<QueryClientProvider client={new QueryClient()}><AskView /></QueryClientProvider>);
    await waitFor(() => expect(status()).toHaveTextContent("Answer ready: 1 citation checked, 0 could not be checked"));
    expect(screen.getByText("1 citation checked against your material")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /^Citation heaps\.pdf/ }));
    await waitFor(() => expect(status()).toHaveTextContent("Passage 1 opened in the source margin"));
    expect(screen.getByRole("button", { name: /^Citation heaps\.pdf/ })).toHaveFocus();
  });

  it("hints instead of ignoring Ctrl+Enter while an answer is being written", async () => {
    serve();
    session.turns = [{ ...done, status: "streaming" }];
    session.busy = true;
    view();
    const box = screen.getByLabelText("Your question");
    await userEvent.type(box, "Another question");
    await act(async () => {
      await userEvent.keyboard("{Control>}{Enter}{/Control}");
    });
    expect(session.ask).not.toHaveBeenCalled();
    expect(screen.getByText(/An answer is still being written/)).toBeInTheDocument();
  });

  it("offers to go further with the study tools, carrying the question", () => {
    serve();
    session.turns = [done];
    view();
    const links = within(screen.getByRole("list", { name: "Go further" })).getAllByRole("link");
    expect(links.map((l) => [l.textContent?.trim(), l.getAttribute("href")])).toEqual([
      ["Concept map of this topic", "/concept-map?topic=What%20is%20a%20binary%20heap%20used%20for%3F"],
      ["Compare your sources", "/compare?topic=What%20is%20a%20binary%20heap%20used%20for%3F"],
      ["Work it out with hints", "/work-it-out?question=What%20is%20a%20binary%20heap%20used%20for%3F"],
    ]);
  });

  it("does not offer the tools for an answer without passages", () => {
    serve();
    session.turns = [{ ...done, chunks: [], citations: [] }];
    view();
    expect(screen.queryByTestId("go-further")).toBeNull();
  });

  it("does not show the steps or Understanding for an answer that failed", () => {
    serve();
    session.turns = [{ ...done, status: "error", answer: "", chunks: [], error: { code: "rate_limited", message: "Busy." } }];
    view();
    expect(screen.queryByRole("navigation", { name: "Steps" })).toBeNull();
    expect(screen.queryByText("Make the idea yours.")).toBeNull();
    expect(screen.getByRole("complementary", { name: "Source margin" })).toHaveTextContent("This question didn't reach your sources. Try again.");
  });
});
