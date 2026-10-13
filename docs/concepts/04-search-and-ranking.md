# 4. Search and ranking: BM25, hybrid search, fusion, reranking

Retrieval quality decides the quality of every answer ([RAG](01-rag.md)), so this project retrieves in stages.

```
question
   ├─► dense search  (embeddings, by meaning)  ─┐
   │                                            ├─► reciprocal rank fusion ─► top k ─► (optional) rerank
   └─► BM25 search   (words, by rare terms)    ─┘
```

## Dense search (by meaning)

See [embeddings](02-embeddings.md). Good at paraphrase ("look things up quickly" finds "hash table"). Weak at exact tokens such as `O(n log n)`, `Dijkstra`, a function name, or a number.

## BM25 (by words)

BM25 is the classic keyword ranking function behind search engines like Lucene and Elasticsearch. For each query term it asks three things:

1. **How rare is the term?** (IDF). A word in every passage tells you nothing; a word in one passage tells you a lot.
2. **How often does it occur in this passage?** More is better, but with diminishing returns (the `k1` parameter, 1.5 here).
3. **How long is the passage?** A match in a short passage is stronger than in a long one (the `b` parameter, 0.75 here).

Formula for one term in one passage:

```
idf(t) = ln(1 + (N - df + 0.5) / (df + 0.5))
score  = idf(t) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len / avg_len))
```

`N` = number of passages, `df` = how many contain the term, `tf` = occurrences in this passage. A passage's score is the sum over query terms.

### A real worked example

Four tiny documents, query **"hash collisions"** (after stemming: `hash`, `collision`):

| Quantity | Value |
|---|---|
| N (passages) | 4, average length 6.75 tokens |
| `hash` appears in 2 passages | idf = **0.693** |
| `collision` appears in 1 passage | idf = **1.204** (rarer, so worth more) |
| Result | doc 2 scores **0.421**, doc 0 scores **0.197** |
| Inside doc 2 | `collision` contributes 1.267, `hash` 0.730 (before normalization) |

The rare word `collision` outweighs the common word `hash`, exactly as intended.

### Implementation notes (`backend/lexical.py`)

- Written from scratch (~100 lines, no dependency).
- **Tokenizer:** lowercase, split on non-alphanumerics, drop stopwords, then a conservative **stemmer** so `collisions → collision`, `sorting → sort`, `queries → query`, `running → run`, `tables → tabl` and `table → tabl` agree. A stemmer only has to be *consistent* between index and query.
- **Normalized score (0..1):** divided by the highest score a passage could possibly get for this query. Unknown query terms count as maximally rare, so a question where 1 of 5 words matches does not score like one where all 5 match. This makes scores comparable across queries, which matters for the "is anything relevant here?" signal.
- The index is rebuilt when `store.revision` changes.

## Hybrid search and Reciprocal Rank Fusion (RRF)

Dense and BM25 fail on different questions, so use both. The problem: their scores are on different scales (cosine ≈ 0.1..0.7, BM25 unbounded), so you cannot just add them.

**RRF** ignores scores and uses only **ranks**. Each list gives an item `1 / (k + rank)` (k = 60), and the contributions are summed:

```
rankings: A = [1, 2, 3]      B = [3, 1, 9]

item 1: 1/(60+1) + 1/(60+2) = 0.0164 + 0.0161 = 0.0325   ← first in A, second in B
item 3: 1/(60+3) + 1/(60+1) = 0.0159 + 0.0164 = 0.0323
item 2: 1/(60+2)            = 0.0161
item 9: 1/(60+3)            = 0.0159
result: [1, 3, 2, 9]
```

An item that both searches rank well wins; an item only one search found still appears. The constant 60 damps the influence of the very top ranks. No tuning, no score calibration: that is why RRF is the usual first choice.

In this repo each retriever returns its top 50, RRF merges them, and the top k (default 3) go to the model. Each returned passage also carries its **cosine score**, so the UI can show how semantically close it is.

## Retrieval modes

Set server-wide with the `RETRIEVAL_MODE` environment variable (or the engine's `retrieval_mode` argument); it is not a per-request parameter:

| Mode | Meaning |
|---|---|
| `auto` (default) | hybrid when the index has a semantic embedder, otherwise BM25 |
| `hybrid` | dense + BM25 with RRF |
| `dense` | embeddings only |
| `bm25` | words only |
| `keyword` | the original naive word-overlap search (kept as the baseline for evaluation) |

## Reranking (optional)

First-stage retrievers compare the query and each passage **separately** (the passage vector is computed in advance). A **cross-encoder** reads the query and a passage **together** in one forward pass and outputs a relevance score, which is far more accurate but too slow to run over thousands of passages. So the standard recipe is: retrieve ~50 cheaply, rerank those with the cross-encoder, keep the best few.

This repo supports `RERANKER=cross-encoder` (`cross-encoder/ms-marco-MiniLM-L-6-v2`). Measured on the real textbooks:

| | hit@3 | MRR | ms/query |
|---|---:|---:|---:|
| default (hybrid) | 94% | 0.78 | 3.5 |
| default + rerank | 94% | 0.86 | 337 |

Reranking improves where the correct passage lands *within* the top 3 (MRR) but not whether it is *in* the top 3, and costs ~100× the time. It is therefore **off by default**: the right trade-off depends on whether the user cares about the very first result. The feature and the measurement are both kept.

## Measured results (see [evaluation](08-evaluation.md))

| Config | hit@3 | MRR |
|---|---:|---:|
| original keyword overlap | 64% | 0.58 |
| BM25 | 82% | 0.71 |
| dense MiniLM, old chunks | 82% | 0.78 |
| **hybrid + new chunking (default)** | **94%** | 0.78 |

Two honest findings: hybrid with the *hashing* embedder is worse than BM25 alone (hence `auto`), and the new chunking with dense-only search *lowers* MRR by 0.12 (interval -0.23 to -0.02). Each half of the default is worth little alone; they work together.

## Where to look in the code

- `backend/lexical.py`: tokenizer, stemmer, `BM25Index`, `reciprocal_rank_fusion`
- `backend/rag_engine.py`: `retrieve_context`
- `backend/rerank.py`: the optional cross-encoder
- `tests/test_lexical.py`, `tests/test_rag_engine.py`
