import type { Chunk } from "@ai-study-mentor/api-client";
import { describe, expect, it } from "vitest";
import { chunkForCitation, closestSentence, excerpt, linkCitations } from "./citations";
import type { CitationCheck } from "./session";

const chunk = (doc: string, page: number | null, text = "text", end_page: number | null = null): Chunk => ({ doc, page, end_page, text, score: 0.8 });
const ok = (label: string, doc: string, page: number | null): CitationCheck => ({ label, doc, page, status: "ok" });

describe("chunkForCitation", () => {
  const chunks = [chunk("heaps.pdf", 1), chunk("heaps.pdf", 4, "t", 5), chunk("notes.md", null)];

  it("picks the passage on the cited page, including a page range", () => {
    expect(chunkForCitation(ok("heaps.pdf (page 1)", "heaps.pdf", 1), chunks)).toBe(0);
    expect(chunkForCitation(ok("heaps.pdf (page 5)", "heaps.pdf", 5), chunks)).toBe(1);
  });

  it("matches documents without their extension or with a section after the name", () => {
    expect(chunkForCitation(ok("heaps (page 1)", "heaps", 1), chunks)).toBe(0);
    expect(chunkForCitation(ok("notes.md > Hashing", "notes.md > Hashing", null), chunks)).toBe(2);
  });

  it("never points an unverified citation at a passage", () => {
    expect(chunkForCitation({ doc: "heaps.pdf", page: 40, status: "page_not_retrieved" }, chunks)).toBeNull();
    expect(chunkForCitation({ doc: "Invented.pdf", page: 9, status: "unknown_source" }, chunks)).toBeNull();
  });
});

describe("linkCitations", () => {
  const chunks = [chunk("heaps.pdf", 1), chunk("graphs.pdf", 2)];

  it("replaces verified citations with numbered references and remembers the citing sentence", () => {
    const answer = "Intro. A heap keeps the smallest key on top [heaps.pdf (page 1)]. BFS uses a queue [graphs.pdf (page 2)].";
    const { markdown, refs } = linkCitations(answer, [ok("heaps.pdf (page 1)", "heaps.pdf", 1), ok("graphs.pdf (page 2)", "graphs.pdf", 2)], chunks);
    expect(markdown).toBe("Intro. A heap keeps the smallest key on top [0](#cite-0). BFS uses a queue [1](#cite-1).");
    expect(refs.map((r) => r.chunk)).toEqual([0, 1]);
    expect(refs[0]?.sentence).toBe("A heap keeps the smallest key on top");
  });

  it("splits a bracket that holds several citations", () => {
    const { markdown, refs } = linkCitations("Both [heaps.pdf (page 1), graphs.pdf (page 2)].", [ok("heaps.pdf (page 1)", "heaps.pdf", 1), ok("graphs.pdf (page 2)", "graphs.pdf", 2)], chunks);
    expect(markdown).toBe("Both [0](#cite-0)[1](#cite-1).");
    expect(refs).toHaveLength(2);
  });

  it("keeps unverified citations as references without a passage", () => {
    const bad: CitationCheck = { label: "Invented.pdf (page 9)", doc: "Invented.pdf", page: 9, status: "unknown_source" };
    const { refs } = linkCitations("Claim [Invented.pdf (page 9)].", [bad], chunks);
    expect(refs[0]).toMatchObject({ chunk: null, status: "unknown_source" });
  });

  it("leaves code, ordinary brackets and unreported citations untouched", () => {
    const answer = "Use `nums[heaps.pdf (page 1)]` and arr[0] or [Other.pdf (page 3)].\n```\nx = [heaps.pdf (page 1)]\n```";
    const { markdown, refs } = linkCitations(answer, [ok("heaps.pdf (page 1)", "heaps.pdf", 1)], chunks);
    expect(markdown).toBe(answer);
    expect(refs).toHaveLength(0);
  });

  it("does nothing until the server has checked the citations", () => {
    expect(linkCitations("A [heaps.pdf (page 1)].", undefined, chunks).refs).toHaveLength(0);
  });
});

describe("closestSentence", () => {
  const text = "Heaps are trees. A binary heap keeps the smallest key at the root of the tree. Arrays store them compactly.";

  it("finds the passage sentence that shares the most words with the citing sentence", () => {
    const span = closestSentence(text, "a binary heap keeps the smallest key on top");
    expect(span && text.slice(span.start, span.end)).toBe("A binary heap keeps the smallest key at the root of the tree.");
  });

  it("returns null when nothing overlaps", () => {
    expect(closestSentence(text, "graphs and queues")).toBeNull();
  });
});

describe("excerpt", () => {
  it("returns short passages whole", () => {
    expect(excerpt("short text", null)).toMatchObject({ text: "short text", clippedStart: false, clippedEnd: false });
  });

  it("centres long passages on the highlight", () => {
    const text = `${"lead ".repeat(200)}TARGET sentence here.${" tail".repeat(200)}`;
    const start = text.indexOf("TARGET");
    const cut = excerpt(text, { start, end: start + 21 }, 50);
    expect(cut.text).toContain("TARGET sentence here.");
    expect(cut.clippedStart && cut.clippedEnd).toBe(true);
    expect(text.slice(cut.offset, cut.offset + cut.text.length)).toBe(cut.text);
  });
});
