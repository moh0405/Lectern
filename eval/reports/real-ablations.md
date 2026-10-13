# Retrieval evaluation: real corpus

33 answerable questions and 6 unanswerable ones. A retrieved passage counts as relevant when it comes from the expected document and contains a key phrase of the answer, so the ground truth does not depend on chunk boundaries.

- **hit@k**: share of answerable questions with a relevant passage in the top k.
- **MRR**: mean of 1 / rank of the first relevant passage.
- **cov@5**: share of the expected pieces of evidence found in the top 5 (matters for comparison questions).
- **AUROC**: how well the top retrieval score separates answerable from unanswerable questions (1.0 perfect, 0.5 no better than chance). This is what a "no good match found" threshold would rely on.

## Summary

| config | setup | chunks | hit@1 | hit@3 | hit@5 | MRR | cov@5 | strict hit@3 | AUROC | ms/query |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **minilm-dense** | all-MiniLM-L6-v2, chunks v1, dense | 4715 | 70% | 82% | 91% | 0.780 | 78% | 76% | 1.00 | 3.1 |
| **hashing-dense** | hashing-512, chunks v1, dense | 4715 | 21% | 33% | 39% | 0.282 | 33% | 24% | 0.51 | 0.3 |
| **hybrid-hashing** | hashing-512, chunks v1, hybrid | 4715 | 45% | 55% | 73% | 0.547 | 61% | 42% | 0.73 | 0.7 |
| **hybrid-hashing-v2** | hashing-512, chunks v2, hybrid | 3867 | 48% | 64% | 73% | 0.587 | 61% | 55% | 0.64 | 3.5 |
| **bm25-v2** | hashing-512, chunks v2, bm25 | 3867 | 48% | 85% | 94% | 0.679 | 74% | 76% | 1.00 | 0.3 |
| **hybrid-minilm-v2** | all-MiniLM-L6-v2, chunks v2, hybrid | 3867 | 67% | 94% | 94% | 0.783 | 78% | 88% | 1.00 | 3.4 |
| **hybrid-minilm-v2-perpage** | all-MiniLM-L6-v2, chunks v2-perpage, hybrid | 4143 | 67% | 85% | 91% | 0.771 | 81% | 82% | 1.00 | 3.4 |
| **hybrid-minilm-rerank** | all-MiniLM-L6-v2, chunks v1, hybrid, rerank | 4715 | 76% | 94% | 94% | 0.842 | 85% | 91% | 1.00 | 302.3 |
| **hybrid-minilm-v2-rerank** | all-MiniLM-L6-v2, chunks v2, hybrid, rerank | 3867 | 79% | 94% | 94% | 0.859 | 84% | 88% | 1.00 | 334.7 |
| **keyword-v2** | hashing-512, chunks v2, keyword | 3867 | 30% | 67% | 82% | 0.523 | 71% | 55% | 0.98 | 71.0 |
| **hashing-dense-v2** | hashing-512, chunks v2, dense | 3867 | 27% | 33% | 36% | 0.312 | 32% | 27% | 0.51 | 0.3 |
| **minilm-dense-v2** | all-MiniLM-L6-v2, chunks v2, dense | 3867 | 48% | 85% | 91% | 0.662 | 75% | 73% | 1.00 | 3.0 |
| **minilm-dense-v2-perpage** | all-MiniLM-L6-v2, chunks v2-perpage, dense | 4143 | 58% | 82% | 91% | 0.720 | 77% | 73% | 1.00 | 3.0 |
| **keyword-v2-600** | hashing-512, chunks v2-600, keyword | 5879 | 36% | 58% | 70% | 0.515 | 59% | 33% | 0.98 | 68.5 |
| **minilm-dense-v2-600** | all-MiniLM-L6-v2, chunks v2-600, dense | 5879 | 45% | 85% | 91% | 0.631 | 79% | 58% | 1.00 | 3.1 |
| **keyword-v2-400** | hashing-512, chunks v2-400, keyword | 8751 | 36% | 61% | 82% | 0.549 | 63% | 36% | 0.99 | 65.3 |
| **minilm-dense-v2-400** | all-MiniLM-L6-v2, chunks v2-400, dense | 8751 | 52% | 85% | 88% | 0.674 | 76% | 55% | 1.00 | 3.4 |

## Change versus `minilm-dense` (paired bootstrap over questions, 95% interval)

An interval that contains 0 means the data do not show a real difference.

| config | Δ hit@3 | 95% interval | P(better) | Δ MRR | 95% interval |
|---|---:|---:|---:|---:|---:|
| **hashing-dense** | -48 pts | [-67, -30] | 0.00 | -0.498 | [-0.654, -0.329] |
| **hybrid-hashing** | -27 pts | [-45, -9] | 0.00 | -0.233 | [-0.383, -0.086] |
| **hybrid-hashing-v2** | -18 pts | [-33, -3] | 0.00 | -0.193 | [-0.335, -0.055] |
| **bm25-v2** | +3 pts | [-12, +18] | 0.57 | -0.101 | [-0.247, +0.053] |
| **hybrid-minilm-v2** | +12 pts | [+3, +24] | 0.99 | +0.003 | [-0.083, +0.093] |
| **hybrid-minilm-v2-perpage** | +3 pts | [-9, +15] | 0.58 | -0.009 | [-0.089, +0.071] |
| **hybrid-minilm-rerank** | +12 pts | [+3, +24] | 0.99 | +0.062 | [-0.025, +0.164] |
| **hybrid-minilm-v2-rerank** | +12 pts | [+3, +24] | 0.99 | +0.078 | [-0.035, +0.194] |
| **keyword-v2** | -15 pts | [-33, +3] | 0.04 | -0.258 | [-0.408, -0.104] |
| **hashing-dense-v2** | -48 pts | [-64, -30] | 0.00 | -0.468 | [-0.618, -0.316] |
| **minilm-dense-v2** | +3 pts | [-6, +15] | 0.60 | -0.119 | [-0.225, -0.020] |
| **minilm-dense-v2-perpage** | +0 pts | [-9, +9] | 0.34 | -0.061 | [-0.136, +0.000] |
| **keyword-v2-600** | -24 pts | [-42, -6] | 0.00 | -0.265 | [-0.411, -0.113] |
| **minilm-dense-v2-600** | +3 pts | [-9, +15] | 0.58 | -0.149 | [-0.258, -0.045] |
| **keyword-v2-400** | -21 pts | [-36, -6] | 0.00 | -0.231 | [-0.348, -0.121] |
| **minilm-dense-v2-400** | +3 pts | [-9, +15] | 0.58 | -0.107 | [-0.231, +0.025] |

## hit@3 by question type

| config | ambiguity (n=3) | direct (n=25) | paraphrase (n=5) |
|---|---:|---:|---:|
| **minilm-dense** | 67% | 88% | 60% |
| **hashing-dense** | 0% | 36% | 40% |
| **hybrid-hashing** | 67% | 52% | 60% |
| **hybrid-hashing-v2** | 67% | 64% | 60% |
| **bm25-v2** | 67% | 88% | 80% |
| **hybrid-minilm-v2** | 100% | 100% | 60% |
| **hybrid-minilm-v2-perpage** | 100% | 88% | 60% |
| **hybrid-minilm-rerank** | 100% | 100% | 60% |
| **hybrid-minilm-v2-rerank** | 100% | 100% | 60% |
| **keyword-v2** | 67% | 68% | 60% |
| **hashing-dense-v2** | 0% | 40% | 20% |
| **minilm-dense-v2** | 100% | 88% | 60% |
| **minilm-dense-v2-perpage** | 67% | 88% | 60% |
| **keyword-v2-600** | 100% | 56% | 40% |
| **minilm-dense-v2-600** | 100% | 88% | 60% |
| **keyword-v2-400** | 100% | 60% | 40% |
| **minilm-dense-v2-400** | 67% | 92% | 60% |

## Questions with no relevant passage in the top 5

**minilm-dense** (3):
- `r25` [direct] What is a B-tree? → got Data Structures Using Python.pdf (0.549), Dsa.pdf (0.529), Data Structures Using Python.pdf (0.526)
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.548), Introduction to Computer Science.pdf (0.548), Introduction to Computer Science.pdf (0.514)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Dsa.pdf (0.464), Dsa.pdf (0.44), Data Structures Using Python.pdf (0.427)

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

**hybrid-hashing** (9):
- `r08` [direct] What is the heap property? → got Dsa.pdf (0.254), Dsa.pdf (0.253), Dsa.pdf (0.249)
- `r09` [direct] How does merge sort work? → got Dsa.pdf (0.168), Dsa.pdf (0.166), Introduction to Computer Science.pdf (0.132)
- `r11` [direct] What is a stack and in what order does it return elements? → got Introduction to Computer Science.pdf (0.26), Dsa.pdf (0.235), Introduction to Computer Science.pdf (0.238)
- `r14` [direct] How does quick sort work? → got Dsa.pdf (0.168), Data Structures Using Python.pdf (0.152), Dsa.pdf (0.14)
- `r19` [direct] What is a tree rotation in an AVL tree? → got Data Structures Using Python.pdf (0.313), Data Structures Using Python.pdf (0.243), Data Structures Using Python.pdf (0.288)
- `r20` [direct] How does insertion sort work and how fast is it? → got Dsa.pdf (0.221), Dsa.pdf (0.228), Introduction to Computer Science.pdf (0.177)
- `r22` [direct] What is recursion? → got Introduction to Computer Science.pdf (0.191), Introduction to Computer Science.pdf (0.216), Dsa.pdf (0.165)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.28), Data Structures Using Python.pdf (0.184), Data Structures Using Python.pdf (0.195)
- `r33` [ambiguity] What is a heap? → got Introduction to Computer Science.pdf (0.275), Dsa.pdf (0.289), Dsa.pdf (0.221)

**hybrid-hashing-v2** (9):
- `r02` [direct] What is a hash collision? → got Introduction to Computer Science.pdf (0.225), Introduction to Computer Science.pdf (0.193), Introduction to Computer Science.pdf (0.172)
- `r09` [direct] How does merge sort work? → got Dsa.pdf (0.154), Introduction to Computer Science.pdf (0.141), Dsa.pdf (0.156)
- `r11` [direct] What is a stack and in what order does it return elements? → got Introduction to Computer Science.pdf (0.225), Introduction to Computer Science.pdf (0.214), Data Structures Using Python.pdf (0.219)
- `r14` [direct] How does quick sort work? → got Dsa.pdf (0.156), Dsa.pdf (0.127), Dsa.pdf (0.117)
- `r18` [direct] What is a graph? → got Data Structures Using Python.pdf (0.298), Data Structures Using Python.pdf (0.262), Introduction to Computer Science.pdf (0.255)
- `r19` [direct] What is a tree rotation in an AVL tree? → got Data Structures Using Python.pdf (0.281), Data Structures Using Python.pdf (0.311), Data Structures Using Python.pdf (0.239)
- `r20` [direct] How does insertion sort work and how fast is it? → got Dsa.pdf (0.227), Data Structures Using Python.pdf (0.162), Dsa.pdf (0.173)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.269), Data Structures Using Python.pdf (0.209), Introduction to Computer Science.pdf (0.229)
- `r33` [ambiguity] What is a heap? → got Introduction to Computer Science.pdf (0.231), Introduction to Computer Science.pdf (0.259), Introduction to Computer Science.pdf (0.256)

**bm25-v2** (2):
- `r19` [direct] What is a tree rotation in an AVL tree? → got Data Structures Using Python.pdf (0.766), Data Structures Using Python.pdf (0.727), Data Structures Using Python.pdf (0.655)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.546), Introduction to Computer Science.pdf (0.466), Introduction to Computer Science.pdf (0.462)

**hybrid-minilm-v2** (2):
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.534), Introduction to Computer Science.pdf (0.526), Introduction to Computer Science.pdf (0.434)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.539), Data Structures Using Python.pdf (0.391), Data Structures Using Python.pdf (0.472)

**hybrid-minilm-v2-perpage** (3):
- `r25` [direct] What is a B-tree? → got Data Structures Using Python.pdf (0.518), Introduction to Computer Science.pdf (0.49), Data Structures Using Python.pdf (0.49)
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.554), Introduction to Computer Science.pdf (0.536), Introduction to Computer Science.pdf (0.526)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.391), Data Structures Using Python.pdf (0.527), Data Structures Using Python.pdf (0.583)

**hybrid-minilm-rerank** (2):
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.496), Introduction to Computer Science.pdf (0.403), Introduction to Computer Science.pdf (0.548)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.395), Data Structures Using Python.pdf (0.427), Data Structures Using Python.pdf (0.349)

**hybrid-minilm-v2-rerank** (2):
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.534), Introduction to Computer Science.pdf (0.411), Introduction to Computer Science.pdf (0.526)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.391), Data Structures Using Python.pdf (0.539), Introduction to Computer Science.pdf (0.313)

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

**minilm-dense-v2-perpage** (3):
- `r25` [direct] What is a B-tree? → got Introduction to Computer Science.pdf (0.529), Data Structures Using Python.pdf (0.523), Dsa.pdf (0.519)
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.554), Introduction to Computer Science.pdf (0.55), Introduction to Computer Science.pdf (0.536)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.583), Data Structures Using Python.pdf (0.527), Dsa.pdf (0.435)

**keyword-v2-600** (10):
- `r11` [direct] What is a stack and in what order does it return elements? → got Introduction to Computer Science.pdf (0.75), Introduction to Computer Science.pdf (0.75), Introduction to Computer Science.pdf (0.75)
- `r12` [direct] What does a queue do? → got Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0)
- `r14` [direct] How does quick sort work? → got Dsa.pdf (0.667), Dsa.pdf (0.667), Data Structures Using Python.pdf (0.667)
- `r17` [direct] What is a binary search tree? → got Data Structures Using Python.pdf (1.0), Dsa.pdf (1.0), Dsa.pdf (1.0)
- `r18` [direct] What is a graph? → got Data Structures Using Python.pdf (1.0), Introduction to Computer Science.pdf (1.0), Introduction to Computer Science.pdf (1.0)
- `r19` [direct] What is a tree rotation in an AVL tree? → got Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0)
- `r20` [direct] How does insertion sort work and how fast is it? → got Data Structures Using Python.pdf (0.75), Dsa.pdf (0.5), Data Structures Using Python.pdf (0.5)
- `r25` [direct] What is a B-tree? → got Introduction to Computer Science.pdf (1.0), Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0)
- `r28` [paraphrase] How can computers share files that live on several servers? → got Introduction to Computer Science.pdf (0.667), Introduction to Computer Science.pdf (0.5), Introduction to Computer Science.pdf (0.5)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.6), Introduction to Computer Science.pdf (0.6), Introduction to Computer Science.pdf (0.6)

**minilm-dense-v2-600** (3):
- `r25` [direct] What is a B-tree? → got Introduction to Computer Science.pdf (0.591), Data Structures Using Python.pdf (0.556), Introduction to Computer Science.pdf (0.556)
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.552), Introduction to Computer Science.pdf (0.552), Introduction to Computer Science.pdf (0.544)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.551), Data Structures Using Python.pdf (0.479), Dsa.pdf (0.477)

**keyword-v2-400** (6):
- `r14` [direct] How does quick sort work? → got Data Structures Using Python.pdf (0.667), Dsa.pdf (0.667), Dsa.pdf (0.667)
- `r18` [direct] What is a graph? → got Introduction to Computer Science.pdf (1.0), Introduction to Computer Science.pdf (1.0), Introduction to Computer Science.pdf (1.0)
- `r19` [direct] What is a tree rotation in an AVL tree? → got Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0)
- `r25` [direct] What is a B-tree? → got Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0)
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.571), Introduction to Computer Science.pdf (0.571), Introduction to Computer Science.pdf (0.571)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.6), Introduction to Computer Science.pdf (0.6), Data Structures Using Python.pdf (0.6)

**minilm-dense-v2-400** (4):
- `r24` [direct] What are heaps most commonly used for? → got Introduction to Computer Science.pdf (0.58), Introduction to Computer Science.pdf (0.579), Introduction to Computer Science.pdf (0.577)
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.593), Introduction to Computer Science.pdf (0.578), Introduction to Computer Science.pdf (0.553)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.583), Data Structures Using Python.pdf (0.488), Dsa.pdf (0.484)
- `r33` [ambiguity] What is a heap? → got Introduction to Computer Science.pdf (0.723), Introduction to Computer Science.pdf (0.681), Introduction to Computer Science.pdf (0.672)

## Unanswerable questions: top score

| question | minilm-dense | hashing-dense | hybrid-hashing | hybrid-hashing-v2 | bm25-v2 | hybrid-minilm-v2 | hybrid-minilm-v2-perpage | hybrid-minilm-rerank | hybrid-minilm-v2-rerank | keyword-v2 | hashing-dense-v2 | minilm-dense-v2 | minilm-dense-v2-perpage | keyword-v2-600 | minilm-dense-v2-600 | keyword-v2-400 | minilm-dense-v2-400 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| What is the capital of Australia? | 0.19 | 0.34 | 0.11 | 0.11 | 0.23 | 0.10 | 0.11 | 0.03 | 0.02 | 0.50 | 0.33 | 0.19 | 0.17 | 0.50 | 0.22 | 0.50 | 0.21 |
| Who won the 2018 football world cup? | 0.22 | 0.25 | 0.16 | 0.19 | 0.11 | 0.11 | 0.08 | 0.12 | 0.11 | 0.40 | 0.19 | 0.22 | 0.22 | 0.40 | 0.22 | 0.20 | 0.20 |
| What is a good recipe for sourdough bread? | 0.33 | 0.27 | 0.22 | 0.24 | 0.21 | 0.25 | 0.29 | 0.20 | 0.25 | 0.25 | 0.25 | 0.25 | 0.29 | 0.25 | 0.28 | 0.25 | 0.36 |
| What is the boiling point of water in Fahrenheit? | 0.33 | 0.30 | 0.26 | 0.23 | 0.15 | 0.25 | 0.24 | 0.19 | 0.25 | 0.25 | 0.28 | 0.30 | 0.32 | 0.25 | 0.32 | 0.25 | 0.41 |
| Summarize the plot of the play Hamlet. | 0.24 | 0.31 | 0.28 | 0.29 | 0.15 | 0.14 | 0.14 | 0.19 | 0.19 | 0.25 | 0.33 | 0.28 | 0.32 | 0.25 | 0.32 | 0.25 | 0.36 |
| How many moons does Jupiter have? | 0.25 | 0.19 | 0.13 | 0.14 | 0.18 | 0.01 | 0.05 | 0.22 | 0.09 | 0.50 | 0.18 | 0.26 | 0.26 | 0.50 | 0.25 | 0.50 | 0.28 |
| *median of answerable questions* | 0.67 | 0.28 | 0.25 | 0.23 | 0.66 | 0.66 | 0.68 | 0.61 | 0.63 | 1.00 | 0.27 | 0.68 | 0.68 | 1.00 | 0.70 | 1.00 | 0.71 |
