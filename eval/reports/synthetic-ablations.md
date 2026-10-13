# Retrieval evaluation: synthetic corpus

44 answerable questions and 6 unanswerable ones. A retrieved passage counts as relevant when it comes from the expected document and contains a key phrase of the answer, so the ground truth does not depend on chunk boundaries.

- **hit@k**: share of answerable questions with a relevant passage in the top k.
- **MRR**: mean of 1 / rank of the first relevant passage.
- **cov@5**: share of the expected pieces of evidence found in the top 5 (matters for comparison questions).
- **AUROC**: how well the top retrieval score separates answerable from unanswerable questions (1.0 perfect, 0.5 no better than chance). This is what a "no good match found" threshold would rely on.

## Summary

| config | setup | chunks | hit@1 | hit@3 | hit@5 | MRR | cov@5 | strict hit@3 | AUROC | ms/query |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **minilm-dense** | all-MiniLM-L6-v2, chunks v1, dense | 45 | 73% | 91% | 98% | 0.829 | 97% | 91% | 1.00 | 2.7 |
| **hashing-dense** | hashing-512, chunks v1, dense | 45 | 52% | 68% | 80% | 0.627 | 77% | 68% | 0.81 | 0.1 |
| **hybrid-hashing** | hashing-512, chunks v1, hybrid | 45 | 68% | 89% | 89% | 0.781 | 86% | 89% | 0.78 | 0.1 |
| **hybrid-hashing-v2** | hashing-512, chunks v2, hybrid | 70 | 70% | 82% | 84% | 0.769 | 82% | 82% | 0.81 | 0.1 |
| **bm25-v2** | hashing-512, chunks v2, bm25 | 70 | 84% | 95% | 98% | 0.903 | 98% | 95% | 1.00 | 0.0 |
| **hybrid-minilm-v2** | all-MiniLM-L6-v2, chunks v2, hybrid | 70 | 93% | 98% | 100% | 0.956 | 99% | 98% | 1.00 | 2.7 |
| **hybrid-minilm-v2-perpage** | all-MiniLM-L6-v2, chunks v2-perpage, hybrid | 70 | 93% | 98% | 100% | 0.956 | 99% | 98% | 1.00 | 2.7 |
| **hybrid-minilm-rerank** | all-MiniLM-L6-v2, chunks v1, hybrid, rerank | 45 | 91% | 100% | 100% | 0.955 | 100% | 100% | 1.00 | 232.5 |
| **hybrid-minilm-v2-rerank** | all-MiniLM-L6-v2, chunks v2, hybrid, rerank | 70 | 91% | 98% | 98% | 0.943 | 98% | 98% | 1.00 | 136.8 |
| **keyword-v2** | hashing-512, chunks v2, keyword | 70 | 66% | 82% | 89% | 0.759 | 86% | 82% | 0.99 | 0.6 |
| **hashing-dense-v2** | hashing-512, chunks v2, dense | 70 | 57% | 64% | 70% | 0.627 | 68% | 64% | 0.82 | 0.1 |
| **minilm-dense-v2** | all-MiniLM-L6-v2, chunks v2, dense | 70 | 77% | 91% | 100% | 0.861 | 98% | 91% | 1.00 | 2.7 |
| **minilm-dense-v2-perpage** | all-MiniLM-L6-v2, chunks v2-perpage, dense | 70 | 77% | 91% | 100% | 0.861 | 98% | 91% | 1.00 | 2.7 |
| **keyword-v2-600** | hashing-512, chunks v2-600, keyword | 70 | 66% | 82% | 89% | 0.759 | 86% | 82% | 0.99 | 0.6 |
| **minilm-dense-v2-600** | all-MiniLM-L6-v2, chunks v2-600, dense | 70 | 77% | 91% | 100% | 0.861 | 98% | 91% | 1.00 | 2.7 |
| **keyword-v2-400** | hashing-512, chunks v2-400, keyword | 84 | 66% | 82% | 84% | 0.746 | 82% | 82% | 0.99 | 0.6 |
| **minilm-dense-v2-400** | all-MiniLM-L6-v2, chunks v2-400, dense | 84 | 70% | 89% | 95% | 0.811 | 93% | 89% | 1.00 | 2.7 |

## Change versus `minilm-dense` (paired bootstrap over questions, 95% interval)

An interval that contains 0 means the data do not show a real difference.

| config | Δ hit@3 | 95% interval | P(better) | Δ MRR | 95% interval |
|---|---:|---:|---:|---:|---:|
| **hashing-dense** | -23 pts | [-36, -9] | 0.00 | -0.202 | [-0.328, -0.067] |
| **hybrid-hashing** | -2 pts | [-16, +11] | 0.30 | -0.048 | [-0.164, +0.068] |
| **hybrid-hashing-v2** | -9 pts | [-25, +7] | 0.09 | -0.060 | [-0.191, +0.069] |
| **bm25-v2** | +5 pts | [-5, +14] | 0.77 | +0.074 | [-0.009, +0.161] |
| **hybrid-minilm-v2** | +7 pts | [-2, +16] | 0.88 | +0.127 | [+0.047, +0.218] |
| **hybrid-minilm-v2-perpage** | +7 pts | [-2, +16] | 0.88 | +0.127 | [+0.047, +0.218] |
| **hybrid-minilm-rerank** | +9 pts | [+2, +18] | 0.98 | +0.126 | [+0.038, +0.220] |
| **hybrid-minilm-v2-rerank** | +7 pts | [-2, +16] | 0.88 | +0.114 | [+0.025, +0.210] |
| **keyword-v2** | -9 pts | [-23, +5] | 0.07 | -0.070 | [-0.185, +0.040] |
| **hashing-dense-v2** | -27 pts | [-43, -11] | 0.00 | -0.202 | [-0.348, -0.058] |
| **minilm-dense-v2** | +0 pts | [-11, +11] | 0.42 | +0.032 | [-0.035, +0.105] |
| **minilm-dense-v2-perpage** | +0 pts | [-11, +11] | 0.42 | +0.032 | [-0.035, +0.105] |
| **keyword-v2-600** | -9 pts | [-23, +5] | 0.07 | -0.070 | [-0.185, +0.040] |
| **minilm-dense-v2-600** | +0 pts | [-11, +11] | 0.42 | +0.032 | [-0.035, +0.105] |
| **keyword-v2-400** | -9 pts | [-23, +2] | 0.05 | -0.083 | [-0.195, +0.026] |
| **minilm-dense-v2-400** | -2 pts | [-14, +9] | 0.28 | -0.018 | [-0.102, +0.070] |

## hit@3 by question type

| config | ambiguity (n=8) | comparison (n=6) | complexity (n=4) | direct (n=16) | paraphrase (n=10) |
|---|---:|---:|---:|---:|---:|
| **minilm-dense** | 100% | 100% | 100% | 94% | 70% |
| **hashing-dense** | 100% | 83% | 50% | 69% | 40% |
| **hybrid-hashing** | 100% | 100% | 75% | 94% | 70% |
| **hybrid-hashing-v2** | 100% | 83% | 75% | 88% | 60% |
| **bm25-v2** | 100% | 100% | 100% | 100% | 80% |
| **hybrid-minilm-v2** | 100% | 100% | 100% | 100% | 90% |
| **hybrid-minilm-v2-perpage** | 100% | 100% | 100% | 100% | 90% |
| **hybrid-minilm-rerank** | 100% | 100% | 100% | 100% | 100% |
| **hybrid-minilm-v2-rerank** | 100% | 100% | 100% | 100% | 90% |
| **keyword-v2** | 100% | 67% | 75% | 94% | 60% |
| **hashing-dense-v2** | 100% | 67% | 50% | 62% | 40% |
| **minilm-dense-v2** | 100% | 100% | 100% | 100% | 60% |
| **minilm-dense-v2-perpage** | 100% | 100% | 100% | 100% | 60% |
| **keyword-v2-600** | 100% | 67% | 75% | 94% | 60% |
| **minilm-dense-v2-600** | 100% | 100% | 100% | 100% | 60% |
| **keyword-v2-400** | 100% | 67% | 75% | 94% | 60% |
| **minilm-dense-v2-400** | 88% | 100% | 100% | 100% | 60% |

## Questions with no relevant passage in the top 5

**minilm-dense** (1):
- `s17` [paraphrase] Which data structure lets me look up values in constant time on average? → got dp-greedy.md (0.365), databases.md (0.339), dp-greedy.md (0.322)

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

**hybrid-hashing** (5):
- `s08` [direct] What is a trie used for? → got arrays-lists.md (0.235), arrays-lists.md (0.191), python-notes.md (0.173)
- `s20` [paraphrase] How can a program crash because functions keep calling themselves too many times? → got python-notes.md (0.106), python-notes.md (0.087), memory.md (0.076)
- `s23` [paraphrase] How do website names get converted into numeric machine addresses? → got memory.md (0.074), file-systems.md (0.091), hashing.md (0.112)
- `s24` [paraphrase] How does a networked storage system survive a server dying? → got file-systems.md (0.117), graphs.md (0.134), databases.md (0.112)
- `s41` [complexity] What is the best possible speed of a comparison-based sort? → got dp-greedy.md (0.207), python-notes.md (0.173), sorting.md (0.145)

**hybrid-hashing-v2** (7):
- `s05` [direct] Why is merge sort a stable sort? → got sorting.md (0.213), sorting.md (0.222), complexity.md (0.225)
- `s08` [direct] What is a trie used for? → got arrays-lists.md (0.303), sorting.md (0.208), python-notes.md (0.196)
- `s20` [paraphrase] How can a program crash because functions keep calling themselves too many times? → got python-notes.md (0.102), python-notes.md (0.099), hashing.md (0.096)
- `s23` [paraphrase] How do website names get converted into numeric machine addresses? → got hashing.md (0.073), arrays-lists.md (0.054), file-systems.md (0.026)
- `s24` [paraphrase] How does a networked storage system survive a server dying? → got file-systems.md (0.16), networking.md (0.126), databases.md (0.176)
- `s37` [comparison] When is BFS enough instead of Dijkstra's algorithm? → got graphs.md (0.155), dp-greedy.md (0.143), graphs.md (0.082)
- `s41` [complexity] What is the best possible speed of a comparison-based sort? → got dp-greedy.md (0.224), sorting.md (0.162), dp-greedy.md (0.149)

**bm25-v2** (1):
- `s25` [paraphrase] How do I stop my search tree from becoming a long chain? → got trees.md (0.182), hashing.md (0.093), hashing.md (0.088)

**hybrid-minilm-v2-rerank** (1):
- `s25` [paraphrase] How do I stop my search tree from becoming a long chain? → got trees.md (0.412), arrays-lists.md (0.211), databases.md (0.351)

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

**keyword-v2-600** (5):
- `s08` [direct] What is a trie used for? → got python-notes.md (0.5), memory.md (0.5), sorting.md (0.5)
- `s17` [paraphrase] Which data structure lets me look up values in constant time on average? → got complexity.md (0.3), python-notes.md (0.3), graphs.md (0.3)
- `s20` [paraphrase] How can a program crash because functions keep calling themselves too many times? → got hashing.md (0.2), arrays-lists.md (0.2), memory.md (0.2)
- `s25` [paraphrase] How do I stop my search tree from becoming a long chain? → got hashing.md (0.286), trees.md (0.286), databases.md (0.286)
- `s37` [comparison] When is BFS enough instead of Dijkstra's algorithm? → got graphs.md (0.5), graphs.md (0.333), graphs.md (0.333)

**keyword-v2-400** (7):
- `s08` [direct] What is a trie used for? → got complexity.md (0.5), memory.md (0.5), python-notes.md (0.5)
- `s17` [paraphrase] Which data structure lets me look up values in constant time on average? → got complexity.md (0.3), python-notes.md (0.3), sorting.md (0.2)
- `s19` [paraphrase] How can I order tasks so that prerequisites always come before the tasks that need them? → got hashing.md (0.286), trees.md (0.143), networking.md (0.143)
- `s20` [paraphrase] How can a program crash because functions keep calling themselves too many times? → got memory.md (0.2), hashing.md (0.2), arrays-lists.md (0.2)
- `s25` [paraphrase] How do I stop my search tree from becoming a long chain? → got trees.md (0.286), trees.md (0.286), hashing.md (0.286)
- `s37` [comparison] When is BFS enough instead of Dijkstra's algorithm? → got graphs.md (0.5), graphs.md (0.333), graphs.md (0.333)
- `s41` [complexity] What is the best possible speed of a comparison-based sort? → got sorting.md (0.333), complexity.md (0.167), sorting.md (0.167)

**minilm-dense-v2-400** (2):
- `s21` [paraphrase] Which tree keeps the smallest element instantly accessible? → got trees.md (0.527), trees.md (0.514), trees.md (0.51)
- `s25` [paraphrase] How do I stop my search tree from becoming a long chain? → got trees.md (0.415), databases.md (0.377), trees.md (0.365)

## Unanswerable questions: top score

| question | minilm-dense | hashing-dense | hybrid-hashing | hybrid-hashing-v2 | bm25-v2 | hybrid-minilm-v2 | hybrid-minilm-v2-perpage | hybrid-minilm-rerank | hybrid-minilm-v2-rerank | keyword-v2 | hashing-dense-v2 | minilm-dense-v2 | minilm-dense-v2-perpage | keyword-v2-600 | minilm-dense-v2-600 | keyword-v2-400 | minilm-dense-v2-400 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| What is the capital of France? | 0.09 | 0.18 | 0.18 | 0.20 | 0.00 | 0.12 | 0.12 | -0.04 | 0.05 | 0.00 | 0.20 | 0.12 | 0.12 | 0.00 | 0.12 | 0.00 | 0.12 |
| How do I train a neural network with backpropagation? | 0.12 | 0.16 | 0.13 | 0.14 | 0.09 | 0.19 | 0.19 | 0.05 | -0.02 | 0.25 | 0.14 | 0.19 | 0.19 | 0.25 | 0.19 | 0.25 | 0.19 |
| Explain quantum entanglement. | 0.14 | 0.08 | -0.02 | -0.03 | 0.09 | 0.05 | 0.05 | 0.11 | 0.10 | 0.00 | 0.07 | 0.21 | 0.21 | 0.00 | 0.21 | 0.00 | 0.21 |
| What is a good recipe for sourdough bread? | 0.13 | 0.19 | 0.18 | 0.20 | 0.09 | 0.16 | 0.16 | -0.01 | -0.04 | 0.25 | 0.22 | 0.16 | 0.16 | 0.25 | 0.16 | 0.25 | 0.16 |
| Who won the 2018 football world cup? | 0.07 | 0.14 | 0.14 | 0.14 | 0.00 | 0.06 | 0.06 | -0.04 | -0.01 | 0.00 | 0.14 | 0.06 | 0.06 | 0.00 | 0.06 | 0.00 | 0.06 |
| How do I configure a Kubernetes ingress controller? | 0.05 | 0.16 | 0.16 | 0.16 | 0.00 | 0.05 | 0.05 | -0.11 | 0.01 | 0.00 | 0.16 | 0.05 | 0.05 | 0.00 | 0.05 | 0.00 | 0.05 |
| *median of answerable questions* | 0.53 | 0.22 | 0.22 | 0.25 | 0.40 | 0.61 | 0.61 | 0.52 | 0.61 | 0.67 | 0.25 | 0.63 | 0.63 | 0.67 | 0.63 | 0.67 | 0.64 |
