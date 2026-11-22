"""A tool-using agent: the model decides which tools to call (ReAct loop), streamed as Server-Sent Events."""

from __future__ import annotations

import logging
import threading
import time
from types import SimpleNamespace
from typing import Any

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
from ..streaming import Emit, StreamCancelled, deadline_from, guarded_stream
from .ask import _llm_failure, _record, sse
from .leetcode import get_leetcode

logger = logging.getLogger("ai-study-mentor.api")

router = APIRouter(prefix="/api/v1/agent", tags=["agent"], dependencies=common_dependencies, responses=ERROR_RESPONSES)


class _Guarded:
    """A tool chat that refuses to start another model turn once the stream has given up (deadline or disconnect).
    A turn already in flight cannot be interrupted; the stream stops waiting for it instead."""

    def __init__(self, inner: Any, cancelled: threading.Event, deadline: float):
        self._inner, self._cancelled, self._deadline = inner, cancelled, deadline

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def send(self, message: Any) -> Any:
        if self._cancelled.is_set() or time.monotonic() >= self._deadline:
            raise StreamCancelled("the agent run is over its deadline or the client left")
        return self._inner.send(message)


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
        "The stream always ends with `done` or `error`. A run that is still going after `AGENT_DEADLINE_S` seconds (default "
        "100, counted from when the request arrived) ends with `error` code `timeout`. While a model call is pending the "
        "server sends SSE comment lines (`: keep-alive`) every few seconds; readers should ignore them. "
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

    started_at = getattr(request.state, "received_at", None) or time.monotonic()
    deadline = deadline_from(started_at, settings.agent_deadline_s)

    def work(emit: Emit, cancelled: threading.Event) -> None:
        t0 = time.time()
        try:
            llm = create_llm(model=req.model, temperature=req.temperature)
            chat = _Guarded(llm.start_tool_chat(SYSTEM_PROMPT, [t.spec() for t in tools], temperature=req.temperature), cancelled, deadline)
        except ToolCallingUnsupported as e:
            emit(sse("error", {"code": "tools_unsupported", "message": str(e)}))
            return
        except Exception as e:
            code, msg = _llm_failure(str(e))
            emit(sse("error", {"code": code, "message": msg}))
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
                    _record(analytics, as_request, ctx.passages, t0, "", answer, True)  # before `done`: the stream ends there
                emit(sse(name, data))
        except StreamCancelled:  # the deadline passed or the client left; the response has already said so
            _record(analytics, as_request, ctx.passages, t0, "", "", False)
            raise
        except Exception as e:
            logger.exception("Agent run failed")
            code, msg = _llm_failure(str(e))
            _record(analytics, as_request, ctx.passages, t0, "", "", False)
            emit(sse("error", {"code": code, "message": msg}))

    timeout_s = round(deadline - started_at)
    events = guarded_stream(
        work,
        deadline=deadline,
        keepalive_s=settings.stream_keepalive_s,
        timeout_frame=sse("error", {"code": "timeout", "message": f"The agent took longer than {timeout_s} seconds and was stopped. Try fewer steps or a simpler task."}),
        fallback_frame=sse("error", {"code": "llm_error", "message": "The agent stopped without finishing. Try again."}),
        name="agent-run",
    )

    return StreamingResponse(
        events,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
