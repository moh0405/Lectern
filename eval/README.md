# Retrieval evaluation

Measures how well the retriever finds the passage that answers a question, so every change to
chunking, search or ranking shows up as a number instead of a feeling.

```bash
python -m eval.run                          # headline configurations on the synthetic corpus
python -m eval.run --corpus real            # your three textbooks (needs the PDFs, see below)
python -m eval.run --corpus both --write    # also update eval/reports/<corpus>.md
python -m eval.run --configs ablations --corpus both --write   # the experiments behind the decisions
python -m eval.run --configs keyword,bm25   # specific configurations
```

Reports (committed): `reports/synthetic.md`, `reports/real.md` (headline) and `reports/*-ablations.md`.

## What it found (real textbooks, 33 answerable questions)

| | hit@3 | strict hit@3 | MRR | ms/query |
|---|---:|---:|---:|---:|
| old keyword scorer | 64% | 45% | 0.58 | 75 |
| **BM25** (replaces it) | 82% | 73% | 0.71 | **0.3** |
| dense MiniLM, v1 chunks (the Phase 1 baseline) | 82% | 76% | 0.78 | 3 |
| **default: hybrid + v2 chunks** | **94%** | **88%** | 0.78 | 3.5 |
| default + cross-encoder reranker (opt-in) | 94% | 88% | 0.86 | 337 |

- **Hybrid + v2 chunks is +12 points at hit@3 (95% interval +3 to +24)**, the only change whose interval excludes zero. MRR is unchanged and hit@1 is slightly lower (67% vs 70%, within noise).
- **BM25 beats the old scorer by 18 points and is about 250 times faster.** With no neural model at all it is as good as dense MiniLM on the old chunks (hit@3 85% vs 82%, not significantly different).
- **Each half of the default is worth little alone:** v2 chunks with dense-only search lowers MRR (-0.12, interval -0.23 to -0.02); hybrid on the old chunks is +3 (not significant). They work together.
- **Hybrid is only used with a semantic index.** Fusing in the non-semantic hashing embedder is worse than BM25 alone (synthetic hit@3 89% vs 98%), so the app's `auto` mode picks BM25 there.
- **The reranker helps top-1 (67% to 79%) but not top-3,** at about 100 times the latency. The answer prompt receives the top 3 passages, so it is off by default (`RERANKER=cross-encoder` enables it).
- **Chunk size is not the lever:** v2 at 400, 600 and 900 characters all give similar hit@3 (85% dense); attributing chunks to every page they span changes nothing; joining text across page breaks costs about 10 points of hit@1 on its own.
- **Still failing (2 of 33):** a paraphrase of dynamic programming, and "which structure removes the element that was added *last*?" which retrieves *queue* passages, since first and last are close in embedding space. These are retrieval-side problems.
- **Unanswerable questions score low** (top cosine at most 0.25 against a median of 0.66 for answerable ones; AUROC 1.00), so a "no good match" cut-off looks viable, but 6 questions are too few to pick a threshold from.

## Corpora

| | What | Questions |
|---|---|---|
| **synthetic** | 12 short Markdown notes written for this repo (algorithms, memory, file systems, databases, networking, Python). Committed, so anyone can run it, and CI uses it. 45 passages. | 50 (44 answerable, 6 not) |
| **real** | The three textbooks the project was developed with: *Data Structures Using Python*, *Dsa*, *Introduction to Computer Science*. About 4,700 passages. They are not redistributed: place them in `data/uploaded_files/` to run this corpus. | 39 (33 answerable, 6 not) |

The synthetic corpus is a regression test, not a benchmark: its questions share words with their
passages, so lexical search does well on it (it beat the neural embedder at first). The **real corpus
is the one that matters**, because it has the failures users actually hit: huge amounts of near-duplicate
text, and words that mean different things in the same book ("DFS" is both *depth-first search* and
*distributed file system* in *Introduction to Computer Science*).

Question types: **direct** (the answer's own words), **paraphrase** (little word overlap),
**ambiguity** (a word or acronym with several senses), **comparison / complexity**, and
**unanswerable** (the material says nothing; the system should show low confidence).

## Metrics

A retrieved passage is **relevant** if it comes from the expected document and
- (synthetic corpus) contains a key phrase of the answer, or
- (real corpus, paged PDFs) comes from a page where the answer appears (a chunk that runs onto the next page counts for both pages). This is how the product cites sources, and it does not depend on where chunk boundaries fall.

The stricter requirement that the key phrase is *inside* the chunk is reported as **strict hit@3**. Phrase-only
labels turned out to depend on chunking (a valid neighbouring chunk was marked wrong), which is why page-level is primary
for PDFs: the evaluation was changed for that reason after seeing v2 chunking's results, and both numbers are shown so
neither hides anything.

- **hit@k**: share of answerable questions with a relevant passage in the top k.
- **MRR**: mean of 1 / rank of the first relevant passage.
- **cov@5**: share of the expected pieces of evidence found in the top 5 (for comparisons).
- **AUROC**: does the top retrieval score separate answerable from unanswerable questions? 1.0 means a
  threshold would be perfect; 0.5 means no better than chance. This decides whether a "no good match" cut-off is viable.

## Caveats

- **Small samples.** 33 and 44 answerable questions: a one-question change moves hit@k by 2 to 3 points. The reports
  therefore show a paired-bootstrap 95% interval for every change; if it contains 0, the data do not show a difference.
  The 6 unanswerable questions make AUROC coarse.
- **Tuned on what it measures.** The real questions were also used to debug (the label audit below, the page-level
  metric). A fresh, larger question set would be a fairer test of the final defaults.
- **One labeller.** Labels were written by the author of this repo (an AI assistant working with the project owner), not
  independently. They are phrase-based and checked against the text by a test, but a human reviewer could disagree.
- **Label audit (disclosed).** After the first real-corpus run I read the passages the best config returned for
  its misses and added **11 alternative evidence passages that genuinely answer the question** (for example, a second book's
  definition of a queue). This was done before any retrieval change and applies to every configuration equally, but it
  was informed by one system's output. Hit@3 on the real corpus before the audit: keyword 36%, hashing 24%, MiniLM 55%.
  After: 45%, 24%, 76%.
- **Retrieval only.** This does not measure whether the model's answer is good or faithful; that needs a model call (and a
  key). The app checks each citation in an answer against the retrieved passages (`backend/citations.py`), which catches
  invented sources but not a wrong claim attributed to a real one.
