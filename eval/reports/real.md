# Retrieval evaluation: real corpus

39 answerable questions and 7 unanswerable ones. A retrieved passage counts as relevant when it comes from the expected document and contains a key phrase of the answer, so the ground truth does not depend on chunk boundaries.

- **hit@k**: share of answerable questions with a relevant passage in the top k.
- **MRR**: mean of 1 / rank of the first relevant passage.
- **cov@5**: share of the expected pieces of evidence found in the top 5 (matters for comparison questions).
- **AUROC**: how well the top retrieval score separates answerable from unanswerable questions (1.0 perfect, 0.5 no better than chance). This is what a "no good match found" threshold would rely on.

## Summary

| config | setup | chunks | hit@1 | hit@3 | hit@5 | MRR | cov@5 | strict hit@3 | AUROC | ms/query |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **keyword** | hashing-512, chunks v1, keyword | 4714 | 41% | 69% | 79% | 0.586 | 65% | 44% | 0.98 | 84.9 |
| **bm25** | hashing-512, chunks v1, bm25 | 4714 | 54% | 82% | 92% | 0.698 | 74% | 72% | 1.00 | 0.4 |
| **minilm-dense** | all-MiniLM-L6-v2, chunks v1, dense | 4714 | 74% | 85% | 92% | 0.814 | 79% | 69% | 1.00 | 3.1 |
| **hybrid-minilm** | all-MiniLM-L6-v2, chunks v1, hybrid | 4714 | 74% | 90% | 95% | 0.825 | 79% | 74% | 1.00 | 3.5 |
| **default-minilm-noexpand** | all-MiniLM-L6-v2, chunks v2, auto, no expansion | 3866 | 67% | 95% | 95% | 0.795 | 76% | 85% | 1.00 | 3.3 |
| **default-minilm** | all-MiniLM-L6-v2, chunks v2, auto | 3866 | 72% | 95% | 95% | 0.821 | 80% | 90% | 1.00 | 3.4 |
| **default-minilm-rerank** | all-MiniLM-L6-v2, chunks v2, auto, rerank | 3866 | 79% | 95% | 95% | 0.868 | 83% | 87% | 1.00 | 337.9 |
| **default-hashing** | hashing-512, chunks v2, auto | 3866 | 49% | 87% | 95% | 0.690 | 81% | 82% | 1.00 | 0.4 |

## Change versus `minilm-dense` (paired bootstrap over questions, 95% interval)

An interval that contains 0 means the data do not show a real difference.

| config | Δ hit@3 | 95% interval | P(better) | Δ MRR | 95% interval |
|---|---:|---:|---:|---:|---:|
| **keyword** | -15 pts | [-31, +0] | 0.01 | -0.228 | [-0.348, -0.111] |
| **bm25** | -3 pts | [-18, +13] | 0.31 | -0.116 | [-0.245, +0.019] |
| **hybrid-minilm** | +5 pts | [+0, +13] | 0.88 | +0.011 | [-0.056, +0.081] |
| **default-minilm-noexpand** | +10 pts | [+3, +21] | 0.99 | -0.019 | [-0.100, +0.064] |
| **default-minilm** | +10 pts | [+3, +21] | 0.99 | +0.006 | [-0.068, +0.079] |
| **default-minilm-rerank** | +10 pts | [+3, +21] | 0.99 | +0.053 | [-0.051, +0.162] |
| **default-hashing** | +3 pts | [-10, +15] | 0.57 | -0.124 | [-0.256, +0.013] |

## hit@3 by question type

| config | ambiguity (n=7) | direct (n=27) | paraphrase (n=5) |
|---|---:|---:|---:|
| **keyword** | 71% | 70% | 60% |
| **bm25** | 86% | 85% | 60% |
| **minilm-dense** | 86% | 89% | 60% |
| **hybrid-minilm** | 100% | 93% | 60% |
| **default-minilm-noexpand** | 100% | 100% | 60% |
| **default-minilm** | 100% | 100% | 60% |
| **default-minilm-rerank** | 100% | 100% | 60% |
| **default-hashing** | 86% | 93% | 60% |

## Questions with no relevant passage in the top 5

**keyword** (8):
- `r02` [direct] What is a hash collision? → got Introduction to Computer Science.pdf (1.0), Introduction to Computer Science.pdf (1.0), Introduction to Computer Science.pdf (1.0)
- `r16` [direct] What is a singly linked list? → got Dsa.pdf (1.0), Dsa.pdf (1.0), Dsa.pdf (1.0)
- `r19` [direct] What is a tree rotation in an AVL tree? → got Data Structures Using Python.pdf (1.0), Dsa.pdf (1.0), Data Structures Using Python.pdf (1.0)
- `r20` [direct] How does insertion sort work and how fast is it? → got Data Structures Using Python.pdf (0.75), Dsa.pdf (0.5), Dsa.pdf (0.5)
- `r25` [direct] What is a B-tree? → got Data Structures Using Python.pdf (1.0), Dsa.pdf (1.0), Data Structures Using Python.pdf (1.0)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.8), Data Structures Using Python.pdf (0.6), Data Structures Using Python.pdf (0.6)
- `r33` [ambiguity] What is a heap? → got Dsa.pdf (1.0), Dsa.pdf (1.0), Dsa.pdf (1.0)
- `r40` [ambiguity] Difference between BFS and DFS? → got Introduction to Computer Science.pdf (0.5), Introduction to Computer Science.pdf (0.5), Introduction to Computer Science.pdf (0.5)

**bm25** (3):
- `r19` [direct] What is a tree rotation in an AVL tree? → got Data Structures Using Python.pdf (0.723), Data Structures Using Python.pdf (0.701), Data Structures Using Python.pdf (0.688)
- `r29` [paraphrase] Which graph search visits every neighbour at one distance before going further out? → got Introduction to Computer Science.pdf (0.22), Data Structures Using Python.pdf (0.211), Data Structures Using Python.pdf (0.198)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.587), Introduction to Computer Science.pdf (0.448), Introduction to Computer Science.pdf (0.42)

**minilm-dense** (3):
- `r25` [direct] What is a B-tree? → got Data Structures Using Python.pdf (0.549), Data Structures Using Python.pdf (0.533), Data Structures Using Python.pdf (0.527)
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.548), Introduction to Computer Science.pdf (0.548), Introduction to Computer Science.pdf (0.514)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.512), Dsa.pdf (0.464), Dsa.pdf (0.443)

**hybrid-minilm** (2):
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.548), Introduction to Computer Science.pdf (0.496), Introduction to Computer Science.pdf (0.548)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.512), Data Structures Using Python.pdf (0.393), Introduction to Computer Science.pdf (0.398)

**default-minilm-noexpand** (2):
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.534), Introduction to Computer Science.pdf (0.526), Introduction to Computer Science.pdf (0.434)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.556), Data Structures Using Python.pdf (0.386), Data Structures Using Python.pdf (0.472)

**default-minilm** (2):
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.534), Introduction to Computer Science.pdf (0.526), Introduction to Computer Science.pdf (0.434)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.556), Data Structures Using Python.pdf (0.386), Data Structures Using Python.pdf (0.472)

**default-minilm-rerank** (2):
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.534), Introduction to Computer Science.pdf (0.411), Introduction to Computer Science.pdf (0.526)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.386), Data Structures Using Python.pdf (0.556), Introduction to Computer Science.pdf (0.313)

**default-hashing** (2):
- `r29` [paraphrase] Which graph search visits every neighbour at one distance before going further out? → got Introduction to Computer Science.pdf (0.234), Introduction to Computer Science.pdf (0.206), Data Structures Using Python.pdf (0.199)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.613), Introduction to Computer Science.pdf (0.466), Introduction to Computer Science.pdf (0.462)

## Unanswerable questions: top score

| question | keyword | bm25 | minilm-dense | hybrid-minilm | default-minilm-noexpand | default-minilm | default-minilm-rerank | default-hashing |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| What is the capital of Australia? | 0.50 | 0.22 | 0.19 | 0.19 | 0.10 | 0.10 | 0.02 | 0.23 |
| Who won the 2018 football world cup? | 0.40 | 0.12 | 0.22 | 0.09 | 0.11 | 0.11 | 0.11 | 0.11 |
| What is a good recipe for sourdough bread? | 0.25 | 0.21 | 0.33 | 0.28 | 0.25 | 0.25 | 0.25 | 0.21 |
| What is the boiling point of water in Fahrenheit? | 0.25 | 0.15 | 0.33 | 0.27 | 0.25 | 0.25 | 0.25 | 0.15 |
| Summarize the plot of the play Hamlet. | 0.25 | 0.17 | 0.24 | 0.18 | 0.14 | 0.14 | 0.19 | 0.15 |
| How many moons does Jupiter have? | 0.50 | 0.17 | 0.25 | 0.18 | 0.01 | 0.01 | 0.09 | 0.18 |
| How does open addressing resolve collisions with linear probing? | 0.33 | 0.18 | 0.41 | 0.36 | 0.36 | 0.36 | 0.18 | 0.21 |
| *median of answerable questions* | 1.00 | 0.62 | 0.67 | 0.64 | 0.65 | 0.66 | 0.63 | 0.64 |
