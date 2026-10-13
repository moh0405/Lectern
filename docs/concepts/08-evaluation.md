# 8. Evaluating retrieval

"It feels better" is not engineering. `eval/` turns retrieval quality into numbers so every change (chunking, BM25, hybrid, reranking) is judged by evidence. The full report is in [`eval/README.md`](../../eval/README.md); this page teaches the ideas.

## What is measured

Only **retrieval**: given a question, did the top results contain a passage that answers it? Generation quality needs a model call and a judge, and is not measured here.

A test set is a list of questions with the *expected evidence* (document, key phrases, and for PDFs the pages where the answer appears). A retrieved passage is **relevant** if it comes from the expected document and either contains a key phrase (strict) or comes from a page where the answer appears (page-level; used as primary for PDFs because it matches how the product cites sources and does not depend on where chunk boundaries fall).

## Metrics

| Metric | Question it answers | Example |
|---|---|---|
| **hit@k** | Is a relevant passage in the top k? | hit@3 = 94% → for 94% of questions the answer is in the 3 passages sent to the model |
| **MRR** (mean reciprocal rank) | How high is the first relevant passage? | 1/rank, averaged: rank 1 → 1.0, rank 2 → 0.5, rank 4 → 0.25 |
| **evidence coverage** | For questions needing several facts, how many were found? | found 2 of 3 pieces → 0.67 |
| **AUROC** | Can the top retrieval score tell answerable from unanswerable questions? | 1.0 = a threshold would be perfect, 0.5 = chance |
| **latency** | milliseconds per query | 3.5 ms hybrid, 337 ms with reranker |

hit@k matters most because the model only sees the top k. MRR matters when you show a ranked list.

## Two test corpora

| | Synthetic | Real |
|---|---|---|
| Documents | 12 short Markdown notes written for this repo (committed) | 3 CS textbooks (not redistributed) |
| Passages | ~45 | ~4,700 |
| Questions | 50 (44 answerable, 6 unanswerable) | 39 (33 answerable, 6 unanswerable) |
| Purpose | regression test that runs in CI | the realistic test |

The synthetic set is **not a benchmark**: its questions share words with the passages, so keyword methods look good. The real set has the failures users hit: near-duplicate text and ambiguity ("DFS" means depth-first search and distributed file system in the same book).

Question types: direct, paraphrase, ambiguity, comparison, unanswerable.

## Why confidence intervals

With 33 questions, one question flips hit@k by about 3 points. So every comparison reports a **paired bootstrap 95% interval**: resample the questions with replacement thousands of times and see how much the *difference* between two configurations varies. If the interval contains 0, the data do not show a difference. Example: default vs dense MiniLM at hit@3 is **+12 points, interval +3 to +24**, the only comparison whose interval excluded zero.

## Results (real textbooks)

| Config | hit@3 | MRR | ms/query |
|---|---:|---:|---:|
| old keyword overlap | 64% | 0.58 | 75 |
| BM25 | 82% | 0.71 | 0.3 |
| dense MiniLM (old chunks) | 82% | 0.78 | 3 |
| **default: hybrid + new chunking** | **94%** | 0.78 | 3.5 |
| default + cross-encoder rerank | 94% | 0.86 | 337 |

What the experiments taught (all in `eval/reports/`):

- BM25 replaced the original scorer: +18 points and about 250× faster.
- Hybrid + new chunking are worth little alone and a lot together.
- Hybrid with a non-semantic embedder is worse than BM25; hence `auto` mode.
- Reranking fixes ordering, not recall, and is ~100× slower, so it is opt-in.
- Chunk size is not the lever.

## Honesty about the evaluation itself

The report discloses weaknesses rather than hiding them:

- **Small sample** (intervals show it).
- **Tuned on what it measures**: the real questions were also used to debug, so the final numbers are optimistic; a fresh, larger set would be fairer.
- **One labeller** (the repo author, with an AI assistant).
- **A label audit**: after the first run, 11 additional valid evidence passages were added for questions where the system found a genuinely correct answer in another book. It applies to every configuration equally but was informed by one system's output; the before/after numbers are published.
- **The metric changed** from phrase-in-chunk to page-level after seeing that phrase labels depended on chunk boundaries. Both are reported (hit@3 and strict hit@3).

## How to run

```bash
python -m eval.run                                   # synthetic, headline configs
python -m eval.run --corpus real                     # needs the PDFs in data/uploaded_files/
python -m eval.run --configs ablations --corpus both --write
```

## Where to look

`eval/harness.py` (builds stores per configuration), `eval/metrics.py` (pure metric functions), `eval/report.py` (tables and bootstrap), `tests/test_eval.py`.
