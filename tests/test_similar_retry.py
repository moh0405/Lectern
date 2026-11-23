"""Similar example: a draft rejected by a guard gets exactly one more model call, told only the guard's reason."""

import json
import logging

import pytest

import backend.similar_practice as sp
from backend.spend_cap import CappedLLM, DailyCap
from tests.fake_gemini import FakeGemini
from tests.test_understanding import GOOD, HEAP, KEY, Q, QUEUE

LEAK = "The answer is SECRET-DRAFT-WORDS, so how many swaps happen?"
BAD = {
    "malformed": "not json SECRET-DRAFT-WORDS",
    "leaks_answer": json.dumps({"question": LEAK, "answer_key": KEY, "citations": ["heaps.pdf (page 2)"]}),
    "rewording": json.dumps({"question": "Why is insert into a binary heap O(log n)?", "answer_key": KEY, "citations": ["heaps.pdf (page 2)"]}),
    "ungrounded": json.dumps({"question": GOOD, "answer_key": KEY, "citations": ["invented.pdf (page 9)"]}),
}
OK = json.dumps({"question": GOOD, "answer_key": KEY, "citations": ["heaps.pdf (page 2)"]})


def script(*replies):
    queue = list(replies)
    return lambda prompt, json_mode: queue.pop(0)


def post(api):
    return api.post("/api/v1/practice/similar", json={"question": Q, "context": [HEAP, QUEUE]})


@pytest.mark.parametrize("guard", sorted(BAD))
def test_one_retry_told_only_the_reason(api, fake_gemini, caplog, guard):
    fake_gemini.handler = script(BAD[guard], OK)
    with caplog.at_level(logging.DEBUG):
        r = post(api)
    assert r.status_code == 200 and r.json()["question"] == GOOD
    assert len(fake_gemini.calls) == 2
    assert "REJECTED" not in fake_gemini.calls[0]
    retry = fake_gemini.calls[1]
    assert sp.RETRY_REASON[guard] in retry
    assert "SECRET-DRAFT-WORDS" not in retry and KEY not in retry
    assert "SECRET-DRAFT-WORDS" not in caplog.text and KEY not in caplog.text and GOOD not in caplog.text
    assert KEY not in r.text


def test_two_rejections_stop_with_the_same_error(api, fake_gemini):
    fake_gemini.handler = script(BAD["leaks_answer"], BAD["leaks_answer"], OK)
    r = post(api)
    assert r.status_code == 502 and r.json()["error"]["message"] == sp.UNAVAILABLE
    assert len(fake_gemini.calls) == 2 and "SECRET-DRAFT-WORDS" not in r.text


def test_a_leaking_retry_is_still_refused(api, fake_gemini):
    fake_gemini.handler = script(BAD["ungrounded"], BAD["leaks_answer"])
    assert post(api).status_code == 502


@pytest.mark.parametrize("message, status", [
    ("Daily limit of 5 model calls reached. Try again after midnight UTC.", 429),
    ("429 RESOURCE_EXHAUSTED quota", 429),
    ("503 UNAVAILABLE", 502),
])
def test_provider_failures_are_not_retried(api, fake_gemini, monkeypatch, message, status):
    calls = []

    class Failing(FakeGemini):
        def generate(self, prompt, **kw):
            calls.append(prompt)
            return {"ok": False, "error": message}

    monkeypatch.setattr(sp, "create_llm", Failing)
    assert post(api).status_code == status
    assert len(calls) == 1


def test_a_raised_provider_error_is_not_retried(api, fake_gemini):
    fake_gemini.fail_with = ValueError("boom")
    assert post(api).status_code == 502
    assert len(fake_gemini.calls) == 1


def test_both_calls_count_against_the_daily_cap(api, fake_gemini, monkeypatch):
    cap = DailyCap(limit=5)
    monkeypatch.setattr(sp, "create_llm", lambda **kw: CappedLLM(FakeGemini(**kw), cap))
    fake_gemini.handler = script(BAD["leaks_answer"], OK)
    assert post(api).status_code == 200
    assert sum(cap._memory.values()) == 2


def test_the_cap_stops_the_retry(api, fake_gemini, monkeypatch):
    cap = DailyCap(limit=1)
    monkeypatch.setattr(sp, "create_llm", lambda **kw: CappedLLM(FakeGemini(**kw), cap))
    fake_gemini.handler = script(BAD["leaks_answer"], OK)
    r = post(api)
    assert r.status_code == 429 and r.json()["error"]["code"] == "daily_limit"
    assert len(fake_gemini.calls) == 1
