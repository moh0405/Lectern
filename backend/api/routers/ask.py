"""Question answering over the indexed material: JSON, Server-Sent Events, search and suggestions."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Iterator, List

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from ...llm_config import GeminiClient
from ...rag_engine import RAGEngine
from ..analytics_store import AnalyticsStore
from ..deps import common_dependencies, get_analytics, get_engine, raise_if_failed
from ..errors import ERROR_RESPONSES, ApiError
from ..schemas import AskRequest, AskResponse, Chunk, SearchResponse, Suggestions

logger = logging.getLogger("ai-study-mentor.api")

router = APIRouter(prefix="/api/v1", tags=["ask"], dependencies=common_dependencies, responses=ERROR_RESPONSES)


def _record(analytics: AnalyticsStore, req: AskRequest, chunks: List[Dict[str, Any]], t0: float,
            prompt: str, answer: str, ok: bool) -> None:
    try:
        analytics.record(
            req.question,
            [float(c.get("score") or 0.0) for c in chunks],
            int((time.time() - t0) * 1000),
            prompt,
            answer,
            req.mode,
            [c.get("doc") or "" for c in chunks],
            ok,
        )
    except Exception:  # analytics must never break an answer
        pass


@router.post("/ask", response_model=AskResponse, summary="Answer a question from the indexed material")
def ask(req: AskRequest, engine: RAGEngine = Depends(get_engine), analytics: AnalyticsStore = Depends(get_analytics)):
    t0 = time.time()
    chunks = engine.retrieve_context(req.question, k=req.k)
    prompt = engine.generate_prompt(req.question, chunks, mode=req.mode)
    result = engine.answer_with_gemini(
        req.question, k=req.k, model=req.model, temperature=req.temperature, mode=req.mode, chunks=chunks
    )
    ok = bool(result.get("ok", False))
    _record(analytics, req, chunks, t0, prompt, result.get("answer") or "", ok)
    raise_if_failed(result)
    return AskResponse(
        answer=result.get("answer") or "",
        chunks=[Chunk(**c) for c in chunks],
        model=result.get("model"),
        prompt=prompt if req.include_prompt else None,
    )


def sse(event: str, data: Dict[str, Any]) -> str:
    """One Server-Sent Event frame. Event names: meta, token, done, error."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post(
    "/ask/stream",
    summary="Stream an answer as Server-Sent Events",
    description=(
        "Same input as `/ask`. The response is `text/event-stream` with these events, in order:\n\n"
        "- `meta`: `{chunks, prompt?}` (retrieved context, sent first)\n"
        "- `token`: `{text}` (zero or more answer fragments)\n"
        "- `done`: `{model}` (end of a successful answer)\n"
        "- `error`: `{code, message}` (terminal; `code` is `llm_unavailable`, `llm_error` or `retrieval_error`)"
    ),
    responses={200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}}},
)
def ask_stream(req: AskRequest, engine: RAGEngine = Depends(get_engine), analytics: AnalyticsStore = Depends(get_analytics)):
    def events() -> Iterator[str]:
        t0 = time.time()
        try:
            chunks = engine.retrieve_context(req.question, k=req.k)
            prompt = engine.generate_prompt(req.question, chunks, mode=req.mode)
        except Exception:
            logger.exception("Retrieval failed for streamed question")
            yield sse("error", {"code": "retrieval_error", "message": "Retrieval failed"})
            return
        meta: Dict[str, Any] = {"chunks": [Chunk(**c).model_dump() for c in chunks]}
        if req.include_prompt:
            meta["prompt"] = prompt
        yield sse("meta", meta)
        parts: List[str] = []
        try:
            client = GeminiClient(model=req.model, temperature=req.temperature)
            for piece in client.stream(prompt, temperature=req.temperature):
                parts.append(piece)
                yield sse("token", {"text": piece})
            if not parts:
                raise RuntimeError("Model returned an empty response (it may have been blocked by a safety filter)")
        except Exception as e:
            msg = str(e)
            code = "llm_unavailable" if ("GEMINI_API_KEY" in msg or "not installed" in msg) else "llm_error"
            _record(analytics, req, chunks, t0, prompt, "".join(parts), False)
            yield sse("error", {"code": code, "message": msg})
            return
        _record(analytics, req, chunks, t0, prompt, "".join(parts), True)
        yield sse("done", {"model": client.model})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.get("/search", response_model=SearchResponse, summary="Retrieval only (no model call)")
def search(
    query: str = Query(..., min_length=2, max_length=500),
    k: int = Query(5, ge=1, le=20),
    engine: RAGEngine = Depends(get_engine),
):
    try:
        return SearchResponse(chunks=[Chunk(**c) for c in engine.retrieve_context(query, k=k)])
    except Exception:
        logger.exception("Retrieval failed for search")
        raise ApiError(500, "Retrieval failed", code="retrieval_error")


@router.get("/suggestions", response_model=Suggestions, summary="Study questions suggested from your own material")
def suggestions(n: int = Query(5, ge=1, le=10), engine: RAGEngine = Depends(get_engine)):
    return Suggestions(questions=engine.generate_query_suggestions(max_questions=n))
