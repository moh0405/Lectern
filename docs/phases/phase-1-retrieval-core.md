# Phase 1: Retrieval core

## Goal

Replace the prototype's fragile search (FAISS plus a pickle file, re-parsing PDFs, a crash on macOS) with a small, correct, tested retrieval layer.

## What was built

1. **`VectorStore`** ([vector databases](../concepts/03-vector-databases.md)): `manifest.json` + `chunks.jsonl` + `embeddings.npy`. No pickle. Atomic writes. Content-hash de-duplication. Records which embedder built it and refuses to mix.
2. **Embedders** ([embeddings](../concepts/02-embeddings.md)): `SentenceTransformerEmbedder` (MiniLM, 384-d) and the dependency-free `HashingEmbedder`, both L2-normalized.
3. **Incremental indexer** (`backend/indexer.py`): a file's SHA-256 fingerprint decides whether it is re-processed; each chunk is hashed so identical text is stored once; only new chunks are embedded (batches of 256); removed files are pruned. Re-indexing an unchanged corpus takes about half a second.
4. **One shared engine** created at API startup, instead of rebuilt per request.
5. A keyword fallback that reports a per-result score.

## How it works

See the indexing sequence in [ARCHITECTURE](../ARCHITECTURE.md#3-data-flow-a-indexing). The key invariant: *the index on disk can always be rebuilt from the source files*, so it is treated as a cache, not as precious data.

## Technologies

NumPy (vector maths), sentence-transformers (MiniLM), optional FAISS, JSON Lines, SHA-256 hashing.

## The macOS crash (a real debugging story)

The app segfaulted on macOS. Cause, found by reproducing all four combinations of import order and thread count: **FAISS and PyTorch each ship their own OpenMP runtime**; when both are loaded and a multithreaded call happens, the process aborts. Neither library alone was at fault. The fix was a decision, not a patch: exact NumPy search returns identical results in about a millisecond at this scale, so **FAISS became opt-in** (`VECTOR_BACKEND=faiss`) and is refused automatically if torch is already loaded.

Lesson: when a dependency is risky and the simple alternative is fast enough, choose the simple one and keep the option.

## Decisions and trade-offs

| Decision | Trade-off |
|---|---|
| Own store instead of a hosted vector DB | fewer moving parts; you own the scaling limit (about 100k passages) |
| Exact search by default | always correct; slower than ANN only at much larger sizes |
| Embedder name in manifest | prevents silent garbage from mixed vector spaces |

## Result

Retrieval ran at 4 to 26 ms per query on the real textbooks (about 4,700 passages), with tests for embedders, store round-trips, de-duplication, removal, the indexer (incremental, prune, failure, rebuild), the engine and an upload-index-search-delete API flow.

Found at the end: ambiguous acronyms mislead pure vector search ("BFS vs DFS" returned distributed-file-system passages). That became Phase 4.
