import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api";
import { errorPosition } from "@/features/math/math-view";
import { topicSuggestions } from "./library";
import { matchPassage, PassageList, passageWhere } from "./passages";
import { nextTabIndex } from "./tutor-view";

const chunk = (doc: string, page: number | null, text = "A heap is a complete binary tree.") => ({ doc, page, text, score: 0.29 });

describe("nextTabIndex (ARIA tabs keyboard pattern)", () => {
  it("moves with arrows, wraps, and jumps with Home/End", () => {
    expect(nextTabIndex("ArrowRight", 0, 4)).toBe(1);
    expect(nextTabIndex("ArrowRight", 3, 4)).toBe(0);
    expect(nextTabIndex("ArrowLeft", 0, 4)).toBe(3);
    expect(nextTabIndex("Home", 2, 4)).toBe(0);
    expect(nextTabIndex("End", 0, 4)).toBe(3);
    expect(nextTabIndex("Enter", 1, 4)).toBeNull();
  });
});

describe("matchPassage", () => {
  const chunks = [chunk("heaps.pdf", 1), chunk("graphs.pdf", 2), chunk("heaps.pdf", 3)];
  it("links a source label to its passage, preferring the named page", () => {
    expect(matchPassage("graphs.pdf", chunks)).toBe(1);
    expect(matchPassage("heaps.pdf", chunks)).toBe(0);
    expect(matchPassage("heaps.pdf (page 3)", chunks)).toBe(2);
    expect(matchPassage("Heaps.pdf p. 3", chunks)).toBe(2);
    expect(matchPassage("heaps.pdf (page 9)", chunks)).toBe(0);
    expect(matchPassage("trees.pdf", chunks)).toBe(-1);
  });
  it("describes where a passage is", () => {
    expect(passageWhere({ doc: "a.pdf", page: 2, end_page: 3 })).toBe("a.pdf · pages 2–3");
    expect(passageWhere({ doc: "notes.md", page: null })).toBe("notes.md");
  });
});

describe("topicSuggestions", () => {
  it("turns file names into topics", () => {
    expect(topicSuggestions(["heaps.pdf", "graphs.pdf"])).toEqual(["Heaps", "Graphs"]);
    expect(topicSuggestions(["graph_algorithms-notes.pdf", "https://example.com/wiki/Hash_table"])).toEqual(["Graph algorithms notes", "Hash table"]);
    expect(topicSuggestions(["a.pdf", "123.pdf", "heaps.pdf", "heaps.PDF"])).toEqual(["Heaps"]);
    expect(topicSuggestions(["one.pdf", "two.pdf", "three.pdf", "four.pdf"])).toHaveLength(3);
  });
});

describe("PassageList", () => {
  it("lists passages on paper with a count and expands long ones", () => {
    const long = "x ".repeat(300);
    render(<PassageList chunks={[chunk("heaps.pdf", 1), chunk("graphs.pdf", 2, long)]} prefix="t" />);
    expect(screen.getByRole("heading", { name: /Built from 2 passages/ })).toBeInTheDocument();
    expect(screen.getAllByTestId("passage")).toHaveLength(2);
    const more = screen.getByRole("button", { name: "Show the whole passage" });
    expect(more).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(more);
    expect(screen.getByRole("button", { name: "Show less" })).toHaveAttribute("aria-expanded", "true");
  });
  it("shows relevance neutrally, with what the number means", () => {
    render(<PassageList chunks={[chunk("heaps.pdf", 1)]} prefix="r" showRelevance />);
    expect(screen.getByTestId("relevance")).toHaveTextContent("relevance 0.29");
    expect(screen.getByText(/Relevance runs from 0 to 1/)).toBeInTheDocument();
  });
  it("opens a targeted passage", () => {
    const long = "y ".repeat(300);
    const { rerender } = render(<PassageList chunks={[chunk("a.pdf", 1, long)]} prefix="g" target={null} />);
    rerender(<PassageList chunks={[chunk("a.pdf", 1, long)]} prefix="g" target={{ index: 0, nonce: 1 }} />);
    expect(screen.getByRole("button", { name: "Show less" })).toBeInTheDocument();
  });
});

describe("errorPosition", () => {
  it("reads the math error position the API sends", () => {
    const err = new ApiError(422, "math_error", "Unbalanced parentheses", { position: 6 });
    expect(errorPosition(err, "x^2 + (3")).toBe(6);
    expect(errorPosition(new ApiError(422, "math_error", "x", { position: 99 }), "short")).toBeNull();
    expect(errorPosition(new ApiError(422, "math_error", "x"), "abc")).toBeNull();
    expect(errorPosition(new Error("boom"), "abc")).toBeNull();
  });
});
