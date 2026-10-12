# Retrieval evaluation: synthetic corpus

44 answerable questions and 6 unanswerable ones. A retrieved passage counts as relevant when it comes from the expected document and contains a key phrase of the answer, so the ground truth does not depend on chunk boundaries.

- **hit@k**: share of answerable questions with a relevant passage in the top k.
- **MRR**: mean of 1 / rank of the first relevant passage.
- **cov@5**: share of the expected pieces of evidence found in the top 5 (matters for comparison questions).
- **AUROC**: how well the top retrieval score separates answerable from unanswerable questions (1.0 perfect, 0.5 no better than chance). This is what a "no good match found" threshold would rely on.

## Summary

| config | setup | chunks | hit@1 | hit@3 | hit@5 | MRR | cov@5 | AUROC | ms/query |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **keyword** | hashing-512, chunks v1, keyword | 45 | 82% | 95% | 95% | 0.883 | 94% | 1.00 | 0.6 |
| **hashing-dense** | hashing-512, chunks v1, dense | 45 | 52% | 68% | 80% | 0.627 | 77% | 0.81 | 0.1 |
| **minilm-dense** | all-MiniLM-L6-v2, chunks v1, dense | 45 | 73% | 91% | 98% | 0.829 | 97% | 1.00 | 2.8 |

## hit@3 by question type

| config | ambiguity (n=8) | comparison (n=6) | complexity (n=4) | direct (n=16) | paraphrase (n=10) |
|---|---:|---:|---:|---:|---:|
| **keyword** | 100% | 100% | 100% | 100% | 80% |
| **hashing-dense** | 100% | 83% | 50% | 69% | 40% |
| **minilm-dense** | 100% | 100% | 100% | 94% | 70% |

## Questions with no relevant passage in the top 5

**keyword** (2):
- `s17` [paraphrase] Which data structure lets me look up values in constant time on average? → got python-notes.md (0.4), python-notes.md (0.4), graphs.md (0.3)
- `s24` [paraphrase] How does a networked storage system survive a server dying? → got file-systems.md (0.333), networking.md (0.333), memory.md (0.167)

**hashing-dense** (9):
- `s06` [direct] What are the ACID properties of a transaction? → got trees.md (0.245), trees.md (0.245), trees.md (0.227)
- `s08` [direct] What is a trie used for? → got arrays-lists.md (0.235), hashing.md (0.207), arrays-lists.md (0.191)
- `s15` [direct] How does Timsort work? → got graphs.md (0.085), graphs.md (0.066), trees.md (0.054)
- `s19` [paraphrase] How can I order tasks so that prerequisites always come before the tasks that need them? → got file-systems.md (0.172), trees.md (0.121), complexity.md (0.112)
- `s20` [paraphrase] How can a program crash because functions keep calling themselves too many times? → got arrays-lists.md (0.118), python-notes.md (0.106), networking.md (0.089)
- `s23` [paraphrase] How do website names get converted into numeric machine addresses? → got python-notes.md (0.127), hashing.md (0.112), graphs.md (0.105)
- `s24` [paraphrase] How does a networked storage system survive a server dying? → got python-notes.md (0.139), graphs.md (0.134), trees.md (0.131)
- `s35` [comparison] Compare quicksort and merge sort. → got sorting.md (0.197), complexity.md (0.169), complexity.md (0.144)
- `s41` [complexity] What is the best possible speed of a comparison-based sort? → got arrays-lists.md (0.213), dp-greedy.md (0.207), trees.md (0.204)

**minilm-dense** (1):
- `s17` [paraphrase] Which data structure lets me look up values in constant time on average? → got dp-greedy.md (0.365), databases.md (0.339), dp-greedy.md (0.322)

## Unanswerable questions: top score

| question | keyword | hashing-dense | minilm-dense |
|---|---:|---:|---:|
| What is the capital of France? | 0.00 | 0.18 | 0.09 |
| How do I train a neural network with backpropagation? | 0.25 | 0.16 | 0.12 |
| Explain quantum entanglement. | 0.00 | 0.08 | 0.14 |
| What is a good recipe for sourdough bread? | 0.25 | 0.19 | 0.13 |
| Who won the 2018 football world cup? | 0.00 | 0.14 | 0.07 |
| How do I configure a Kubernetes ingress controller? | 0.00 | 0.16 | 0.05 |
| *median of answerable questions* | 0.75 | 0.22 | 0.53 |
