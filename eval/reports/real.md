# Retrieval evaluation: real corpus

33 answerable questions and 6 unanswerable ones. A retrieved passage counts as relevant when it comes from the expected document and contains a key phrase of the answer, so the ground truth does not depend on chunk boundaries.

- **hit@k**: share of answerable questions with a relevant passage in the top k.
- **MRR**: mean of 1 / rank of the first relevant passage.
- **cov@5**: share of the expected pieces of evidence found in the top 5 (matters for comparison questions).
- **AUROC**: how well the top retrieval score separates answerable from unanswerable questions (1.0 perfect, 0.5 no better than chance). This is what a "no good match found" threshold would rely on.

## Summary

| config | setup | chunks | hit@1 | hit@3 | hit@5 | MRR | cov@5 | strict hit@3 | AUROC | ms/query |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **keyword** | hashing-512, chunks v1, keyword | 4715 | 42% | 64% | 82% | 0.584 | 69% | 45% | 0.98 | 74.9 |
| **bm25** | hashing-512, chunks v1, bm25 | 4715 | 58% | 82% | 94% | 0.714 | 74% | 73% | 0.99 | 0.3 |
| **minilm-dense** | all-MiniLM-L6-v2, chunks v1, dense | 4715 | 70% | 82% | 91% | 0.780 | 78% | 76% | 1.00 | 3.1 |
| **hybrid-minilm** | all-MiniLM-L6-v2, chunks v1, hybrid | 4715 | 73% | 85% | 91% | 0.800 | 78% | 82% | 1.00 | 3.6 |
| **default-minilm** | all-MiniLM-L6-v2, chunks v2, auto | 3867 | 67% | 94% | 94% | 0.783 | 78% | 88% | 1.00 | 3.5 |
| **default-minilm-rerank** | all-MiniLM-L6-v2, chunks v2, auto, rerank | 3867 | 79% | 94% | 94% | 0.859 | 84% | 88% | 1.00 | 336.6 |
| **default-hashing** | hashing-512, chunks v2, auto | 3867 | 48% | 85% | 94% | 0.679 | 74% | 76% | 1.00 | 0.3 |

## Change versus `minilm-dense` (paired bootstrap over questions, 95% interval)

An interval that contains 0 means the data do not show a real difference.

| config | Δ hit@3 | 95% interval | P(better) | Δ MRR | 95% interval |
|---|---:|---:|---:|---:|---:|
| **keyword** | -18 pts | [-36, +0] | 0.01 | -0.197 | [-0.327, -0.069] |
| **bm25** | +0 pts | [-15, +18] | 0.43 | -0.066 | [-0.207, +0.079] |
| **hybrid-minilm** | +3 pts | [-6, +12] | 0.61 | +0.020 | [-0.057, +0.102] |
| **default-minilm** | +12 pts | [+3, +24] | 0.99 | +0.003 | [-0.083, +0.093] |
| **default-minilm-rerank** | +12 pts | [+3, +24] | 0.99 | +0.078 | [-0.035, +0.194] |
| **default-hashing** | +3 pts | [-12, +18] | 0.57 | -0.101 | [-0.247, +0.053] |

## hit@3 by question type

| config | ambiguity (n=3) | direct (n=25) | paraphrase (n=5) |
|---|---:|---:|---:|
| **keyword** | 67% | 64% | 60% |
| **bm25** | 67% | 84% | 80% |
| **minilm-dense** | 67% | 88% | 60% |
| **hybrid-minilm** | 100% | 88% | 60% |
| **default-minilm** | 100% | 100% | 60% |
| **default-minilm-rerank** | 100% | 100% | 60% |
| **default-hashing** | 67% | 88% | 80% |

## Questions with no relevant passage in the top 5

**keyword** (6):
- `r02` [direct] What is a hash collision? → got Introduction to Computer Science.pdf (1.0), Introduction to Computer Science.pdf (1.0), Introduction to Computer Science.pdf (1.0)
- `r19` [direct] What is a tree rotation in an AVL tree? → got Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0)
- `r20` [direct] How does insertion sort work and how fast is it? → got Data Structures Using Python.pdf (0.75), Dsa.pdf (0.5), Dsa.pdf (0.5)
- `r25` [direct] What is a B-tree? → got Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0), Dsa.pdf (1.0)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.8), Data Structures Using Python.pdf (0.6), Data Structures Using Python.pdf (0.6)
- `r33` [ambiguity] What is a heap? → got Dsa.pdf (1.0), Dsa.pdf (1.0), Dsa.pdf (1.0)

**bm25** (2):
- `r19` [direct] What is a tree rotation in an AVL tree? → got Data Structures Using Python.pdf (0.718), Data Structures Using Python.pdf (0.691), Data Structures Using Python.pdf (0.66)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.528), Introduction to Computer Science.pdf (0.448), Introduction to Computer Science.pdf (0.42)

**minilm-dense** (3):
- `r25` [direct] What is a B-tree? → got Data Structures Using Python.pdf (0.549), Dsa.pdf (0.529), Data Structures Using Python.pdf (0.526)
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.548), Introduction to Computer Science.pdf (0.548), Introduction to Computer Science.pdf (0.514)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Dsa.pdf (0.464), Dsa.pdf (0.44), Data Structures Using Python.pdf (0.427)

**hybrid-minilm** (3):
- `r19` [direct] What is a tree rotation in an AVL tree? → got Data Structures Using Python.pdf (0.822), Data Structures Using Python.pdf (0.682), Data Structures Using Python.pdf (0.685)
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.548), Introduction to Computer Science.pdf (0.496), Introduction to Computer Science.pdf (0.548)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.395), Data Structures Using Python.pdf (0.427), Introduction to Computer Science.pdf (0.398)

**default-minilm** (2):
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.534), Introduction to Computer Science.pdf (0.526), Introduction to Computer Science.pdf (0.434)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.539), Data Structures Using Python.pdf (0.391), Data Structures Using Python.pdf (0.472)

**default-minilm-rerank** (2):
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.534), Introduction to Computer Science.pdf (0.411), Introduction to Computer Science.pdf (0.526)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.391), Data Structures Using Python.pdf (0.539), Introduction to Computer Science.pdf (0.313)

**default-hashing** (2):
- `r19` [direct] What is a tree rotation in an AVL tree? → got Data Structures Using Python.pdf (0.766), Data Structures Using Python.pdf (0.727), Data Structures Using Python.pdf (0.655)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.546), Introduction to Computer Science.pdf (0.466), Introduction to Computer Science.pdf (0.462)

## Unanswerable questions: top score

| question | keyword | bm25 | minilm-dense | hybrid-minilm | default-minilm | default-minilm-rerank | default-hashing |
|---|---:|---:|---:|---:|---:|---:|---:|
| What is the capital of Australia? | 0.50 | 0.23 | 0.19 | 0.03 | 0.10 | 0.02 | 0.23 |
| Who won the 2018 football world cup? | 0.40 | 0.12 | 0.22 | 0.09 | 0.11 | 0.11 | 0.11 |
| What is a good recipe for sourdough bread? | 0.25 | 0.21 | 0.33 | 0.28 | 0.25 | 0.25 | 0.21 |
| What is the boiling point of water in Fahrenheit? | 0.25 | 0.15 | 0.33 | 0.27 | 0.25 | 0.25 | 0.15 |
| Summarize the plot of the play Hamlet. | 0.25 | 0.17 | 0.24 | 0.18 | 0.14 | 0.19 | 0.15 |
| How many moons does Jupiter have? | 0.50 | 0.17 | 0.25 | 0.18 | 0.01 | 0.09 | 0.18 |
| *median of answerable questions* | 1.00 | 0.67 | 0.67 | 0.64 | 0.66 | 0.63 | 0.66 |
