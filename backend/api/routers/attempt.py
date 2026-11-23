"""Try first: feedback on the student's own attempt (one model call), and a similar practice question (up to two)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from ... import attempt_feedback, similar_practice
from ...rag_engine import RAGEngine
from ..deps import common_dependencies, get_engine, raise_if_failed
from ..errors import ERROR_RESPONSES, ApiError
from ..schemas import AttemptFeedback, AttemptFeedbackRequest, AttemptItem, CitationCheck, Chunk, SimilarPractice, SimilarPracticeRequest

router = APIRouter(prefix="/api/v1", tags=["tutor"], dependencies=common_dependencies, responses=ERROR_RESPONSES)


@router.post(
    "/attempt/feedback",
    response_model=AttemptFeedback,
    summary="Feedback on your own attempt, checked against your sources (never the full solution)",
    description=(
        "Splits the attempt into steps, code lines or sentences and judges each one as `supported`, `contradicted` or "
        "`not_covered` by the passages retrieved for the question (or the `context` given). Each verdict's citations are "
        "checked against those passages the same way `/ask` checks an answer; a verdict without a verified citation has "
        "`checked: false` and should be shown as not checked against your sources. The feedback gives pointers only: "
        "ask `/ask` (\"Show me the evidence\") for the answer. With `judge: problem` a unit may instead be judged on whether "
        "its reasoning works for the problem statement: such an item has `basis: problem`, `checked: false` and no verified "
        "citation, and must be shown as reasoned from the problem, not from your sources. One model call per request; "
        "nothing is cached or stored."
    ),
)
async def feedback(req: AttemptFeedbackRequest, engine: RAGEngine = Depends(get_engine)):
    try:
        units = attempt_feedback.split_units(req.attempt, req.format)
    except attempt_feedback.AttemptTooLong as e:
        raise ApiError(422, str(e), code="attempt_too_long")
    if not units:
        raise ApiError(422, "Write at least one step, line or sentence of your attempt.", code="attempt_empty")
    if req.context is not None:
        chunks = [c.model_dump() for c in req.context]
    elif req.k:
        try:
            chunks = await run_in_threadpool(engine.retrieve_context, req.question, req.k)
        except Exception:
            raise ApiError(500, "Retrieval failed", code="retrieval_error")
    else:
        chunks = []
    res = raise_if_failed(await run_in_threadpool(
        attempt_feedback.give_feedback, req.question, req.attempt, req.format, chunks, req.language, req.model, req.temperature, req.judge
    ))
    return AttemptFeedback(
        format=req.format,
        units=res["units"],
        items=[AttemptItem(**i) for i in res["items"]],
        summary=res["summary"],
        chunks=[Chunk(**c) for c in chunks if (c.get("text") or "").strip()],
        model=res.get("model"),
        unverified_citations=res["unverified_citations"],
        withheld=res["withheld"],
    )


@router.post(
    "/practice/similar",
    response_model=SimilarPractice,
    summary="One new practice question on the same concept, from the same passages (answer never returned)",
    description=(
        "Writes one question from the `context` passages. It is returned only if it cites one of them, shares content "
        "with that passage, does not give its answer away and is not a rewording of `question` or `previous`. Answer it "
        "with `/attempt/feedback`. Up to two model calls per request (a second only when a guard rejects the first draft, "
        "never after a provider, quota or daily-limit error); each counts against the daily limit. Nothing is cached or stored."
    ),
)
async def similar(req: SimilarPracticeRequest):
    res = raise_if_failed(await run_in_threadpool(
        similar_practice.similar_question, req.question, [c.model_dump() for c in req.context], req.previous, req.model, req.temperature
    ))
    return SimilarPractice(question=res["question"], citations=[CitationCheck(**c) for c in res["citations"]], model=res.get("model"))
