"""Tutoring tools built on the same material: concept maps, Socratic hints, synthesis, adaptive explanations, math."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from ... import advanced_ai
from ...rag_engine import RAGEngine
from ..deps import common_dependencies, get_engine, raise_if_failed
from ..errors import ERROR_RESPONSES, ApiError
from ..schemas import (
    Adaptive,
    AdaptiveRequest,
    Chunk,
    ConceptEdge,
    ConceptMap,
    ConceptNode,
    MathRequest,
    MathResult,
    Socratic,
    SocraticRequest,
    Synthesis,
    SynthesisCitation,
    SynthesisRequest,
    TopicRequest,
)

router = APIRouter(prefix="/api/v1", tags=["tutor"], dependencies=common_dependencies, responses=ERROR_RESPONSES)


def _strs(value: Any) -> List[str]:
    if isinstance(value, str):
        return [value]
    return [str(v) for v in (value or [])]


@router.post("/concept-map", response_model=ConceptMap, summary="Concept map (nodes, edges, Graphviz DOT) for a topic")
async def concept_map(req: TopicRequest, engine: RAGEngine = Depends(get_engine)):
    res = raise_if_failed(await run_in_threadpool(advanced_ai.build_concept_map, req.topic, None, req.temperature, engine))
    nodes: List[ConceptNode] = []
    seen = set()
    for n in res.get("nodes") or []:
        if isinstance(n, dict) and n.get("id") and str(n["id"]) not in seen:
            seen.add(str(n["id"]))
            nodes.append(ConceptNode(id=str(n["id"]), label=str(n.get("label") or n["id"])))
    edges = [
        ConceptEdge(**{"from": str(e["from"]), "to": str(e["to"]), "label": e.get("label")})
        for e in (res.get("edges") or [])
        if isinstance(e, dict) and str(e.get("from")) in seen and str(e.get("to")) in seen
    ]
    dot = advanced_ai.concept_map_to_dot([n.model_dump() for n in nodes], [e.model_dump(by_alias=True) for e in edges])
    return ConceptMap(nodes=nodes, edges=edges, dot=dot, model=res.get("model"), warning=res.get("warning"))


@router.post("/socratic", response_model=Socratic, summary="Guiding questions and a hint ladder, without the answer")
async def socratic(req: SocraticRequest, engine: RAGEngine = Depends(get_engine)):
    chunks = await run_in_threadpool(engine.retrieve_context, req.question, req.k) if req.k else []
    res = raise_if_failed(
        await run_in_threadpool(advanced_ai.socratic_tutor, req.question, chunks, req.depth, req.temperature)
    )
    return Socratic(questions=_strs(res.get("questions")), hints=_strs(res.get("hints")),
                    model=res.get("model"), warning=res.get("warning"))


@router.post("/synthesis", response_model=Synthesis, summary="Compare how each document explains a topic")
async def synthesis(req: SynthesisRequest, engine: RAGEngine = Depends(get_engine)):
    res = raise_if_failed(
        await run_in_threadpool(advanced_ai.multi_document_synthesis, req.topic, req.k_per_doc, req.temperature, engine)
    )
    cites: List[SynthesisCitation] = []
    for c in res.get("citations") or []:
        if isinstance(c, dict):
            cites.append(SynthesisCitation(doc=str(c.get("doc", "")), point=str(c.get("point", ""))))
        else:
            cites.append(SynthesisCitation(doc="", point=str(c)))
    return Synthesis(
        similarities=_strs(res.get("similarities")),
        conflicts=_strs(res.get("conflicts")),
        synthesis=str(res.get("synthesis") or ""),
        citations=cites,
        model=res.get("model"),
        warning=res.get("warning"),
    )


@router.post("/adaptive", response_model=Adaptive, summary="Explain at a chosen level (ELI5 to Expert) with a mini quiz")
async def adaptive(req: AdaptiveRequest, engine: RAGEngine = Depends(get_engine)):
    res = raise_if_failed(await run_in_threadpool(advanced_ai.adaptive_explain, req.question, req.level, req.temperature, engine))
    return Adaptive(
        answer=res.get("answer") or "",
        chunks=[Chunk(**c) for c in res.get("chunks") or []],
        level=req.level,
        model=res.get("model"),
        warning=res.get("warning"),
    )


@router.post("/math", response_model=MathResult, summary="Symbolic math with LaTeX output (simplify, differentiate, integrate, solve, ...)")
async def math(req: MathRequest):
    res: Dict[str, Any] = await run_in_threadpool(advanced_ai.math_solve, req.input)
    if not res.get("ok"):
        raise ApiError(422, str(res.get("error") or "Could not compute"), code="math_error")
    return MathResult(kind=res["kind"], latex=res["latex"], steps=_strs(res.get("steps")))
