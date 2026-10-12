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
| **hashing-dense** | hashing-512, chunks v1, dense | 45 | 52% | 68% | 80% | 0.627 | 77% | 68% | 0.81 | 0.1 |
| **minilm-dense** | all-MiniLM-L6-v2, chunks v1, dense | 45 | 73% | 91% | 98% | 0.829 | 97% | 91% | 1.00 | 2.8 |
| **keyword-v2** | hashing-512, chunks v2, keyword | 70 | 66% | 82% | 89% | 0.759 | 86% | 82% | 0.99 | 0.6 |
| **hashing-dense-v2** | hashing-512, chunks v2, dense | 70 | 57% | 64% | 70% | 0.627 | 68% | 64% | 0.82 | 0.1 |
| **minilm-dense-v2** | all-MiniLM-L6-v2, chunks v2, dense | 70 | 77% | 91% | 100% | 0.861 | 98% | 91% | 1.00 | 2.7 |

## hit@3 by question type

| config | ambiguity (n=8) | comparison (n=6) | complexity (n=4) | direct (n=16) | paraphrase (n=10) |
|---|---:|---:|---:|---:|---:|
| **keyword** | 100% | 100% | 100% | 100% | 80% |
| **hashing-dense** | 100% | 83% | 50% | 69% | 40% |
| **minilm-dense** | 100% | 100% | 100% | 94% | 70% |
| **keyword-v2** | 100% | 67% | 75% | 94% | 60% |
| **hashing-dense-v2** | 100% | 67% | 50% | 62% | 40% |
| **minilm-dense-v2** | 100% | 100% | 100% | 100% | 60% |

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

**keyword-v2** (5):
- `s08` [direct] What is a trie used for? → got python-notes.md (0.5), memory.md (0.5), sorting.md (0.5)
- `s17` [paraphrase] Which data structure lets me look up values in constant time on average? → got complexity.md (0.3), python-notes.md (0.3), graphs.md (0.3)
- `s20` [paraphrase] How can a program crash because functions keep calling themselves too many times? → got hashing.md (0.2), arrays-lists.md (0.2), memory.md (0.2)
- `s25` [paraphrase] How do I stop my search tree from becoming a long chain? → got hashing.md (0.286), trees.md (0.286), databases.md (0.286)
- `s37` [comparison] When is BFS enough instead of Dijkstra's algorithm? → got graphs.md (0.5), graphs.md (0.333), graphs.md (0.333)

**hashing-dense-v2** (13):
- `s05` [direct] Why is merge sort a stable sort? → got python-notes.md (0.244), sorting.md (0.239), arrays-lists.md (0.226)
- `s06` [direct] What are the ACID properties of a transaction? → got trees.md (0.245), hashing.md (0.228), complexity.md (0.219)
- `s08` [direct] What is a trie used for? → got arrays-lists.md (0.303), sorting.md (0.208), python-notes.md (0.208)
- `s15` [direct] How does Timsort work? → got sorting.md (0.067), graphs.md (0.067), memory.md (0.062)
- `s19` [paraphrase] How can I order tasks so that prerequisites always come before the tasks that need them? → got trees.md (0.144), file-systems.md (0.14), dp-greedy.md (0.138)
- `s20` [paraphrase] How can a program crash because functions keep calling themselves too many times? → got python-notes.md (0.122), memory.md (0.11), python-notes.md (0.102)
- `s21` [paraphrase] Which tree keeps the smallest element instantly accessible? → got trees.md (0.277), arrays-lists.md (0.223), sorting.md (0.204)
- `s23` [paraphrase] How do website names get converted into numeric machine addresses? → got complexity.md (0.124), hashing.md (0.108), file-systems.md (0.104)
- `s24` [paraphrase] How does a networked storage system survive a server dying? → got databases.md (0.176), file-systems.md (0.16), python-notes.md (0.14)
- `s25` [paraphrase] How do I stop my search tree from becoming a long chain? → got hashing.md (0.17), trees.md (0.165), arrays-lists.md (0.145)
- `s35` [comparison] Compare quicksort and merge sort. → got sorting.md (0.232), complexity.md (0.185), python-notes.md (0.183)
- `s37` [comparison] When is BFS enough instead of Dijkstra's algorithm? → got python-notes.md (0.181), graphs.md (0.155), complexity.md (0.148)
- `s41` [complexity] What is the best possible speed of a comparison-based sort? → got dp-greedy.md (0.224), memory.md (0.193), trees.md (0.186)

## Unanswerable questions: top score

| question | keyword | hashing-dense | minilm-dense | keyword-v2 | hashing-dense-v2 | minilm-dense-v2 |
|---|---:|---:|---:|---:|---:|---:|
| What is the capital of France? | 0.00 | 0.18 | 0.09 | 0.00 | 0.20 | 0.12 |
| How do I train a neural network with backpropagation? | 0.25 | 0.16 | 0.12 | 0.25 | 0.14 | 0.19 |
| Explain quantum entanglement. | 0.00 | 0.08 | 0.14 | 0.00 | 0.07 | 0.21 |
| What is a good recipe for sourdough bread? | 0.25 | 0.19 | 0.13 | 0.25 | 0.22 | 0.16 |
| Who won the 2018 football world cup? | 0.00 | 0.14 | 0.07 | 0.00 | 0.14 | 0.06 |
| How do I configure a Kubernetes ingress controller? | 0.00 | 0.16 | 0.05 | 0.00 | 0.16 | 0.05 |
| *median of answerable questions* | 0.75 | 0.22 | 0.53 | 0.67 | 0.25 | 0.63 |
