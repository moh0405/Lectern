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


DEFAULT = llm_config.DEFAULT_MODEL
LITE, SECOND, THIRD = llm_config.DEFAULT_FALLBACKS  # the chain after the default model


def make(models=(DEFAULT,), model=None, **kw):
    return GeminiClient(model=model, client=FakeClient(models=[FakeModel(m) for m in models], **kw))


def test_requires_api_key(monkeypatch):
    pytest.importorskip("google.genai")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        GeminiClient()


def test_default_model_is_used_when_available():
    assert make().model == DEFAULT


def test_unavailable_model_falls_back_to_best_candidate(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-9-ultra")
    assert make(models=("gemini-3.6-flash", "other")).model == "gemini-3.6-flash"


def test_non_text_models_are_not_selected():
    client = GeminiClient(client=FakeClient(models=[FakeModel("gemini-3.8-flash", actions=("embedContent",)), FakeModel("x")]))
    assert client.model == "x"


def test_model_resolution_is_cached_per_key_and_request():
    fake = FakeClient(models=[FakeModel(DEFAULT)])
    GeminiClient(client=fake)
    fake.models._models = []  # a second listing would now find nothing
    assert GeminiClient(client=fake).model == DEFAULT


def test_listing_failure_uses_requested_model_without_caching():
    class Boom(FakeModels):
        def list(self):
            raise RuntimeError("network down")

    fake = FakeClient(models=[])
    fake.models.__class__ = Boom
    assert GeminiClient(client=fake).model == DEFAULT
    assert not llm_config._resolved_models


def test_generate_success():
    c = make(script=["hello"])
    assert c.generate("hi") == {"ok": True, "model": DEFAULT, "answer": "hello"}


def test_generate_retries_transient_errors_then_succeeds():
    c = make(script=[FakeAPIError(503, "Service Unavailable"), FakeAPIError(429, "rate limit"), "ok"])
    assert c.generate("hi")["answer"] == "ok"
    assert len(c._client.models.calls) == 3


def test_generate_gives_up_after_retries():
    # A model named by the caller is never swapped, so an overloaded one is retried and then reported.
    c = make(model=DEFAULT, script=[FakeAPIError(503, "unavailable")] * 3)
    res = c.generate("hi")
    assert res["ok"] is False and "unavailable" in res["error"]
    assert c._client.models.calls == [DEFAULT] * 3


def test_generate_does_not_retry_auth_errors():
    c = make(script=[FakeAPIError(401, "API key not valid")])
    res = c.generate("hi")
    assert res["ok"] is False and len(c._client.models.calls) == 1


def test_generate_tries_default_model_when_requested_one_is_missing(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "custom-model")
    c = make(models=("custom-model", DEFAULT), script=[FakeAPIError(404, "model not found"), "recovered"])
    res = c.generate("hi")
    assert res["ok"] and res["model"] == DEFAULT


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


# ----------------------------------------------------------------- rate limits: honour the provider's retry hint
PER_MINUTE = (
    "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota. * Quota exceeded for metric: "
    "generate_content_free_tier_requests, limit: 5, model: gemini-3.6-flash, description: Generate content requests per minute "
    "limit exceeded on Free Tier.\\nPlease retry in 14.650727173s.', 'details': [{'retryDelay': '14s'}]}}"
)
PER_DAY = "429 RESOURCE_EXHAUSTED. You exceeded your current quota. Please retry in 20h3m1.5s. retryDelay': '72000s'"


def test_the_retry_hint_is_parsed_from_either_form():
    assert llm_config.retry_delay_seconds(PER_MINUTE) == pytest.approx(14.65, abs=0.01)
    assert llm_config.retry_delay_seconds("... 'retryDelay': '14s' ...") == 14.0
    assert llm_config.retry_delay_seconds("503 UNAVAILABLE high demand") is None


def test_a_short_rate_limit_is_retried_after_the_providers_own_delay(monkeypatch):
    sleeps = []
    monkeypatch.setattr(llm_config.time, "sleep", sleeps.append)
    client = GeminiClient(model="gemini-3.8-flash", client=FakeClient(models=[FakeModel("gemini-3.8-flash")], script=[FakeAPIError(429, PER_MINUTE), "pong"]))
    assert client.generate("hi") == {"ok": True, "model": "gemini-3.8-flash", "answer": "pong"}
    assert sleeps == [pytest.approx(15.15, abs=0.05)]  # waited what Gemini asked (plus half a second), not under a second


def test_the_wait_is_capped(monkeypatch):
    sleeps = []
    monkeypatch.setattr(llm_config.time, "sleep", sleeps.append)
    hint = "429 RESOURCE_EXHAUSTED. Please retry in 29.9s."
    client = GeminiClient(model="gemini-3.8-flash", client=FakeClient(models=[FakeModel("gemini-3.8-flash")], script=[FakeAPIError(429, hint), "ok"]))
    client.generate("hi")
    assert sleeps and sleeps[0] <= llm_config.MAX_RETRY_WAIT_S


def test_a_long_wait_such_as_a_daily_quota_is_not_retried(monkeypatch):
    sleeps = []
    monkeypatch.setattr(llm_config.time, "sleep", sleeps.append)
    fake = FakeClient(models=[FakeModel("gemini-3.8-flash")], script=[FakeAPIError(429, PER_DAY)])
    result = GeminiClient(model="gemini-3.8-flash", client=fake).generate("hi")
    assert result["ok"] is False and "quota" in result["error"].lower()
    assert sleeps == [] and fake.models.calls == ["gemini-3.8-flash"]  # failed fast: one call, no waiting


def test_other_transient_errors_still_use_the_short_backoff(monkeypatch):
    sleeps = []
    monkeypatch.setattr(llm_config.time, "sleep", sleeps.append)
    client = GeminiClient(model="gemini-3.8-flash", client=FakeClient(models=[FakeModel("gemini-3.8-flash")], script=[FakeAPIError(503, "503 UNAVAILABLE"), "ok"]))
    client.generate("hi")
    assert sleeps == [0.8]


def test_the_user_message_says_which_kind_of_limit_was_hit():
    from backend.api.deps import QUOTA_MESSAGE, quota_message

    minute = quota_message(PER_MINUTE)
    assert "per minute" in minute and "15 seconds" in minute and "per day" not in minute
    assert quota_message(PER_DAY) == QUOTA_MESSAGE


# ----------------------------------------------------------------- fail-over between models
ALL = (DEFAULT, LITE, SECOND, THIRD)
OVERLOADED = "503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand.'}}"


@pytest.fixture
def sleeps(monkeypatch):
    waited = []
    monkeypatch.setattr(llm_config.time, "sleep", waited.append)
    monkeypatch.delenv("GEMINI_FALLBACK_MODELS", raising=False)
    return waited


def test_the_default_model_is_one_that_answers():
    assert DEFAULT == "gemini-3.6-flash" and LITE == "gemini-3.1-flash-lite"
    assert "gemini-3.8-flash" not in llm_config.DEFAULT_FALLBACKS  # it times out (~87 s), which would outlast the Lambda
    assert "gemini-2.5-flash" not in llm_config.DEFAULT_FALLBACKS  # retired for new keys (404)


def test_an_overloaded_model_hands_over_to_the_next_immediately(sleeps):
    c = make(models=ALL, script=[FakeAPIError(503, OVERLOADED), "pong"])
    res = c.generate("hi")
    assert res == {"ok": True, "model": LITE, "answer": "pong"}
    assert c._client.models.calls == [DEFAULT, LITE]  # one try on the overloaded model, not three
    assert sleeps == []  # and no waiting on it
    assert c.model == LITE  # the client reports the model that really answered


def test_a_timeout_also_hands_over(sleeps):
    c = make(models=ALL, script=[FakeAPIError(504, "504 DEADLINE_EXCEEDED"), "pong"])
    assert c.generate("hi")["model"] == LITE and sleeps == []


def test_a_model_that_is_out_of_quota_hands_over_whether_the_limit_is_per_minute_or_per_day(sleeps):
    for quota in (PER_MINUTE, PER_DAY):
        c = make(models=ALL, script=[FakeAPIError(429, quota), "pong"])
        assert c.generate("hi")["model"] == LITE, quota[:40]
    assert sleeps == []  # a daily limit is not waited out, and a per-minute one is not waited out when another model can answer


def test_it_moves_down_the_whole_chain(sleeps):
    c = make(models=ALL, script=[FakeAPIError(503, OVERLOADED), FakeAPIError(429, PER_DAY), FakeAPIError(503, OVERLOADED), "last resort"])
    res = c.generate("hi")
    assert res["model"] == THIRD and c._client.models.calls == [DEFAULT, LITE, SECOND, THIRD]


def test_a_model_the_key_cannot_use_is_skipped(sleeps):
    c = make(models=ALL, script=[FakeAPIError(503, OVERLOADED), FakeAPIError(404, "model not found"), "ok"])
    assert c.generate("hi")["model"] == SECOND


def test_when_every_model_fails_the_error_is_reported(sleeps):
    c = make(models=ALL, script=[FakeAPIError(503, OVERLOADED)] * 6)
    res = c.generate("hi")
    assert res["ok"] is False and "UNAVAILABLE" in res["error"]
    assert c._client.models.calls[:4] == [DEFAULT, LITE, SECOND, THIRD]  # each model was tried


def test_a_bad_key_or_bad_request_is_not_passed_around(sleeps):
    for code, text in ((401, "API key not valid"), (403, "permission denied"), (400, "invalid argument")):
        c = make(models=ALL, script=[FakeAPIError(code, text), "never reached"])
        assert c.generate("hi")["ok"] is False and c._client.models.calls == [DEFAULT], code


def test_a_model_named_by_the_caller_is_never_swapped(sleeps):
    c = make(models=ALL, model=LITE, script=[FakeAPIError(503, OVERLOADED)] * 3)
    assert c.generate("hi")["ok"] is False
    assert set(c._client.models.calls) == {LITE}  # retried on the same model, never moved to another


def test_fail_over_can_be_turned_off(sleeps, monkeypatch):
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "none")
    c = make(models=ALL, script=[FakeAPIError(503, OVERLOADED), FakeAPIError(503, OVERLOADED), "ok"])
    assert c.generate("hi")["model"] == DEFAULT and c._client.models.calls == [DEFAULT] * 3


def test_the_fallback_list_can_be_chosen(sleeps, monkeypatch):
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", f"{SECOND}, custom-model")
    assert llm_config.fallback_models() == [SECOND, "custom-model"]
    c = make(models=ALL + ("custom-model",), script=[FakeAPIError(503, OVERLOADED), "ok"])
    assert c.generate("hi")["model"] == SECOND


def test_streaming_hands_over_before_the_first_token(sleeps):
    c = make(models=ALL, stream_script=[FakeAPIError(503, OVERLOADED), [FakeResp("Hel"), FakeResp("lo")]])
    assert "".join(c.stream("hi")) == "Hello"
    assert c._client.models.calls == [DEFAULT, LITE] and c.model == LITE


def test_streaming_never_switches_models_in_the_middle_of_an_answer(sleeps):
    def torn():
        yield FakeResp("Hel")
        raise FakeAPIError(503, OVERLOADED)

    c = make(models=ALL, stream_script=[torn(), [FakeResp("other model")]])
    got = []
    with pytest.raises(FakeAPIError):
        for piece in c.stream("hi"):
            got.append(piece)
    assert got == ["Hel"] and c._client.models.calls == [DEFAULT]


def test_a_streaming_client_reports_the_model_that_answered(sleeps):
    c = make(models=ALL, stream_script=[[FakeResp("hi")]])
    list(c.stream("hi"))
    assert c.model == DEFAULT


# ----------------------------------------------------------------- the time budget, and honest errors
def test_a_chain_never_outlasts_the_time_budget(sleeps, monkeypatch):
    now = [1000.0]

    def fake_monotonic():
        now[0] += 50  # every call to the clock is "50 s later": the first failure already uses up most of the budget
        return now[0]

    monkeypatch.setattr(llm_config.time, "monotonic", fake_monotonic)
    monkeypatch.setenv("GEMINI_TOTAL_BUDGET_S", "60")
    c = make(models=ALL, script=[FakeAPIError(503, OVERLOADED)] * 10)
    res = c.generate("hi")
    assert res["ok"] is False and "UNAVAILABLE" in res["error"]
    assert len(c._client.models.calls) <= 2  # it stopped starting new calls once out of time


def test_the_budget_can_be_set_and_has_a_sane_default(monkeypatch):
    monkeypatch.delenv("GEMINI_TOTAL_BUDGET_S", raising=False)
    assert llm_config._total_budget_s() == 90.0
    monkeypatch.setenv("GEMINI_TOTAL_BUDGET_S", "30")
    assert llm_config._total_budget_s() == 30.0
    monkeypatch.setenv("GEMINI_TOTAL_BUDGET_S", "junk")
    assert llm_config._total_budget_s() == 90.0


def test_a_retired_models_404_does_not_hide_the_real_reason(sleeps):
    quota = "429 RESOURCE_EXHAUSTED. You exceeded your current quota. retryDelay': '40s'"
    c = make(models=ALL, script=[FakeAPIError(429, quota), FakeAPIError(404, "model is no longer available to new users"), FakeAPIError(404, "not found"), FakeAPIError(404, "not found")])
    res = c.generate("hi")
    assert res["ok"] is False and "quota" in res["error"].lower() and "no longer available" not in res["error"]


def test_the_stream_also_keeps_the_real_reason(sleeps):
    c = make(models=ALL, stream_script=[FakeAPIError(503, OVERLOADED), FakeAPIError(404, "gone"), FakeAPIError(404, "gone"), FakeAPIError(404, "gone")])
    with pytest.raises(FakeAPIError) as caught:
        list(c.stream("hi"))
    assert "UNAVAILABLE" in str(caught.value)
