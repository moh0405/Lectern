import type { Chunk } from "@ai-study-mentor/api-client";
import { describe, expect, it } from "vitest";
import { chunkForCitation, cleanParen, closestSentence, excerpt, linkCitations } from "./citations";
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

describe("citation matching regressions", () => {
  it("does not confuse a document with another whose name starts the same way", () => {
    const chunks = [chunk("notes.md", null, "plain notes"), chunk("notes advanced.md", null, "advanced notes")];
    const cite = ok("notes advanced.md", "notes advanced.md", null);
    expect(chunkForCitation(cite, chunks)).toBe(1);
    const { refs } = linkCitations("Deep dive [notes advanced.md].", [cite], chunks);
    expect(refs).toHaveLength(1);
    expect(refs[0]).toMatchObject({ chunk: 1, status: "ok" });
  });

  it("gives each bracket only its own citations when one document is cited in several brackets", () => {
    const chunks = [chunk("Dsa.pdf", 12, "a"), chunk("Dsa.pdf", 14, "b"), chunk("Dsa.pdf", 30, "c")];
    const citations = [ok("Dsa.pdf (page 12)", "Dsa.pdf", 12), ok("Dsa.pdf (page 14)", "Dsa.pdf", 14), ok("Dsa.pdf (page 30)", "Dsa.pdf", 30)];
    const { markdown, refs } = linkCitations("Heaps are trees [Dsa.pdf (page 12, 14)]. Graphs have edges [Dsa.pdf (page 30)].", citations, chunks);
    expect(markdown).toBe("Heaps are trees [0](#cite-0)[1](#cite-1). Graphs have edges [2](#cite-2).");
    expect(refs.map((r) => [r.page, r.chunk])).toEqual([
      [12, 0],
      [14, 1],
      [30, 2],
    ]);
  });

  it("splits a page list written without parentheses", () => {
    const chunks = [chunk("Dsa.pdf", 58), chunk("Dsa.pdf", 170)];
    const citations = [ok("Dsa.pdf (page 58)", "Dsa.pdf", 58), ok("Dsa.pdf (page 170)", "Dsa.pdf", 170)];
    const { markdown, refs } = linkCitations("See [Dsa.pdf, pages 58, 170].", citations, chunks);
    expect(markdown).toBe("See [0](#cite-0)[1](#cite-1).");
    expect(refs.map((r) => r.chunk)).toEqual([0, 1]);
  });

  it("finds a page range by any retrieved page in it, not only its first", () => {
    const chunks = [chunk("heaps.pdf", 1), chunk("heaps.pdf", 6)];
    const cite = ok("heaps.pdf (pages 4-6)", "heaps.pdf", 4);
    expect(chunkForCitation(cite, chunks)).toBe(1);
    expect(chunkForCitation(ok("heaps.pdf, pp. 4–6", "heaps.pdf", 4), chunks)).toBe(1);
    expect(linkCitations("Sift down [heaps.pdf (pages 4-6)].", [cite], chunks).refs[0]?.chunk).toBe(1);
  });

  it("picks the passage on the cited page that best matches the citing sentence", () => {
    const chunks = [chunk("heaps.pdf", 3, "Arrays store a heap compactly by index."), chunk("heaps.pdf", 3, "Sift down restores the heap property after removing the root.")];
    const cite = ok("heaps.pdf (page 3)", "heaps.pdf", 3);
    const { refs } = linkCitations("Removing the root needs a sift down to restore order [heaps.pdf (page 3)].", [cite], chunks);
    expect(refs[0]?.chunk).toBe(1);
    expect(linkCitations("Heaps live compactly in arrays [heaps.pdf (page 3)].", [cite], chunks).refs[0]?.chunk).toBe(0);
  });

  it("follows a citation with a section path to its document", () => {
    const chunks = [chunk("graphs.pdf", 2), chunk("notes.md", null, "hash tables")];
    const cite = ok("notes.md > Hashing", "notes.md", null);
    const { markdown, refs } = linkCitations("Collisions chain [notes.md > Hashing].", [cite], chunks);
    expect(markdown).toBe("Collisions chain [0](#cite-0).");
    expect(refs[0]).toMatchObject({ chunk: 1, status: "ok" });
  });

  it("shows no passage, but keeps it verified, when the cited page is not among the listed passages", () => {
    const chunks = [chunk("heaps.pdf", 1)];
    const cite = ok("heaps.pdf (page 9)", "heaps.pdf", 9);
    expect(chunkForCitation(cite, chunks)).toBeNull();
    const { refs } = linkCitations("Claim [heaps.pdf (page 9)].", [cite], chunks);
    expect(refs[0]).toMatchObject({ chunk: null, status: "ok" });
  });

  it("does not link a bracket that only mentions a cited document", () => {
    const chunks = [chunk("a.md", null)];
    const { markdown, refs } = linkCitations("Fine [a.md]. Not this [see a.md for more].", [ok("a.md", "a.md", null)], chunks);
    expect(markdown).toBe("Fine [0](#cite-0). Not this [see a.md for more].");
    expect(refs).toHaveLength(1);
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

// Labels exactly as backend/citations.py reports prose-parenthesis citations (live evaluation, defect 1).
describe("prose-parenthesis citations", () => {
  const book = "Data Structures Using Python.pdf";
  const chunks = [chunk(book, 118, "t", 119), chunk(book, 120), chunk("heaps.pdf", 1)];

  it("cleans a parenthesis the way the server labels it", () => {
    expect(cleanParen(`*${book}*, pages 118–120`)).toBe(`${book}, pages 118–120`);
    expect(cleanParen("see **heaps.pdf**,  p. 1")).toBe("heaps.pdf, p. 1");
    expect(cleanParen("_my_notes.pdf_, page 2")).toBe("my_notes.pdf, page 2");
  });

  it("turns a parenthesis citation into a chip in place of the parenthesis", () => {
    const answer = "A binary heap is used to implement a priority queue (heaps.pdf, page 1).";
    const { markdown, refs } = linkCitations(answer, [ok("heaps.pdf, page 1", "heaps.pdf", 1)], chunks);
    expect(markdown).toBe("A binary heap is used to implement a priority queue [0](#cite-0).");
    expect(refs[0]).toMatchObject({ chunk: 2, status: "ok", sentence: "A binary heap is used to implement a priority queue" });
  });

  it("handles emphasis, page ranges and pp.", () => {
    const answer = `Repeat until the queue is empty (*${book}*, pages 118–120). Then stop (_${book}_, pp. 120).`;
    const cites = [ok(`${book}, pages 118–120`, book, 118), ok(`${book}, pp. 120`, book, 120)];
    const { markdown, refs } = linkCitations(answer, cites, chunks);
    expect(markdown).toBe("Repeat until the queue is empty [0](#cite-0). Then stop [1](#cite-1).");
    expect(refs.map((r) => r.chunk)).toEqual([0, 1]);
  });

  it("splits several citations in one parenthesis and keeps parts that are not citations", () => {
    const answer = `Both agree (heaps.pdf, p. 1; ${book}, page 120; see the lecture).`;
    const { markdown, refs } = linkCitations(answer, [ok("heaps.pdf, p. 1", "heaps.pdf", 1), ok(`${book}, page 120`, book, 120)], chunks);
    expect(markdown).toBe("Both agree [0](#cite-0)[1](#cite-1) (see the lecture).");
    expect(refs.map((r) => r.chunk)).toEqual([2, 1]);
  });

  it("leaves ordinary and unreported parentheses alone", () => {
    const answer = "Fast (O(log n)), explained later (see below), unlike (Cormen.pdf, page 3). Code: `f(heaps.pdf, page 1)`.";
    const { markdown, refs } = linkCitations(answer, [ok("heaps.pdf, page 1", "heaps.pdf", 1)], chunks);
    expect(markdown).toBe(answer);
    expect(refs).toHaveLength(0);
  });

  it("numbers bracket and parenthesis citations in reading order", () => {
    const answer = "Queues (heaps.pdf, page 1) and heaps [heaps.pdf (page 1)] differ. Books too (Data Structures Using Python.pdf, page 120).";
    const cites = [ok("heaps.pdf (page 1)", "heaps.pdf", 1), ok("heaps.pdf, page 1", "heaps.pdf", 1), ok(`${book}, page 120`, book, 120)];
    const { markdown } = linkCitations(answer, cites, chunks);
    expect(markdown).toBe("Queues [0](#cite-0) and heaps [1](#cite-1) differ. Books too [2](#cite-2).");
  });
});

// Live evaluation, defect 9: a chip shown as "(01 )" and two chips for the same passage.
describe("chip glitches", () => {
  const chunks = [chunk("heaps.pdf", 1, "t", 2), chunk("graphs.pdf", 3)];

  it("drops the parentheses a model put around a bracket citation", () => {
    const cites = [ok("heaps.pdf (page 1)", "heaps.pdf", 1), ok("graphs.pdf (page 3)", "graphs.pdf", 3)];
    expect(linkCitations("A heap ([heaps.pdf (page 1)]).", cites, chunks).markdown).toBe("A heap [0](#cite-0).");
    expect(linkCitations("A heap (see [heaps.pdf (page 1)]).", cites, chunks).markdown).toBe("A heap [0](#cite-0).");
    expect(linkCitations("Both ([heaps.pdf (page 1)], [graphs.pdf (page 3)]).", cites, chunks).markdown).toBe("Both [0](#cite-0)[1](#cite-1).");
  });

  it("keeps parentheses that hold more than chips", () => {
    const cites = [ok("heaps.pdf (page 1)", "heaps.pdf", 1)];
    expect(linkCitations("A heap (a tree [heaps.pdf (page 1)]).", cites, chunks).markdown).toBe("A heap (a tree [0](#cite-0)).");
  });

  it("shows one chip when one bracket cites the same passage twice", () => {
    const cites = [ok("heaps.pdf (page 1)", "heaps.pdf", 1), ok("heaps.pdf (page 2)", "heaps.pdf", 2)];
    const { markdown, refs } = linkCitations("A heap [heaps.pdf (page 1); heaps.pdf (page 2)].", cites, chunks);
    expect(markdown).toBe("A heap [0](#cite-0).");
    expect(refs).toHaveLength(1);
  });

  it("shows one chip when adjacent citations point to the same passage", () => {
    const cites = [ok("heaps.pdf (page 1)", "heaps.pdf", 1), ok("heaps.pdf, page 2", "heaps.pdf", 2)];
    const { markdown, refs } = linkCitations("A heap [heaps.pdf (page 1)] (heaps.pdf, page 2).", cites, chunks);
    expect(markdown).toBe("A heap [0](#cite-0).");
    expect(refs).toHaveLength(1);
  });

  it("still links the same passage again from a later sentence", () => {
    const cites = [ok("heaps.pdf (page 1)", "heaps.pdf", 1)];
    const { markdown, refs } = linkCitations("A heap [heaps.pdf (page 1)]. Also a tree [heaps.pdf (page 1)].", cites, chunks);
    expect(markdown).toBe("A heap [0](#cite-0). Also a tree [1](#cite-1).");
    expect(refs.map((r) => r.chunk)).toEqual([0, 0]);
  });
});
