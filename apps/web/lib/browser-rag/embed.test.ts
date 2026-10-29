import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const pipeline = vi.fn();
vi.mock("@huggingface/transformers", () => ({ pipeline: (...a: unknown[]) => pipeline(...a), env: {} }));

beforeEach(() => {
  vi.resetModules();
  pipeline.mockReset();
  vi.stubEnv("NEXT_PUBLIC_BROWSER_EMBEDDINGS", "on");
});
afterEach(() => vi.unstubAllEnvs());

describe("loadEmbedder", () => {
  it("gives up when the model download stalls, instead of waiting forever", async () => {
    pipeline.mockReturnValue(new Promise(() => {})); // never settles
    const { loadEmbedder } = await import("./embed");
    expect(await loadEmbedder(undefined, 30)).toBeNull();
  });

  it("tries again later after a failure or timeout", async () => {
    const { loadEmbedder } = await import("./embed");
    pipeline.mockReturnValueOnce(new Promise(() => {}));
    expect(await loadEmbedder(undefined, 20)).toBeNull();
    const extractor = vi.fn();
    pipeline.mockResolvedValueOnce(extractor);
    expect(await loadEmbedder(undefined, 1000)).toBe(extractor);
  });

  it("is off when disabled by configuration", async () => {
    vi.stubEnv("NEXT_PUBLIC_BROWSER_EMBEDDINGS", "off");
    const { loadEmbedder } = await import("./embed");
    expect(await loadEmbedder()).toBeNull();
    expect(pipeline).not.toHaveBeenCalled();
  });
});

describe("embedTexts", () => {
  it("returns unit vectors per text and reports progress", async () => {
    const { EMBEDDING_DIM, embedTexts } = await import("./embed");
    pipeline.mockResolvedValue(async (texts: string[]) => ({ data: new Float32Array(texts.length * EMBEDDING_DIM).fill(0.05) }));
    const progress = vi.fn();
    const out = await embedTexts(["a", "b", "c"], progress, 2);
    expect(out).toHaveLength(3);
    expect(out![0]).toHaveLength(EMBEDDING_DIM);
    expect(progress).toHaveBeenLastCalledWith(3, 3);
  });

  it("returns null (keyword fallback) when a batch stalls", async () => {
    const { embedTexts } = await import("./embed");
    pipeline.mockResolvedValue(() => new Promise(() => {}));
    expect(await embedTexts(["a"], undefined, 16, 30)).toBeNull();
  });
});
