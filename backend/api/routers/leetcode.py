"""LeetCode problem bank: search, browse, and AI study guides."""

from __future__ import annotations

import threading
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.concurrency import run_in_threadpool

from ...leetcode_handler import LeetCodeHandler
from ..deps import common_dependencies, raise_if_failed
from ..errors import ERROR_RESPONSES, ApiError
from ..schemas import Explanation, Problem, ProblemSearch, ProblemStats, ProblemSummary

router = APIRouter(prefix="/api/v1/leetcode", tags=["leetcode"], dependencies=common_dependencies,
                   responses=ERROR_RESPONSES)

_load_lock = threading.Lock()


def get_leetcode(request: Request) -> LeetCodeHandler:
    """Loaded once per process, on first use (reads the cached normalized dataset; no network calls)."""
    handler = getattr(request.app.state, "leetcode", None)
    if handler is None:
        with _load_lock:
            handler = getattr(request.app.state, "leetcode", None)
            if handler is None:
                handler = LeetCodeHandler()
                handler.load_all(generate_embeddings=False)
                request.app.state.leetcode = handler
    if not handler.is_loaded():
        raise ApiError(503, "LeetCode dataset not available. Run: python scripts/prepare_leetcode_data.py",
                       code="dataset_unavailable")
    return handler


def _summary(d: dict) -> ProblemSummary:
    return ProblemSummary(
        pid=d["pid"], title=d["title"], difficulty=d.get("difficulty") or "", topics=d.get("topics") or [],
        acceptance=d.get("acceptance"), likes=d.get("likes"), dislikes=d.get("dislikes"),
        url=d.get("url"), score=d.get("score"), source=d.get("source"),
    )


@router.get("/stats", response_model=ProblemStats, summary="Counts by difficulty and the most common topics")
async def lc_stats(handler: LeetCodeHandler = Depends(get_leetcode)):
    s = handler.get_stats()
    return ProblemStats(total=s["total"], by_difficulty=s["by_difficulty"], top_topics=[list(t) for t in s["top_topics"]])


@router.get("/search", response_model=ProblemSearch, summary="Search problems (semantic when embeddings exist, else keyword)")
async def lc_search(
    query: str = Query("", max_length=300, description="Empty returns problems in dataset order"),
    top_k: int = Query(10, ge=1, le=50),
    difficulty: Optional[List[str]] = Query(None, description="Easy, Medium and/or Hard"),
    topic: Optional[List[str]] = Query(None, description="Topic tags, e.g. Array, Tree"),
    handler: LeetCodeHandler = Depends(get_leetcode),
):
    results = await run_in_threadpool(handler.search, query, top_k, difficulty, topic)
    return ProblemSearch(problems=[_summary(r) for r in results])


@router.get("/problems/{pid}", response_model=Problem, summary="One problem with its description")
async def lc_problem(pid: str, handler: LeetCodeHandler = Depends(get_leetcode)):
    p = handler.get_by_id(pid)
    if p is None:
        raise ApiError(404, f"Problem '{pid}' not found")
    return Problem(
        pid=p.pid, title=p.title, difficulty=p.difficulty, topics=p.topics or [], acceptance=p.acceptance,
        likes=p.likes, dislikes=p.dislikes, url=p.url, source=p.source, description=p.description,
    )


@router.post("/problems/{pid}/explain", response_model=Explanation, summary="AI study guide: approach, complexity, hints, solution")
async def lc_explain(pid: str, handler: LeetCodeHandler = Depends(get_leetcode)):
    if handler.get_by_id(pid) is None:
        raise ApiError(404, f"Problem '{pid}' not found")
    res = raise_if_failed(await run_in_threadpool(handler.explain_problem, pid))
    return Explanation(markdown=res.get("markdown") or "", model=res.get("model"))
