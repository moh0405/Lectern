"""The agent stream always ends with a terminal event (`done` or `error`), however the run goes wrong.

Live-eval defect: on the public site an agent run streamed tool steps and then the page waited for a `done` that
never came. These tests pin the guarantees that make that impossible from the server side: exceptions anywhere, a
model failing mid-run, a model call that hangs past the deadline, and work that ends without saying so.
"""

from __future__ import annotations

import threading
import time

import pytest
from fastapi import Request

from backend.api.settings import settings
from backend.api.streaming import guarded_stream
from backend.tool_chat import ToolCall, TurnResult

from .test_api_features import parse_sse
from .test_tool_agent import ANSWER, URL, call, names, scripted

TERMINAL = {"done", "error"}


def stream(client, **body):
    r = client.post(URL, json={"task": "what is a binary heap", **body})
    assert r.status_code == 200, r.text
    return r.text, parse_sse(r.text)


def assert_ends_once_with_terminal(events):
    assert events, "the stream sent no events"
    assert events[-1][0] in TERMINAL
    assert sum(1 for n, _ in events if n in TERMINAL) == 1


def test_the_stream_opens_with_a_comment_so_headers_leave_before_the_first_model_call(indexed, fake_gemini):
    fake_gemini.tool_script = scripted(ANSWER)
    text, events = stream(indexed)
    assert text.startswith(": ")
    assert names(events) == ["meta", "token", "done"]


def test_a_tool_that_raises_does_not_end_the_run(indexed, fake_gemini, monkeypatch):
    import dataclasses

    import backend.api.routers.agent as router

    def explode(ctx, args):
        raise RuntimeError("disk on fire")

    real = router.default_tools
    monkeypatch.setattr(router, "default_tools", lambda **k: [dataclasses.replace(t, run=explode) if t.name == "search_documents" else t for t in real(**k)])
    fake_gemini.tool_script = scripted(call("search_documents", query="heap"), TurnResult(text="Nothing found."))
    _, events = stream(indexed)
    assert names(events) == ["tool_call", "tool_result", "meta", "token", "done"]
    assert events[1][1]["error"] is True
    assert_ends_once_with_terminal(events)


def test_quota_running_out_after_the_first_turn_ends_with_a_typed_error(indexed, fake_gemini):
    """What CloudWatch shows for the failing live run: turn 1 and its tool succeed, turn 2 gets 429."""

    def second_turn_429(message):
        raise RuntimeError("429 RESOURCE_EXHAUSTED. You exceeded your current quota")

    fake_gemini.tool_script = scripted(call("search_documents", query="binary heap"), second_turn_429)
    _, events = stream(indexed, max_steps=3)
    assert names(events) == ["tool_call", "tool_result", "error"]
    assert events[-1][1]["code"] == "quota_exhausted" and events[-1][1]["message"]


def test_an_unexpected_error_in_the_agent_loop_still_ends_with_error(indexed, fake_gemini, monkeypatch):
    import backend.react_agent as react

    def broken(*a, **k):
        yield {"event": "thought", "data": {"text": "starting"}}
        raise KeyError("state got corrupted")

    monkeypatch.setattr(react, "run_react_agent", broken)
    _, events = stream(indexed)
    assert names(events) == ["thought", "error"] and events[-1][1]["code"] == "llm_error"


def test_failover_exhaustion_on_the_first_turn_ends_with_error(indexed, fake_gemini):
    def overloaded(turn, message):
        raise RuntimeError("503 UNAVAILABLE: The model is overloaded. Please try again later.")

    fake_gemini.tool_script = overloaded
    _, events = stream(indexed)
    assert names(events) == ["error"] and events[0][1]["code"] == "llm_error"


def test_a_model_call_that_hangs_past_the_deadline_ends_with_a_timeout_error(indexed, fake_gemini, monkeypatch):
    monkeypatch.setattr(settings, "agent_deadline_s", 1.0)
    monkeypatch.setattr(settings, "stream_keepalive_s", 0.2)
    release = threading.Event()

    def hang(message):
        release.wait(10)  # a provider that never answers within the budget
        return ANSWER

    fake_gemini.tool_script = scripted(call("search_documents", query="heap"), hang)
    t0 = time.monotonic()
    try:
        text, events = stream(indexed)
    finally:
        release.set()
    elapsed = time.monotonic() - t0
    assert elapsed < 5, f"the deadline did not stop the stream ({elapsed:.1f}s)"
    assert names(events) == ["tool_call", "tool_result", "error"]
    assert events[-1][1]["code"] == "timeout" and "seconds" in events[-1][1]["message"]
    assert ": keep-alive" in text  # comments flowed while the model call was pending


def test_no_new_model_turn_starts_after_the_deadline(indexed, fake_gemini, monkeypatch):
    monkeypatch.setattr(settings, "agent_deadline_s", 1.0)
    monkeypatch.setattr(settings, "stream_keepalive_s", 0.1)
    turns = []

    def slow_tool_loop(turn, message):
        turns.append(turn)
        time.sleep(0.6)
        return TurnResult(calls=[ToolCall("search_documents", {"query": f"heap {turn}"})])

    fake_gemini.tool_script = slow_tool_loop
    _, events = stream(indexed, max_steps=8)
    assert events[-1][0] == "error" and events[-1][1]["code"] == "timeout"
    time.sleep(1.0)  # let the background run notice
    assert len(turns) <= 3, turns  # it stopped calling the model soon after the deadline


def test_the_deadline_counts_from_when_the_request_arrived(indexed, fake_gemini, monkeypatch):
    """Time spent before the handler (a cold start waiting for the index) uses up the same budget."""
    import backend.api.routers.agent as router

    monkeypatch.setattr(settings, "agent_deadline_s", 5.0)
    seen = {}
    real = router.guarded_stream

    def spy(work, **kw):
        seen["budget"] = kw["deadline"] - time.monotonic()
        return real(work, **kw)

    monkeypatch.setattr(router, "guarded_stream", spy)
    from backend.api.deps import get_engine

    def slow_engine(request: Request):  # stands in for waiting on a cold start before the handler runs
        time.sleep(0.6)
        return get_engine(request)

    indexed.app.dependency_overrides[get_engine] = slow_engine
    try:
        fake_gemini.tool_script = scripted(ANSWER)
        stream(indexed)
    finally:
        indexed.app.dependency_overrides.pop(get_engine, None)
    assert 0 < seen["budget"] <= 5.0 - 0.5


# ------------------------------------------------------------- guarded_stream itself

def _frames(gen):
    return list(gen)


def kw(**extra):
    base = dict(deadline=time.monotonic() + 5, keepalive_s=0.05, timeout_frame="event: error\ndata: {\"code\": \"timeout\"}\n\n",
                fallback_frame="event: error\ndata: {\"code\": \"llm_error\"}\n\n")
    return {**base, **extra}


def test_work_that_returns_without_a_terminal_event_gets_one():
    out = _frames(guarded_stream(lambda emit, c: emit("event: thought\ndata: {}\n\n"), **kw()))
    assert out[-1].startswith("event: error") and '"llm_error"' in out[-1]


def test_work_that_raises_gets_a_terminal_event():
    def work(emit, cancelled):
        emit("event: thought\ndata: {}\n\n")
        raise ValueError("bug")

    out = _frames(guarded_stream(work, **kw()))
    assert out[-1].startswith("event: error")


def test_nothing_is_sent_after_the_terminal_event():
    def work(emit, cancelled):
        emit("event: done\ndata: {}\n\n")
        time.sleep(0.2)
        with pytest.raises(Exception):
            emit("event: token\ndata: {}\n\n")

    out = _frames(guarded_stream(work, **kw()))
    assert out[-1].startswith("event: done") and not any(f.startswith("event: token") for f in out)


def test_a_client_that_goes_away_cancels_the_work():
    seen = threading.Event()

    def work(emit, cancelled):
        emit("event: thought\ndata: {}\n\n")
        cancelled.wait(5)
        seen.set()

    gen = guarded_stream(work, **kw())
    assert next(gen).startswith(":")
    assert next(gen).startswith("event: thought")
    gen.close()  # what Starlette does when the client disconnects
    assert seen.wait(2)
