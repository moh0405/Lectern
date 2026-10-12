# Retrieval evaluation

Measures how well the retriever finds the passage that answers a question, so every change to
chunking, search or ranking shows up as a number instead of a feeling.

```bash
python -m eval.run                          # synthetic corpus, every configuration
python -m eval.run --corpus real            # your three textbooks (needs the PDFs, see below)
python -m eval.run --corpus both --write    # also update eval/reports/*.md
python -m eval.run --configs keyword,minilm-dense
```

`eval/reports/synthetic.md` and `eval/reports/real.md` hold the latest committed results.

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

A retrieved passage is **relevant** if it comes from the expected document *and* contains a key phrase of the
answer. Judging by phrase rather than chunk id keeps the labels valid when chunking changes.

- **hit@k**: share of answerable questions with a relevant passage in the top k.
- **MRR**: mean of 1 / rank of the first relevant passage.
- **cov@5**: share of the expected pieces of evidence found in the top 5 (for comparisons).
- **AUROC**: does the top retrieval score separate answerable from unanswerable questions? 1.0 means a
  threshold would be perfect; 0.5 means no better than chance. This decides whether a "no good match" cut-off is viable.

## Caveats

- **Small samples.** 33 and 44 answerable questions: a one-question change moves hit@k by 2 to 3 points. Treat differences
  under about 5 points as noise. The 6 unanswerable questions make AUROC coarse.
- **One labeller.** Labels were written by the author of this repo (an AI assistant working with the project owner), not
  independently. They are phrase-based and checked against the text by a test, but a human reviewer could disagree.
- **Label audit (disclosed).** After the first real-corpus run I read the passages the best config returned for
  its misses and added **11 alternative evidence passages that genuinely answer the question** (for example, a second book's
  definition of a queue). This was done before any retrieval change and applies to every configuration equally, but it
  was informed by one system's output. Hit@3 on the real corpus before the audit: keyword 36%, hashing 24%, MiniLM 55%.
  After: 45%, 24%, 76%.
- **Retrieval only.** This does not measure whether the model's answer is good or faithful; that needs a model call (and a
  key). Citation checking is handled separately (see `docs/PLAN.md`, Phase 4).
