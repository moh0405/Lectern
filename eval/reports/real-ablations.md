# Retrieval evaluation: real corpus

39 answerable questions and 7 unanswerable ones. A retrieved passage counts as relevant when it comes from the expected document and contains a key phrase of the answer, so the ground truth does not depend on chunk boundaries.

- **hit@k**: share of answerable questions with a relevant passage in the top k.
- **MRR**: mean of 1 / rank of the first relevant passage.
- **cov@5**: share of the expected pieces of evidence found in the top 5 (matters for comparison questions).
- **AUROC**: how well the top retrieval score separates answerable from unanswerable questions (1.0 perfect, 0.5 no better than chance). This is what a "no good match found" threshold would rely on.

## Summary

| config | setup | chunks | hit@1 | hit@3 | hit@5 | MRR | cov@5 | strict hit@3 | AUROC | ms/query |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **minilm-dense** | all-MiniLM-L6-v2, chunks v1, dense | 4714 | 74% | 85% | 92% | 0.814 | 79% | 69% | 1.00 | 3.9 |
| **hashing-dense** | hashing-512, chunks v1, dense | 4714 | 21% | 38% | 49% | 0.315 | 38% | 28% | 0.57 | 0.3 |
| **hybrid-hashing** | hashing-512, chunks v1, hybrid | 4714 | 46% | 62% | 72% | 0.565 | 63% | 46% | 0.77 | 0.7 |
| **hybrid-hashing-v2** | hashing-512, chunks v2, hybrid | 3866 | 49% | 67% | 74% | 0.611 | 62% | 62% | 0.70 | 0.7 |
| **bm25-v2** | hashing-512, chunks v2, bm25 | 3866 | 49% | 87% | 95% | 0.690 | 81% | 82% | 1.00 | 0.5 |
| **hybrid-minilm-v2** | all-MiniLM-L6-v2, chunks v2, hybrid | 3866 | 72% | 95% | 95% | 0.821 | 80% | 90% | 1.00 | 3.6 |
| **hybrid-minilm-v2-perpage** | all-MiniLM-L6-v2, chunks v2-perpage, hybrid | 4143 | 74% | 87% | 92% | 0.821 | 80% | 85% | 1.00 | 3.4 |
| **hybrid-minilm-rerank** | all-MiniLM-L6-v2, chunks v1, hybrid, rerank | 4714 | 72% | 95% | 95% | 0.828 | 83% | 85% | 1.00 | 315.9 |
| **hybrid-minilm-v2-rerank** | all-MiniLM-L6-v2, chunks v2, hybrid, rerank | 3866 | 79% | 95% | 95% | 0.868 | 83% | 87% | 1.00 | 354.2 |
| **keyword-v2** | hashing-512, chunks v2, keyword | 3866 | 33% | 64% | 77% | 0.529 | 65% | 51% | 0.97 | 76.5 |
| **hashing-dense-v2** | hashing-512, chunks v2, dense | 3866 | 31% | 44% | 46% | 0.376 | 37% | 38% | 0.59 | 0.3 |
| **minilm-dense-v2** | all-MiniLM-L6-v2, chunks v2, dense | 3866 | 59% | 87% | 92% | 0.721 | 76% | 77% | 1.00 | 3.3 |
| **minilm-dense-v2-perpage** | all-MiniLM-L6-v2, chunks v2-perpage, dense | 4143 | 67% | 85% | 92% | 0.776 | 76% | 77% | 1.00 | 3.2 |
| **keyword-v2-600** | hashing-512, chunks v2-600, keyword | 5880 | 36% | 62% | 69% | 0.527 | 56% | 38% | 0.97 | 75.6 |
| **minilm-dense-v2-600** | all-MiniLM-L6-v2, chunks v2-600, dense | 5880 | 46% | 87% | 92% | 0.654 | 78% | 56% | 1.00 | 3.1 |
| **keyword-v2-400** | hashing-512, chunks v2-400, keyword | 8750 | 41% | 64% | 77% | 0.577 | 58% | 41% | 0.97 | 72.7 |
| **minilm-dense-v2-400** | all-MiniLM-L6-v2, chunks v2-400, dense | 8750 | 54% | 87% | 90% | 0.698 | 77% | 67% | 1.00 | 3.3 |
| **default-hashing-noexpand** | hashing-512, chunks v2, auto, no expansion | 3866 | 54% | 87% | 95% | 0.716 | 76% | 74% | 1.00 | 0.3 |
| **default-minilm-rerank-noexpand** | all-MiniLM-L6-v2, chunks v2, auto, rerank, no expansion | 3866 | 79% | 95% | 95% | 0.868 | 80% | 87% | 1.00 | 324.4 |

## Change versus `minilm-dense` (paired bootstrap over questions, 95% interval)

An interval that contains 0 means the data do not show a real difference.

| config | Δ hit@3 | 95% interval | P(better) | Δ MRR | 95% interval |
|---|---:|---:|---:|---:|---:|
| **hashing-dense** | -46 pts | [-64, -28] | 0.00 | -0.499 | [-0.637, -0.353] |
| **hybrid-hashing** | -23 pts | [-38, -8] | 0.00 | -0.249 | [-0.383, -0.113] |
| **hybrid-hashing-v2** | -18 pts | [-31, -5] | 0.00 | -0.203 | [-0.331, -0.077] |
| **bm25-v2** | +3 pts | [-10, +15] | 0.57 | -0.124 | [-0.256, +0.013] |
| **hybrid-minilm-v2** | +10 pts | [+3, +21] | 0.99 | +0.006 | [-0.068, +0.079] |
| **hybrid-minilm-v2-perpage** | +3 pts | [-8, +13] | 0.58 | +0.006 | [-0.056, +0.071] |
| **hybrid-minilm-rerank** | +10 pts | [+3, +21] | 0.99 | +0.014 | [-0.083, +0.118] |
| **hybrid-minilm-v2-rerank** | +10 pts | [+3, +21] | 0.99 | +0.053 | [-0.051, +0.162] |
| **keyword-v2** | -21 pts | [-38, -3] | 0.01 | -0.285 | [-0.418, -0.145] |
| **hashing-dense-v2** | -41 pts | [-56, -26] | 0.00 | -0.438 | [-0.574, -0.299] |
| **minilm-dense-v2** | +3 pts | [-5, +13] | 0.61 | -0.093 | [-0.186, -0.011] |
| **minilm-dense-v2-perpage** | +0 pts | [-8, +8] | 0.34 | -0.038 | [-0.096, +0.006] |
| **keyword-v2-600** | -23 pts | [-38, -8] | 0.00 | -0.287 | [-0.414, -0.149] |
| **minilm-dense-v2-600** | +3 pts | [-8, +13] | 0.58 | -0.160 | [-0.252, -0.077] |
| **keyword-v2-400** | -21 pts | [-36, -5] | 0.00 | -0.238 | [-0.349, -0.132] |
| **minilm-dense-v2-400** | +3 pts | [-8, +15] | 0.58 | -0.116 | [-0.226, -0.000] |
| **default-hashing-noexpand** | +3 pts | [-10, +15] | 0.57 | -0.098 | [-0.229, +0.036] |
| **default-minilm-rerank-noexpand** | +10 pts | [+3, +21] | 0.99 | +0.053 | [-0.051, +0.158] |

## hit@3 by question type

| config | ambiguity (n=7) | direct (n=27) | paraphrase (n=5) |
|---|---:|---:|---:|
| **minilm-dense** | 86% | 89% | 60% |
| **hashing-dense** | 57% | 33% | 40% |
| **hybrid-hashing** | 71% | 59% | 60% |
| **hybrid-hashing-v2** | 86% | 63% | 60% |
| **bm25-v2** | 86% | 93% | 60% |
| **hybrid-minilm-v2** | 100% | 100% | 60% |
| **hybrid-minilm-v2-perpage** | 100% | 89% | 60% |
| **hybrid-minilm-rerank** | 100% | 100% | 60% |
| **hybrid-minilm-v2-rerank** | 100% | 100% | 60% |
| **keyword-v2** | 71% | 63% | 60% |
| **hashing-dense-v2** | 86% | 37% | 20% |
| **minilm-dense-v2** | 100% | 89% | 60% |
| **minilm-dense-v2-perpage** | 86% | 89% | 60% |
| **keyword-v2-600** | 86% | 59% | 40% |
| **minilm-dense-v2-600** | 100% | 89% | 60% |
| **keyword-v2-400** | 86% | 63% | 40% |
| **minilm-dense-v2-400** | 86% | 93% | 60% |
| **default-hashing-noexpand** | 86% | 93% | 60% |
| **default-minilm-rerank-noexpand** | 100% | 100% | 60% |

## Questions with no relevant passage in the top 5

**minilm-dense** (3):
- `r25` [direct] What is a B-tree? → got Data Structures Using Python.pdf (0.549), Data Structures Using Python.pdf (0.533), Data Structures Using Python.pdf (0.527)
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.548), Introduction to Computer Science.pdf (0.548), Introduction to Computer Science.pdf (0.514)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.512), Dsa.pdf (0.464), Dsa.pdf (0.443)

**hashing-dense** (20):
- `r01` [direct] What is a hash table and how does it store elements? → got Introduction to Computer Science.pdf (0.317), Introduction to Computer Science.pdf (0.302), Introduction to Computer Science.pdf (0.265)
- `r02` [direct] What is a hash collision? → got Introduction to Computer Science.pdf (0.264), Introduction to Computer Science.pdf (0.261), Introduction to Computer Science.pdf (0.259)
- `r05` [direct] What is the running time of breadth-first search? → got Data Structures Using Python.pdf (0.368), Introduction to Computer Science.pdf (0.301), Introduction to Computer Science.pdf (0.295)
- `r08` [direct] What is the heap property? → got Introduction to Computer Science.pdf (0.29), Introduction to Computer Science.pdf (0.281), Introduction to Computer Science.pdf (0.268)
- `r09` [direct] How does merge sort work? → got Introduction to Computer Science.pdf (0.192), Introduction to Computer Science.pdf (0.192), Dsa.pdf (0.18)
- `r11` [direct] What is a stack and in what order does it return elements? → got Introduction to Computer Science.pdf (0.29), Introduction to Computer Science.pdf (0.284), Introduction to Computer Science.pdf (0.269)
- `r12` [direct] What does a queue do? → got Introduction to Computer Science.pdf (0.227), Introduction to Computer Science.pdf (0.215), Introduction to Computer Science.pdf (0.214)
- `r14` [direct] How does quick sort work? → got Introduction to Computer Science.pdf (0.192), Introduction to Computer Science.pdf (0.19), Introduction to Computer Science.pdf (0.171)
- `r18` [direct] What is a graph? → got Data Structures Using Python.pdf (0.315), Data Structures Using Python.pdf (0.312), Introduction to Computer Science.pdf (0.295)
- `r19` [direct] What is a tree rotation in an AVL tree? → got Data Structures Using Python.pdf (0.337), Data Structures Using Python.pdf (0.311), Data Structures Using Python.pdf (0.309)
- `r20` [direct] How does insertion sort work and how fast is it? → got Introduction to Computer Science.pdf (0.28), Introduction to Computer Science.pdf (0.238), Introduction to Computer Science.pdf (0.235)
- `r21` [direct] What is dynamic programming? → got Introduction to Computer Science.pdf (0.274), Introduction to Computer Science.pdf (0.27), Introduction to Computer Science.pdf (0.247)
- `r22` [direct] What is recursion? → got Dsa.pdf (0.252), Introduction to Computer Science.pdf (0.249), Introduction to Computer Science.pdf (0.249)
- `r24` [direct] What are heaps most commonly used for? → got Introduction to Computer Science.pdf (0.234), Introduction to Computer Science.pdf (0.224), Introduction to Computer Science.pdf (0.212)
- `r26` [paraphrase] How can I find the shortest route between two places in a weighted road network? → got Introduction to Computer Science.pdf (0.286), Introduction to Computer Science.pdf (0.264), Dsa.pdf (0.256)
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.232), Introduction to Computer Science.pdf (0.214), Introduction to Computer Science.pdf (0.204)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.294), Data Structures Using Python.pdf (0.239), Introduction to Computer Science.pdf (0.231)
- `r33` [ambiguity] What is a heap? → got Introduction to Computer Science.pdf (0.293), Introduction to Computer Science.pdf (0.29), Dsa.pdf (0.289)
- `r44` [direct] How do hash tables handle collisions? → got Introduction to Computer Science.pdf (0.178), Introduction to Computer Science.pdf (0.158), Dsa.pdf (0.152)
- `r45` [direct] What is collision resolution in hashing? → got Dsa.pdf (0.314), Data Structures Using Python.pdf (0.255), Introduction to Computer Science.pdf (0.218)

**hybrid-hashing** (11):
- `r08` [direct] What is the heap property? → got Dsa.pdf (0.254), Dsa.pdf (0.253), Dsa.pdf (0.249)
- `r09` [direct] How does merge sort work? → got Dsa.pdf (0.169), Dsa.pdf (0.166), Introduction to Computer Science.pdf (0.132)
- `r11` [direct] What is a stack and in what order does it return elements? → got Introduction to Computer Science.pdf (0.26), Dsa.pdf (0.235), Introduction to Computer Science.pdf (0.238)
- `r14` [direct] How does quick sort work? → got Dsa.pdf (0.169), Data Structures Using Python.pdf (0.152), Dsa.pdf (0.14)
- `r18` [direct] What is a graph? → got Data Structures Using Python.pdf (0.282), Data Structures Using Python.pdf (0.272), Data Structures Using Python.pdf (0.315)
- `r19` [direct] What is a tree rotation in an AVL tree? → got Data Structures Using Python.pdf (0.337), Dsa.pdf (0.279), Data Structures Using Python.pdf (0.243)
- `r20` [direct] How does insertion sort work and how fast is it? → got Dsa.pdf (0.221), Dsa.pdf (0.228), Introduction to Computer Science.pdf (0.177)
- `r22` [direct] What is recursion? → got Introduction to Computer Science.pdf (0.191), Introduction to Computer Science.pdf (0.216), Dsa.pdf (0.165)
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.192), Introduction to Computer Science.pdf (0.191), Introduction to Computer Science.pdf (0.177)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.294), Data Structures Using Python.pdf (0.184), Data Structures Using Python.pdf (0.177)
- `r33` [ambiguity] What is a heap? → got Introduction to Computer Science.pdf (0.275), Dsa.pdf (0.289), Dsa.pdf (0.221)

**hybrid-hashing-v2** (10):
- `r02` [direct] What is a hash collision? → got Introduction to Computer Science.pdf (0.225), Introduction to Computer Science.pdf (0.193), Introduction to Computer Science.pdf (0.172)
- `r09` [direct] How does merge sort work? → got Dsa.pdf (0.154), Introduction to Computer Science.pdf (0.141), Dsa.pdf (0.17)
- `r11` [direct] What is a stack and in what order does it return elements? → got Introduction to Computer Science.pdf (0.225), Data Structures Using Python.pdf (0.225), Introduction to Computer Science.pdf (0.214)
- `r14` [direct] How does quick sort work? → got Dsa.pdf (0.156), Dsa.pdf (0.127), Dsa.pdf (0.117)
- `r18` [direct] What is a graph? → got Data Structures Using Python.pdf (0.298), Data Structures Using Python.pdf (0.262), Introduction to Computer Science.pdf (0.255)
- `r19` [direct] What is a tree rotation in an AVL tree? → got Data Structures Using Python.pdf (0.259), Data Structures Using Python.pdf (0.301), Data Structures Using Python.pdf (0.333)
- `r20` [direct] How does insertion sort work and how fast is it? → got Dsa.pdf (0.227), Data Structures Using Python.pdf (0.162), Dsa.pdf (0.173)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.287), Data Structures Using Python.pdf (0.193), Introduction to Computer Science.pdf (0.229)
- `r33` [ambiguity] What is a heap? → got Introduction to Computer Science.pdf (0.231), Introduction to Computer Science.pdf (0.259), Introduction to Computer Science.pdf (0.256)
- `r45` [direct] What is collision resolution in hashing? → got Introduction to Computer Science.pdf (0.162), Introduction to Computer Science.pdf (0.237), Introduction to Computer Science.pdf (0.165)

**bm25-v2** (2):
- `r29` [paraphrase] Which graph search visits every neighbour at one distance before going further out? → got Introduction to Computer Science.pdf (0.234), Introduction to Computer Science.pdf (0.206), Data Structures Using Python.pdf (0.199)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.613), Introduction to Computer Science.pdf (0.466), Introduction to Computer Science.pdf (0.462)

**hybrid-minilm-v2** (2):
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.534), Introduction to Computer Science.pdf (0.526), Introduction to Computer Science.pdf (0.434)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.556), Data Structures Using Python.pdf (0.386), Data Structures Using Python.pdf (0.472)

**hybrid-minilm-v2-perpage** (3):
- `r25` [direct] What is a B-tree? → got Introduction to Computer Science.pdf (0.49), Data Structures Using Python.pdf (0.527), Data Structures Using Python.pdf (0.49)
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.554), Introduction to Computer Science.pdf (0.536), Introduction to Computer Science.pdf (0.526)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.386), Data Structures Using Python.pdf (0.527), Data Structures Using Python.pdf (0.585)

**hybrid-minilm-rerank** (2):
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.496), Introduction to Computer Science.pdf (0.403), Introduction to Computer Science.pdf (0.548)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.393), Data Structures Using Python.pdf (0.512), Data Structures Using Python.pdf (0.349)

**hybrid-minilm-v2-rerank** (2):
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.534), Introduction to Computer Science.pdf (0.411), Introduction to Computer Science.pdf (0.526)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.386), Data Structures Using Python.pdf (0.556), Introduction to Computer Science.pdf (0.313)

**keyword-v2** (9):
- `r12` [direct] What does a queue do? → got Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0)
- `r18` [direct] What is a graph? → got Introduction to Computer Science.pdf (1.0), Data Structures Using Python.pdf (1.0), Introduction to Computer Science.pdf (1.0)
- `r19` [direct] What is a tree rotation in an AVL tree? → got Data Structures Using Python.pdf (1.0), Dsa.pdf (1.0), Data Structures Using Python.pdf (1.0)
- `r25` [direct] What is a B-tree? → got Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0), Introduction to Computer Science.pdf (1.0)
- `r28` [paraphrase] How can computers share files that live on several servers? → got Introduction to Computer Science.pdf (0.667), Introduction to Computer Science.pdf (0.667), Introduction to Computer Science.pdf (0.5)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.8), Data Structures Using Python.pdf (0.6), Introduction to Computer Science.pdf (0.6)
- `r33` [ambiguity] What is a heap? → got Dsa.pdf (1.0), Dsa.pdf (1.0), Dsa.pdf (1.0)
- `r40` [ambiguity] Difference between BFS and DFS? → got Introduction to Computer Science.pdf (0.5), Introduction to Computer Science.pdf (0.5), Introduction to Computer Science.pdf (0.5)
- `r45` [direct] What is collision resolution in hashing? → got Introduction to Computer Science.pdf (0.333), Introduction to Computer Science.pdf (0.333), Introduction to Computer Science.pdf (0.333)

**hashing-dense-v2** (21):
- `r01` [direct] What is a hash table and how does it store elements? → got Introduction to Computer Science.pdf (0.268), Introduction to Computer Science.pdf (0.266), Introduction to Computer Science.pdf (0.26)
- `r02` [direct] What is a hash collision? → got Introduction to Computer Science.pdf (0.275), Introduction to Computer Science.pdf (0.258), Introduction to Computer Science.pdf (0.248)
- `r05` [direct] What is the running time of breadth-first search? → got Data Structures Using Python.pdf (0.34), Dsa.pdf (0.277), Introduction to Computer Science.pdf (0.269)
- `r08` [direct] What is the heap property? → got Introduction to Computer Science.pdf (0.291), Introduction to Computer Science.pdf (0.277), Introduction to Computer Science.pdf (0.273)
- `r09` [direct] How does merge sort work? → got Introduction to Computer Science.pdf (0.177), Data Structures Using Python.pdf (0.173), Dsa.pdf (0.17)
- `r11` [direct] What is a stack and in what order does it return elements? → got Introduction to Computer Science.pdf (0.263), Introduction to Computer Science.pdf (0.26), Introduction to Computer Science.pdf (0.259)
- `r12` [direct] What does a queue do? → got Introduction to Computer Science.pdf (0.229), Introduction to Computer Science.pdf (0.206), Introduction to Computer Science.pdf (0.197)
- `r14` [direct] How does quick sort work? → got Introduction to Computer Science.pdf (0.192), Introduction to Computer Science.pdf (0.168), Introduction to Computer Science.pdf (0.163)
- `r18` [direct] What is a graph? → got Data Structures Using Python.pdf (0.298), Introduction to Computer Science.pdf (0.27), Introduction to Computer Science.pdf (0.265)
- `r19` [direct] What is a tree rotation in an AVL tree? → got Data Structures Using Python.pdf (0.333), Data Structures Using Python.pdf (0.301), Data Structures Using Python.pdf (0.273)
- `r20` [direct] How does insertion sort work and how fast is it? → got Introduction to Computer Science.pdf (0.268), Introduction to Computer Science.pdf (0.235), Introduction to Computer Science.pdf (0.232)
- `r21` [direct] What is dynamic programming? → got Introduction to Computer Science.pdf (0.263), Introduction to Computer Science.pdf (0.251), Introduction to Computer Science.pdf (0.238)
- `r22` [direct] What is recursion? → got Dsa.pdf (0.252), Introduction to Computer Science.pdf (0.251), Introduction to Computer Science.pdf (0.242)
- `r24` [direct] What are heaps most commonly used for? → got Introduction to Computer Science.pdf (0.216), Data Structures Using Python.pdf (0.209), Introduction to Computer Science.pdf (0.199)
- `r25` [direct] What is a B-tree? → got Introduction to Computer Science.pdf (0.282), Introduction to Computer Science.pdf (0.282), Introduction to Computer Science.pdf (0.282)
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.214), Introduction to Computer Science.pdf (0.205), Introduction to Computer Science.pdf (0.198)
- `r28` [paraphrase] How can computers share files that live on several servers? → got Introduction to Computer Science.pdf (0.22), Introduction to Computer Science.pdf (0.216), Introduction to Computer Science.pdf (0.206)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.287), Data Structures Using Python.pdf (0.25), Introduction to Computer Science.pdf (0.245)
- `r33` [ambiguity] What is a heap? → got Introduction to Computer Science.pdf (0.296), Introduction to Computer Science.pdf (0.292), Introduction to Computer Science.pdf (0.292)
- `r44` [direct] How do hash tables handle collisions? → got Introduction to Computer Science.pdf (0.189), Introduction to Computer Science.pdf (0.158), Introduction to Computer Science.pdf (0.149)
- `r45` [direct] What is collision resolution in hashing? → got Dsa.pdf (0.309), Data Structures Using Python.pdf (0.247), Introduction to Computer Science.pdf (0.237)

**minilm-dense-v2** (3):
- `r21` [direct] What is dynamic programming? → got Introduction to Computer Science.pdf (0.56), Introduction to Computer Science.pdf (0.545), Introduction to Computer Science.pdf (0.529)
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.55), Introduction to Computer Science.pdf (0.534), Introduction to Computer Science.pdf (0.526)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.556), Data Structures Using Python.pdf (0.472), Dsa.pdf (0.438)

**minilm-dense-v2-perpage** (3):
- `r25` [direct] What is a B-tree? → got Introduction to Computer Science.pdf (0.529), Data Structures Using Python.pdf (0.527), Data Structures Using Python.pdf (0.523)
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.554), Introduction to Computer Science.pdf (0.55), Introduction to Computer Science.pdf (0.536)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.585), Data Structures Using Python.pdf (0.527), Dsa.pdf (0.435)

**keyword-v2-600** (12):
- `r04` [direct] How does depth-first search work? → got Data Structures Using Python.pdf (0.75), Introduction to Computer Science.pdf (0.75), Introduction to Computer Science.pdf (0.75)
- `r11` [direct] What is a stack and in what order does it return elements? → got Introduction to Computer Science.pdf (0.75), Introduction to Computer Science.pdf (0.75), Introduction to Computer Science.pdf (0.75)
- `r12` [direct] What does a queue do? → got Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0)
- `r14` [direct] How does quick sort work? → got Dsa.pdf (0.667), Dsa.pdf (0.667), Data Structures Using Python.pdf (0.667)
- `r18` [direct] What is a graph? → got Data Structures Using Python.pdf (1.0), Introduction to Computer Science.pdf (1.0), Introduction to Computer Science.pdf (1.0)
- `r19` [direct] What is a tree rotation in an AVL tree? → got Data Structures Using Python.pdf (1.0), Dsa.pdf (1.0), Data Structures Using Python.pdf (1.0)
- `r20` [direct] How does insertion sort work and how fast is it? → got Data Structures Using Python.pdf (0.75), Dsa.pdf (0.5), Data Structures Using Python.pdf (0.5)
- `r25` [direct] What is a B-tree? → got Introduction to Computer Science.pdf (1.0), Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0)
- `r28` [paraphrase] How can computers share files that live on several servers? → got Introduction to Computer Science.pdf (0.667), Introduction to Computer Science.pdf (0.5), Introduction to Computer Science.pdf (0.5)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.6), Introduction to Computer Science.pdf (0.6), Introduction to Computer Science.pdf (0.6)
- `r40` [ambiguity] Difference between BFS and DFS? → got Introduction to Computer Science.pdf (0.5), Data Structures Using Python.pdf (0.5), Introduction to Computer Science.pdf (0.5)
- `r45` [direct] What is collision resolution in hashing? → got Introduction to Computer Science.pdf (0.333), Introduction to Computer Science.pdf (0.333), Introduction to Computer Science.pdf (0.333)

**minilm-dense-v2-600** (3):
- `r25` [direct] What is a B-tree? → got Introduction to Computer Science.pdf (0.591), Introduction to Computer Science.pdf (0.556), Dsa.pdf (0.535)
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.552), Introduction to Computer Science.pdf (0.552), Introduction to Computer Science.pdf (0.544)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.556), Data Structures Using Python.pdf (0.495), Dsa.pdf (0.477)

**keyword-v2-400** (9):
- `r14` [direct] How does quick sort work? → got Data Structures Using Python.pdf (0.667), Dsa.pdf (0.667), Dsa.pdf (0.667)
- `r18` [direct] What is a graph? → got Introduction to Computer Science.pdf (1.0), Introduction to Computer Science.pdf (1.0), Introduction to Computer Science.pdf (1.0)
- `r19` [direct] What is a tree rotation in an AVL tree? → got Dsa.pdf (1.0), Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0)
- `r20` [direct] How does insertion sort work and how fast is it? → got Data Structures Using Python.pdf (0.75), Data Structures Using Python.pdf (0.75), Data Structures Using Python.pdf (0.5)
- `r25` [direct] What is a B-tree? → got Data Structures Using Python.pdf (1.0), Data Structures Using Python.pdf (1.0), Introduction to Computer Science.pdf (1.0)
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.571), Introduction to Computer Science.pdf (0.571), Introduction to Computer Science.pdf (0.571)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.6), Data Structures Using Python.pdf (0.6), Introduction to Computer Science.pdf (0.6)
- `r40` [ambiguity] Difference between BFS and DFS? → got Introduction to Computer Science.pdf (0.5), Data Structures Using Python.pdf (0.5), Introduction to Computer Science.pdf (0.5)
- `r45` [direct] What is collision resolution in hashing? → got Introduction to Computer Science.pdf (0.333), Introduction to Computer Science.pdf (0.333), Introduction to Computer Science.pdf (0.333)

**minilm-dense-v2-400** (4):
- `r24` [direct] What are heaps most commonly used for? → got Introduction to Computer Science.pdf (0.58), Introduction to Computer Science.pdf (0.579), Introduction to Computer Science.pdf (0.577)
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.593), Introduction to Computer Science.pdf (0.578), Introduction to Computer Science.pdf (0.553)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.585), Data Structures Using Python.pdf (0.495), Data Structures Using Python.pdf (0.488)
- `r33` [ambiguity] What is a heap? → got Introduction to Computer Science.pdf (0.723), Introduction to Computer Science.pdf (0.681), Introduction to Computer Science.pdf (0.672)

**default-hashing-noexpand** (2):
- `r29` [paraphrase] Which graph search visits every neighbour at one distance before going further out? → got Introduction to Computer Science.pdf (0.234), Introduction to Computer Science.pdf (0.206), Data Structures Using Python.pdf (0.199)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.613), Introduction to Computer Science.pdf (0.466), Introduction to Computer Science.pdf (0.462)

**default-minilm-rerank-noexpand** (2):
- `r27` [paraphrase] Which technique splits a problem into subproblems and caches each result? → got Introduction to Computer Science.pdf (0.534), Introduction to Computer Science.pdf (0.411), Introduction to Computer Science.pdf (0.526)
- `r30` [paraphrase] Which structure removes the element that was added last? → got Data Structures Using Python.pdf (0.386), Data Structures Using Python.pdf (0.556), Introduction to Computer Science.pdf (0.313)

## Unanswerable questions: top score

| question | minilm-dense | hashing-dense | hybrid-hashing | hybrid-hashing-v2 | bm25-v2 | hybrid-minilm-v2 | hybrid-minilm-v2-perpage | hybrid-minilm-rerank | hybrid-minilm-v2-rerank | keyword-v2 | hashing-dense-v2 | minilm-dense-v2 | minilm-dense-v2-perpage | keyword-v2-600 | minilm-dense-v2-600 | keyword-v2-400 | minilm-dense-v2-400 | default-hashing-noexpand | default-minilm-rerank-noexpand |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| What is the capital of Australia? | 0.19 | 0.34 | 0.11 | 0.11 | 0.23 | 0.10 | 0.11 | 0.03 | 0.02 | 0.50 | 0.33 | 0.19 | 0.17 | 0.50 | 0.22 | 0.50 | 0.21 | 0.23 | 0.02 |
| Who won the 2018 football world cup? | 0.22 | 0.25 | 0.16 | 0.19 | 0.11 | 0.11 | 0.08 | 0.12 | 0.11 | 0.40 | 0.19 | 0.22 | 0.22 | 0.40 | 0.22 | 0.20 | 0.20 | 0.11 | 0.11 |
| What is a good recipe for sourdough bread? | 0.33 | 0.27 | 0.22 | 0.24 | 0.21 | 0.25 | 0.29 | 0.20 | 0.25 | 0.25 | 0.25 | 0.25 | 0.29 | 0.25 | 0.28 | 0.25 | 0.36 | 0.21 | 0.25 |
| What is the boiling point of water in Fahrenheit? | 0.33 | 0.30 | 0.26 | 0.23 | 0.15 | 0.25 | 0.24 | 0.19 | 0.25 | 0.25 | 0.28 | 0.30 | 0.32 | 0.25 | 0.32 | 0.25 | 0.41 | 0.15 | 0.25 |
| Summarize the plot of the play Hamlet. | 0.24 | 0.31 | 0.28 | 0.29 | 0.15 | 0.14 | 0.14 | 0.19 | 0.19 | 0.25 | 0.33 | 0.28 | 0.32 | 0.25 | 0.32 | 0.25 | 0.36 | 0.15 | 0.19 |
| How many moons does Jupiter have? | 0.25 | 0.19 | 0.13 | 0.14 | 0.18 | 0.01 | 0.05 | 0.22 | 0.09 | 0.50 | 0.18 | 0.26 | 0.26 | 0.50 | 0.25 | 0.50 | 0.28 | 0.18 | 0.09 |
| How does open addressing resolve collisions with linear probing? | 0.41 | 0.16 | 0.13 | 0.11 | 0.21 | 0.36 | 0.36 | 0.29 | 0.18 | 0.33 | 0.15 | 0.39 | 0.39 | 0.33 | 0.37 | 0.33 | 0.42 | 0.21 | 0.18 |
| *median of answerable questions* | 0.67 | 0.29 | 0.25 | 0.23 | 0.64 | 0.66 | 0.68 | 0.61 | 0.63 | 1.00 | 0.27 | 0.68 | 0.68 | 1.00 | 0.70 | 1.00 | 0.72 | 0.65 | 0.63 |
