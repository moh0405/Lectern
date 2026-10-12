# Retrieval evaluation: real corpus

33 answerable questions and 6 unanswerable ones. A retrieved passage counts as relevant when it comes from the expected document and contains a key phrase of the answer, so the ground truth does not depend on chunk boundaries.

- **hit@k**: share of answerable questions with a relevant passage in the top k.
- **MRR**: mean of 1 / rank of the first relevant passage.
- **cov@5**: share of the expected pieces of evidence found in the top 5 (matters for comparison questions).
- **AUROC**: how well the top retrieval score separates answerable from unanswerable questions (1.0 perfect, 0.5 no better than chance). This is what a "no good match found" threshold would rely on.

## Summary

| config | setup | chunks | hit@1 | hit@3 | hit@5 | MRR | cov@5 | strict hit@3 | AUROC | ms/query |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **keyword** | hashing-512, chunks v1, keyword | 4715 | 42% | 64% | 82% | 0.584 | 69% | 45% | 0.98 | 74.2 |
| **hashing-dense** | hashing-512, chunks v1, dense | 4715 | 21% | 33% | 39% | 0.282 | 33% | 24% | 0.51 | 0.3 |
| **minilm-dense** | all-MiniLM-L6-v2, chunks v1, dense | 4715 | 70% | 82% | 91% | 0.780 | 78% | 76% | 1.00 | 3.1 |
| **keyword-v2** | hashing-512, chunks v2, keyword | 3867 | 30% | 67% | 82% | 0.523 | 71% | 55% | 0.98 | 70.1 |
| **hashing-dense-v2** | hashing-512, chunks v2, dense | 3867 | 27% | 33% | 36% | 0.312 | 32% | 27% | 0.51 | 0.3 |
| **minilm-dense-v2** | all-MiniLM-L6-v2, chunks v2, dense | 3867 | 48% | 85% | 91% | 0.662 | 75% | 73% | 1.00 | 3.0 |

## hit@3 by question type

| config | ambiguity (n=3) | direct (n=25) | paraphrase (n=5) |
|---|---:|---:|---:|
| **keyword** | 67% | 64% | 60% |
| **hashing-dense** | 0% | 36% | 40% |
| **minilm-dense** | 67% | 88% | 60% |
| **keyword-v2** | 67% | 68% | 60% |
| **hashing-dense-v2** | 0% | 40% | 20% |
| **minilm-dense-v2** | 100% | 88% | 60% |

## Questions with no relevant passage in the top 5

**keyword** (6):
- `r02` [direct] What is a hash collision? → got Introduction to Computer Science.pdf (1.0), Introduction to Computer Science.pdf (1.0), Introduction to Computer Science.pdf (1.0)
- `r19` [direct] What is a tree rotation in an AVL tree? → got Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0)
- `r20` [direct] How does insertion sort work and how fast is it? → got Data Structures Using Python.pdf (0.75), Dsa.pdf (0.5), Dsa.pdf (0.5)
- `r25` [direct] What is a B-tree? → got Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0), Dsa.pdf (1.0)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.8), Data Structures Using Python.pdf (0.6), Data Structures Using Python.pdf (0.6)
- `r33` [ambiguity] What is a heap? → got Dsa.pdf (1.0), Dsa.pdf (1.0), Dsa.pdf (1.0)

**hashing-dense** (20):
- `r01` [direct] What is a hash table and how does it store elements? → got Introduction to Computer Science.pdf (0.317), Introduction to Computer Science.pdf (0.302), Introduction to Computer Science.pdf (0.265)
- `r02` [direct] What is a hash collision? → got Introduction to Computer Science.pdf (0.264), Introduction to Computer Science.pdf (0.261), Introduction to Computer Science.pdf (0.259)
- `r05` [direct] What is the running time of breadth-first search? → got Data Structures Using Python.pdf (0.334), Introduction to Computer Science.pdf (0.301), Introduction to Computer Science.pdf (0.295)
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
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.28), Introduction to Computer Science.pdf (0.231), Data Structures Using Python.pdf (0.224)
- `r31` [ambiguity] What is DFS? → got Introduction to Computer Science.pdf (0.275), Introduction to Computer Science.pdf (0.266), Introduction to Computer Science.pdf (0.249)
- `r32` [ambiguity] How do DFS and BFS differ when exploring a graph? → got Introduction to Computer Science.pdf (0.227), Introduction to Computer Science.pdf (0.226), Introduction to Computer Science.pdf (0.213)
- `r33` [ambiguity] What is a heap? → got Introduction to Computer Science.pdf (0.293), Introduction to Computer Science.pdf (0.29), Dsa.pdf (0.289)

**minilm-dense** (3):
- `r25` [direct] What is a B-tree? → got Data Structures Using Python.pdf (0.549), Dsa.pdf (0.529), Data Structures Using Python.pdf (0.526)
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.548), Introduction to Computer Science.pdf (0.548), Introduction to Computer Science.pdf (0.514)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Dsa.pdf (0.464), Dsa.pdf (0.44), Data Structures Using Python.pdf (0.427)

**keyword-v2** (6):
- `r12` [direct] What does a queue do? → got Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0)
- `r18` [direct] What is a graph? → got Introduction to Computer Science.pdf (1.0), Data Structures Using Python.pdf (1.0), Introduction to Computer Science.pdf (1.0)
- `r25` [direct] What is a B-tree? → got Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0)
- `r28` [paraphrase] How can computers share files that live on several servers? → got Introduction to Computer Science.pdf (0.667), Introduction to Computer Science.pdf (0.667), Introduction to Computer Science.pdf (0.5)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.8), Data Structures Using Python.pdf (0.6), Introduction to Computer Science.pdf (0.6)
- `r33` [ambiguity] What is a heap? → got Dsa.pdf (1.0), Dsa.pdf (1.0), Dsa.pdf (1.0)

**hashing-dense-v2** (21):
- `r01` [direct] What is a hash table and how does it store elements? → got Introduction to Computer Science.pdf (0.268), Introduction to Computer Science.pdf (0.266), Introduction to Computer Science.pdf (0.26)
- `r02` [direct] What is a hash collision? → got Introduction to Computer Science.pdf (0.275), Introduction to Computer Science.pdf (0.258), Introduction to Computer Science.pdf (0.248)
- `r05` [direct] What is the running time of breadth-first search? → got Data Structures Using Python.pdf (0.305), Dsa.pdf (0.271), Introduction to Computer Science.pdf (0.269)
- `r08` [direct] What is the heap property? → got Introduction to Computer Science.pdf (0.291), Introduction to Computer Science.pdf (0.277), Introduction to Computer Science.pdf (0.273)
- `r09` [direct] How does merge sort work? → got Introduction to Computer Science.pdf (0.177), Data Structures Using Python.pdf (0.173), Dsa.pdf (0.17)
- `r11` [direct] What is a stack and in what order does it return elements? → got Introduction to Computer Science.pdf (0.263), Introduction to Computer Science.pdf (0.26), Introduction to Computer Science.pdf (0.259)
- `r12` [direct] What does a queue do? → got Introduction to Computer Science.pdf (0.229), Introduction to Computer Science.pdf (0.206), Introduction to Computer Science.pdf (0.197)
- `r14` [direct] How does quick sort work? → got Introduction to Computer Science.pdf (0.192), Introduction to Computer Science.pdf (0.168), Introduction to Computer Science.pdf (0.163)
- `r18` [direct] What is a graph? → got Data Structures Using Python.pdf (0.298), Introduction to Computer Science.pdf (0.27), Introduction to Computer Science.pdf (0.265)
- `r19` [direct] What is a tree rotation in an AVL tree? → got Data Structures Using Python.pdf (0.311), Data Structures Using Python.pdf (0.281), Data Structures Using Python.pdf (0.272)
- `r20` [direct] How does insertion sort work and how fast is it? → got Introduction to Computer Science.pdf (0.268), Introduction to Computer Science.pdf (0.235), Introduction to Computer Science.pdf (0.232)
- `r21` [direct] What is dynamic programming? → got Introduction to Computer Science.pdf (0.263), Introduction to Computer Science.pdf (0.251), Introduction to Computer Science.pdf (0.238)
- `r22` [direct] What is recursion? → got Dsa.pdf (0.252), Introduction to Computer Science.pdf (0.251), Introduction to Computer Science.pdf (0.242)
- `r24` [direct] What are heaps most commonly used for? → got Introduction to Computer Science.pdf (0.216), Data Structures Using Python.pdf (0.209), Introduction to Computer Science.pdf (0.199)
- `r25` [direct] What is a B-tree? → got Introduction to Computer Science.pdf (0.282), Introduction to Computer Science.pdf (0.282), Introduction to Computer Science.pdf (0.282)
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.214), Introduction to Computer Science.pdf (0.205), Introduction to Computer Science.pdf (0.198)
- `r28` [paraphrase] How can computers share files that live on several servers? → got Introduction to Computer Science.pdf (0.22), Introduction to Computer Science.pdf (0.216), Introduction to Computer Science.pdf (0.206)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.269), Introduction to Computer Science.pdf (0.245), Introduction to Computer Science.pdf (0.229)
- `r31` [ambiguity] What is DFS? → got Introduction to Computer Science.pdf (0.271), Introduction to Computer Science.pdf (0.268), Introduction to Computer Science.pdf (0.261)
- `r32` [ambiguity] How do DFS and BFS differ when exploring a graph? → got Introduction to Computer Science.pdf (0.217), Introduction to Computer Science.pdf (0.204), Introduction to Computer Science.pdf (0.204)
- `r33` [ambiguity] What is a heap? → got Introduction to Computer Science.pdf (0.296), Introduction to Computer Science.pdf (0.292), Introduction to Computer Science.pdf (0.292)

**minilm-dense-v2** (3):
- `r21` [direct] What is dynamic programming? → got Introduction to Computer Science.pdf (0.56), Introduction to Computer Science.pdf (0.545), Introduction to Computer Science.pdf (0.529)
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.55), Introduction to Computer Science.pdf (0.534), Introduction to Computer Science.pdf (0.526)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.539), Data Structures Using Python.pdf (0.472), Dsa.pdf (0.438)

## Unanswerable questions: top score

| question | keyword | hashing-dense | minilm-dense | keyword-v2 | hashing-dense-v2 | minilm-dense-v2 |
|---|---:|---:|---:|---:|---:|---:|
| What is the capital of Australia? | 0.50 | 0.34 | 0.19 | 0.50 | 0.33 | 0.19 |
| Who won the 2018 football world cup? | 0.40 | 0.25 | 0.22 | 0.40 | 0.19 | 0.22 |
| What is a good recipe for sourdough bread? | 0.25 | 0.27 | 0.33 | 0.25 | 0.25 | 0.25 |
| What is the boiling point of water in Fahrenheit? | 0.25 | 0.30 | 0.33 | 0.25 | 0.28 | 0.30 |
| Summarize the plot of the play Hamlet. | 0.25 | 0.31 | 0.24 | 0.25 | 0.33 | 0.28 |
| How many moons does Jupiter have? | 0.50 | 0.19 | 0.25 | 0.50 | 0.18 | 0.26 |
| *median of answerable questions* | 1.00 | 0.28 | 0.67 | 1.00 | 0.27 | 0.68 |
