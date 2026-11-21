"""The browser-test API server with fuller scripted replies, for the README screenshots.

    python tests/screenshot_server.py [port]

Everything except the language model is real (see tests/e2e_server.py). The replies below are written by hand
from the two fixture PDFs in apps/web/e2e/fixtures, so no API key or network is needed. They are not model output.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.e2e_server import FakeGemini, app, port  # noqa: E402

HEAP = "heaps.pdf (page 1)"
GRAPH = "graphs.pdf (page 1)"

CONCEPT_MAP = {
    "nodes": [
        {"id": "heap", "label": "Binary heap"},
        {"id": "tree", "label": "Complete binary tree"},
        {"id": "pq", "label": "Priority queue"},
        {"id": "min-heap", "label": "Min-heap"},
        {"id": "order", "label": "Parent ≤ children"},
        {"id": "insert", "label": "Insert"},
        {"id": "extract", "label": "Extract-min"},
        {"id": "log", "label": "O(log n)"},
    ],
    "edges": [
        {"from": "heap", "to": "tree", "label": "is a"},
        {"from": "heap", "to": "pq", "label": "implements"},
        {"from": "min-heap", "to": "heap", "label": "is a"},
        {"from": "min-heap", "to": "order", "label": "keeps"},
        {"from": "heap", "to": "insert", "label": "supports"},
        {"from": "heap", "to": "extract", "label": "supports"},
        {"from": "insert", "to": "log", "label": "takes"},
        {"from": "extract", "to": "log", "label": "takes"},
    ],
}

SOCRATIC = {
    "questions": [
        "In a min-heap, what must be true of every parent and its children?",
        "Given that rule, where in the tree must the smallest value be?",
        "How tall is a complete binary tree holding n values?",
        "How many levels can a new value move through after an insert?",
    ],
    "hints": [
        "Start from the ordering rule and follow it up the tree to the root.",
        "A complete tree fills each level before starting the next, so its height grows with log n.",
        "Each swap moves a value one level, so count the levels rather than the values.",
    ],
}

STUDY_GUIDE = """## Key observation

For each number `x`, the value you need is `target - x`. Remembering the numbers already seen makes that check O(1).

## Approach

1. Keep a hash map from value to index.
2. For each `x`, look up `target - x`.
3. If it is there, return both indices. Otherwise store `x`.

```python
def two_sum(nums, target):
    seen = {}
    for i, x in enumerate(nums):
        if target - x in seen:
            return [seen[target - x], i]
        seen[x] = i
```

## Complexity

O(n) time and O(n) space.
"""


def reply(prompt: str, json_mode: bool) -> str:
    if "study map" in prompt.lower():
        return json.dumps(CONCEPT_MAP)
    if "Socratic tutor" in prompt:
        return json.dumps(SOCRATIC)
    if "algorithms mentor" in prompt:
        return STUDY_GUIDE
    if "TASK:" not in prompt and "flashcard author" not in prompt and "study corpus" not in prompt:
        labels = re.findall(r"^- \[(.+?)\] ", prompt, re.MULTILINE)
        if HEAP in labels:
            return (
                f"A **binary heap** is a complete binary tree used to implement a priority queue. [{HEAP}]\n\n"
                f"- **Ordering:** in a min-heap, every parent is smaller than or equal to its children. [{HEAP}]\n"
                f"- **Cost:** insert and extract-min both take O(log n) time. [{HEAP}]"
            )
        if GRAPH in labels:
            return (
                f"**Breadth-first search** explores a graph level by level using a queue. [{GRAPH}]\n\n"
                f"**Depth-first search** follows a path as deep as possible using a stack or recursion. [{GRAPH}]"
            )
    return FakeGemini.default_reply(prompt, json_mode)


if __name__ == "__main__":
    import uvicorn

    FakeGemini.handler = staticmethod(reply)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
