# 3. Vector databases and vector search

## What a vector database is

A **vector database** stores vectors next to their original data and answers one question quickly: *"which stored vectors are closest to this query vector?"* This is **nearest-neighbour search**.

Everything else a database offers (updates, deletes, filters by metadata, persistence) is there to make that usable in a real application.

## Exact vs approximate search

| | Exact ("brute force") | Approximate (ANN) |
|---|---|---|
| How | compare the query with **every** vector | build a structure that visits only a small part |
| Result | always the true top-k | usually the true top-k (e.g. 95-99%) |
| Cost | grows linearly with the number of vectors | grows much slower |
| Examples | NumPy matrix multiply | FAISS IVF / HNSW, Pinecone, Qdrant, pgvector, Chroma |

Approximate indexes exist because brute force stops being fast at millions of vectors. Common structures:

- **IVF** (inverted file): cluster the vectors; at query time search only the few nearest clusters.
- **HNSW**: a layered graph where each vector links to near neighbours; you "walk" the graph toward the query.
- **PQ** (product quantization): compress vectors so more fit in memory.

## What this project does, and why

This project has **its own small vector store** (`backend/vector_store.py`) instead of a hosted vector database. It is a deliberate choice for a portfolio project at this scale (about 5,000 passages from three textbooks), and also a way to show what a vector database actually *is*.

On disk (`data/vector_store/`):

```
manifest.json     which embedder (name, dimension), store version, one record per source file
                  (SHA-256 fingerprint, chunker version, chunk count)
chunks.jsonl      one JSON line per passage: text, doc, page, end_page, content hash, source key
embeddings.npy    a float32 matrix, shape (number_of_chunks, 384); row i belongs to line i of chunks.jsonl
index.faiss       only if VECTOR_BACKEND=faiss
```

Search (the exact path, the default):

```python
scores = embeddings @ query          # (N, 384) @ (384,) -> (N,)  all cosine similarities at once
top_k  = np.argsort(-scores)[:k]            # indices of the k best
```

For ~5,000 vectors this takes about a millisecond. The measured retrieval time per query is ≈3.5 ms for the whole hybrid pipeline, most of which is embedding the question.

### Why not pickle, SQLite or a server?

| Option | Rejected because |
|---|---|
| pickle | loading a pickle can execute code; an untrusted index file would be a security hole |
| SQLite blobs | possible, but then you cannot just open the chunks in an editor or diff them |
| Hosted vector DB | another service to run, pay for and secure, for a corpus that fits in memory |

The three-file layout is readable (open `chunks.jsonl` in any editor), safe to load, and entirely rebuildable from the source documents.

### Operations the store supports

| Operation | Notes |
|---|---|
| `add` | appends chunks and vectors; **de-duplicates by content hash** |
| `remove_source` | removes every chunk of a file (used when a file changes or is deleted) |
| `search` | exact (NumPy) or FAISS |
| `save` / `load` | atomic: write a temp file, then rename, so a crash cannot corrupt the index |
| `revision` | a counter that increases on every change; the BM25 index and the answer cache use it to know when they are stale |
| manifest check | refuses to load vectors made by a different embedder |

## FAISS (optional)

FAISS is Meta's library for fast vector search. It is supported with `VECTOR_BACKEND=faiss`, using an inner-product index (equivalent to cosine for normalized vectors).

It is **not** the default because of a real problem found in Phase 1: on macOS, FAISS and PyTorch each bundle their own OpenMP runtime, and when both are loaded in one process it aborts (`OMP: Error #15`). Since the exact search is already about a millisecond here, the default favours robustness. The code refuses FAISS when torch is already loaded rather than crashing.

## When you would switch to a real vector database

- more than roughly 100,000 passages (brute force starts to be felt),
- many users writing at once (this store is single-process),
- you need filtering on metadata combined with similarity at scale,
- you need replication and backups as a service.

Then you would keep the same chunk records and replace the `VectorStore` class; the rest of the app calls only `add`, `search` and `remove_source`.

## Metadata and filters

Each vector carries metadata (`doc`, `page`, `end_page`, source key). Here the metadata is used to show citations and to remove a document's chunks. Production vector databases also let you filter ("only chunks from `dsa.pdf`") during search; adding that here would be a mask over the score vector.

## Where to look in the code

- `backend/vector_store.py`: the store
- `backend/indexer.py`: building and updating it incrementally
- `tests/test_vector_store.py`: behaviour, including persistence and refusal to mix embedders
