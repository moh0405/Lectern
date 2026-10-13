"""Provider interface: selection, and the OpenAI-compatible client against a fake SDK (no network)."""

from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

from backend import llm_providers as lp


class FakeCompletions:
    def __init__(self, replies=None, fail=None):
        self.replies, self.fail, self.calls = replies or ["Hello world"], fail, []

    def create(self, **kw):
        self.calls.append(kw)
        if self.fail:
            err, self.fail = self.fail, None
            raise err
        if kw.get("stream"):
            return iter([NS(choices=[NS(delta=NS(content=p))]) for p in self.replies] + [NS(choices=[NS(delta=NS(content=None))])])
        return NS(choices=[NS(message=NS(content="".join(self.replies)))])


def fake_sdk(**kw):
    comps = FakeCompletions(**kw)
    return NS(chat=NS(completions=comps), models=NS(list=lambda: [NS(id="b-model"), NS(id="a-model")])), comps


def test_generate_and_json_mode():
    sdk, comps = fake_sdk()
    c = lp.OpenAICompatClient(client=sdk, model="m1")
    assert c.generate("hi") == {"ok": True, "model": "m1", "answer": "Hello world"}
    c.generate("hi", json_mode=True, temperature=0.9)
    assert comps.calls[-1]["response_format"] == {"type": "json_object"} and comps.calls[-1]["temperature"] == 0.9
    assert comps.calls[0]["messages"] == [{"role": "user", "content": "hi"}]


def test_stream_yields_pieces_and_skips_empty():
    sdk, _ = fake_sdk(replies=["A", "B", "C"])
    assert list(lp.OpenAICompatClient(client=sdk).stream("x")) == ["A", "B", "C"]


def test_empty_and_error_responses_are_reported():
    sdk, _ = fake_sdk(replies=[""])
    assert lp.OpenAICompatClient(client=sdk).generate("x")["ok"] is False
    sdk, _ = fake_sdk(fail=RuntimeError("boom"))
    assert lp.OpenAICompatClient(client=sdk).generate("x") == {"ok": False, "error": "boom"}


def test_transient_error_is_retried(monkeypatch):
    monkeypatch.setattr(lp.time, "sleep", lambda s: None)
    sdk, comps = fake_sdk(fail=RuntimeError("503 service unavailable"))
    assert lp.OpenAICompatClient(client=sdk).generate("x")["ok"] is True
    assert len(comps.calls) == 2


def test_models_are_listed_sorted():
    sdk, _ = fake_sdk()
    assert lp.OpenAICompatClient(client=sdk).list_supported_models() == ["a-model", "b-model"]


def test_clients_satisfy_the_provider_protocol():
    sdk, _ = fake_sdk()
    assert isinstance(lp.OpenAICompatClient(client=sdk), lp.LLMProvider)


def test_create_llm_selects_by_env(monkeypatch):
    sdk, _ = fake_sdk()
    monkeypatch.setitem(lp.PROVIDERS, "openai", lambda **kw: lp.OpenAICompatClient(client=sdk, **kw))
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    assert isinstance(lp.create_llm(model="z"), lp.OpenAICompatClient)
    monkeypatch.setenv("LLM_PROVIDER", "nope")
    with pytest.raises(RuntimeError, match="Unknown LLM_PROVIDER"):
        lp.create_llm()


def test_openai_requires_a_key_unless_a_base_url_is_set(monkeypatch):
    pytest.importorskip("openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        lp.OpenAICompatClient()
    assert lp.OpenAICompatClient(base_url="http://localhost:11434/v1").model
