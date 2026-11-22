"""The tool-using (ReAct) agent: the model chooses tools, the server runs them, the loop is bounded."""

from __future__ import annotations

import json

import pytest

from backend.tool_chat import ToolCall, TurnResult

from .test_api_features import parse_sse

URL = "/api/v1/agent/run/stream"


def run(client, task="what is a binary heap", **extra):
    r = client.post(URL, json={"task": task, **extra})
    assert r.status_code == 200, r.text
    return parse_sse(r.text)


def names(events):
    return [n for n, _ in events]


def scripted(*turns):
    """A model that plays the given turns in order; each is a TurnResult, or a callable(message) -> TurnResult."""
    plan = list(turns)

    def script(turn, message):
        step = plan[min(turn, len(plan) - 1)]
        return step(message) if callable(step) else step

    return script


def call(name, **args):
    return TurnResult(calls=[ToolCall(name, args)])


ANSWER = TurnResult(text="A binary heap is a complete binary tree. [heaps.pdf (page 1)]")


def test_the_model_chooses_a_tool_reads_the_result_then_answers(indexed, fake_gemini):
    fake_gemini.tool_script = scripted(call("search_documents", query="binary heap"), ANSWER)
    events = run(indexed)
    kinds = names(events)
    assert kinds == ["tool_call", "tool_result", "meta", "token", "done"]
    assert events[0][1] == {"name": "search_documents", "arguments": {"query": "binary heap"}}
    assert events[1][1]["error"] is False and "heaps.pdf" in events[1][1]["summary"]
    assert events[2][1]["chunks"][0]["doc"] == "heaps.pdf"  # the passages the tool handed out
    assert events[3][1]["text"] == ANSWER.text
    done = events[-1][1]
    assert done["steps"] == 2 and done["tool_calls"] == 1 and done["llm_calls"] == 2 and done["wrapped_up"] is False
    assert done["unverified_citations"] == 0 and done["citations"][0]["status"] == "ok" and done["model"] == "fake-model"


def test_the_tool_result_really_reaches_the_model(indexed, fake_gemini):
    seen = []

    def answer(message):
        seen.append(message)
        return ANSWER

    fake_gemini.tool_script = scripted(call("search_documents", query="heap"), answer)
    run(indexed)
    payload = seen[0][0].payload
    assert payload["count"] >= 1 and payload["passages"][0]["doc"] == "heaps.pdf" and "binary heap" in payload["passages"][0]["text"]


def test_several_tools_in_one_task(indexed, fake_gemini):
    fake_gemini.tool_script = scripted(
        TurnResult(calls=[ToolCall("list_documents", {}), ToolCall("search_documents", {"query": "heap"})]),
        call("find_leetcode_problem", query="two sum", difficulty="Easy"),
        ANSWER,
    )
    events = run(indexed)
    results = [d for n, d in events if n == "tool_result"]
    assert [r["name"] for r in results] == ["list_documents", "search_documents", "find_leetcode_problem"]
    assert results[0]["summary"] == "1 document" and "problem" in results[2]["summary"]
    assert events[-1][1]["tool_calls"] == 3 and events[-1][1]["steps"] == 3


def test_math_runs_in_the_sandboxed_solver(indexed, fake_gemini):
    fake_gemini.tool_script = scripted(call("solve_math", expression="integrate x^2"), TurnResult(text="It is x^3/3 + C."))
    events = run(indexed)
    result = next(d for n, d in events if n == "tool_result")
    assert result["error"] is False and "x" in result["summary"]


def test_read_page_returns_the_pages_text_and_counts_it_as_a_source(indexed, fake_gemini):
    fake_gemini.tool_script = scripted(call("read_page", document="heaps.pdf", page=1), ANSWER)
    events = run(indexed)
    assert next(d for n, d in events if n == "tool_result")["summary"].startswith("heaps.pdf page 1")
    assert events[-1][1]["unverified_citations"] == 0


def test_a_failing_tool_is_reported_to_the_model_which_can_recover(indexed, fake_gemini):
    fake_gemini.tool_script = scripted(call("read_page", document="nope.pdf", page=1), call("search_documents", query="heap"), ANSWER)
    events = run(indexed)
    results = [d for n, d in events if n == "tool_result"]
    assert results[0]["error"] is True and "Unknown document" in results[0]["summary"]
    assert results[1]["error"] is False and names(events)[-1] == "done"


def test_unknown_tools_and_bad_arguments_are_errors_not_crashes(indexed, fake_gemini):
    fake_gemini.tool_script = scripted(
        TurnResult(calls=[ToolCall("delete_everything", {}), ToolCall("search_documents", {}), ToolCall("find_leetcode_problem", {"query": "x", "difficulty": "Nightmare"})]),
        ANSWER,
    )
    results = [d for n, d in run(indexed) if n == "tool_result"]
    assert [r["error"] for r in results] == [True, True, True]
    assert "Unknown tool" in results[0]["summary"] and "'query' is required" in results[1]["summary"] and "Easy, Medium or Hard" in results[2]["summary"]


def test_an_identical_repeated_call_is_not_run_again(indexed, fake_gemini):
    fake_gemini.tool_script = scripted(call("search_documents", query="heap"), call("search_documents", query="heap"), ANSWER)
    results = [d for n, d in run(indexed) if n == "tool_result"]
    assert results[0]["error"] is False
    assert results[1]["error"] is True and "already made this exact call" in results[1]["summary"]


def test_the_step_limit_forces_a_final_answer(indexed, fake_gemini):
    fake_gemini.tool_script = scripted(call("search_documents", query="a"), call("search_documents", query="b"), TurnResult(text="Best effort. [heaps.pdf (page 1)]"))  # turn 3 is the forced wrap-up
    events = run(indexed, max_steps=2)
    done = events[-1][1]
    assert done["wrapped_up"] is True and done["steps"] == 2 and done["llm_calls"] == 3  # two turns, then the wrap-up
    assert "Best effort" in next(d for n, d in events if n == "token")["text"]
    assert any(n == "thought" and "Step limit" in d["text"] for n, d in events)


def test_a_model_that_never_stops_calling_tools_still_ends(indexed, fake_gemini):
    fake_gemini.tool_script = scripted(call("search_documents", query="x"))  # asks for a tool on every turn, forever
    events = run(indexed, max_steps=3)
    done = events[-1]
    assert done[0] == "done" and done[1]["wrapped_up"] is True and done[1]["llm_calls"] <= 4
    assert "could not finish" in next(d for n, d in events if n == "token")["text"]


def test_too_many_calls_in_one_turn_are_cut_off(indexed, fake_gemini):
    fake_gemini.tool_script = scripted(TurnResult(calls=[ToolCall("list_documents", {}) for _ in range(6)]), ANSWER)
    results = [d for n, d in run(indexed) if n == "tool_result"]
    assert len(results) == 6 and sum(r["error"] for r in results) == 5  # the first runs; the repeats are refused (the same call)


def test_citations_in_the_final_answer_are_checked_against_what_the_tools_returned(indexed, fake_gemini):
    fake_gemini.tool_script = scripted(call("search_documents", query="heap"), TurnResult(text="It is a tree. [Invented Notes.pdf (page 9)]"))
    done = run(indexed)[-1][1]
    assert done["unverified_citations"] == 1 and done["citations"][0]["status"] == "unknown_source"


def test_thoughts_alongside_tool_calls_are_streamed(indexed, fake_gemini):
    fake_gemini.tool_script = scripted(TurnResult(text="I should look this up.", calls=[ToolCall("search_documents", {"query": "heap"})]), ANSWER)
    events = run(indexed)
    assert events[0] == ("thought", {"text": "I should look this up."})


def test_an_empty_final_turn_gets_an_honest_fallback(indexed, fake_gemini):
    fake_gemini.tool_script = scripted(call("search_documents", query="heap"), TurnResult(text=""))
    assert "could not finish" in next(d for n, d in run(indexed) if n == "token")["text"]


def test_write_tools_are_not_offered_by_default_and_a_request_cannot_turn_them_on(indexed, fake_gemini):
    def script(turn, message):
        return call("save_flashcard", front="Q", back="A") if turn == 0 else ANSWER

    fake_gemini.tool_script = script
    events = run(indexed, task="make me a flashcard", **{"allow_writes": True})  # an unknown field is ignored
    result = next(d for n, d in events if n == "tool_result")
    assert result["error"] is True and "Unknown tool" in result["summary"]
    assert indexed.get("/api/v1/cards").json()["stats"]["total"] == 0


def test_write_tools_work_when_the_deployment_allows_them(indexed, fake_gemini, monkeypatch):
    from backend.api.settings import settings

    monkeypatch.setattr(settings, "agent_allow_writes", True)
    fake_gemini.tool_script = scripted(call("save_flashcard", front="What is a heap?", back="A tree"), TurnResult(text="Saved."))
    result = next(d for n, d in run(indexed, task="make me a flashcard") if n == "tool_result")
    assert result == {"name": "save_flashcard", "summary": "saved", "error": False}
    assert indexed.get("/api/v1/cards").json()["stats"]["total"] == 1


def test_running_out_of_quota_ends_with_an_error_event(indexed, fake_gemini):
    def boom(turn, message):
        raise RuntimeError("429 RESOURCE_EXHAUSTED: you exceeded your current quota")

    fake_gemini.tool_script = boom
    events = run(indexed)
    assert names(events) == ["error"] and events[0][1]["code"] == "quota_exhausted"


def test_a_missing_model_key_is_reported_first(indexed, fake_gemini):
    fake_gemini.fail_with = RuntimeError("GEMINI_API_KEY is not set")
    events = run(indexed)
    assert names(events) == ["error"] and events[0][1]["code"] == "llm_unavailable"


def test_a_provider_without_tool_calling_says_so(indexed, monkeypatch):
    import backend.api.routers.agent as router
    from backend.tool_chat import ToolCallingUnsupported

    class NoTools:
        def __init__(self, *a, **k):
            pass

        def start_tool_chat(self, *a, **k):
            raise ToolCallingUnsupported("Tool calling is implemented for the Gemini provider only.")

    monkeypatch.setattr(router, "create_llm", NoTools)
    events = run(indexed)
    assert names(events) == ["error"] and events[0][1]["code"] == "tools_unsupported"


def test_every_model_turn_counts_against_the_daily_cap(indexed, fake_gemini, monkeypatch):
    from backend import spend_cap

    calls = []
    cap = spend_cap.DailyCap(limit=2)
    original = cap.reserve
    monkeypatch.setattr(cap, "reserve", lambda: (calls.append(1), original())[1])
    monkeypatch.setattr(spend_cap, "get_cap", lambda: cap)
    fake_gemini.tool_script = scripted(call("search_documents", query="heap"), call("search_documents", query="other"), ANSWER)
    # The fake model is not wrapped by create_llm, so wrap its chat the way create_llm would.
    import backend.api.routers.agent as router

    base = router.create_llm

    def wrapped(*a, **k):
        return spend_cap.wrap(base(*a, **k))

    monkeypatch.setattr(router, "create_llm", wrapped)
    events = run(indexed)
    assert len(calls) == 3 or events[-1][0] == "error"  # the third turn is refused: the cap is 2
    assert events[-1][0] == "error" and events[-1][1]["code"] == "daily_limit"


def test_runs_are_recorded_in_analytics(indexed, fake_gemini):
    fake_gemini.tool_script = scripted(call("search_documents", query="heap"), ANSWER)
    run(indexed)
    assert indexed.get("/api/v1/analytics").json()["queries"] == 1


def test_validation(indexed):
    assert indexed.post(URL, json={"task": ""}).status_code == 422
    assert indexed.post(URL, json={"task": "what is a heap", "max_steps": 9}).status_code == 422


def test_the_endpoint_and_its_events_are_in_the_published_schema(indexed):
    spec = indexed.get("/openapi.json").json()
    assert URL in spec["paths"] and {"SseToolCall", "SseToolResult", "SseThought", "SseAgentRunDone", "AgentRunRequest"} <= set(spec["components"]["schemas"])


def test_without_langgraph_the_endpoint_says_so(indexed, monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "backend.react_agent", None)
    r = indexed.post(URL, json={"task": "what is a heap"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "agent_unavailable"


def test_tool_results_are_bounded_before_they_reach_the_model():
    from backend.tools import RESULT_CHARS, bounded

    big = {"passages": [{"text": "x" * 1000} for _ in range(50)]}
    out = bounded(big)
    assert out["truncated"] is True and len(out["text"]) == RESULT_CHARS
    assert bounded({"ok": 1}) == {"ok": 1}


@pytest.mark.parametrize("args", [{"query": 5}, {"query": "heap", "k": "many"}])
def test_argument_types_are_validated(args):
    from backend.tools import ToolContext, default_tools, run_tool

    out = run_tool(default_tools(), ToolContext(engine=None), "search_documents", args)
    assert "error" in out and "Bad arguments" in out["error"]
    json.dumps(out)  # always serialisable


def test_tool_results_leave_out_the_page_key_for_sources_without_pages():
    from backend.tools import _passage

    assert "page" not in _passage({"doc": "hashing.md", "page": None, "text": "t"})
    assert _passage({"doc": "a.pdf", "page": 3, "text": "t"})["page"] == 3


def test_trace_summaries_use_the_right_plural():
    from backend.tools import summarize

    one = {"count": 1, "passages": [{"doc": "graphs.pdf"}]}
    assert summarize("search_documents", one) == "1 passage from graphs.pdf"
    assert summarize("search_documents", {"count": 3, "passages": []}) == "3 passages"
    assert summarize("search_documents", {"count": 0, "passages": []}) == "0 passages"
    assert summarize("list_documents", {"count": 1}) == "1 document"
    assert summarize("find_leetcode_problem", {"count": 2}) == "2 problems"


# --- Failing over to another model mid-run (live, 2026-11-22 01:11 UTC: turn 2 got a daily-quota 429 and the run ended) ---


def _gemini_behind_the_route(monkeypatch, plans):
    """The real GeminiClient and GeminiToolChat, on a scripted SDK client: the failover code under test is the real one."""
    import backend.api.routers.agent as router
    from backend import llm_config
    from backend.llm_config import GeminiClient

    from .test_llm_config import ALL, FakeClient, FakeModel
    from .test_tool_chat import Chats

    monkeypatch.setattr(llm_config.time, "sleep", lambda s: None)
    monkeypatch.delenv("GEMINI_FALLBACK_MODELS", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    llm_config._resolved_models.clear()
    fake = FakeClient(models=[FakeModel(m) for m in ALL])
    fake.chats = Chats(plans)
    monkeypatch.setattr(router, "create_llm", lambda model=None, temperature=0.2: GeminiClient(model=model, client=fake))
    return fake.chats


def test_turn_two_out_of_quota_is_served_by_the_next_model_with_the_tool_results_kept(indexed, monkeypatch):
    from backend.llm_config import DEFAULT_FALLBACKS, DEFAULT_MODEL

    from .test_tool_chat import QUOTA_DAY, SEARCH, Part, Resp

    lite = DEFAULT_FALLBACKS[0]
    chats = _gemini_behind_the_route(monkeypatch, {DEFAULT_MODEL: [SEARCH, QUOTA_DAY], lite: [Resp(Part(text=ANSWER.text))]})
    events = run(indexed)
    assert names(events) == ["tool_call", "tool_result", "thought", "meta", "token", "done"]
    assert f"{DEFAULT_MODEL} was unavailable" in events[2][1]["text"] and f"so {lite} continued with the tool results" in events[2][1]["text"]
    assert events[4][1]["text"] == ANSWER.text
    done = events[-1][1]
    assert done["model"] == lite and done["models"] == [DEFAULT_MODEL, lite]  # the badge names the model that wrote the answer
    assert done["tool_calls"] == 1 and done["llm_calls"] == 2  # the search was not run again
    replay = chats.last.sent[0]
    assert "what is a binary heap" in replay and "heaps.pdf" in replay  # the next model got the passages already found


def test_turn_two_with_every_model_exhausted_ends_with_a_typed_error(indexed, monkeypatch):
    from backend.llm_config import DEFAULT_FALLBACKS, DEFAULT_MODEL

    from .test_tool_chat import QUOTA_DAY, SEARCH

    plans = {DEFAULT_MODEL: [SEARCH, QUOTA_DAY], **{m: [QUOTA_DAY] for m in DEFAULT_FALLBACKS}}
    chats = _gemini_behind_the_route(monkeypatch, plans)
    events = run(indexed)
    assert names(events) == ["tool_call", "tool_result", "error"]
    assert events[-1][1]["code"] == "quota_exhausted"
    assert chats.created == [DEFAULT_MODEL, *DEFAULT_FALLBACKS]


def test_a_model_named_in_the_request_is_not_swapped_mid_run(indexed, monkeypatch):
    from backend.llm_config import DEFAULT_FALLBACKS

    from .test_tool_chat import QUOTA_DAY, SEARCH

    lite = DEFAULT_FALLBACKS[0]
    chats = _gemini_behind_the_route(monkeypatch, {lite: [SEARCH, QUOTA_DAY]})
    events = run(indexed, model=lite)
    assert events[-1][0] == "error" and events[-1][1]["code"] == "quota_exhausted" and chats.created == [lite]


def test_every_turn_on_one_model_reports_it(indexed, fake_gemini):
    fake_gemini.tool_script = scripted(call("search_documents", query="heap"), ANSWER)
    done = run(indexed)[-1][1]
    assert done["model"] == "fake-model" and done["models"] == ["fake-model", "fake-model"]
    assert not [e for e in run(indexed) if e[0] == "thought"]  # no failover, no note about one


def test_the_scripted_busy_model_shows_the_switch(indexed, fake_gemini):
    # The trigger the browser test uses (tests/fake_gemini.py).
    events = run(indexed, task="binary heap (busy model)")
    thought = [d["text"] for n, d in events if n == "thought"]
    assert thought == ["fake-model was unavailable (busy or out of quota), so gemini-3.1-flash-lite continued with the tool results gathered so far."]
    assert events[-1][1]["models"] == ["fake-model", "gemini-3.1-flash-lite"]


# ---------------------------------------------------------------- citations through a real run
class _Store:
    """Chunks as the store keeps them: a passage's end page lives in `extra`."""

    def __init__(self, chunks):
        self.chunks = chunks

    def _docstore_iter(self):
        return self.chunks

    def retrieve_context(self, query, k=4):
        return [{**c, "end_page": (c.get("extra") or {}).get("end_page"), "score": 0.5} for c in self.chunks[:k]]


def _run_with(chunks, script):
    from backend.react_agent import run_react_agent
    from backend.tool_chat import TurnResult
    from backend.tools import ToolContext, default_tools

    class Chat:
        model = "m"

        def __init__(self):
            self.turn = 0

        def send(self, message):
            item = script[self.turn]
            self.turn += 1
            return item if isinstance(item, TurnResult) else TurnResult(text=item)

    ctx = ToolContext(engine=_Store(chunks))
    events = list(run_react_agent(Chat(), default_tools(), ctx, "What is a binary heap?"))
    return {e["event"]: e["data"] for e in events}, ctx


def test_read_page_keeps_the_end_page_so_a_spanning_citation_verifies():
    from backend.tool_chat import ToolCall, TurnResult

    chunks = [{"doc": "Dsa.pdf", "page": 118, "text": "A binary heap is a complete tree.", "extra": {"end_page": 119}}]
    out, ctx = _run_with(chunks, [TurnResult(calls=[ToolCall("read_page", {"document": "Dsa.pdf", "page": 119})]), "A heap is complete [Dsa.pdf (page 119)]."])
    assert ctx.passages[0]["end_page"] == 119
    assert out["done"]["unverified_citations"] == 0 and out["done"]["citations"][0]["status"] == "ok"


def test_a_citation_beyond_the_first_twelve_passages_keeps_its_evidence():
    from backend.tool_chat import ToolCall, TurnResult

    chunks = [{"doc": "big.pdf", "page": n, "text": f"passage number {n} about heaps"} for n in range(1, 16)]
    calls = [TurnResult(calls=[ToolCall("read_page", {"document": "big.pdf", "page": n}) for n in range(a, a + 4)]) for a in (1, 5, 9, 13)]
    out, _ctx = _run_with(chunks, [*calls, "See [big.pdf (page 15)]."])
    assert out["done"]["unverified_citations"] == 0
    assert any(c["page"] == 15 for c in out["meta"]["chunks"]) and len(out["meta"]["chunks"]) == 12


def test_a_search_only_counts_passages_the_model_actually_received():
    from backend.tools import RESULT_CHARS, ToolContext, run_tool, default_tools

    chunks = [{"doc": "big.pdf", "page": n, "text": "x" * 900} for n in range(1, 9)]
    ctx = ToolContext(engine=_Store(chunks))
    res = run_tool(default_tools(), ctx, "search_documents", {"query": "heap", "k": 8})
    assert "truncated" not in res and len(str(res)) <= RESULT_CHARS + 200
    assert [p["page"] for p in res["passages"]] == [p["page"] for p in ctx.passages] and res["count"] < 8


def test_passages_survive_a_failover_between_turns():
    """The chat may move to another model mid-run; the record of what was retrieved lives outside it."""
    from backend.react_agent import run_react_agent
    from backend.tool_chat import ToolCall, TurnResult
    from backend.tools import ToolContext, default_tools

    class Chat:
        model = "gemini-3.6-flash"
        turn = 0

        def send(self, message):
            self.turn += 1
            if self.turn == 1:
                return TurnResult(calls=[ToolCall("search_documents", {"query": "heap"})])
            self.model = "gemini-3.1-flash-lite"
            return TurnResult(text="A heap [Dsa.pdf page 118] is a tree [Dsa.pdf (page 118)].")

    ctx = ToolContext(engine=_Store([{"doc": "Dsa.pdf", "page": 118, "text": "A binary heap."}]))
    done = [e for e in run_react_agent(Chat(), default_tools(), ctx, "q") if e["event"] == "done"][0]["data"]
    assert done["models"][-1] == "gemini-3.1-flash-lite" and len(done["citations"]) == 2 and done["unverified_citations"] == 0
