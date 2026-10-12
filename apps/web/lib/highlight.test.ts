import { describe, expect, it } from "vitest";
import { queryTerms, splitByTerms } from "./highlight";

describe("queryTerms", () => {
  it("drops stopwords and short words, lowercases and de-duplicates", () => {
    expect(queryTerms("What is the Linked List, a list?")).toEqual(["linked", "list"]);
  });
  it("returns nothing for empty input", () => {
    expect(queryTerms("")).toEqual([]);
  });
});

describe("splitByTerms", () => {
  it("marks whole-word, case-insensitive matches", () => {
    const parts = splitByTerms("A Linked list links nodes", ["linked", "list"]);
    expect(parts.filter((p) => p.match).map((p) => p.text)).toEqual(["Linked", "list"]);
    expect(parts.map((p) => p.text).join("")).toBe("A Linked list links nodes");
  });
  it("does not match inside longer words", () => {
    expect(splitByTerms("listing", ["list"]).some((p) => p.match)).toBe(false);
  });
  it("escapes regex characters in terms", () => {
    expect(() => splitByTerms("a (b) c", ["(b)", "c++"])).not.toThrow();
  });
  it("handles no terms", () => {
    expect(splitByTerms("text", [])).toEqual([{ text: "text", match: false }]);
  });
});
