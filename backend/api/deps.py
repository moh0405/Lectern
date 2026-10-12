"""FastAPI dependencies: shared engine, rate limiting, API key, LLM access, LeetCode handler."""

from __future__ import annotations

import hmac
import time
from typing import Any, Dict, List, Optional

from fastapi import Depends, Request
from fastapi.concurrency import run_in_threadpool

from ..rag_engine import RAGEngine
from .analytics_store import AnalyticsStore
from .errors import ApiError
from .jobs import JobManager
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


def rate_limit(request: Request) -> None:
    ip = (request.client.host if request.client else "unknown") or "unknown"
    now = time.time()
    times = [t for t in _rate_state.get(ip, []) if now - t < 60.0]
    if len(times) >= settings.rate_limit_per_min:
        raise ApiError(429, "Rate limit exceeded", headers=None)
    times.append(now)
    _rate_state[ip] = times


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


def raise_if_failed(result: Dict[str, Any]) -> Dict[str, Any]:
    """Turn an {"ok": False, "error": ...} result from the LLM layer into an HTTP error."""
    if result.get("ok", True):
        return result
    msg = str(result.get("error") or "The language model request failed")
    if "GEMINI_API_KEY" in msg or "not installed" in msg:
        raise ApiError(503, msg, code="llm_unavailable")
    raise ApiError(502, msg, code="llm_error")


async def in_thread(fn, *args, **kwargs):
    return await run_in_threadpool(fn, *args, **kwargs)


def opt(value: Optional[Any], default: Any) -> Any:
    return default if value is None else value
