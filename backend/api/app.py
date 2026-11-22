"""FastAPI application factory.

Run:   uvicorn backend.api:app --reload
Docs:  /docs (Swagger UI), /redoc, /openapi.json
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from .. import __version__, cloud_sync
from .deps import make_engine, shared_engine
from .errors import ERROR_RESPONSES, ApiError, ErrorResponse, install_error_handlers
from .jobs import JobManager
from .routers import agent, ask, attempt, leetcode, sources, study, tracking, tutor, viz
from .schemas import Health, SseAgentDone, SseAgentRunDone, SseDone, SseError, SseMeta, SseReplace, SseStep, SseThought, SseToken, SseToolCall, SseToolResult
from .settings import settings
from .startup import LAMBDA_INVOKE_HEADER, DeferredStartup

logger = logging.getLogger("ai-study-mentor.api")
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def _load_state(app: FastAPI) -> None:
    """Secrets, then the saved index and database, then the engine and embedding model. Safe to run again if it fails."""
    sync = None
    if settings.s3_bucket:
        from ..cloud_sync import S3Sync, load_secret_env

        load_secret_env()
        if not settings.api_key:  # settings were read at import, before the secret was fetched
            settings.api_key = os.getenv("API_KEY") or None

        sync = S3Sync(settings.s3_bucket, settings.s3_prefix, settings.store_dir, settings.study_db)
        sync.pull()  # before the engine loads the index
    engine = make_engine()
    try:
        # Load the embedding model now so the first question is not slow.
        engine.warm()
    except Exception as e:  # semantic search is optional; keyword fallback still works
        logger.warning("Embedder warm-up failed: %s", e)
    app.state.engine = engine
    if sync and cloud_sync.ON_LAMBDA:
        app.state.request_sync = sync  # frozen between requests: save after each change instead of on a timer
    elif sync:
        app.state.timer_sync = sync
        sync.start(settings.s3_sync_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    app.state.request_sync = app.state.timer_sync = app.state.startup = None
    app.state.jobs = JobManager()
    if cloud_sync.ON_LAMBDA or settings.defer_startup:
        app.state.startup = DeferredStartup(lambda: _load_state(app))
    else:
        await run_in_threadpool(_load_state, app)
    yield
    app.state.startup = None
    app.state.jobs.shutdown()
    sync = app.state.timer_sync or app.state.request_sync
    if sync:
        await run_in_threadpool(sync.stop)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Lectern API",
        version=__version__,
        description=(
            "RAG tutor for Computer Science learning. Add sources (PDFs, audio, YouTube, GitHub, web), "
            "ask questions with cited answers (JSON or streaming), and use tutoring tools.\n\n"
            "All `/api/v1` routes are rate limited per IP. If the server sets `API_KEY`, send it as `X-API-Key`. "
            "Errors always have the shape `{\"error\": {\"code\", \"message\", \"details?\"}}`."
        ),
        lifespan=lifespan,
        responses=ERROR_RESPONSES,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key"],
    )
    install_error_handlers(app)

    @app.middleware("http")
    async def note_arrival(request: Request, call_next):
        # Streams with a deadline count from here, so time spent waiting for a cold start is included.
        request.state.received_at = time.monotonic()
        return await call_next(request)

    @app.middleware("http")
    async def save_changes_to_s3(request: Request, call_next):
        response = await call_next(request)
        sync = getattr(app.state, "request_sync", None)
        if sync and request.method not in ("GET", "HEAD", "OPTIONS"):
            try:
                await run_in_threadpool(sync.push)
            except Exception as e:  # the answer is still good; the next change retries the upload
                logger.warning("S3 save failed: %s", e)
        return response

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse("/docs")

    @app.get("/health", response_model=Health, tags=["meta"], summary="Liveness and basic index status",
             description="During a cold start this answers `status: starting`, with `chunks` and `semantic_search` null.")
    async def health(request: Request, response: Response) -> Health:
        startup = getattr(app.state, "startup", None)
        if startup is not None and not startup.ready:
            # The Lambda adapter's readiness check must get an instant answer and must not trigger the heavy load.
            readiness_check = cloud_sync.ON_LAMBDA and LAMBDA_INVOKE_HEADER not in request.headers
            if readiness_check or not await startup.wait(settings.health_startup_wait_s):
                if startup.failed:
                    raise ApiError(503, "The study service could not start. It will try again.", code="startup_failed",
                                   headers={"Retry-After": "5"})
                response.headers["Cache-Control"] = "no-store"
                return Health(status="starting", version=__version__, semantic_search=None, chunks=None)
        engine = await run_in_threadpool(shared_engine, app)
        return Health(status="ok", version=__version__, semantic_search=engine.semantic_search, chunks=len(engine.store))

    for r in (sources.router, ask.router, agent.router, tutor.router, attempt.router, leetcode.router, study.router, viz.router, tracking.router):
        app.include_router(r)

    base_openapi = app.openapi

    def custom_openapi() -> Dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = base_openapi()
        components = schema.setdefault("components", {}).setdefault("schemas", {})
        # Not referenced by any route response, but the client needs them to type the SSE stream.
        for model in (SseMeta, SseToken, SseDone, SseError, SseStep, SseReplace, SseAgentDone, SseThought, SseToolCall, SseToolResult, SseAgentRunDone, ErrorResponse):
            components.update(model.model_json_schema(ref_template="#/components/schemas/{model}").pop("$defs", {}))
            components[model.__name__] = {
                k: v for k, v in model.model_json_schema(ref_template="#/components/schemas/{model}").items() if k != "$defs"
            }
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
    return app


app = create_app()
