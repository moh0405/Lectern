"""FastAPI application factory.

Run:   uvicorn backend.api:app --reload
Docs:  /docs (Swagger UI), /redoc, /openapi.json
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from .. import __version__
from .deps import make_engine
from .errors import ERROR_RESPONSES, ErrorResponse, install_error_handlers
from .jobs import JobManager
from .routers import ask, leetcode, sources, study, tracking, tutor, viz
from .schemas import Health, SseDone, SseError, SseMeta, SseToken
from .settings import settings

logger = logging.getLogger("ai-study-mentor.api")
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    sync = None
    app.state.request_sync = None
    if settings.s3_bucket:
        from ..cloud_sync import ON_LAMBDA, S3Sync, load_secret_env

        await run_in_threadpool(load_secret_env)
        if not settings.api_key:  # settings were read at import, before the secret was fetched
            settings.api_key = os.getenv("API_KEY") or None

        sync = S3Sync(settings.s3_bucket, settings.s3_prefix, settings.store_dir, settings.study_db)
        await run_in_threadpool(sync.pull)  # before the engine loads the index
    app.state.engine = make_engine()
    app.state.jobs = JobManager()
    try:
        # Load the embedding model now so the first question is not slow.
        await run_in_threadpool(app.state.engine.warm)
    except Exception as e:  # semantic search is optional; keyword fallback still works
        logger.warning("Embedder warm-up failed: %s", e)
    if sync and ON_LAMBDA:
        app.state.request_sync = sync  # frozen between requests: save after each change instead of on a timer
    elif sync:
        sync.start(settings.s3_sync_seconds)
    yield
    app.state.jobs.shutdown()
    if sync:
        await run_in_threadpool(sync.stop)


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Study Mentor API",
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

    @app.get("/health", response_model=Health, tags=["meta"], summary="Liveness and basic index status")
    def health() -> Health:
        engine = getattr(app.state, "engine", None) or get_engine_lazy(app)
        return Health(status="ok", version=__version__, semantic_search=engine.semantic_ready, chunks=len(engine.store))

    for r in (sources.router, ask.router, tutor.router, leetcode.router, study.router, viz.router, tracking.router):
        app.include_router(r)

    base_openapi = app.openapi

    def custom_openapi() -> Dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = base_openapi()
        components = schema.setdefault("components", {}).setdefault("schemas", {})
        # Not referenced by any route response, but the client needs them to type the SSE stream.
        for model in (SseMeta, SseToken, SseDone, SseError, ErrorResponse):
            components.update(model.model_json_schema(ref_template="#/components/schemas/{model}").pop("$defs", {}))
            components[model.__name__] = {
                k: v for k, v in model.model_json_schema(ref_template="#/components/schemas/{model}").items() if k != "$defs"
            }
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
    return app


def get_engine_lazy(app: FastAPI):
    if getattr(app.state, "engine", None) is None:
        app.state.engine = make_engine()
    return app.state.engine


app = create_app()
