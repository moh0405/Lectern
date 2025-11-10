from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any

from .rag_engine import RAGEngine


app = FastAPI(title="AI Study Mentor API", version="0.1.0")


class QueryRequest(BaseModel):
    question: str
    k: int = 3


class Chunk(BaseModel):
    text: str
    doc: str
    page: int | None
    score: float


class QueryResponse(BaseModel):
    prompt: str
    chunks: List[Chunk]


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    # Use hardened RAGEngine: no auto embeddings at init; keyword fallback if needed
    engine = RAGEngine(auto_embeddings=False)
    chunks = engine.retrieve_context(req.question, k=req.k)
    prompt = engine.generate_prompt(req.question, chunks)
    return QueryResponse(prompt=prompt, chunks=[Chunk(**c) for c in chunks])


class AnswerRequest(BaseModel):
    question: str
    k: int = 3
    model: str | None = None  # Gemini model optional; defaults via env
    temperature: float = 0.2


class AnswerResponse(BaseModel):
    prompt: str
    chunks: List[Chunk]
    answer: str | None = None
    ok: bool
    model: str | None = None
    error: str | None = None


@app.post("/answer", response_model=AnswerResponse)
def answer(req: AnswerRequest) -> AnswerResponse:
    # Cloud-only path: use Gemini for generation, keep RAG retrieval identical
    engine = RAGEngine(auto_embeddings=False)
    result = engine.answer_with_gemini(req.question, k=req.k, model=req.model, temperature=req.temperature)
    chunks = [Chunk(**c) for c in result.get("chunks", [])]
    return AnswerResponse(
        prompt=result.get("prompt", ""),
        chunks=chunks,
        answer=result.get("answer"),
        ok=bool(result.get("ok", False)),
        model=result.get("model"),
        error=result.get("error")
    )