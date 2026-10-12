"""Study aids: notes from a chat, document export, and query analytics."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from fastapi.concurrency import run_in_threadpool

from ...export_utils import markdown_to_html_document, markdown_to_pdf
from ...rag_engine import RAGEngine
from ..analytics_store import AnalyticsStore
from ..deps import common_dependencies, get_analytics, get_engine
from ..errors import ERROR_RESPONSES, ApiError
from ..schemas import AnalyticsEvent, AnalyticsSummary, Cleared, ExportRequest, Notes, NotesRequest

router = APIRouter(prefix="/api/v1", tags=["study"], dependencies=common_dependencies, responses=ERROR_RESPONSES)


@router.post("/notes", response_model=Notes, summary="Turn a Q&A history into Markdown study notes")
async def notes(req: NotesRequest, engine: RAGEngine = Depends(get_engine)):
    history = [{"q": h.q, "answer": h.answer} for h in req.history]
    res = await run_in_threadpool(engine.summarize_chat, history, None, req.temperature)
    return Notes(markdown=res.get("markdown") or "")


@router.post(
    "/export",
    summary="Render Markdown as a downloadable PDF, HTML or Markdown file",
    responses={200: {"content": {"application/pdf": {}, "text/html": {}, "text/markdown": {}}}},
)
async def export(req: ExportRequest):
    name = req.filename.strip() or "study-notes"
    if req.format == "md":
        body, media, ext = req.markdown.encode("utf-8"), "text/markdown; charset=utf-8", "md"
    elif req.format == "html":
        body, media, ext = markdown_to_html_document(req.markdown, title=name).encode("utf-8"), "text/html; charset=utf-8", "html"
    else:
        pdf = await run_in_threadpool(markdown_to_pdf, req.markdown)
        if pdf is None:
            raise ApiError(503, "PDF export needs the 'export' extra (reportlab)", code="export_unavailable")
        body, media, ext = pdf, "application/pdf", "pdf"
    return Response(content=body, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{name}.{ext}"'})


@router.get("/analytics", response_model=AnalyticsSummary, summary="Totals, document usage and recent questions")
def analytics_summary(limit: int = Query(20, ge=0, le=200), analytics: AnalyticsStore = Depends(get_analytics)):
    return AnalyticsSummary(**analytics.summary(), recent=[AnalyticsEvent(**e) for e in analytics.events(limit)])


@router.delete("/analytics", response_model=Cleared, summary="Delete all recorded analytics")
def analytics_clear(analytics: AnalyticsStore = Depends(get_analytics)):
    return Cleared(ok=True, removed=analytics.clear())
