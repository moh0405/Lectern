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