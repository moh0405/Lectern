import { describe, expect, it } from "vitest";
import { chunkPages } from "./chunk";

const sentence = (n: number) => `Sentence number ${n} talks about hashing and buckets in some detail.`;

describe("chunkPages", () => {
  it("returns nothing for empty pages", () => {
    expect(chunkPages(["", "   "])).toEqual([]);
  });

  it("keeps a short page as one passage on its page", () => {
    expect(chunkPages(["A heap is a tree. It keeps the minimum on top."])).toEqual([{ text: "A heap is a tree. It keeps the minimum on top.", page: 1 }]);
  });

  it("groups sentences near the target size, overlapping by one sentence, and marks passages that span pages", () => {
    const pages = [Array.from({ length: 20 }, (_, i) => sentence(i)).join(" "), Array.from({ length: 20 }, (_, i) => sentence(20 + i)).join(" ")];
    const out = chunkPages(pages, { target: 60 });
    expect(out.length).toBeGreaterThan(3);
    for (const p of out) expect(p.text.split(/\s+/).length).toBeLessThanOrEqual(80);
    // overlap: each passage starts with the last sentence of the one before
    const lastOfFirst = out[0]!.text.split(/(?<=\.)\s/).at(-1)!;
    expect(out[1]!.text.startsWith(lastOfFirst)).toBe(true);
    expect(out.some((p) => p.end_page === 2 && p.page === 1)).toBe(true);
    expect(out.at(-1)!.page).toBeGreaterThanOrEqual(1);
  });

  it("splits a single enormous 'sentence' instead of making one giant passage", () => {
    const long = Array.from({ length: 500 }, (_, i) => `w${i}`).join(" ");
    const out = chunkPages([long], { max: 100 });
    expect(out.length).toBeGreaterThanOrEqual(5);
    for (const p of out) expect(p.text.split(/\s+/).length).toBeLessThanOrEqual(200);
  });
});
