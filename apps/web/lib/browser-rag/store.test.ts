import "fake-indexeddb/auto";
import { beforeEach, describe, expect, it } from "vitest";
import { chunkPages } from "./chunk";
import { retrieveLocal } from "./retrieve";
import { deleteDoc, listDocs, newDocId, saveDoc, vectorAt, type StoredDoc } from "./store";

const doc = (name: string, text: string, vectors: Float32Array | null = null, dim = 2): StoredDoc => {
  const passages = chunkPages([text]);
  return { id: newDocId(), name, addedAt: Date.now(), pages: 1, passages, vectors, dim };
};

beforeEach(async () => {
  for (const d of await listDocs()) await deleteDoc(d.id);
});

describe("browser document store", () => {
  it("saves, lists newest first, and deletes", async () => {
    const a = { ...doc("a.pdf", "Alpha text about heaps."), addedAt: 1 };
    const b = { ...doc("b.pdf", "Beta text about graphs."), addedAt: 2 };
    await saveDoc(a);
    await saveDoc(b);
    expect((await listDocs()).map((d) => d.name)).toEqual(["b.pdf", "a.pdf"]);
    await deleteDoc(b.id);
    expect((await listDocs()).map((d) => d.name)).toEqual(["a.pdf"]);
  });

  it("round-trips vectors", async () => {
    const d = doc("v.pdf", "One sentence only.", new Float32Array([0.6, 0.8]));
    await saveDoc(d);
    const [back] = await listDocs();
    expect(Array.from(vectorAt(back!, 0)!)).toEqual([expect.closeTo(0.6), expect.closeTo(0.8)]);
  });
});

describe("retrieveLocal", () => {
  it("returns nothing without documents", async () => {
    expect(await retrieveLocal("anything", 3, { docs: [] })).toEqual([]);
  });

  it("finds the right document and page by keywords when there are no vectors", async () => {
    const docs = [doc("notes.pdf", "Dijkstra finds shortest paths with a priority queue."), doc("other.pdf", "Quicksort partitions around a pivot.")];
    const hits = await retrieveLocal("how does dijkstra find shortest paths", 2, { docs });
    expect(hits[0]).toMatchObject({ doc: "notes.pdf", page: 1, score: 1 });
  });

  it("uses meaning search when every passage has a vector and the question can be embedded", async () => {
    const docs = [doc("a.pdf", "Unrelated words here.", new Float32Array([1, 0])), doc("b.pdf", "Different words there.", new Float32Array([0, 1]))];
    const hits = await retrieveLocal("zzz", 1, { docs, embed: async () => [new Float32Array([0, 1])] });
    expect(hits[0]).toMatchObject({ doc: "b.pdf" });
  });

  it("falls back to keywords when the embedder is unavailable", async () => {
    const docs = [doc("a.pdf", "Hash tables use buckets.", new Float32Array([1, 0]))];
    const hits = await retrieveLocal("hash buckets", 1, { docs, embed: async () => null });
    expect(hits[0]).toMatchObject({ doc: "a.pdf" });
  });
});
