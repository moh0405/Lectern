"""A tool-using agent: the model decides which tools to call (ReAct loop), streamed as Server-Sent Events."""

from __future__ import annotations

import logging
import time
from types import SimpleNamespace
from typing import Any, Iterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from ...llm_providers import create_llm
from ...rag_engine import RAGEngine
from ...tool_chat import ToolCallingUnsupported
from ...tools import ToolContext, default_tools
from ..analytics_store import AnalyticsStore
from ..deps import common_dependencies, get_analytics, get_engine, get_study
from ..errors import ERROR_RESPONSES, ApiError
from ..schemas import Chunk, AgentRunRequest, SseAgentRunDone, SseMeta, SseThought, SseToken, SseToolCall, SseToolResult
from ..settings import settings
from .ask import _llm_failure, _record, sse
from .leetcode import get_leetcode

logger = logging.getLogger("ai-study-mentor.api")

router = APIRouter(prefix="/api/v1/agent", tags=["agent"], dependencies=common_dependencies, responses=ERROR_RESPONSES)


@router.post(
    "/run/stream",
    summary="Run the tool-using agent, streamed as Server-Sent Events",
    description=(
        "The model is given the task and a set of tools (search the study material, list documents, read a page, solve "
        "math, find a LeetCode problem) and decides which to call, in a loop: it asks for a tool, the server runs it and "
        "returns the result, and the model asks again or answers. The loop is bounded (`max_steps` model turns, then a "
        "forced wrap-up) and every model turn counts against the daily cap. Tools that change data are available only when "
        "the deployment sets `AGENT_ALLOW_WRITES=1`; a request cannot enable them.\\n\\n"
        "Events: `thought` (`{text}`), `tool_call` (`{name, arguments}`), `tool_result` (`{name, summary, error}`), then "
        "`meta` (`{chunks}`, the passages the tools returned), `token` (the whole final answer), and `done` or `error`. "
        "Needs the Gemini provider; other providers answer with `tools_unsupported`."
    ),
    responses={200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}}},
)
def agent_run_stream(
    req: AgentRunRequest,
    request: Request,
    engine: RAGEngine = Depends(get_engine),
    analytics: AnalyticsStore = Depends(get_analytics),
):
    try:
        from ...react_agent import SYSTEM_PROMPT, run_react_agent
    except ImportError:  # langgraph is an optional extra
        raise ApiError(503, "The agent needs the 'agent' extra (langgraph) on the server", code="agent_unavailable")

    tools = default_tools(allow_writes=settings.agent_allow_writes)
    ctx = ToolContext(engine=engine, leetcode=lambda: get_leetcode(request), study=lambda: get_study(request))
    as_request: Any = SimpleNamespace(question=req.task, mode=None)  # what analytics records

    def events() -> Iterator[str]:
        t0 = time.time()
        answer = ""
        try:
            llm = create_llm(model=req.model, temperature=req.temperature)
            chat = llm.start_tool_chat(SYSTEM_PROMPT, [t.spec() for t in tools], temperature=req.temperature)
        except ToolCallingUnsupported as e:
            yield sse("error", {"code": "tools_unsupported", "message": str(e)})
            return
        except Exception as e:
            code, msg = _llm_failure(str(e))
            yield sse("error", {"code": code, "message": msg})
            return
        try:
            for ev in run_react_agent(chat, tools, ctx, req.task, max_steps=req.max_steps):
                name, data = ev["event"], ev["data"]
                if name == "thought":
                    data = SseThought(**data).model_dump()
                elif name == "tool_call":
                    data = SseToolCall(**data).model_dump()
                elif name == "tool_result":
                    data = SseToolResult(**data).model_dump()
                elif name == "meta":
                    data = SseMeta(chunks=[Chunk(**c) for c in data["chunks"]]).model_dump()
                elif name == "token":
                    data = SseToken(**data).model_dump()
                elif name == "done":
                    answer = data.pop("_answer")
                    data = SseAgentRunDone(model=getattr(chat, "model", None), **data).model_dump()
                yield sse(name, data)
        except Exception as e:
            logger.exception("Agent run failed")
            code, msg = _llm_failure(str(e))
            _record(analytics, as_request, ctx.passages, t0, "", answer, False)
            yield sse("error", {"code": code, "message": msg})
            return
        _record(analytics, as_request, ctx.passages, t0, "", answer, True)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
