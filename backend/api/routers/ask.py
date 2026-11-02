"""Question answering over the indexed material: JSON, Server-Sent Events, search and suggestions."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Iterator, List

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from ...citations import check_answer
from ...llm_config import DEFAULT_MODEL
from ...llm_providers import create_llm
from ...rag_engine import RAGEngine
from ..analytics_store import AnalyticsStore
from ..answer_cache import AnswerCache, make_key
from ..deps import (
    quota_message,
    common_dependencies,
    get_analytics,
    get_answer_cache,
    get_engine,
    is_quota_error,
    raise_if_failed,
    store_version,
)
from ..errors import ERROR_RESPONSES, ApiError
from ..schemas import AgentAskRequest, AskRequest, AskResponse, Chunk, Models, SearchResponse, SseAgentDone, SseMeta, SseReplace, SseStep, SseToken, Suggestions

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


def _supplied(req: AskRequest) -> List[Dict[str, Any]] | None:
    """Passages the caller brought. Such questions are about private material: skip the cache and analytics."""
    if not req.context:
        return None
    return [c.model_dump() for c in req.context]


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
    supplied = _supplied(req)
    key = _cache_key(req, engine)
    hit = None if (req.no_cache or supplied) else cache.get(key)
    if hit is not None:
        _record(analytics, req, hit["chunks"], t0, hit["prompt"], hit["answer"], True)
        return _response(req, hit, cached=True)

    chunks = supplied if supplied is not None else engine.retrieve_context(req.question, k=req.k)
    prompt = engine.generate_prompt(req.question, chunks, mode=req.mode)
    result = engine.answer_with_gemini(
        req.question, k=req.k, model=req.model, temperature=req.temperature, mode=req.mode, chunks=chunks
    )
    ok = bool(result.get("ok", False))
    if supplied is None:
        _record(analytics, req, chunks, t0, prompt, result.get("answer") or "", ok)
    raise_if_failed(result)
    answer = result.get("answer") or ""
    entry = {"answer": answer, "chunks": chunks, "model": result.get("model"), "prompt": prompt, "check": check_answer(answer, chunks)}
    if answer.strip() and supplied is None:
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
        supplied = _supplied(req)
        key = _cache_key(req, engine)
        hit = None if (req.no_cache or supplied) else cache.get(key)
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
            chunks = supplied if supplied is not None else engine.retrieve_context(req.question, k=req.k)
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
            client = create_llm(model=req.model, temperature=req.temperature)
            for piece in client.stream(prompt, temperature=req.temperature):
                parts.append(piece)
                yield sse("token", {"text": piece})
            if not parts:
                raise RuntimeError("Model returned an empty response (it may have been blocked by a safety filter)")
        except Exception as e:
            msg = str(e)
            code = "llm_unavailable" if ("_API_KEY" in msg or "not installed" in msg or "LLM_PROVIDER" in msg) else "llm_error"
            if "daily limit" in msg.lower() or "calls are paused" in msg.lower():
                code = "daily_limit"
            elif is_quota_error(msg):
                code, msg = "quota_exhausted", quota_message(msg)
            if supplied is None:
                _record(analytics, req, chunks, t0, prompt, "".join(parts), False)
            yield sse("error", {"code": code, "message": msg})
            return
        text = "".join(parts)
        check = check_answer(text, chunks)
        if supplied is None:
            _record(analytics, req, chunks, t0, prompt, text, True)
            cache.put(key, {"answer": text, "chunks": chunks, "model": client.model, "prompt": prompt, "check": check})
        yield done_event(client.model, check, False)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


def _llm_failure(msg: str) -> tuple[str, str]:
    """The (code, message) the stream reports for a model failure."""
    code = "llm_unavailable" if ("_API_KEY" in msg or "not installed" in msg or "LLM_PROVIDER" in msg) else "llm_error"
    if "daily limit" in msg.lower() or "calls are paused" in msg.lower():
        code = "daily_limit"
    elif is_quota_error(msg):
        code, msg = "quota_exhausted", quota_message(msg)
    return code, msg


@router.post(
    "/ask/agent/stream",
    summary="Answer with an agentic workflow (LangGraph), streamed as Server-Sent Events",
    description=(
        "A slower, more careful path for harder questions. The workflow rewrites the question into a better search "
        "query, retrieves, asks the model whether the passages are sufficient (searching once more if not), writes the "
        "answer, and verifies its citations (rewriting once if it cited sources it was not given). It uses up to 6 model "
        "calls per question. Always searches the server's index; nothing is cached.\n\n"
        "Events: `step` (`{name, detail}`, as each stage finishes), `meta` (`{chunks}`, when answering starts), `token`, "
        "`replace` (`{reason}`: discard the answer streamed so far, a corrected one follows), then `done` or `error`."
    ),
    responses={200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}}},
)
def ask_agent_stream(
    req: AgentAskRequest,
    engine: RAGEngine = Depends(get_engine),
    analytics: AnalyticsStore = Depends(get_analytics),
):
    try:
        from ...agent import run_agent
    except ImportError:  # langgraph is an optional extra
        raise ApiError(503, "The agentic mode needs the 'agent' extra (langgraph) on the server", code="agent_unavailable")

    def events() -> Iterator[str]:
        t0 = time.time()
        text, prompt, chunks = "", "", []
        try:
            llm = create_llm(model=req.model, temperature=req.temperature)
        except Exception as e:
            code, msg = _llm_failure(str(e))
            yield sse("error", {"code": code, "message": msg})
            return
        try:
            for ev in run_agent(engine, llm, req.question, k=req.k, mode=req.mode, temperature=req.temperature):
                name, data = ev["event"], ev["data"]
                if name == "meta":
                    chunks = data["chunks"]
                    data = SseMeta(chunks=[Chunk(**c) for c in chunks]).model_dump()
                elif name == "token":
                    data = SseToken(**data).model_dump()
                elif name == "step":
                    data = SseStep(**data).model_dump()
                elif name == "replace":
                    data = SseReplace(**data).model_dump()
                elif name == "done":
                    text, prompt = data.pop("_answer"), data.pop("_prompt")
                    data.pop("_chunks", None)
                    data = SseAgentDone(**data).model_dump()
                yield sse(name, data)
        except Exception as e:
            logger.exception("Agent run failed")
            code, msg = _llm_failure(str(e))
            if not chunks and code == "llm_error":
                code, msg = "retrieval_error", "Retrieval failed"
            _record(analytics, req, chunks, t0, prompt, text, False)  # type: ignore[arg-type]
            yield sse("error", {"code": code, "message": msg})
            return
        _record(analytics, req, chunks, t0, prompt, text, True)  # type: ignore[arg-type]

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
        client = create_llm()
    except RuntimeError as e:
        raise ApiError(503, str(e), code="llm_unavailable")
    return Models(models=client.list_supported_models(), default=client.model or DEFAULT_MODEL)
