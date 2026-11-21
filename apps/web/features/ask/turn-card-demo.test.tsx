import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DemoContext } from "@/lib/demo";
import { listLocalCards } from "@/lib/local-cards";

const post = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { http: { POST: (...a: unknown[]) => post(...a) } },
  unwrap: (r: { data?: unknown }) => r.data,
  errorMessage: (e: unknown) => String(e),
}));

import { NotesPanel } from "./notes-panel";
import type { Turn } from "./session";
import { TurnCard } from "./turn-card";

const turn: Turn = {
  id: "1",
  question: "What is a heap?",
  answer: "A heap is a tree [heaps.pdf (page 1)].",
  chunks: [{ text: "heap text", doc: "heaps.pdf", page: 1, score: 0.7 }],
  citations: [{ label: "heaps.pdf (page 1)", doc: "heaps.pdf", page: 1, status: "ok" }],
  status: "done",
  local: true,
};

const inDemo = (ui: React.ReactElement) =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <DemoContext.Provider value={true}>{ui}</DemoContext.Provider>
    </QueryClientProvider>,
  );

describe("Ask in the public demo", () => {
  it("saves a flashcard in this browser without asking the server", async () => {
    localStorage.clear();
    inDemo(<TurnCard turn={turn} onStop={() => {}} onRemove={() => {}} scope="In this browser" />);
    await userEvent.click(screen.getByRole("button", { name: "Save as flashcard" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Saved as flashcard" })).toBeInTheDocument());
    expect(screen.getAllByText("Saved to this browser").length).toBeGreaterThan(0);
    expect(post).not.toHaveBeenCalled();
    expect(listLocalCards().cards.map((c) => c.front)).toEqual(["What is a heap?"]);
    expect(screen.getByText(/In this browser/)).toBeInTheDocument();
  });

  it("writes study notes in the browser and offers only a Markdown download", async () => {
    inDemo(<NotesPanel turns={[turn]} />);
    await userEvent.click(screen.getByRole("button", { name: /Generate from this session/ }));
    expect(await screen.findByRole("heading", { name: "Study notes", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "MD" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "PDF" })).toBeNull();
    expect(post).not.toHaveBeenCalled();
  });

  it("offers the shared textbooks when your own documents match nothing, without an error alert", async () => {
    const onSearchShared = vi.fn();
    inDemo(<TurnCard turn={{ ...turn, answer: "", chunks: [], citations: [], status: "error", error: { code: "no_local_match", message: "Nothing in your documents matches that question." } }} onStop={() => {}} onRemove={() => {}} onSearchShared={onSearchShared} />);
    expect(screen.queryByRole("alert")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Search the shared textbooks instead" }));
    expect(onSearchShared).toHaveBeenCalled();
    expect(screen.getByRole("link", { name: "Add material" })).toHaveAttribute("href", "/sources");
  });
});
