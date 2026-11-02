"""FastAPI dependencies: shared engine, rate limiting, API key, LLM access, LeetCode handler."""

from __future__ import annotations

import hmac
import time
from typing import Any, Dict, List, Optional

from fastapi import Depends, Request
from fastapi.concurrency import run_in_threadpool

from ..rag_engine import RAGEngine
from .analytics_store import AnalyticsStore
from .answer_cache import AnswerCache
from .errors import ApiError
from .jobs import JobManager
from .study_store import StudyStore
from .settings import settings

_rate_state: Dict[str, List[float]] = {}


def make_engine() -> RAGEngine:
    return RAGEngine(store_dir=str(settings.store_dir), input_dir=str(settings.upload_dir))


def get_engine(request: Request) -> RAGEngine:
    """The one engine for this process (created at startup, or lazily if startup did not run)."""
    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        engine = request.app.state.engine = make_engine()
    return engine


def get_jobs(request: Request) -> JobManager:
    jobs = getattr(request.app.state, "jobs", None)
    if jobs is None:
        jobs = request.app.state.jobs = JobManager()
    return jobs


def get_analytics(request: Request) -> AnalyticsStore:
    store = getattr(request.app.state, "analytics", None)
    if store is None:
        store = request.app.state.analytics = AnalyticsStore(settings.analytics_db)
    return store


def get_study(request: Request) -> StudyStore:
    store = getattr(request.app.state, "study", None)
    if store is None:
        store = request.app.state.study = StudyStore(settings.study_db)
    return store


def get_answer_cache(request: Request) -> AnswerCache:
    cache = getattr(request.app.state, "answer_cache", None)
    if cache is None:
        cache = request.app.state.answer_cache = AnswerCache()
    return cache


def store_version(engine: RAGEngine) -> str:
    """Changes whenever the index, or how it is searched, changes, so cached answers never outlive their sources."""
    return f"{engine.store.embedder_name}:{engine.store.revision}:{engine.retrieval_mode}:{bool(engine._reranker)}"


VISITOR_HEADER = "x-visitor-ip"
_MAX_TRACKED_CLIENTS = 10_000


def _key_matches(request: Request) -> bool:
    expected = settings.api_key
    given = request.headers.get("x-api-key", "")
    return bool(expected) and hmac.compare_digest(given.encode(), expected.encode())


def _rate_key(request: Request) -> str:
    """Who is being counted. Behind the hosted web app every call arrives from the proxy's address, so one
    shared bucket would throttle all visitors together. The proxy passes the visitor's address in
    `X-Visitor-IP`; it is believed only when the call also carries the right API key, so a direct caller
    cannot pick its own bucket."""
    visitor = request.headers.get(VISITOR_HEADER, "").strip()
    if visitor and _key_matches(request):
        return "visitor:" + visitor[:64]
    return (request.client.host if request.client else "unknown") or "unknown"


def rate_limit(request: Request) -> None:
    key = _rate_key(request)
    now = time.time()
    if len(_rate_state) > _MAX_TRACKED_CLIENTS:  # forget clients with nothing recent, so memory stays bounded
        for k in [k for k, v in _rate_state.items() if not v or now - v[-1] >= 60.0]:
            del _rate_state[k]
    times = [t for t in _rate_state.get(key, []) if now - t < 60.0]
    if len(times) >= settings.rate_limit_per_min:
        raise ApiError(429, "Rate limit exceeded", headers=None)
    times.append(now)
    _rate_state[key] = times


def require_api_key(request: Request) -> None:
    """Enforced only when API_KEY is configured."""
    expected = settings.api_key
    if not expected:
        return
    given = request.headers.get("x-api-key", "")
    if not hmac.compare_digest(given.encode(), expected.encode()):
        raise ApiError(401, "Missing or invalid X-API-Key header")


# Applied to every /api/v1 route.
common_dependencies = [Depends(rate_limit), Depends(require_api_key)]


QUOTA_MESSAGE = (
    "The language model provider says its quota is used up (a free API key allows only a few calls per day). "
    "Try again later."
)


def quota_message(msg: str) -> str:
    """What to tell the user about a quota error. A per-minute limit (the free tier allows only a few requests a
    minute) clears in seconds, so say that instead of 'a few calls per day'."""
    from ..llm_config import retry_delay_seconds

    if "per minute" in msg.lower() or "perminute" in msg.lower():
        wait = retry_delay_seconds(msg)
        after = f" Wait about {int(wait) + 1} seconds and try again." if wait is not None else " Wait a minute and try again."
        return "The language model is rate-limited (a free API key allows only a few requests per minute, and a question can use several)." + after
    return QUOTA_MESSAGE


def is_quota_error(msg: str) -> bool:
    return "RESOURCE_EXHAUSTED" in msg or "exceeded your current quota" in msg.lower()


def raise_if_failed(result: Dict[str, Any]) -> Dict[str, Any]:
    """Turn an {"ok": False, "error": ...} result from the LLM layer into an HTTP error."""
    if result.get("ok", True):
        return result
    msg = str(result.get("error") or "The language model request failed")
    if "daily limit" in msg.lower() or "calls are paused" in msg.lower():
        raise ApiError(429, msg, code="daily_limit")
    if is_quota_error(msg):
        raise ApiError(429, quota_message(msg), code="quota_exhausted")
    if "_API_KEY" in msg or "not installed" in msg or "LLM_PROVIDER" in msg:
        raise ApiError(503, msg, code="llm_unavailable")
    raise ApiError(502, msg, code="llm_error")


async def in_thread(fn, *args, **kwargs):
    return await run_in_threadpool(fn, *args, **kwargs)


def opt(value: Optional[Any], default: Any) -> Any:
    return default if value is None else value
