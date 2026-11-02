"""The agentic workflow (LangGraph): rewrite, retrieve, grade, answer, verify, with a scripted model."""

from __future__ import annotations

import json

import pytest

from backend.rag_engine import RAGEngine

from .test_api_features import parse_sse

URL = "/api/v1/ask/agent/stream"
GOOD = "A binary heap is a complete binary tree. [heaps.pdf (page 1)]"
INVENTED = "A binary heap is a tree. [Invented Notes.pdf (page 9)]"


def script(rewrite=None, grade=None, answer=GOOD, regenerate=None):
    """A model that answers the workflow's three kinds of prompt. Each argument is a reply (str), a callable, or None for the default."""

    def handler(prompt: str, json_mode: bool) -> str:
        def pick(spec, default):
            return spec(prompt) if callable(spec) else (default if spec is None else spec)

        if "TASK: REWRITE_QUERY" in prompt:
            return pick(rewrite, json.dumps({"query": "binary heap priority queue"}))
        if "TASK: GRADE_PASSAGES" in prompt:
            return pick(grade, json.dumps({"sufficient": True, "reason": "ok", "better_query": ""}))
        if "previous answer cited sources" in prompt:
            return pick(regenerate, GOOD)
        return pick(answer, GOOD)

    return handler


def run(client, question="what is a binary heap", **extra):
    r = client.post(URL, json={"question": question, **extra})
    assert r.status_code == 200, r.text
    return parse_sse(r.text)


def names(events):
    return [n for n, _ in events]


@pytest.fixture
def searches(monkeypatch):
    """Record every query the engine is asked to retrieve for."""
    seen: list[str] = []
    original = RAGEngine.retrieve_context

    def spy(self, query, k=3):
        seen.append(query)
        return original(self, query, k=k)

    monkeypatch.setattr(RAGEngine, "retrieve_context", spy)
    return seen


def test_happy_path_streams_steps_then_answer_then_done(indexed, fake_gemini):
    fake_gemini.handler = script()
    events = run(indexed)
    kinds = names(events)
    assert [d["name"] for n, d in events if n == "step"] == ["rewrite", "retrieve", "grade", "answer", "verify"]
    assert kinds.index("meta") < kinds.index("token") and kinds[-1] == "done"
    assert events[kinds.index("meta")][1]["chunks"][0]["doc"] == "heaps.pdf"
    done = events[-1][1]
    assert "".join(d["text"] for n, d in events if n == "token") == GOOD
    assert done["llm_calls"] == 3 and done["regenerated"] is False and done["unverified_citations"] == 0
    assert done["citations"][0]["status"] == "ok" and done["model"] == "fake-model"
    assert "_answer" not in done and "_prompt" not in done  # internals never leak into the stream


def test_retrieval_uses_the_question_and_the_rewrite(indexed, fake_gemini, searches):
    fake_gemini.handler = script(rewrite=json.dumps({"query": "heap ordered complete tree"}))
    run(indexed, "explain heaps")
    assert searches == ["explain heaps", "heap ordered complete tree"]  # the original is always searched too


def test_a_rewrite_that_is_unusable_keeps_the_original_wording(indexed, fake_gemini, searches):
    fake_gemini.handler = script(rewrite="not json at all")
    events = run(indexed, "explain heaps")
    assert searches == ["explain heaps"]
    assert next(d for n, d in events if n == "step")["detail"] == "Kept your wording"
    assert events[-1][0] == "done"


def test_weak_passages_trigger_one_more_search_with_the_suggested_query(indexed, fake_gemini, searches):
    verdicts = iter([{"sufficient": False, "reason": "off topic", "better_query": "binary heap definition"}, {"sufficient": True, "better_query": ""}])
    fake_gemini.handler = script(grade=lambda prompt: json.dumps(next(verdicts)))
    events = run(indexed)
    assert searches[-1] == "binary heap definition" and len(searches) == 4  # question + rewrite, then the retry's question + suggestion
    assert [d["name"] for n, d in events if n == "step"].count("retrieve") == 2
    assert any("Searched again" in d["detail"] for n, d in events if n == "step")
    assert events[-1][1]["llm_calls"] == 4  # rewrite, grade, grade, answer


def test_searching_again_happens_at_most_once(indexed, fake_gemini):
    fake_gemini.handler = script(grade=json.dumps({"sufficient": False, "reason": "weak", "better_query": "something else"}))
    events = run(indexed)
    assert [d["name"] for n, d in events if n == "step"].count("retrieve") == 2
    assert events[-1][0] == "done"  # it still answers, from the best passages it has


def test_an_answer_with_invented_citations_is_replaced_once(indexed, fake_gemini):
    fake_gemini.handler = script(answer=INVENTED, regenerate=GOOD)
    events = run(indexed)
    kinds = names(events)
    assert kinds.count("replace") == 1 and kinds.index("replace") > kinds.index("token")
    first, second = "".join(d["text"] for n, d in events[: kinds.index("replace")] if n == "token"), "".join(d["text"] for n, d in events[kinds.index("replace") :] if n == "token")
    assert first == INVENTED and second == GOOD
    done = events[-1][1]
    assert done["regenerated"] is True and done["unverified_citations"] == 0 and done["llm_calls"] == 4
    assert "heaps.pdf" in fake_gemini.calls[-1]  # the retry prompt listed the valid sources


def test_the_answer_is_rewritten_only_once_even_if_it_keeps_inventing(indexed, fake_gemini):
    fake_gemini.handler = script(answer=INVENTED, regenerate=INVENTED)
    events = run(indexed)
    assert names(events).count("replace") == 1
    done = events[-1][1]
    assert done["unverified_citations"] == 1 and done["regenerated"] is True  # honest: the flag stays


def test_a_model_call_budget_is_never_exceeded(indexed, fake_gemini):
    fake_gemini.handler = script(answer=INVENTED, regenerate=INVENTED, grade=json.dumps({"sufficient": False, "better_query": "x"}))
    done = run(indexed)[-1][1]
    assert done["llm_calls"] <= 6


def test_planning_failures_fall_back_to_the_plain_behaviour(indexed, fake_gemini):
    def handler(prompt, json_mode):
        if json_mode:
            raise ValueError("planning model hiccup")
        return GOOD

    fake_gemini.handler = handler
    events = run(indexed)
    assert events[-1][0] == "done" and "".join(d["text"] for n, d in events if n == "token") == GOOD


def test_running_out_of_quota_stops_instead_of_pretending(indexed, fake_gemini):
    def handler(prompt, json_mode):
        raise RuntimeError("429 RESOURCE_EXHAUSTED: you exceeded your current quota")

    fake_gemini.handler = handler
    events = run(indexed)
    assert names(events)[-1] == "error" and "token" not in names(events)
    assert events[-1][1]["code"] == "quota_exhausted"


def test_missing_model_key_is_reported_before_anything_else(indexed, fake_gemini):
    fake_gemini.fail_with = RuntimeError("GEMINI_API_KEY is not set")
    events = run(indexed)
    assert names(events) == ["error"] and events[0][1]["code"] == "llm_unavailable"


def test_an_error_while_writing_the_answer_is_an_error_event(indexed, fake_gemini):
    def handler(prompt, json_mode):
        if json_mode:
            return json.dumps({"query": "heap", "sufficient": True})
        raise ValueError("boom")

    fake_gemini.handler = handler
    events = run(indexed)
    assert events[-1][0] == "error" and events[-1][1]["code"] == "llm_error"


def test_runs_are_recorded_in_analytics_but_never_cached(indexed, fake_gemini):
    fake_gemini.handler = script()
    run(indexed)
    run(indexed)
    assert indexed.get("/api/v1/analytics").json()["queries"] == 2
    assert all(d["cached"] is False for n, d in run(indexed) if n == "done")


def test_validation(indexed):
    assert indexed.post(URL, json={"question": ""}).status_code == 422
    assert indexed.post(URL, json={"question": "what is a heap", "k": 11}).status_code == 422


def test_the_endpoint_is_in_the_published_schema(indexed):
    spec = indexed.get("/openapi.json").json()
    assert URL in spec["paths"] and {"SseStep", "SseReplace", "SseAgentDone"} <= set(spec["components"]["schemas"])


def test_without_langgraph_installed_the_endpoint_says_so_and_the_rest_still_works(indexed, fake_gemini, monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "backend.agent", None)  # makes `from ...agent import run_agent` raise ImportError
    r = indexed.post(URL, json={"question": "what is a binary heap"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "agent_unavailable"
    assert indexed.post("/api/v1/ask", json={"question": "what is a binary heap"}).status_code == 200
