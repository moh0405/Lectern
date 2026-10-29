/**
 * Meaning search in the browser: the same MiniLM model the server uses, run with transformers.js (WebAssembly).
 * The first use downloads the model (about 25 MB, cached by the browser afterwards). If it cannot load, callers
 * fall back to keyword search; nothing breaks.
 */

export const EMBEDDING_MODEL = "Xenova/all-MiniLM-L6-v2";
export const EMBEDDING_DIM = 384;

type Extractor = (texts: string[], opts: { pooling: "mean"; normalize: true }) => Promise<{ data: Float32Array }>;

/** How long to wait for the model download, and for each batch of embeddings, before giving up on meaning search. */
export const MODEL_LOAD_TIMEOUT_MS = 90_000;
export const BATCH_TIMEOUT_MS = 60_000;

let loading: Promise<Extractor | null> | null = null;

/** Resolve with `fallback` if `work` has not settled in `ms` (a stalled download must not leave a spinner forever). */
function withTimeout<T>(work: Promise<T>, ms: number, fallback: T): Promise<T> {
  let timer: ReturnType<typeof setTimeout>;
  const timeout = new Promise<T>((resolve) => {
    timer = setTimeout(() => resolve(fallback), ms);
  });
  return Promise.race([work, timeout]).finally(() => clearTimeout(timer));
}

export const embeddingsEnabled = () => process.env.NEXT_PUBLIC_BROWSER_EMBEDDINGS !== "off";

export function loadEmbedder(onStatus?: (s: string) => void, timeoutMs = MODEL_LOAD_TIMEOUT_MS): Promise<Extractor | null> {
  if (!embeddingsEnabled()) return Promise.resolve(null);
  const attempt = (async (): Promise<Extractor | null> => {
    try {
      const { pipeline, env } = await import("@huggingface/transformers");
      env.allowLocalModels = false;
      onStatus?.("Downloading the search model (about 25 MB, once)");
      const extractor = await pipeline("feature-extraction", EMBEDDING_MODEL, { dtype: "q8" });
      return extractor as unknown as Extractor;
    } catch {
      return null;
    }
  })();
  // A timeout or failure is not remembered, so the next document gets another try.
  loading ??= withTimeout(attempt, timeoutMs, null).then((e) => {
    if (!e) loading = null;
    return e;
  });
  return loading;
}

/** Unit vectors for each text, or null when the model is unavailable. */
export async function embedTexts(texts: string[], onProgress?: (done: number, total: number) => void, batch = 16, batchTimeoutMs = BATCH_TIMEOUT_MS): Promise<Float32Array[] | null> {
  const extractor = await loadEmbedder();
  if (!extractor) return null;
  const out: Float32Array[] = [];
  try {
    for (let i = 0; i < texts.length; i += batch) {
      const part = texts.slice(i, i + batch);
      const res = await withTimeout(extractor(part, { pooling: "mean", normalize: true }), batchTimeoutMs, null);
      if (!res) return null;
      for (let j = 0; j < part.length; j++) out.push(res.data.slice(j * EMBEDDING_DIM, (j + 1) * EMBEDDING_DIM));
      onProgress?.(Math.min(i + batch, texts.length), texts.length);
      await new Promise((r) => setTimeout(r)); // let the page paint between batches
    }
  } catch {
    return null;
  }
  return out;
}
