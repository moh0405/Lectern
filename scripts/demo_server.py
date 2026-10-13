"""Run the real API offline, for demos and screenshots.

    python scripts/demo_server.py [port]

What is real and what is not:

- REAL: indexing, chunking, MiniLM embeddings, hybrid retrieval, citation checking, caching, analytics,
  the embedding-map projection. The corpus is the committed synthetic one (`eval/corpus/*.md`, written for
  this repo, so nothing here is copyrighted).
- SCRIPTED: the language model. Without an API key there is no real model, so answers, concept maps and
  study guides come from the small `DemoModel` below. They are written to be grounded in the retrieved
  passages and to cite them the way the real prompt asks, but they are not model output.
  Run the app with a `GEMINI_API_KEY` for real answers.

Needs the `embeddings` extra (sentence-transformers); falls back to the hashing embedder if it is missing.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# NOTE: the math tool runs in a *spawned* worker process, and `spawn` re-imports this script as a module.
# So everything with side effects (indexing, starting the server) lives in main(), under the __main__ guard.

# --------------------------------------------------------------------------------------------- scripted model
ANSWERS = [
    (
        r"hash|collision",
        "hashing.md",
        "A hash table has to deal with **collisions**: two different keys that land in the same bucket. There are two classic strategies.\n\n"
        "- **Separate chaining**: every bucket holds a small list of entries. A lookup hashes to the bucket and scans that list. [{doc}]\n"
        "- **Open addressing**: every entry lives in the array itself. On a collision the table probes for another free slot (linear probing, "
        "quadratic probing, or double hashing). [{doc}]\n\n"
        "Both stay O(1) on average as long as the **load factor** (entries per bucket) is kept low, which is why tables resize, usually by "
        "doubling, once they get too full. [{doc}]",
    ),
    (
        r"bfs|dfs|breadth|depth",
        "graphs.md",
        "Both visit every vertex in O(V + E) time; the difference is the **order of exploration**.\n\n"
        "| | BFS | DFS |\n|---|---|---|\n| Data structure | queue | stack or recursion |\n| Shape | wide, level by level | deep, as far as possible first |\n"
        "| Finds shortest paths (unweighted) | yes | no |\n\n"
        "BFS discovers vertices in order of distance, so it finds shortest paths in an unweighted graph. [{doc}] DFS goes deep before "
        "backtracking and is the tool for cycle detection, connected components and topological ordering. [{doc}]",
    ),
    (
        r"heap",
        "trees.md",
        "A **binary heap** is a complete binary tree that satisfies the **heap property**: in a min-heap every parent is smaller than or "
        "equal to its children, so the smallest element is always at the root. [{doc}]\n\n"
        "Because the tree is complete it fits in an array, where the children of index *i* are at *2i + 1* and *2i + 2*. Insertion and "
        "removal of the minimum are both O(log n), and building a heap from n items takes only O(n). [{doc}] This is why heaps are the "
        "standard implementation of a **priority queue**.",
    ),
    (
        r"quick|merge|sort",
        "sorting.md",
        "Both are divide-and-conquer sorts with O(n log n) typical cost, but they trade off differently.\n\n"
        "- **Quicksort** partitions around a pivot and sorts in place with little extra memory, but its worst case is O(n²) when pivots are "
        "badly chosen. [{doc}]\n- **Merge sort** is O(n log n) in every case and **stable**, at the price of O(n) extra space. [{doc}]\n\n"
        "That is why merge sort is popular for linked lists and external sorting, and quicksort for in-memory arrays.",
    ),
    (
        r"distributed|file system|dfs|replic",
        "file-systems.md",
        "A **distributed file system** lets many machines share files over a network as if they were local, while hiding where the data "
        "really lives. [{doc}]\n\nTo survive machine failures it **replicates blocks** across several servers: HDFS, for example, splits "
        "files into 128 MB blocks and keeps three copies of each on different DataNodes, with a central NameNode tracking where everything "
        "is. [{doc}]",
    ),
    (
        r"dynamic|memo|dp\b",
        "dp-greedy.md",
        "**Dynamic programming** solves a problem by breaking it into *overlapping subproblems* and storing each answer so it is computed "
        "only once. [{doc}] It applies when the problem has optimal substructure.\n\nThere are two styles: **memoization** (top-down: write the "
        "recursion, cache results) and **tabulation** (bottom-up: fill a table from the base cases). [{doc}]",
    ),
]

CONCEPT_MAP = {
    "nodes": [
        {"id": "hash-table", "label": "Hash table"}, {"id": "hash-function", "label": "Hash function"},
        {"id": "bucket", "label": "Bucket"}, {"id": "collision", "label": "Collision"},
        {"id": "chaining", "label": "Separate chaining"}, {"id": "open-addressing", "label": "Open addressing"},
        {"id": "probing", "label": "Probing"}, {"id": "load-factor", "label": "Load factor"},
        {"id": "resizing", "label": "Resizing"}, {"id": "amortized", "label": "Amortized O(1)"},
    ],
    "edges": [
        {"from": "hash-table", "to": "hash-function", "label": "uses"}, {"from": "hash-function", "to": "bucket", "label": "chooses"},
        {"from": "bucket", "to": "collision", "label": "may suffer"}, {"from": "collision", "to": "chaining", "label": "resolved by"},
        {"from": "collision", "to": "open-addressing", "label": "resolved by"}, {"from": "open-addressing", "to": "probing", "label": "needs"},
        {"from": "hash-table", "to": "load-factor", "label": "tracks"}, {"from": "load-factor", "to": "resizing", "label": "triggers"},
        {"from": "resizing", "to": "amortized", "label": "gives"},
    ],
}
SOCRATIC = {
    "questions": [
        "What does a hash function turn a key into, and what happens to that number next?",
        "If two keys end up in the same bucket, what information would you need to keep both?",
        "What happens to lookup speed as more and more entries pile into the same buckets?",
        "How could the table notice that it is getting too crowded?",
    ],
    "hints": [
        "Think about the difference between *finding* a bucket and *searching inside* it.",
        "A bucket does not have to hold exactly one entry. What could it hold instead?",
        "The ratio of entries to buckets is what controls how long the searches inside buckets get.",
    ],
}
SYNTHESIS = {
    "similarities": ["Both treat a hash table as an array of buckets indexed by a hash function.", "Both rely on keeping the load factor low."],
    "conflicts": ["The notes differ on whether open addressing or chaining is the better default."],
    "synthesis": "A hash table maps keys to buckets with a hash function; collisions are unavoidable and are handled by chaining or probing, "
                 "and the load factor controls when the table grows. Chaining degrades gracefully, while open addressing is cache-friendly but "
                 "slows sharply as it fills.",
    "citations": [{"doc": "hashing.md", "point": "defines collisions, chaining and open addressing"}],
}
TWO_SUM_GUIDE = (
    "## Key observation\nFor each number `x` you only need to know whether `target - x` has already been seen.\n\n"
    "## Approach\n1. Walk the array once, keeping a dictionary from value to index.\n2. For each `x`, check whether `target - x` is in the "
    "dictionary; if so, return both indices.\n3. Otherwise store `x`.\n\n## Complexity\n- Time: **O(n)**, one pass with O(1) dictionary lookups\n"
    "- Space: **O(n)** for the dictionary\n\n## Pitfall\nDo not use the same element twice: check the dictionary *before* inserting `x`.\n\n"
    "```python\ndef two_sum(nums, target):\n    seen = {}\n    for i, x in enumerate(nums):\n        if target - x in seen:\n            return [seen[target - x], i]\n"
    "        seen[x] = i\n```"
)


class DemoModel:
    """Scripted stand-in for GeminiClient. See the module docstring: this is not a real model."""

    def __init__(self, model=None, temperature=0.2, **kw):
        self.model = model or "demo-scripted-model"

    def list_supported_models(self):
        return ["demo-scripted-model"]

    @staticmethod
    def _labels(prompt: str):
        return re.findall(r"^- \[(.+?)\]", prompt, re.M)

    def _answer(self, prompt: str, json_mode: bool) -> str:
        low = prompt.lower()
        if json_mode and "study map" in low:
            return json.dumps(CONCEPT_MAP)
        if json_mode and "socratic" in low:
            return json.dumps(SOCRATIC)
        if json_mode and "synthesizer" in low:
            return json.dumps(SYNTHESIS)
        if "algorithms mentor" in low:
            return TWO_SUM_GUIDE
        if "study note generator" in low:
            return "# Study notes\n\n## Summary\nThis session covered how hash tables resolve collisions and how graph traversals differ.\n\n## Key points\n- Chaining and open addressing resolve collisions.\n- Keep the load factor low to stay O(1).\n- BFS uses a queue and finds shortest paths; DFS goes deep.\n"
        if "study corpus" in low:
            return (
                "1. How does a hash table handle collisions?\n2. What is the difference between BFS and DFS?\n"
                "3. Why is merge sort stable?\n4. What is the heap property?\n5. When is dynamic programming better than greedy?"
            )
        m = re.search(r"Question:\s*(.+)", prompt)
        question = (m.group(1) if m else prompt).lower()
        labels = self._labels(prompt)
        for pattern, doc, template in ANSWERS:
            if re.search(pattern, question):
                label = next((lab for lab in labels if lab.startswith(doc.split(".")[0])), labels[0] if labels else doc)
                return template.replace("{doc}", label)
        ctx = re.search(r"^- \[(.+?)\] (.+)$", prompt, re.M)
        if ctx:
            first = " ".join(re.split(r"(?<=[.!?])\s+", ctx.group(2))[:2])
            return f"Based on your material: {first} [{ctx.group(1)}]"
        return "I could not find that in your sources."

    def generate(self, prompt, temperature=None, json_mode=False):
        return {"ok": True, "model": self.model, "answer": self._answer(prompt, json_mode)}

    def stream(self, prompt, temperature=None, json_mode=False):
        text = self._answer(prompt, json_mode)
        time.sleep(0.25)  # time to first token
        for w in re.split(r"(?<=\s)", text):
            time.sleep(0.012)  # roughly the pace of a real streamed answer
            yield w



def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8200
    work = Path(tempfile.mkdtemp(prefix="asm-demo-"))
    os.environ.update(
        UPLOAD_DIR=str(work / "uploads"),
        STORE_DIR=str(work / "store"),
        ANALYTICS_DB=str(work / "analytics.db"),
        CORS_ORIGINS=os.getenv("DEMO_WEB_ORIGIN", "http://localhost:3200"),
        RATE_LIMIT_PER_MIN="100000",
        GEMINI_API_KEY="",
    )
    os.chdir(work)
    (work / "data" / "leetcode").mkdir(parents=True)
    src = ROOT / "data" / "leetcode" / "normalized_problems.jsonl"
    if src.exists():
        shutil.copy(src, work / "data" / "leetcode" / "normalized_problems.jsonl")

    for module_name in ("backend.llm_config", "backend.advanced_ai", "backend.leetcode_handler", "backend.api.routers.ask"):
        __import__(module_name)
        sys.modules[module_name].GeminiClient = DemoModel

    from eval.harness import CONFIGS, CORPORA, build_store

    print("Indexing the synthetic corpus (real chunking and embeddings)...", flush=True)
    try:
        built = build_store(CORPORA["synthetic"], CONFIGS["default-minilm"])
    except Exception as e:  # sentence-transformers missing or offline: keep the demo usable
        print(f"MiniLM unavailable ({e}); using the hashing embedder", flush=True)
        built = build_store(CORPORA["synthetic"], CONFIGS["default-hashing"])
    shutil.copytree(built, work / "store", dirs_exist_ok=True)

    import uvicorn

    from backend.api import app

    print(f"Demo API on http://127.0.0.1:{port}  (storage: {work})", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
