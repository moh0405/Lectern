import pytest

from backend import llm_config
from backend.llm_config import GeminiClient


class FakeModel:
    def __init__(self, name, actions=("generateContent",)):
        self.name = f"models/{name}"
        self.supported_actions = list(actions)


class FakeResp:
    def __init__(self, text):
        self.text = text


class FakeAPIError(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


class FakeModels:
    def __init__(self, models, script=None, stream_script=None):
        self._models = models
        self.script = list(script or [])
        self.stream_script = list(stream_script or [])
        self.calls = []

    def list(self):
        return iter(self._models)

    def generate_content(self, model, contents, config):
        self.calls.append(model)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeResp(item)

    def generate_content_stream(self, model, contents, config):
        self.calls.append(model)
        item = self.stream_script.pop(0)
        if isinstance(item, Exception):
            raise item
        return iter(item)


class FakeClient:
    def __init__(self, **kw):
        self.models = FakeModels(**kw)


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(llm_config.time, "sleep", lambda s: None)
    llm_config._resolved_models.clear()
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_TEMPERATURE", raising=False)


def make(models=("gemini-3.8-flash",), **kw):
    return GeminiClient(client=FakeClient(models=[FakeModel(m) for m in models], **kw))


def test_requires_api_key(monkeypatch):
    pytest.importorskip("google.genai")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        GeminiClient()


def test_default_model_is_used_when_available():
    assert make().model == "gemini-3.8-flash"


def test_unavailable_model_falls_back_to_best_candidate(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-9-ultra")
    assert make(models=("gemini-3.6-flash", "other")).model == "gemini-3.6-flash"


def test_non_text_models_are_not_selected():
    client = GeminiClient(client=FakeClient(models=[FakeModel("gemini-3.8-flash", actions=("embedContent",)), FakeModel("x")]))
    assert client.model == "x"


def test_model_resolution_is_cached_per_key_and_request():
    fake = FakeClient(models=[FakeModel("gemini-3.8-flash")])
    GeminiClient(client=fake)
    fake.models._models = []  # a second listing would now find nothing
    assert GeminiClient(client=fake).model == "gemini-3.8-flash"


def test_listing_failure_uses_requested_model_without_caching():
    class Boom(FakeModels):
        def list(self):
            raise RuntimeError("network down")

    fake = FakeClient(models=[])
    fake.models.__class__ = Boom
    assert GeminiClient(client=fake).model == "gemini-3.8-flash"
    assert not llm_config._resolved_models


def test_generate_success():
    c = make(script=["hello"])
    assert c.generate("hi") == {"ok": True, "model": "gemini-3.8-flash", "answer": "hello"}


def test_generate_retries_transient_errors_then_succeeds():
    c = make(script=[FakeAPIError(503, "Service Unavailable"), FakeAPIError(429, "rate limit"), "ok"])
    assert c.generate("hi")["answer"] == "ok"
    assert len(c._client.models.calls) == 3


def test_generate_gives_up_after_retries():
    c = make(script=[FakeAPIError(503, "unavailable")] * 3)
    res = c.generate("hi")
    assert res["ok"] is False and "unavailable" in res["error"]


def test_generate_does_not_retry_auth_errors():
    c = make(script=[FakeAPIError(401, "API key not valid")])
    res = c.generate("hi")
    assert res["ok"] is False and len(c._client.models.calls) == 1


def test_generate_tries_default_model_when_requested_one_is_missing(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "custom-model")
    c = make(models=("custom-model", "gemini-3.8-flash"), script=[FakeAPIError(404, "model not found"), "recovered"])
    res = c.generate("hi")
    assert res["ok"] and res["model"] == "gemini-3.8-flash"


def test_generate_reports_empty_response():
    res = make(script=[""]).generate("hi")
    assert res["ok"] is False and "empty" in res["error"].lower()


def test_stream_yields_deltas():
    c = make(stream_script=[[FakeResp("Hel"), FakeResp(""), FakeResp("lo")]])
    assert list(c.stream("hi")) == ["Hel", "lo"]


def test_stream_retries_before_first_delta_only():
    c = make(stream_script=[FakeAPIError(503, "unavailable"), [FakeResp("ok")]])
    assert list(c.stream("hi")) == ["ok"]

    def broken():
        yield FakeResp("partial")
        raise FakeAPIError(503, "unavailable")

    c2 = make(stream_script=[broken()])
    c2._client.models.generate_content_stream = lambda **kw: broken()
    got = []
    with pytest.raises(FakeAPIError):
        for piece in c2.stream("hi"):
            got.append(piece)
    assert got == ["partial"]


def test_list_supported_models_sorts_flash_latest_first():
    c = make(models=("gemini-pro-x", "gemini-3.8-flash", "gemini-flash-latest"))
    assert c.list_supported_models()[0] == "gemini-flash-latest"


def test_timeout_comes_from_env_and_is_never_unbounded(monkeypatch):
    from backend import llm_config

    monkeypatch.delenv("GEMINI_TIMEOUT_S", raising=False)
    assert llm_config._timeout_s() == llm_config.DEFAULT_TIMEOUT_S
    monkeypatch.setenv("GEMINI_TIMEOUT_S", "12")
    assert llm_config._timeout_s() == 12.0
    monkeypatch.setenv("GEMINI_TIMEOUT_S", "nonsense")
    assert llm_config._timeout_s() == llm_config.DEFAULT_TIMEOUT_S
    monkeypatch.setenv("GEMINI_TIMEOUT_S", "0")
    assert llm_config._timeout_s() == 1.0
