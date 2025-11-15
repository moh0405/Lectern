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

from fastapi import FastAPI, UploadFile, File, Form, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .rag_engine import RAGEngine
from .document_processor import list_chunks_from_dir


# ----------------------------------------------------------------------------
# App setup
# ----------------------------------------------------------------------------
app = FastAPI(title="AI Study Mentor API", version="1.0.0", description="Full‑stack RAG API for hackathon demo")

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
UPLOAD_DIR = Path("data/uploaded_files").resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def _doc_stats() -> Dict[str, Any]:
    try:
        engine = RAGEngine(auto_embeddings=False)
        items = engine._docstore_iter()
    except Exception:
        # Fallback to scanning uploaded PDFs without FAISS
        try:
            items = list_chunks_from_dir(str(UPLOAD_DIR))
        except Exception:
            items = []
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
):
    results: List[UploadResult] = []
    for f in files:
        try:
            name = (f.filename or "uploaded.pdf").strip()
            if not name.lower().endswith(".pdf"):
                raise ValueError("Only .pdf files are supported")
            data = await f.read()
            dest = UPLOAD_DIR / name
            dest.write_bytes(data)
            results.append(UploadResult(filename=name, size_bytes=len(data), ok=True))
            logger.info("Uploaded %s (%d bytes)", name, len(data))
        except Exception as e:
            results.append(UploadResult(filename=f.filename or "", size_bytes=0, ok=False, error=str(e)))
    # Warm metadata for downstream queries
    try:
        list_chunks_from_dir(str(UPLOAD_DIR))
    except Exception as e:
        logger.warning("Metadata warm failed: %s", e)
    return UploadResponse(count=len(results), results=results)


@app.get("/api/documents", response_model=DocumentsResponse)
def api_documents(request: Request, deps: None = Depends(rate_limit)) -> DocumentsResponse:
    stats = _doc_stats()
    return DocumentsResponse(documents=stats["unique_docs"])


@app.delete("/api/documents/{doc}")
def api_delete_document(doc: str, request: Request, deps: None = Depends(rate_limit)) -> Dict[str, Any]:
    # Delete from uploaded_files; index maintenance is out of scope for demo
    target = UPLOAD_DIR / doc
    if not target.exists():
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        target.unlink()
        logger.info("Deleted document %s", doc)
        return {"ok": True, "deleted": doc}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {e}")


@app.get("/api/stats", response_model=StatsResponse)
def api_stats(request: Request, deps: None = Depends(rate_limit)) -> StatsResponse:
    s = _doc_stats()
    return StatsResponse(documents=s["documents"], chunks=s["chunks"], min_page=s["min_page"], max_page=s["max_page"])


@app.get("/api/search")
def api_search(query: str, k: int = 5, request: Request = None, deps: None = Depends(rate_limit)) -> Dict[str, Any]:
    if not query or len(query) < 2:
        raise HTTPException(status_code=400, detail="Query must be provided")
    try:
        engine = RAGEngine(auto_embeddings=False)
        chunks = engine.retrieve_context(query, k=k)
        return {"chunks": chunks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/query")
async def api_query(req: QueryRequest, request: Request, deps: None = Depends(rate_limit)):
    """RAG query with optional SSE streaming.

    - If `stream=false` (default), returns JSON with prompt, chunks, answer.
    - If `stream=true`, returns `text/event-stream` SSE with tokens as they are produced.
    """
    engine = RAGEngine(auto_embeddings=False)
    try:
        chunks = engine.retrieve_context(req.question, k=req.k)
        prompt = engine.generate_prompt(req.question, chunks)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {e}")

    if not req.stream:
        # Non-streaming: attempt Gemini, fall back gracefully
        result = engine.answer_with_gemini(req.question, k=req.k, model=req.model, temperature=req.temperature)
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
        result = engine.answer_with_gemini(req.question, k=req.k, model=req.model, temperature=req.temperature)
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