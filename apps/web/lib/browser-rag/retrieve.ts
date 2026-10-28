/** Find the passages of the visitor's own documents that best match a question. */

import { embedTexts } from "./embed";
import { Bm25, hybridSearch } from "./search";
import { listDocs, vectorAt, type StoredDoc } from "./store";

export interface LocalPassage {
  text: string;
  doc: string;
  page: number;
  end_page?: number;
  score: number;
}

type Embedder = (texts: string[]) => Promise<Float32Array[] | null>;

export async function retrieveLocal(question: string, k: number, opts: { docs?: StoredDoc[]; embed?: Embedder } = {}): Promise<LocalPassage[]> {
  const docs = opts.docs ?? (await listDocs());
  const flat = docs.flatMap((d) => d.passages.map((p, i) => ({ p, doc: d, vec: vectorAt(d, i) })));
  if (flat.length === 0) return [];
  // Meaning search only when every passage has a vector (mixed sets fall back to keywords rather than guess).
  const allVectors = flat.every((f) => f.vec);
  const queryVector = allVectors ? ((await (opts.embed ?? embedTexts)([question]))?.[0] ?? null) : null;
  const hits = hybridSearch({
    query: question,
    bm25: new Bm25(flat.map((f) => f.p.text)),
    vectors: queryVector ? flat.map((f) => f.vec!) : null,
    queryVector,
    k,
  });
  return hits.map(({ index, score }) => {
    const { p, doc } = flat[index]!;
    return { text: p.text, doc: doc.name, page: p.page, ...(p.end_page ? { end_page: p.end_page } : {}), score: Number(score.toFixed(4)) };
  });
}
