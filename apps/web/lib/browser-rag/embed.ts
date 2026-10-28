/**
 * Meaning search in the browser: the same MiniLM model the server uses, run with transformers.js (WebAssembly).
 * The first use downloads the model (about 25 MB, cached by the browser afterwards). If it cannot load, callers
 * fall back to keyword search; nothing breaks.
 */

export const EMBEDDING_MODEL = "Xenova/all-MiniLM-L6-v2";
export const EMBEDDING_DIM = 384;

type Extractor = (texts: string[], opts: { pooling: "mean"; normalize: true }) => Promise<{ data: Float32Array }>;

let loading: Promise<Extractor | null> | null = null;

export const embeddingsEnabled = () => process.env.NEXT_PUBLIC_BROWSER_EMBEDDINGS !== "off";

export function loadEmbedder(onStatus?: (s: string) => void): Promise<Extractor | null> {
  if (!embeddingsEnabled()) return Promise.resolve(null);
  loading ??= (async () => {
    try {
      const { pipeline, env } = await import("@huggingface/transformers");
      env.allowLocalModels = false;
      onStatus?.("Downloading the search model (about 25 MB, once)");
      const extractor = await pipeline("feature-extraction", EMBEDDING_MODEL, { dtype: "q8" });
      return extractor as unknown as Extractor;
    } catch {
      loading = null; // allow a retry later
      return null;
    }
  })();
  return loading;
}

/** Unit vectors for each text, or null when the model is unavailable. */
export async function embedTexts(texts: string[], onProgress?: (done: number, total: number) => void, batch = 16): Promise<Float32Array[] | null> {
  const extractor = await loadEmbedder();
  if (!extractor) return null;
  const out: Float32Array[] = [];
  try {
    for (let i = 0; i < texts.length; i += batch) {
      const part = texts.slice(i, i + batch);
      const res = await extractor(part, { pooling: "mean", normalize: true });
      for (let j = 0; j < part.length; j++) out.push(res.data.slice(j * EMBEDDING_DIM, (j + 1) * EMBEDDING_DIM));
      onProgress?.(Math.min(i + batch, texts.length), texts.length);
      await new Promise((r) => setTimeout(r)); // let the page paint between batches
    }
  } catch {
    return null;
  }
  return out;
}
