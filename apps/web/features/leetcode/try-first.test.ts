import type { Chunk } from "@ai-study-mentor/api-client";
import { describe, expect, it } from "vitest";
import { attemptContext, attemptQuestion, LIBRARY_PASSAGES } from "./try-first";

const problem = { pid: "1", title: "Two Sum", description: "Given an array of integers, return two indices." };
const chunk = (n: number): Chunk => ({ text: `passage ${n}`, doc: `book${n}.pdf`, page: n, score: 0.5 });

describe("LeetCode Try first", () => {
  it("names the problem in the question", () => {
    expect(attemptQuestion(problem)).toBe("Solve LeetCode problem 1: Two Sum");
  });

  it("judges against the statement first, then a few library passages", () => {
    const context = attemptContext(problem, [1, 2, 3, 4, 5].map(chunk));
    expect(context[0]).toMatchObject({ doc: "LeetCode 1. Two Sum", text: problem.description, page: null });
    expect(context).toHaveLength(1 + LIBRARY_PASSAGES);
    expect(context[1]).toMatchObject({ doc: "book1.pdf", page: 1 });
  });

  it("still works when the library has nothing", () => {
    expect(attemptContext(problem, [])).toHaveLength(1);
  });

  it("keeps every passage inside the API's limits", () => {
    const [statement] = attemptContext({ ...problem, title: "t".repeat(400), description: "d".repeat(5000) }, []);
    expect(statement!.text).toHaveLength(4000);
    expect(statement!.doc).toHaveLength(300);
  });

  it("leaves out a blank statement, which the API would reject", () => {
    expect(attemptContext({ ...problem, description: "  \n" }, [chunk(1)]).map((p) => p.doc)).toEqual(["book1.pdf"]);
  });
});
