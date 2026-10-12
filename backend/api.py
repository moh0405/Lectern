"""
AI Study Mentor — FastAPI Backend

Production‑ready endpoints for hackathon demo with:
- Swagger docs, CORS, logging, basic rate limiting
- PDF upload, RAG query (optional streaming), documents, stats, delete, search
"""

from __future__ import annotations

import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .rag_engine import RAGEngine


# ----------------------------------------------------------------------------
# App setup
# ----------------------------------------------------------------------------
# Locations are module-level so tests (and deployments) can point them elsewhere.
UPLOAD_DIR = Path("data/uploaded_files").resolve()
STORE_DIR = Path("data/vector_store").resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _make_engine() -> RAGEngine:
    return RAGEngine(store_dir=str(STORE_DIR), input_dir=str(UPLOAD_DIR))


def get_engine(request: Request) -> RAGEngine:
    """The one engine for this process (created at startup, or lazily if startup did not run)."""
    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        engine = request.app.state.engine = _make_engine()
    return engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.engine = _make_engine()
    try:
        # Load the embedding model now so the first query is not slow.
        await run_in_threadpool(app.state.engine.warm)
    except Exception as e:  # semantic search is optional; keyword fallback still works
        logger.warning("Embedder warm-up failed: %s", e)
    yield


app = FastAPI(
    title="AI Study Mentor API",
    version="1.0.0",
    description="Full‑stack RAG API for hackathon demo",
    lifespan=lifespan,
)

# CORS: allow all for demo purposes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger("ai-study-mentor.api")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# ----------------------------------------------------------------------------
# Simple in-memory rate limiting (demo-grade)
# ----------------------------------------------------------------------------
RATE_LIMIT_PER_MIN = 60
_rate_state: Dict[str, List[float]] = {}

def rate_limit(request: Request):
    ip = (request.client.host if request.client else "unknown") or "unknown"
    now = time.time()
    window = 60.0
    times = [t for t in _rate_state.get(ip, []) if now - t < window]
    if len(times) >= RATE_LIMIT_PER_MIN:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    times.append(now)
    _rate_state[ip] = times


# ----------------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------------
class Chunk(BaseModel):
    text: str
    doc: str
    page: Optional[int] = None
    score: float = 0.0
    url: Optional[str] = None


class UploadResult(BaseModel):
    filename: str
    size_bytes: int
    ok: bool
    chunks_indexed: int = 0
    error: Optional[str] = None


class UploadResponse(BaseModel):
    count: int
    results: List[UploadResult]


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, description="User question to answer with RAG")
    k: int = Field(3, ge=1, le=20, description="Top‑k retrieval")
    model: Optional[str] = Field(None, description="LLM model (Gemini)")
    temperature: float = Field(0.2, ge=0.0, le=1.0)
    stream: bool = Field(False, description="If true, returns Server‑Sent Events stream")


class AnswerResponse(BaseModel):
    prompt: str
    chunks: List[Chunk]
    answer: Optional[str] = None
    ok: bool = True
    model: Optional[str] = None
    error: Optional[str] = None


class DocumentsResponse(BaseModel):
    documents: List[str]


class StatsResponse(BaseModel):
    documents: int
    chunks: int
    min_page: Optional[int]
    max_page: Optional[int]


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def _doc_stats(engine: RAGEngine) -> Dict[str, Any]:
    items = engine._docstore_iter()
    docs = sorted({it.get("doc", "") for it in items if it.get("doc")})
    pages = [it.get("page") for it in items if it.get("page") is not None]
    return {
        "documents": len(docs),
        "chunks": len(items),
        "min_page": min(pages) if pages else None,
        "max_page": max(pages) if pages else None,
        "unique_docs": docs,
    }


# ----------------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------------
@app.get("/health")
def health(request: Request, deps: None = Depends(rate_limit)) -> Dict[str, Any]:
    return {"status": "ok", "uptime_sec": int(time.time())}


@app.post("/api/upload", response_model=UploadResponse)
async def api_upload(
    request: Request,
    files: List[UploadFile] = File(..., description="PDF files to upload"),
    deps: None = Depends(rate_limit),
    engine: RAGEngine = Depends(get_engine),
):
    results: List[UploadResult] = []
    saved: List[Path] = []
    for f in files:
        try:
            name = Path((f.filename or "uploaded.pdf").strip()).name  # drop any directory part
            if not name.lower().endswith(".pdf"):
                raise ValueError("Only .pdf files are supported")
            data = await f.read()
            dest = UPLOAD_DIR / name
            dest.write_bytes(data)
            saved.append(dest)
            results.append(UploadResult(filename=name, size_bytes=len(data), ok=True))
            logger.info("Uploaded %s (%d bytes)", name, len(data))
        except Exception as e:
            results.append(UploadResult(filename=f.filename or "", size_bytes=0, ok=False, error=str(e)))
    if saved:
        # Update the live index incrementally (only new/changed files are processed).
        report = await run_in_threadpool(engine.add_sources, [str(p) for p in saved])
        for r in results:
            if not r.ok:
                continue
            if r.filename in report.failed:
                r.ok = False
                r.error = f"indexing failed: {report.failed[r.filename]}"
            else:
                r.chunks_indexed = engine.store.sources.get(r.filename, {}).get("chunks", 0)
    return UploadResponse(count=len(results), results=results)


@app.get("/api/documents", response_model=DocumentsResponse)
def api_documents(
    request: Request, deps: None = Depends(rate_limit), engine: RAGEngine = Depends(get_engine)
) -> DocumentsResponse:
    stats = _doc_stats(engine)
    return DocumentsResponse(documents=stats["unique_docs"])


@app.delete("/api/documents/{doc}")
def api_delete_document(
    doc: str, request: Request, deps: None = Depends(rate_limit), engine: RAGEngine = Depends(get_engine)
) -> Dict[str, Any]:
    """Delete an uploaded file and remove its chunks from the index."""
    target = UPLOAD_DIR / doc
    in_index = doc in engine.store.sources
    if not target.exists() and not in_index:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        if target.exists():
            target.unlink()
        removed = engine.remove_source(doc)
        logger.info("Deleted document %s (%d chunks)", doc, removed)
        return {"ok": True, "deleted": doc, "chunks_removed": removed}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {e}")


@app.get("/api/stats", response_model=StatsResponse)
def api_stats(
    request: Request, deps: None = Depends(rate_limit), engine: RAGEngine = Depends(get_engine)
) -> StatsResponse:
    s = _doc_stats(engine)
    return StatsResponse(documents=s["documents"], chunks=s["chunks"], min_page=s["min_page"], max_page=s["max_page"])


@app.get("/api/search")
def api_search(
    query: str,
    request: Request,
    k: int = 5,
    deps: None = Depends(rate_limit),
    engine: RAGEngine = Depends(get_engine),
) -> Dict[str, Any]:
    if not query or len(query) < 2:
        raise HTTPException(status_code=400, detail="Query must be provided")
    try:
        return {"chunks": engine.retrieve_context(query, k=k)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/query")
async def api_query(
    req: QueryRequest,
    request: Request,
    deps: None = Depends(rate_limit),
    engine: RAGEngine = Depends(get_engine),
):
    """RAG query with optional SSE streaming.

    - If `stream=false` (default), returns JSON with prompt, chunks, answer.
    - If `stream=true`, returns `text/event-stream` SSE with tokens as they are produced.
    """
    try:
        chunks = await run_in_threadpool(engine.retrieve_context, req.question, req.k)
        prompt = engine.generate_prompt(req.question, chunks)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {e}")

    def generate() -> Dict[str, Any]:
        # Reuse the chunks retrieved above instead of retrieving a second time.
        return engine.answer_with_gemini(
            req.question, k=req.k, model=req.model, temperature=req.temperature, chunks=chunks
        )

    if not req.stream:
        # Non-streaming: attempt Gemini, fall back gracefully
        result = await run_in_threadpool(generate)
        out = AnswerResponse(
            prompt=prompt,
            chunks=[Chunk(**c) for c in result.get("chunks", chunks)],
            answer=result.get("answer"),
            ok=bool(result.get("ok", True)),
            model=result.get("model"),
            error=result.get("error"),
        )
        return out

    async def sse_gen():
        # Send initial metadata
        meta = {"event": "meta", "prompt": prompt, "chunks": chunks}
        yield f"data: {json.dumps(meta)}\n\n"
        # Generate answer (Gemini or fallback) and stream tokens
        result = await run_in_threadpool(generate)
        text = result.get("answer") or ""
        if not text:
            # Fallback: stream the formatted prompt as a placeholder
            text = prompt
        for token in text.split():
            yield f"data: {json.dumps({'event':'token','text': token})}\n\n"
            await _async_sleep(0.01)
        final = {"event": "done", "ok": True, "model": result.get("model"), "error": result.get("error")}
        yield f"data: {json.dumps(final)}\n\n"

    return StreamingResponse(sse_gen(), media_type="text/event-stream")


# tiny async sleep helper to pace token streaming
async def _async_sleep(sec: float):
    import asyncio
    await asyncio.sleep(sec)


# ----------------------------------------------------------------------------
# Notes: FastAPI auto docs are available at /docs and /redoc
# ----------------------------------------------------------------------------