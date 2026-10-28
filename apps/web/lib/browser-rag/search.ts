/** Retrieval over passages held in the browser: BM25 (exact words) + cosine (meaning), merged by rank fusion. */

const STOP = new Set(
  "a an and are as at be but by for from has have how i in is it its of on or that the this to was were what when where which who why will with you your do does did can could should would not no".split(" "),
);

export function tokenize(text: string): string[] {
  return (text.toLowerCase().match(/[a-z0-9]+/g) ?? [])
    .filter((t) => !STOP.has(t))
    .map((t) => (t.length > 3 && t.endsWith("s") && !t.endsWith("ss") ? t.slice(0, -1) : t)); // crude plural strip
}

export class Bm25 {
  private tf: Map<string, number>[];
  private len: number[];
  private df = new Map<string, number>();
  private avg: number;

  constructor(docs: string[], private k1 = 1.5, private b = 0.75) {
    const tokens = docs.map(tokenize);
    this.len = tokens.map((t) => t.length);
    this.avg = this.len.reduce((a, c) => a + c, 0) / Math.max(1, docs.length);
    this.tf = tokens.map((t) => {
      const m = new Map<string, number>();
      for (const w of t) m.set(w, (m.get(w) ?? 0) + 1);
      for (const w of m.keys()) this.df.set(w, (this.df.get(w) ?? 0) + 1);
      return m;
    });
  }

  scores(query: string): number[] {
    const n = this.tf.length;
    const q = [...new Set(tokenize(query))];
    return this.tf.map((m, i) => {
      let s = 0;
      for (const w of q) {
        const f = m.get(w);
        if (!f) continue;
        const idf = Math.log(1 + (n - (this.df.get(w) ?? 0) + 0.5) / ((this.df.get(w) ?? 0) + 0.5));
        s += (idf * f * (this.k1 + 1)) / (f + this.k1 * (1 - this.b + (this.b * this.len[i]!) / (this.avg || 1)));
      }
      return s;
    });
  }
}

export function cosine(a: ArrayLike<number>, b: ArrayLike<number>): number {
  let s = 0;
  for (let i = 0; i < a.length; i++) s += a[i]! * b[i]!; // vectors are unit length, so the dot product is the cosine
  return s;
}

const topIndices = (scores: number[], n: number) =>
  scores
    .map((s, i) => [s, i] as const)
    .filter(([s]) => s > 0)
    .sort((x, y) => y[0] - x[0] || x[1] - y[1])
    .slice(0, n)
    .map(([, i]) => i);

export interface Hit {
  index: number;
  /** Cosine similarity when meaning search ran, else BM25 scaled to 0..1 by the best match. */
  score: number;
}

/** Reciprocal rank fusion of the keyword and meaning rankings (60 is the usual constant). */
export function hybridSearch(opts: { query: string; bm25: Bm25; vectors?: ArrayLike<number>[] | null; queryVector?: ArrayLike<number> | null; k: number }): Hit[] {
  const lex = opts.bm25.scores(opts.query);
  const sem = opts.vectors && opts.queryVector ? opts.vectors.map((v) => cosine(v, opts.queryVector!)) : null;
  const fused = new Map<number, number>();
  const add = (ranking: number[]) => ranking.forEach((idx, rank) => fused.set(idx, (fused.get(idx) ?? 0) + 1 / (60 + rank + 1)));
  add(topIndices(lex, 50));
  if (sem) add(topIndices(sem, 50));
  const best = Math.max(...lex, 1e-9);
  return [...fused.entries()]
    .sort((a, b) => b[1] - a[1] || a[0] - b[0])
    .slice(0, opts.k)
    .map(([index]) => ({ index, score: sem ? Math.max(0, sem[index]!) : lex[index]! / best }));
}
