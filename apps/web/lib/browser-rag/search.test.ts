import { describe, expect, it } from "vitest";
import { Bm25, cosine, hybridSearch, tokenize } from "./search";

const docs = [
  "A hash table maps keys to buckets and resolves collisions by chaining.",
  "Dijkstra finds shortest paths with a priority queue.",
  "Quicksort partitions the array around a pivot.",
];

describe("tokenize", () => {
  it("lowercases, drops stop words and strips simple plurals", () => {
    expect(tokenize("How do Hash Tables handle collisions?")).toEqual(["hash", "table", "handle", "collision"]);
  });
});

describe("Bm25", () => {
  it("ranks the passage with the query's rare words first", () => {
    const s = new Bm25(docs).scores("shortest path priority queue");
    expect(s.indexOf(Math.max(...s))).toBe(1);
    expect(s[0]).toBe(0);
  });
});

describe("hybridSearch", () => {
  const bm25 = new Bm25(docs);
  it("keyword-only: finds the match and scales the score to 0..1", () => {
    const hits = hybridSearch({ query: "quicksort pivot", bm25, k: 2 });
    expect(hits[0]).toMatchObject({ index: 2, score: 1 });
  });
  it("fuses meaning: a passage with no shared words can still surface through its vector", () => {
    const vectors = [[1, 0], [0, 1], [0.8, 0.6]];
    const hits = hybridSearch({ query: "unrelated words", bm25, vectors, queryVector: [0, 1], k: 2 });
    expect(hits[0]!.index).toBe(1); // nearest vector
    expect(hits[0]!.score).toBeCloseTo(1);
  });
  it("returns nothing when nothing matches", () => {
    expect(hybridSearch({ query: "zzzz", bm25, k: 3 })).toEqual([]);
  });
});

it("cosine of unit vectors is the dot product", () => {
  expect(cosine([0.6, 0.8], [0.6, 0.8])).toBeCloseTo(1);
  expect(cosine([1, 0], [0, 1])).toBe(0);
});
