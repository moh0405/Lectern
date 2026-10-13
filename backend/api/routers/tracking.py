"""Your study state, kept on the server: flashcards (spaced repetition), LeetCode progress and plan, Ask history.

There are no accounts: this is one person's tool, stored in one SQLite file (`STUDY_DB`).
"""

from __future__ import annotations

import random
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query, Response
from fastapi.concurrency import run_in_threadpool

from ... import flashcards
from ...leetcode_handler import LeetCodeHandler
from ...llm_providers import create_llm
from ...rag_engine import RAGEngine
from ...study_plan import build_plan
from ..deps import common_dependencies, get_engine, get_study, raise_if_failed
from ..errors import ERROR_RESPONSES, ApiError
from ..schemas import (Card, CardCreate, CardList, CardStats, GenerateCardsRequest, HistoryTurn, ProgressItem, ProgressList,
                       ProgressSummary, ProgressUpdate, ReviewRequest, SavedHistory, SavedTurn, StudyPlan)
from ..study_store import StudyStore
from .leetcode import get_leetcode

router = APIRouter(prefix="/api/v1", tags=["tracking"], dependencies=common_dependencies, responses=ERROR_RESPONSES)


def _card_list(store: StudyStore, due: bool, limit: int) -> CardList:
    return CardList(cards=[Card(**c) for c in store.list_cards(due_only=due, limit=limit)], stats=CardStats(**store.card_stats()))


# ------------------------------------------------------------------ flashcards
@router.get("/cards", response_model=CardList, summary="Flashcards (all, or only those due for review) with deck statistics")
def list_cards(due: bool = Query(False, description="Only cards due now"), limit: int = Query(200, ge=1, le=1000),
               store: StudyStore = Depends(get_study)):
    return _card_list(store, due, limit)


@router.post("/cards", response_model=Card, status_code=201, summary="Add a flashcard")
def add_card(req: CardCreate, store: StudyStore = Depends(get_study)):
    return Card(**store.add_card(req.front, req.back, req.source))


@router.post("/cards/generate", response_model=CardList, status_code=201,
             summary="Write flashcards from your indexed material with the language model, and add them to the deck")
async def generate_cards(req: GenerateCardsRequest, engine: RAGEngine = Depends(get_engine), store: StudyStore = Depends(get_study)):
    if len(engine.store) == 0:
        raise ApiError(409, "Index some material first", code="no_material")
    if req.topic:
        chunks: List[Dict[str, Any]] = await run_in_threadpool(engine.retrieve_context, req.topic, 6)
    else:
        every = list(engine.store.iter_chunks())
        chunks = random.sample(every, min(6, len(every)))
    prompt = flashcards.build_prompt(chunks, req.n, req.topic)

    def call() -> Dict[str, Any]:
        try:
            return create_llm(temperature=req.temperature).generate(prompt, json_mode=True)
        except RuntimeError as e:
            return {"ok": False, "error": str(e)}

    res = raise_if_failed(await run_in_threadpool(call))
    cards = flashcards.parse_cards(res.get("answer", ""), req.n)
    if not cards:
        raise ApiError(502, "The model did not return usable flashcards. Try again.", code="llm_error")
    source = req.topic or ", ".join(sorted({c.get("doc") or "" for c in chunks if c.get("doc")})[:3]) or None
    for c in cards:
        store.add_card(c["front"], c["back"], source)
    return _card_list(store, False, 200)


@router.get(
    "/cards/export", summary="Download the deck as Anki-importable CSV or as an Anki package (.apkg)",
    responses={200: {"content": {"text/csv": {}, "application/octet-stream": {}}}},
)
def export_cards(format: str = Query("csv", pattern="^(csv|apkg)$"), store: StudyStore = Depends(get_study)):
    cards = store.list_cards(limit=100000)
    if not cards:
        raise ApiError(409, "The deck is empty", code="no_cards")
    if format == "csv":
        return Response(flashcards.to_csv(cards), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="flashcards.csv"'})
    data = flashcards.to_apkg(cards)
    if data is None:
        raise ApiError(503, "Anki package export needs the 'anki' extra (genanki). The CSV export works without it.",
                       code="export_unavailable")
    return Response(data, media_type="application/octet-stream", headers={"Content-Disposition": 'attachment; filename="flashcards.apkg"'})


@router.post("/cards/{card_id}/review", response_model=Card, summary="Record a review; the card is rescheduled with SM-2")
def review_card(card_id: int, req: ReviewRequest, store: StudyStore = Depends(get_study)):
    card = store.review_card(card_id, req.grade)
    if card is None:
        raise ApiError(404, "No such card", code="not_found")
    return Card(**card)


@router.delete("/cards/{card_id}", status_code=204, summary="Delete a flashcard")
def delete_card(card_id: int, store: StudyStore = Depends(get_study)):
    if not store.delete_card(card_id):
        raise ApiError(404, "No such card", code="not_found")
    return Response(status_code=204)


# ------------------------------------------------------------------ LeetCode progress
def _progress_list(store: StudyStore) -> ProgressList:
    rows = store.list_progress()
    by_diff: Dict[str, int] = {}
    for r in rows:
        if r["status"] == "solved":
            key = (r["difficulty"] or "Unknown").title()
            by_diff[key] = by_diff.get(key, 0) + 1
    count = lambda s: sum(1 for r in rows if r["status"] == s)  # noqa: E731
    return ProgressList(items=[ProgressItem(**r) for r in rows],
                        summary=ProgressSummary(solved=count("solved"), attempted=count("attempted"), todo=count("todo"),
                                                solved_by_difficulty=by_diff))


@router.get("/leetcode/progress", response_model=ProgressList, summary="Your LeetCode progress: every problem you have marked")
def list_progress(store: StudyStore = Depends(get_study)):
    return _progress_list(store)


@router.put("/leetcode/progress/{pid}", response_model=ProgressItem, summary="Mark a problem todo, attempted or solved (with optional notes)")
def set_progress(pid: str, req: ProgressUpdate, store: StudyStore = Depends(get_study), handler: LeetCodeHandler = Depends(get_leetcode)):
    problem = handler.get_by_id(pid)
    if problem is None:
        raise ApiError(404, f"Problem '{pid}' not found", code="not_found")
    row = store.set_progress(pid, problem.title, req.status, notes=req.notes, topics=[t.strip().title() for t in problem.topics or []],
                             difficulty=(problem.difficulty or "").strip().title())
    return ProgressItem(**row)


@router.delete("/leetcode/progress/{pid}", status_code=204, summary="Forget your progress on a problem")
def clear_progress(pid: str, store: StudyStore = Depends(get_study)):
    if not store.clear_progress(pid):
        raise ApiError(404, "No progress recorded for that problem", code="not_found")
    return Response(status_code=204)


@router.get("/leetcode/plan", response_model=StudyPlan, summary="A study plan from your weak topics (unsolved problems, easiest first)")
def study_plan(size: int = Query(10, ge=1, le=30), store: StudyStore = Depends(get_study), handler: LeetCodeHandler = Depends(get_leetcode)):
    progress = {r["pid"]: r for r in store.list_progress()}
    bank = [{"pid": p.pid, "title": p.title, "difficulty": (p.difficulty or "").strip().title(),
             "topics": [t.strip().title() for t in p.topics or []]} for p in handler._problems]
    return StudyPlan(**build_plan(progress, bank, size=size))


# ------------------------------------------------------------------ Ask history
@router.get("/history", response_model=SavedHistory, summary="Your saved Ask turns, newest first")
def list_history(limit: int = Query(100, ge=1, le=500), store: StudyStore = Depends(get_study)):
    return SavedHistory(turns=[SavedTurn(**t) for t in store.list_history(limit)])


@router.post("/history", response_model=SavedTurn, status_code=201, summary="Save a finished Ask turn")
def save_turn(turn: HistoryTurn, store: StudyStore = Depends(get_study)):
    data = turn.model_dump()
    return SavedTurn(**store.add_history(data))


@router.delete("/history/{turn_id}", status_code=204, summary="Delete one saved turn")
def delete_turn(turn_id: int, store: StudyStore = Depends(get_study)):
    if not store.delete_history(turn_id):
        raise ApiError(404, "No such turn", code="not_found")
    return Response(status_code=204)


@router.delete("/history", status_code=204, summary="Delete all saved turns")
def clear_history(store: StudyStore = Depends(get_study)):
    store.delete_history()
    return Response(status_code=204)
