"""LeetCode study plan from what you have (not) solved.

Pure function over plain data, so it is easy to test. For each topic it counts the problems you attempted
and solved; a topic is **weak** once you have tried at least `MIN_EVIDENCE` of its problems and solved under
half of them (one unlucky attempt is not enough to call a topic weak). The plan then lists unsolved problems
from the weakest topics first, easiest and best-known first (so each session starts with something winnable),
skipping problems already solved. With no history at all it starts from well-known easy fundamentals spread
over different topics.

Only algorithm problems are planned: database (SQL) and shell problems, and problems without topics (in this
bank those are SQL stubs whose description is just "SQL Schema"), are never suggested.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Mapping

DIFFICULTY_ORDER = {"easy": 0, "medium": 1, "hard": 2}
MIN_EVIDENCE = 2  # problems tried in a topic before it can be called weak
NON_ALGORITHM_TOPICS = {"database", "shell", "concurrency"}
PER_TOPIC_AT_START = 2  # spread suggestions for untried topics over several topics


def plannable(p: Mapping[str, Any]) -> bool:
    """Is this a problem worth suggesting? Algorithm problems with topics; no SQL, shell or topic-less stubs."""
    topics = [t for t in (p.get("topics") or []) if t]
    if not topics or {t.strip().lower() for t in topics} & NON_ALGORITHM_TOPICS:
        return False
    return not str(p.get("description") or "").strip().lower().startswith("sql schema")


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
    min_evidence: int = MIN_EVIDENCE,
) -> Dict[str, Any]:
    """{weak_topics, topics, items}. Each item: pid, title, difficulty, topics, reason."""
    bank = {p["pid"]: p for p in problems}
    stats = topic_stats(progress, bank)
    weak = [s["topic"] for s in stats if s["solve_rate"] < weak_below and s["attempted"] >= min_evidence]
    done = {pid for pid, r in progress.items() if r["status"] == "solved"}
    candidates = [p for p in bank.values() if plannable(p) and p["pid"] not in done]

    def rank(p: Mapping[str, Any]) -> tuple:
        # Easiest first; within a difficulty, the best-known problems (most likes) first.
        return (DIFFICULTY_ORDER.get((p.get("difficulty") or "").lower(), 3), -(p.get("likes") or 0), p["title"])

    items: List[Dict[str, Any]] = []
    seen = set()
    for topic in weak:
        for p in sorted((p for p in candidates if topic in (p.get("topics") or [])), key=rank)[:3]:
            if p["pid"] not in seen and len(items) < size:
                seen.add(p["pid"])
                items.append({**_brief(p), "reason": f"Weak topic: {topic}"})
    if len(items) < size:  # top up with unsolved problems from topics you have not tried, a couple per topic
        tried = {s["topic"] for s in stats}
        fresh = sorted((p for p in candidates if p["pid"] not in seen and not set(p.get("topics") or []) & tried), key=rank)
        room = size - len(items)
        per_topic: Dict[str, int] = defaultdict(int)
        picked: List[Mapping[str, Any]] = []
        for p in fresh:
            if len(picked) >= room:
                break
            lead = (p.get("topics") or [""])[0]
            if per_topic[lead] < PER_TOPIC_AT_START:
                per_topic[lead] += 1
                picked.append(p)
        if len(picked) < room:  # not enough variety: fill with the next best regardless of topic
            chosen = {p["pid"] for p in picked}
            picked += [p for p in fresh if p["pid"] not in chosen][: room - len(picked)]
        for p in picked:
            items.append({**_brief(p), "reason": "New topic" if tried else "Good place to start"})
    return {"weak_topics": weak, "topics": stats, "items": items}


def _brief(p: Mapping[str, Any]) -> Dict[str, Any]:
    return {"pid": p["pid"], "title": p["title"], "difficulty": p.get("difficulty") or "", "topics": list(p.get("topics") or [])}
