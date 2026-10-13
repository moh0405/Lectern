# Retrieval evaluation: synthetic corpus

44 answerable questions and 6 unanswerable ones. A retrieved passage counts as relevant when it comes from the expected document and contains a key phrase of the answer, so the ground truth does not depend on chunk boundaries.

- **hit@k**: share of answerable questions with a relevant passage in the top k.
- **MRR**: mean of 1 / rank of the first relevant passage.
- **cov@5**: share of the expected pieces of evidence found in the top 5 (matters for comparison questions).
- **AUROC**: how well the top retrieval score separates answerable from unanswerable questions (1.0 perfect, 0.5 no better than chance). This is what a "no good match found" threshold would rely on.

## Summary

| config | setup | chunks | hit@1 | hit@3 | hit@5 | MRR | cov@5 | strict hit@3 | AUROC | ms/query |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **keyword** | hashing-512, chunks v1, keyword | 45 | 82% | 95% | 95% | 0.883 | 94% | 95% | 1.00 | 0.6 |
| **bm25** | hashing-512, chunks v1, bm25 | 45 | 91% | 98% | 98% | 0.939 | 97% | 98% | 1.00 | 0.1 |
| **minilm-dense** | all-MiniLM-L6-v2, chunks v1, dense | 45 | 73% | 91% | 98% | 0.829 | 97% | 91% | 1.00 | 2.8 |
| **hybrid-minilm** | all-MiniLM-L6-v2, chunks v1, hybrid | 45 | 91% | 98% | 100% | 0.948 | 99% | 98% | 1.00 | 2.8 |
| **default-minilm** | all-MiniLM-L6-v2, chunks v2, auto | 70 | 93% | 98% | 100% | 0.956 | 99% | 98% | 1.00 | 2.8 |
| **default-minilm-rerank** | all-MiniLM-L6-v2, chunks v2, auto, rerank | 70 | 91% | 98% | 98% | 0.943 | 98% | 98% | 1.00 | 143.2 |
| **default-hashing** | hashing-512, chunks v2, auto | 70 | 84% | 95% | 98% | 0.903 | 98% | 95% | 1.00 | 0.0 |

## Change versus `minilm-dense` (paired bootstrap over questions, 95% interval)

An interval that contains 0 means the data do not show a real difference.

| config | Δ hit@3 | 95% interval | P(better) | Δ MRR | 95% interval |
|---|---:|---:|---:|---:|---:|
| **keyword** | +5 pts | [-5, +14] | 0.78 | +0.054 | [-0.034, +0.141] |
| **bm25** | +7 pts | [+0, +16] | 0.96 | +0.110 | [+0.030, +0.197] |
| **hybrid-minilm** | +7 pts | [+0, +16] | 0.96 | +0.119 | [+0.058, +0.186] |
| **default-minilm** | +7 pts | [-2, +16] | 0.88 | +0.127 | [+0.047, +0.218] |
| **default-minilm-rerank** | +7 pts | [-2, +16] | 0.88 | +0.114 | [+0.025, +0.210] |
| **default-hashing** | +5 pts | [-5, +14] | 0.77 | +0.074 | [-0.009, +0.161] |

## hit@3 by question type

| config | ambiguity (n=8) | comparison (n=6) | complexity (n=4) | direct (n=16) | paraphrase (n=10) |
|---|---:|---:|---:|---:|---:|
| **keyword** | 100% | 100% | 100% | 100% | 80% |
| **bm25** | 100% | 100% | 100% | 100% | 90% |
| **minilm-dense** | 100% | 100% | 100% | 94% | 70% |
| **hybrid-minilm** | 100% | 100% | 100% | 100% | 90% |
| **default-minilm** | 100% | 100% | 100% | 100% | 90% |
| **default-minilm-rerank** | 100% | 100% | 100% | 100% | 90% |
| **default-hashing** | 100% | 100% | 100% | 100% | 80% |

## Questions with no relevant passage in the top 5

**keyword** (2):
- `s17` [paraphrase] Which data structure lets me look up values in constant time on average? → got python-notes.md (0.4), python-notes.md (0.4), graphs.md (0.3)
- `s24` [paraphrase] How does a networked storage system survive a server dying? → got file-systems.md (0.333), networking.md (0.333), memory.md (0.167)

**bm25** (1):
- `s17` [paraphrase] Which data structure lets me look up values in constant time on average? → got complexity.md (0.164), python-notes.md (0.154), graphs.md (0.13)

**minilm-dense** (1):
- `s17` [paraphrase] Which data structure lets me look up values in constant time on average? → got dp-greedy.md (0.365), databases.md (0.339), dp-greedy.md (0.322)

**default-minilm-rerank** (1):
- `s25` [paraphrase] How do I stop my search tree from becoming a long chain? → got trees.md (0.412), arrays-lists.md (0.211), databases.md (0.351)

**default-hashing** (1):
- `s25` [paraphrase] How do I stop my search tree from becoming a long chain? → got trees.md (0.182), hashing.md (0.093), hashing.md (0.088)

## Unanswerable questions: top score

| question | keyword | bm25 | minilm-dense | hybrid-minilm | default-minilm | default-minilm-rerank | default-hashing |
|---|---:|---:|---:|---:|---:|---:|---:|
| What is the capital of France? | 0.00 | 0.00 | 0.09 | 0.09 | 0.12 | 0.05 | 0.00 |
| How do I train a neural network with backpropagation? | 0.25 | 0.11 | 0.12 | 0.09 | 0.19 | -0.02 | 0.09 |
| Explain quantum entanglement. | 0.00 | 0.09 | 0.14 | 0.10 | 0.05 | 0.10 | 0.09 |
| What is a good recipe for sourdough bread? | 0.25 | 0.07 | 0.13 | 0.07 | 0.16 | -0.04 | 0.09 |
| Who won the 2018 football world cup? | 0.00 | 0.00 | 0.07 | 0.07 | 0.06 | -0.01 | 0.00 |
| How do I configure a Kubernetes ingress controller? | 0.00 | 0.00 | 0.05 | 0.05 | 0.05 | 0.01 | 0.00 |
| *median of answerable questions* | 0.75 | 0.45 | 0.53 | 0.52 | 0.61 | 0.61 | 0.40 |
