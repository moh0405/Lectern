import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TurnCard } from "./turn-card";
import type { Turn } from "./session";

const turn = (over: Partial<Turn>): Turn => ({ id: "1", question: "what is a heap", answer: "", chunks: [], status: "done", ...over });
const chunks = [{ text: "heap text", doc: "heaps.pdf", page: 1, score: 0.7 }];

describe("TurnCard", () => {
  it("explains a missing API key and still shows the retrieved sources", () => {
    render(
      <TurnCard
        turn={turn({ status: "error", chunks, error: { code: "llm_unavailable", message: "GEMINI_API_KEY is not set" } })}
        onStop={() => {}}
        onRemove={() => {}}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent(/no GEMINI_API_KEY/i);
    expect(screen.getByText("Sources (1)")).toBeInTheDocument();
    expect(screen.getByRole("article")).toHaveTextContent("heap text");
  });

  it("shows other errors as alerts", () => {
    render(<TurnCard turn={turn({ status: "error", error: { code: "llm_error", message: "upstream exploded" } })} onStop={() => {}} onRemove={() => {}} />);
    expect(screen.getByRole("alert")).toHaveTextContent("upstream exploded");
  });

  it("offers Stop while streaming and remove when finished", async () => {
    const onStop = vi.fn();
    const onRemove = vi.fn();
    const { rerender } = render(<TurnCard turn={turn({ status: "streaming", answer: "Par" })} onStop={onStop} onRemove={onRemove} />);
    await userEvent.click(screen.getByRole("button", { name: /stop/i }));
    expect(onStop).toHaveBeenCalled();
    rerender(<TurnCard turn={turn({ answer: "Done." })} onStop={onStop} onRemove={onRemove} />);
    await userEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(onRemove).toHaveBeenCalled();
  });

  it("renders markdown answers without executing raw HTML", () => {
    const { container } = render(
      <TurnCard turn={turn({ answer: "**bold** <img src=x onerror=alert(1)> <script>alert(1)</script>" })} onStop={() => {}} onRemove={() => {}} />,
    );
    expect(screen.getByText("bold").tagName).toBe("STRONG");
    expect(container.querySelector("img, script")).toBeNull();
  });

  it("says when nothing matched", () => {
    render(<TurnCard turn={turn({ answer: "I could not find that.", chunks: [] })} onStop={() => {}} onRemove={() => {}} />);
    expect(screen.getByText(/No matching passages/)).toBeInTheDocument();
  });
});


describe("TurnCard citation checks", () => {
  const done = (over: Partial<Turn>) => turn({ answer: "A heap is a tree.", ...over });

  it("warns about citations to sources the model was not given", () => {
    render(
      <TurnCard
        turn={done({
          citations: [
            { label: "heaps.pdf (page 1)", doc: "heaps.pdf", page: 1, status: "ok" },
            { label: "Invented.pdf (page 9)", doc: "Invented.pdf", page: 9, status: "unknown_source" },
            { label: "heaps.pdf (page 40)", doc: "heaps.pdf", page: 40, status: "page_not_retrieved" },
          ],
        })}
        onStop={() => {}}
        onRemove={() => {}}
      />,
    );
    const note = screen.getByRole("status");
    expect(note).toHaveTextContent("cites things it was not given");
    expect(note).toHaveTextContent("[Invented.pdf (page 9)]");
    expect(note).toHaveTextContent("that source was not among the passages");
    expect(note).toHaveTextContent("[heaps.pdf (page 40)]");
    expect(note).toHaveTextContent("that page was not among the passages");
    expect(note).not.toHaveTextContent("[heaps.pdf (page 1)]");
  });

  it("says nothing when every citation checks out", () => {
    render(
      <TurnCard
        turn={done({ citations: [{ label: "heaps.pdf (page 1)", doc: "heaps.pdf", page: 1, status: "ok" }] })}
        onStop={() => {}}
        onRemove={() => {}}
      />,
    );
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("notes an answer that cites none of its sources", () => {
    render(<TurnCard turn={done({ uncited: true, citations: [] })} onStop={() => {}} onRemove={() => {}} />);
    expect(screen.getByRole("status")).toHaveTextContent("does not cite any of the sources");
  });

  it("does not judge an answer that is still streaming", () => {
    render(
      <TurnCard
        turn={done({ status: "streaming", citations: [{ label: "x.pdf", doc: "x.pdf", page: null, status: "unknown_source" }] })}
        onStop={() => {}}
        onRemove={() => {}}
      />,
    );
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("shows a cached badge and offers a fresh answer", async () => {
    const onFresh = vi.fn();
    const { rerender } = render(<TurnCard turn={done({ cached: true })} onStop={() => {}} onRemove={() => {}} onFresh={onFresh} />);
    expect(screen.getByText("cached")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Fresh answer" }));
    expect(onFresh).toHaveBeenCalled();
    rerender(<TurnCard turn={done({ cached: false })} onStop={() => {}} onRemove={() => {}} onFresh={onFresh} />);
    expect(screen.queryByText("cached")).toBeNull();
    expect(screen.queryByRole("button", { name: "Fresh answer" })).toBeNull();
  });
});
