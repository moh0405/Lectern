"""Embedding-space visualization data."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.concurrency import run_in_threadpool

from ...projection import pca_project, sample_indices
from ...rag_engine import RAGEngine
from ..deps import common_dependencies, get_engine
from ..errors import ERROR_RESPONSES
from ..schemas import Projection, ProjectionPoint

router = APIRouter(prefix="/api/v1", tags=["visualize"], dependencies=common_dependencies, responses=ERROR_RESPONSES)


def _project(engine: RAGEngine, limit: int) -> Projection:
    store = engine.store
    n = len(store)
    if n == 0:
        return Projection(points=[], explained_variance=[0.0, 0.0, 0.0], method="pca", embedder=None, semantic=False, total_chunks=0)
    idx = sample_indices(n, limit)
    coords, explained = pca_project(store.embeddings[idx], 3)
    points = []
    for row, i in enumerate(idx):
        c = store.chunks[int(i)]
        text = (c.get("text") or "").strip().replace("\n", " ")
        points.append(
            ProjectionPoint(
                x=float(coords[row, 0]), y=float(coords[row, 1]), z=float(coords[row, 2]),
                doc=c.get("doc") or "", page=c.get("page"), text=text[:200], index=int(i),
            )
        )
    name = store.embedder_name or ""
    return Projection(
        points=points,
        explained_variance=explained,
        method="pca",
        embedder=name or None,
        semantic=not name.startswith("hashing"),
        total_chunks=n,
    )


@router.get(
    "/embeddings/projection",
    response_model=Projection,
    summary="3D PCA projection of indexed passages (for the embedding-space view)",
    description=(
        "Projects the stored embeddings onto their top three principal components. `explained_variance` says how much of "
        "the structure each axis keeps, and `semantic` is false when the index was built with the non-semantic hashing "
        "embedder (distances then reflect shared words, not meaning)."
    ),
)
async def projection(limit: int = Query(400, ge=10, le=1000), engine: RAGEngine = Depends(get_engine)):
    return await run_in_threadpool(_project, engine, limit)
