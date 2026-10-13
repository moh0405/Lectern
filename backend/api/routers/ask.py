"""Question answering over the indexed material: JSON, Server-Sent Events, search and suggestions."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Iterator, List

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from ...citations import check_answer
from ...llm_config import DEFAULT_MODEL, GeminiClient
from ...rag_engine import RAGEngine
from ..analytics_store import AnalyticsStore
from ..answer_cache import AnswerCache, make_key
from ..deps import common_dependencies, get_analytics, get_answer_cache, get_engine, raise_if_failed, store_version
from ..errors import ERROR_RESPONSES, ApiError
from ..schemas import AskRequest, AskResponse, Chunk, Models, SearchResponse, Suggestions

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


def _cache_key(req: AskRequest, engine: RAGEngine):
    return make_key(req.question, req.mode, req.k, req.model, req.temperature, store_version(engine))


@router.post("/ask", response_model=AskResponse, summary="Answer a question from the indexed material")
def ask(
    req: AskRequest,
    engine: RAGEngine = Depends(get_engine),
    analytics: AnalyticsStore = Depends(get_analytics),
    cache: AnswerCache = Depends(get_answer_cache),
):
    t0 = time.time()
    key = _cache_key(req, engine)
    hit = None if req.no_cache else cache.get(key)
    if hit is not None:
        _record(analytics, req, hit["chunks"], t0, hit["prompt"], hit["answer"], True)
        return _response(req, hit, cached=True)

    chunks = engine.retrieve_context(req.question, k=req.k)
    prompt = engine.generate_prompt(req.question, chunks, mode=req.mode)
    result = engine.answer_with_gemini(
        req.question, k=req.k, model=req.model, temperature=req.temperature, mode=req.mode, chunks=chunks
    )
    ok = bool(result.get("ok", False))
    _record(analytics, req, chunks, t0, prompt, result.get("answer") or "", ok)
    raise_if_failed(result)
    answer = result.get("answer") or ""
    entry = {"answer": answer, "chunks": chunks, "model": result.get("model"), "prompt": prompt, "check": check_answer(answer, chunks)}
    if answer.strip():
        cache.put(key, entry)
    return _response(req, entry, cached=False)


def _response(req: AskRequest, entry: Dict[str, Any], cached: bool) -> AskResponse:
    check = entry["check"]
    return AskResponse(
        answer=entry["answer"],
        chunks=[Chunk(**c) for c in entry["chunks"]],
        model=entry.get("model"),
        prompt=entry["prompt"] if req.include_prompt else None,
        citations=check["citations"],
        unverified_citations=check["unverified"],
        uncited=check["uncited"],
        cached=cached,
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
        "- `done`: `{model, citations, unverified_citations, uncited, cached}` (end of a successful answer; the citations are checked against the retrieved passages)\n"
        "- `error`: `{code, message}` (terminal; `code` is `llm_unavailable`, `llm_error` or `retrieval_error`)"
    ),
    responses={200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}}},
)
def ask_stream(
    req: AskRequest,
    engine: RAGEngine = Depends(get_engine),
    analytics: AnalyticsStore = Depends(get_analytics),
    cache: AnswerCache = Depends(get_answer_cache),
):
    def done_event(model, check, cached):
        return sse("done", {"model": model, "citations": check["citations"], "unverified_citations": check["unverified"],
                            "uncited": check["uncited"], "cached": cached})

    def events() -> Iterator[str]:
        t0 = time.time()
        key = _cache_key(req, engine)
        hit = None if req.no_cache else cache.get(key)
        if hit is not None:
            chunks, prompt = hit["chunks"], hit["prompt"]
            meta: Dict[str, Any] = {"chunks": [Chunk(**c).model_dump() for c in chunks]}
            if req.include_prompt:
                meta["prompt"] = prompt
            yield sse("meta", meta)
            text = hit["answer"]
            for i in range(0, len(text), 48):  # replay in small pieces so the client behaves as it does for a live answer
                yield sse("token", {"text": text[i : i + 48]})
            _record(analytics, req, chunks, t0, prompt, text, True)
            yield done_event(hit.get("model"), hit["check"], True)
            return
        try:
            chunks = engine.retrieve_context(req.question, k=req.k)
            prompt = engine.generate_prompt(req.question, chunks, mode=req.mode)
        except Exception:
            logger.exception("Retrieval failed for streamed question")
            yield sse("error", {"code": "retrieval_error", "message": "Retrieval failed"})
            return
        meta = {"chunks": [Chunk(**c).model_dump() for c in chunks]}
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
        text = "".join(parts)
        check = check_answer(text, chunks)
        _record(analytics, req, chunks, t0, prompt, text, True)
        cache.put(key, {"answer": text, "chunks": chunks, "model": client.model, "prompt": prompt, "check": check})
        yield done_event(client.model, check, False)

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


@router.get("/models", response_model=Models, summary="Models the server can use (needs a Gemini key)")
def models():
    try:
        client = GeminiClient()
    except RuntimeError as e:
        raise ApiError(503, str(e), code="llm_unavailable")
    return Models(models=client.list_supported_models(), default=client.model or DEFAULT_MODEL)
