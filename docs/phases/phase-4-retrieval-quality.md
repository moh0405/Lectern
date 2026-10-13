# Phase 4: Answer quality, measured

## Goal

Stop guessing. Build an evaluation, then improve retrieval and trust, with every change shown as a number.

## What was built

1. **Evaluation harness** (`eval/`): two corpora, labelled questions, hit@k, MRR, coverage, AUROC, paired-bootstrap intervals, committed reports. See [evaluation](../concepts/08-evaluation.md).
2. **BM25** from scratch, and **hybrid retrieval** with reciprocal rank fusion ([search and ranking](../concepts/04-search-and-ranking.md)).
3. **Chunking v2** ([chunking](../concepts/05-chunking.md)).
4. **Citation checker** and the "unverified citation" flags in the API and UI ([LLMs](../concepts/06-llms-and-prompting.md)).
5. **Answer cache** keyed by (question, mode, k, model, temperature, index version).
6. **Optional cross-encoder reranker**.
7. Re-examined **fine-tuning** with the numbers.

## Results (real textbooks, 33 answerable questions)

| | hit@3 | MRR | ms/query |
|---|---:|---:|---:|
| old keyword | 64% | 0.58 | 75 |
| BM25 | 82% | 0.71 | 0.3 |
| dense MiniLM | 82% | 0.78 | 3 |
| **default: hybrid + v2 chunks** | **94%** | 0.78 | 3.5 |
| default + rerank | 94% | 0.86 | 337 |

+12 points at hit@3 (interval +3 to +24) over dense search.

## Method worth copying

- Measure first; change one thing at a time; keep the ablations.
- Report intervals; say what you cannot conclude.
- When the evaluation itself is flawed, fix it **and say so**: page-level relevance replaced phrase-in-chunk labels, a label audit added 11 valid passages. Both are disclosed.
- Negative results are results: v2 chunks alone hurt MRR; hybrid with the hashing embedder is worse than BM25; chunk size does not matter.

## The fine-tuning verdict

No. 2 of 33 questions still miss, and in those the right passage never reaches the model, so no change to the model could help. The one place fine-tuning could apply later is the embedding model, which needs a larger labelled set than exists. Details: `docs/PLAN.md`, Model strategy.

## Bugs found

"page None" citations were flagged as invented (fixed after the phase); a noise filter once deleted a tiny document entirely (now never empties a document); BM25 scores were not comparable across queries until unknown terms counted as maximally rare; an end-to-end test raced the stream.

## Not done, deliberately

A "no good match" threshold (6 unanswerable examples are too few to choose one) and answer-faithfulness scoring (needs a model and a key).
