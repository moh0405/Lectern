import { describe, expect, it } from "vitest";
import { plainText, toFlashcardsCsv } from "./flashcards";
import type { Turn } from "./session";

const turn = (over: Partial<Turn>): Turn => ({ id: "x", question: "q", answer: "a", chunks: [], status: "done", ...over });

describe("plainText", () => {
  it("removes markdown markers and keeps code content and link text", () => {
    expect(plainText("**Bold** and `code` and [a link](https://x.y)")).toBe("Bold and code and a link");
    expect(plainText("```python\nx = 1\n```")).toBe("x = 1");
    expect(plainText("# Title\n\n\n\nBody")).toBe("Title\n\nBody");
  });
});

describe("toFlashcardsCsv", () => {
  it("lists answered turns oldest first and skips unfinished or empty ones", () => {
    const turns = [
      turn({ id: "3", question: "newest", answer: "three" }), // turns are stored newest first
      turn({ id: "2", question: "failed", answer: "", status: "error" }),
      turn({ id: "1", question: "oldest, with comma", answer: "**one**" }),
    ];
    expect(toFlashcardsCsv(turns)).toBe('front,back\n"oldest, with comma",one\nnewest,three\n');
  });
  it("neutralises spreadsheet formulas in questions and answers", () => {
    const csv = toFlashcardsCsv([turn({ question: "=HYPERLINK(\"http://evil\")", answer: "+1" })]);
    expect(csv).toContain("'=HYPERLINK");
    expect(csv).toContain("'+1");
  });
});
