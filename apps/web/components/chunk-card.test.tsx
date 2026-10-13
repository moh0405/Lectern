import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ChunkCard, scoreTone } from "./chunk-card";

const base = { text: "A heap is a complete binary tree used for a priority queue.", doc: "heaps.pdf", page: 4, score: 0.72 };

describe("ChunkCard", () => {
  it("shows document, page, index and score, and highlights query terms", () => {
    const { container } = render(<ChunkCard chunk={base} query="what is a heap" index={0} />);
    expect(screen.getByText(/heaps\.pdf/)).toBeInTheDocument();
    expect(screen.getByText(/page 4/)).toBeInTheDocument();
    expect(screen.getByText("[1]")).toBeInTheDocument();
    expect(screen.getByText("0.72")).toBeInTheDocument();
    expect([...container.querySelectorAll("mark")].map((m) => m.textContent)).toEqual(["heap"]);
  });

  it("prefers the deep citation link (e.g. a YouTube timestamp) and opens it safely", () => {
    render(<ChunkCard chunk={{ ...base, url: "https://youtu.be/x", citation_url: "https://www.youtube.com/watch?v=x&t=95s" }} query="heap" />);
    const link = screen.getByRole("link", { name: /open/ });
    expect(link).toHaveAttribute("href", "https://www.youtube.com/watch?v=x&t=95s");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });

  it("truncates very long passages", () => {
    render(<ChunkCard chunk={{ ...base, text: "word ".repeat(400) }} query="" />);
    expect(screen.getByText(/…$/)).toBeInTheDocument();
  });

  it("buckets scores", () => {
    expect([scoreTone(0.8), scoreTone(0.4), scoreTone(0.1)]).toEqual(["good", "mid", "low"]);
  });
});

describe("ChunkCard page labels", () => {
  it("shows a page range when the passage spans two pages", () => {
    render(<ChunkCard chunk={{ ...base, page: 132, end_page: 133 }} query="heap" />);
    expect(screen.getByText(/pages 132–133/)).toBeInTheDocument();
  });
});
