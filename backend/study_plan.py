"""LeetCode study plan from what you have (not) solved.

Pure function over plain data, so it is easy to test. For each topic it counts the problems you attempted
and solved; a topic is **weak** when you attempted some of it and solved under half of what you tried.
The plan then lists unsolved problems from the weakest topics first, easiest first (so each session starts
with something winnable), skipping problems already solved. With no history at all it falls back to
the most common topics of the bank.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Mapping

DIFFICULTY_ORDER = {"easy": 0, "medium": 1, "hard": 2}


def topic_stats(progress: Mapping[str, Mapping[str, Any]], problems: Mapping[str, Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Per topic: attempted, solved, solve_rate. `progress` maps pid -> {status}; `problems` maps pid -> {topics, ...}."""
    attempted: Dict[str, int] = defaultdict(int)
    solved: Dict[str, int] = defaultdict(int)
    for pid, row in progress.items():
        if row["status"] == "todo":
            continue
        for t in (problems.get(pid) or {}).get("topics") or row.get("topics") or []:
            attempted[t] += 1
            if row["status"] == "solved":
                solved[t] += 1
    out = [{"topic": t, "attempted": n, "solved": solved[t], "solve_rate": solved[t] / n} for t, n in attempted.items()]
    return sorted(out, key=lambda r: (r["solve_rate"], -r["attempted"], r["topic"]))


def build_plan(
    progress: Mapping[str, Mapping[str, Any]],
    problems: Iterable[Mapping[str, Any]],
    size: int = 10,
    weak_below: float = 0.5,
) -> Dict[str, Any]:
    """{weak_topics, topics, items}. Each item: pid, title, difficulty, topics, reason."""
    bank = {p["pid"]: p for p in problems}
    stats = topic_stats(progress, bank)
    weak = [s["topic"] for s in stats if s["solve_rate"] < weak_below]
    done = {pid for pid, r in progress.items() if r["status"] == "solved"}

    def rank(p: Mapping[str, Any]) -> tuple:
        return (DIFFICULTY_ORDER.get((p.get("difficulty") or "").lower(), 3), p["title"])

    items: List[Dict[str, Any]] = []
    seen = set()
    for topic in weak:
        candidates = sorted((p for p in bank.values() if topic in (p.get("topics") or []) and p["pid"] not in done), key=rank)
        for p in candidates[:3]:
            if p["pid"] not in seen and len(items) < size:
                seen.add(p["pid"])
                items.append({**_brief(p), "reason": f"Weak topic: {topic}"})
    if len(items) < size:  # top up with unsolved easy problems from topics you have not tried
        tried = {s["topic"] for s in stats}
        fresh = sorted((p for p in bank.values() if p["pid"] not in done and p["pid"] not in seen
                        and not set(p.get("topics") or []) & tried), key=rank)
        for p in fresh[: size - len(items)]:
            items.append({**_brief(p), "reason": "New topic" if tried else "Good place to start"})
    return {"weak_topics": weak, "topics": stats, "items": items}


def _brief(p: Mapping[str, Any]) -> Dict[str, Any]:
    return {"pid": p["pid"], "title": p["title"], "difficulty": p.get("difficulty") or "", "topics": list(p.get("topics") or [])}
