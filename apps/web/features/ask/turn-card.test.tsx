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
