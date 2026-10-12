# Retrieval evaluation: real corpus

33 answerable questions and 6 unanswerable ones. A retrieved passage counts as relevant when it comes from the expected document and contains a key phrase of the answer, so the ground truth does not depend on chunk boundaries.

- **hit@k**: share of answerable questions with a relevant passage in the top k.
- **MRR**: mean of 1 / rank of the first relevant passage.
- **cov@5**: share of the expected pieces of evidence found in the top 5 (matters for comparison questions).
- **AUROC**: how well the top retrieval score separates answerable from unanswerable questions (1.0 perfect, 0.5 no better than chance). This is what a "no good match found" threshold would rely on.

## Summary

| config | setup | chunks | hit@1 | hit@3 | hit@5 | MRR | cov@5 | AUROC | ms/query |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **keyword** | hashing-512, chunks v1, keyword | 4715 | 27% | 45% | 61% | 0.412 | 43% | 0.98 | 74.7 |
| **hashing-dense** | hashing-512, chunks v1, dense | 4715 | 18% | 24% | 30% | 0.226 | 25% | 0.51 | 0.4 |
| **minilm-dense** | all-MiniLM-L6-v2, chunks v1, dense | 4715 | 48% | 76% | 85% | 0.636 | 65% | 1.00 | 3.2 |

## hit@3 by question type

| config | ambiguity (n=3) | direct (n=25) | paraphrase (n=5) |
|---|---:|---:|---:|
| **keyword** | 33% | 48% | 40% |
| **hashing-dense** | 0% | 32% | 0% |
| **minilm-dense** | 67% | 84% | 40% |

## Questions with no relevant passage in the top 5

**keyword** (13):
- `r02` [direct] What is a hash collision? → got Introduction to Computer Science.pdf (1.0), Introduction to Computer Science.pdf (1.0), Introduction to Computer Science.pdf (1.0)
- `r07` [direct] What is a binary heap? → got Introduction to Computer Science.pdf (1.0), Introduction to Computer Science.pdf (1.0), Introduction to Computer Science.pdf (1.0)
- `r09` [direct] How does merge sort work? → got Introduction to Computer Science.pdf (1.0), Dsa.pdf (0.667), Data Structures Using Python.pdf (0.667)
- `r14` [direct] How does quick sort work? → got Dsa.pdf (0.667), Dsa.pdf (0.667), Dsa.pdf (0.667)
- `r18` [direct] What is a graph? → got Data Structures Using Python.pdf (1.0), Introduction to Computer Science.pdf (1.0), Data Structures Using Python.pdf (1.0)
- `r19` [direct] What is a tree rotation in an AVL tree? → got Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0)
- `r20` [direct] How does insertion sort work and how fast is it? → got Data Structures Using Python.pdf (0.75), Dsa.pdf (0.5), Dsa.pdf (0.5)
- `r21` [direct] What is dynamic programming? → got Introduction to Computer Science.pdf (1.0), Introduction to Computer Science.pdf (1.0), Introduction to Computer Science.pdf (1.0)
- `r25` [direct] What is a B-tree? → got Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0), Dsa.pdf (1.0)
- `r28` [paraphrase] How can computers share files that live on several servers? → got Introduction to Computer Science.pdf (0.5), Introduction to Computer Science.pdf (0.5), Introduction to Computer Science.pdf (0.5)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.8), Data Structures Using Python.pdf (0.6), Data Structures Using Python.pdf (0.6)
- `r31` [ambiguity] What is DFS? → got Data Structures Using Python.pdf (1.0), Introduction to Computer Science.pdf (1.0), Introduction to Computer Science.pdf (1.0)
- `r33` [ambiguity] What is a heap? → got Dsa.pdf (1.0), Dsa.pdf (1.0), Dsa.pdf (1.0)

**hashing-dense** (23):
- `r01` [direct] What is a hash table and how does it store elements? → got Introduction to Computer Science.pdf (0.317), Introduction to Computer Science.pdf (0.302), Introduction to Computer Science.pdf (0.265)
- `r02` [direct] What is a hash collision? → got Introduction to Computer Science.pdf (0.264), Introduction to Computer Science.pdf (0.261), Introduction to Computer Science.pdf (0.259)
- `r05` [direct] What is the running time of breadth-first search? → got Data Structures Using Python.pdf (0.334), Introduction to Computer Science.pdf (0.301), Introduction to Computer Science.pdf (0.295)
- `r07` [direct] What is a binary heap? → got Introduction to Computer Science.pdf (0.32), Data Structures Using Python.pdf (0.309), Introduction to Computer Science.pdf (0.293)
- `r08` [direct] What is the heap property? → got Introduction to Computer Science.pdf (0.29), Introduction to Computer Science.pdf (0.281), Introduction to Computer Science.pdf (0.268)
- `r09` [direct] How does merge sort work? → got Introduction to Computer Science.pdf (0.192), Introduction to Computer Science.pdf (0.192), Dsa.pdf (0.181)
- `r11` [direct] What is a stack and in what order does it return elements? → got Introduction to Computer Science.pdf (0.29), Introduction to Computer Science.pdf (0.284), Introduction to Computer Science.pdf (0.269)
- `r12` [direct] What does a queue do? → got Introduction to Computer Science.pdf (0.227), Introduction to Computer Science.pdf (0.215), Introduction to Computer Science.pdf (0.214)
- `r14` [direct] How does quick sort work? → got Introduction to Computer Science.pdf (0.192), Introduction to Computer Science.pdf (0.19), Introduction to Computer Science.pdf (0.171)
- `r18` [direct] What is a graph? → got Data Structures Using Python.pdf (0.316), Data Structures Using Python.pdf (0.312), Introduction to Computer Science.pdf (0.295)
- `r19` [direct] What is a tree rotation in an AVL tree? → got Data Structures Using Python.pdf (0.313), Data Structures Using Python.pdf (0.309), Data Structures Using Python.pdf (0.288)
- `r20` [direct] How does insertion sort work and how fast is it? → got Introduction to Computer Science.pdf (0.28), Introduction to Computer Science.pdf (0.238), Introduction to Computer Science.pdf (0.235)
- `r21` [direct] What is dynamic programming? → got Introduction to Computer Science.pdf (0.274), Introduction to Computer Science.pdf (0.27), Introduction to Computer Science.pdf (0.247)
- `r22` [direct] What is recursion? → got Introduction to Computer Science.pdf (0.249), Introduction to Computer Science.pdf (0.249), Dsa.pdf (0.249)
- `r24` [direct] What are heaps most commonly used for? → got Introduction to Computer Science.pdf (0.234), Introduction to Computer Science.pdf (0.224), Introduction to Computer Science.pdf (0.212)
- `r26` [paraphrase] How can I find the shortest route between two places in a weighted road network? → got Introduction to Computer Science.pdf (0.286), Introduction to Computer Science.pdf (0.264), Dsa.pdf (0.256)
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.232), Introduction to Computer Science.pdf (0.214), Introduction to Computer Science.pdf (0.204)
- `r28` [paraphrase] How can computers share files that live on several servers? → got Introduction to Computer Science.pdf (0.214), Introduction to Computer Science.pdf (0.209), Introduction to Computer Science.pdf (0.205)
- `r29` [paraphrase] Which graph search visits every neighbour at one distance before going further out? → got Introduction to Computer Science.pdf (0.17), Introduction to Computer Science.pdf (0.169), Introduction to Computer Science.pdf (0.167)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.28), Introduction to Computer Science.pdf (0.231), Data Structures Using Python.pdf (0.224)
- `r31` [ambiguity] What is DFS? → got Introduction to Computer Science.pdf (0.275), Introduction to Computer Science.pdf (0.266), Introduction to Computer Science.pdf (0.249)
- `r32` [ambiguity] How do DFS and BFS differ when exploring a graph? → got Introduction to Computer Science.pdf (0.227), Introduction to Computer Science.pdf (0.226), Introduction to Computer Science.pdf (0.213)
- `r33` [ambiguity] What is a heap? → got Introduction to Computer Science.pdf (0.293), Introduction to Computer Science.pdf (0.29), Dsa.pdf (0.289)

**minilm-dense** (5):
- `r09` [direct] How does merge sort work? → got Introduction to Computer Science.pdf (0.779), Introduction to Computer Science.pdf (0.642), Dsa.pdf (0.626)
- `r25` [direct] What is a B-tree? → got Data Structures Using Python.pdf (0.549), Dsa.pdf (0.529), Data Structures Using Python.pdf (0.526)
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.548), Introduction to Computer Science.pdf (0.548), Introduction to Computer Science.pdf (0.514)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Dsa.pdf (0.464), Dsa.pdf (0.44), Data Structures Using Python.pdf (0.427)
- `r33` [ambiguity] What is a heap? → got Dsa.pdf (0.663), Dsa.pdf (0.645), Dsa.pdf (0.644)

## Unanswerable questions: top score

| question | keyword | hashing-dense | minilm-dense |
|---|---:|---:|---:|
| What is the capital of Australia? | 0.50 | 0.34 | 0.19 |
| Who won the 2018 football world cup? | 0.40 | 0.25 | 0.22 |
| What is a good recipe for sourdough bread? | 0.25 | 0.27 | 0.33 |
| What is the boiling point of water in Fahrenheit? | 0.25 | 0.30 | 0.33 |
| Summarize the plot of the play Hamlet. | 0.25 | 0.31 | 0.24 |
| How many moons does Jupiter have? | 0.50 | 0.19 | 0.25 |
| *median of answerable questions* | 1.00 | 0.28 | 0.67 |
