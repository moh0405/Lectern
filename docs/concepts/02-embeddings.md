# 2. Embeddings

## What problem do they solve?

Computers compare text badly. "How do I look things up quickly by key?" and "A hash table maps keys to values in O(1)" share almost no words, yet they are about the same thing. Keyword search would score them near zero.

An **embedding** turns a piece of text into a list of numbers (a **vector**) so that *texts with similar meaning get similar vectors*. Once meaning is a position in space, "similar meaning" becomes "close together", which a computer can calculate very fast.

## What is a vector here?

The model used by default, **`all-MiniLM-L6-v2`** (sentence-transformers), maps any text to **384 numbers**. These are the first six numbers for the sentence *"A hash table maps keys to values for fast lookup"* (real output):

```
[ 0.045,  0.056, -0.085, -0.069, -0.072,  0.003, ... 378 more ]
```

No single number means anything you could name ("dimension 2 = animals"). Meaning is spread across all 384; only the **geometry** (distances and angles between vectors) is meaningful.

You can picture it in 2D: every sentence is a dot, and dots about similar topics cluster. The **Embedding map** page in the app does this for real, projecting the 384 dimensions down to 3 with PCA so you can rotate your own documents in 3D (`backend/projection.py`).

## How similarity is measured

The standard measure is **cosine similarity**: the cosine of the angle between two vectors.

- same direction → 1.0 (same meaning)
- unrelated → around 0
- opposite → negative (rare for sentence embeddings)

This repo **normalizes** every vector to length 1. For unit vectors, cosine similarity is just the **dot product** (multiply matching numbers, add them up), so searching is one matrix multiplication:

```python
scores = embeddings @ query_vector      # one number per stored passage
top = np.argsort(-scores)[:k]
```

Real numbers from MiniLM:

| Pair | Cosine | Reading |
|---|---:|---|
| "hash table maps keys to values" vs "dictionaries store key-value pairs" | **0.61** (angle ≈ 52°) | same topic, different words |
| ... vs "The capital of France is Paris" | **-0.03** | unrelated |
| ... vs "A linked list stores nodes with pointers" | 0.26 | related field, different topic |

And for a *question* against four passages, "How do I look things up quickly by key?" gave **0.39, 0.36, 0.06, 0.14**: the two hash-related passages score high with almost no shared vocabulary. That is the point of embeddings.

Scores like 0.39 look low, but cosine values for sentence embeddings rarely get near 1 unless the texts are near-duplicates. What matters is the **ranking**, not the absolute number (although this project does use the top cosine as a weak "is this relevant?" signal, see [evaluation](08-evaluation.md) AUROC).

## Where do embedding models come from?

A neural network (a small Transformer, 6 layers for MiniLM-L6, ~22 million parameters) was trained on over a billion sentence pairs with a **contrastive** objective: pull the vectors of pairs that belong together closer, push random pairs apart. After training, the network is frozen; we only run it forward ("inference") to get vectors. Running it for 5,000 passages on a laptop CPU takes well under a minute.

Important properties:

- **Same model for documents and questions.** Vectors from different models live in different spaces and cannot be compared. The store's manifest records the embedder's name and dimension and refuses to mix them.
- **Long inputs are truncated.** MiniLM reads about 256 word-pieces, which is why passages are kept to about 900 characters ([chunking](05-chunking.md)).
- **Embeddings are not understanding.** They are good at topical similarity and weaker at negation ("is not stable"), exact identifiers, numbers and rare acronyms. That weakness is exactly why this project adds BM25 ([search and ranking](04-search-and-ranking.md)).

## The fallback: HashingEmbedder

`backend/embeddings.py` also contains `HashingEmbedder`, which needs no download or model:

1. split into words (and word pairs),
2. hash each word to one of 512 slots (`hash(word) mod 512`),
3. count, then normalize.

It is *not semantic*: two texts that share no words get cosine **0.0**. It exists so the app, the tests and CI work with zero downloads, and so evaluation can show how much a real model adds. Measured: with this embedder hybrid search is *worse* than BM25 alone, so the retrieval mode `auto` only uses hybrid when the embedder is semantic.

## Design choices in this repo

| Choice | Why |
|---|---|
| 384-dim MiniLM | small (≈90 MB), fast on CPU, good quality for English study text |
| L2-normalize everything | cosine = dot product; makes exact search trivial |
| float32 | half the memory of float64, no quality loss that matters |
| Embed in batches of 256 | speed |
| Re-embed only new chunks (content hash) | a re-index of an unchanged corpus takes ~0.5 s |
| Store the embedder name in the manifest | stops mixing incompatible vectors |

## Should the embedding model be fine-tuned?

Considered and decided **no** for now (with evidence): the retrieval misses were mostly about chunk boundaries and exact terms, which chunking and BM25 fixed (hit@3 went from 82% to 94%). Fine-tuning needs labelled question-passage pairs and risks overfitting to the 33-question evaluation set. See [Phase 4](../phases/phase-4-retrieval-quality.md).

## Where to look in the code

- `backend/embeddings.py`: `SentenceTransformerEmbedder`, `HashingEmbedder`, `get_embedder`, `get_embedder_by_name`
- `backend/vector_store.py`: where vectors are stored and searched
- `backend/projection.py`: PCA down to 3 dimensions for the map
