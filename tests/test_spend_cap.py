import io
import json

import pytest

import backend.spend_cap as sc
from backend.spend_cap import CappedLLM, DailyCap, DailyLimitReached


class NoSuchKey(Exception):
    response = {"Error": {"Code": "NoSuchKey"}}


class Bucket:
    """The two S3 calls the cap uses, kept in a dict."""

    def __init__(self):
        self.objects = {}

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise NoSuchKey()
        return {"Body": io.BytesIO(self.objects[Key])}

    def put_object(self, Bucket, Key, Body):
        self.objects[Key] = Body


class Model:
    model = "m"

    def __init__(self):
        self.calls = 0

    def generate(self, prompt, temperature=None, json_mode=False):
        self.calls += 1
        return {"ok": True, "answer": "hi", "model": "m"}

    def stream(self, prompt, temperature=None, json_mode=False):
        self.calls += 1
        return iter(["a", "b"])


def test_no_limit_means_no_counting():
    cap = DailyCap(0)
    assert [cap.reserve() for _ in range(5)] == [0] * 5


def test_calls_up_to_the_limit_pass_then_stop():
    cap = DailyCap(3)
    assert [cap.reserve() for _ in range(3)] == [1, 2, 3]
    with pytest.raises(DailyLimitReached, match="Daily limit of 3"):
        cap.reserve()


def test_a_new_day_starts_a_new_count(monkeypatch):
    cap = DailyCap(1)
    monkeypatch.setattr(DailyCap, "_today", staticmethod(lambda: "2026-01-01"))
    cap.reserve()
    with pytest.raises(DailyLimitReached):
        cap.reserve()
    monkeypatch.setattr(DailyCap, "_today", staticmethod(lambda: "2026-01-02"))
    assert cap.reserve() == 1


def test_the_count_is_shared_through_s3_between_copies():
    bucket = Bucket()
    a = DailyCap(2, bucket, "b", "pfx")
    b = DailyCap(2, bucket, "b", "pfx")  # another copy of the function
    a.reserve()
    b.reserve()
    with pytest.raises(DailyLimitReached):
        a.reserve()
    (key,) = bucket.objects
    assert key.startswith("pfx/usage/") and json.loads(bucket.objects[key]) == {"calls": 2}


def test_if_the_count_cannot_be_read_the_call_is_refused():
    class Broken(Bucket):
        def get_object(self, Bucket, Key):
            raise OSError("network down")

    with pytest.raises(DailyLimitReached, match="paused"):
        DailyCap(5, Broken(), "b").reserve()


def test_wrapped_model_counts_generate_and_stream_and_refuses_after_the_limit():
    inner = Model()
    llm = CappedLLM(inner, DailyCap(2))
    assert llm.model == "m"  # other attributes pass through
    assert llm.generate("q")["ok"]
    assert list(llm.stream("q")) == ["a", "b"]
    refused = llm.generate("q")
    assert refused["ok"] is False and "Daily limit" in refused["error"]
    with pytest.raises(DailyLimitReached):
        llm.stream("q")
    assert inner.calls == 2  # the model was never reached once the limit was hit


def test_create_llm_wraps_only_when_a_limit_is_set(monkeypatch):
    import backend.llm_providers as lp

    monkeypatch.setitem(lp.PROVIDERS, "gemini", lambda **kw: Model())
    monkeypatch.setattr(lp, "provider_name", lambda: "gemini")
    sc.reset_cap()
    monkeypatch.delenv("DAILY_LLM_LIMIT", raising=False)
    assert isinstance(lp.create_llm(), Model)
    sc.reset_cap()
    monkeypatch.setenv("DAILY_LLM_LIMIT", "5")
    monkeypatch.delenv("S3_BUCKET", raising=False)
    assert isinstance(lp.create_llm(), CappedLLM)
    sc.reset_cap()


def test_a_refused_call_becomes_a_429_with_its_own_code():
    from backend.api.deps import raise_if_failed
    from backend.api.errors import ApiError

    for msg in ("Daily limit of 5 model calls reached. Try again after midnight UTC.", "Model calls are paused because the daily count could not be checked (x)."):
        with pytest.raises(ApiError) as e:
            raise_if_failed({"ok": False, "error": msg})
        assert e.value.status_code == 429 and e.value.code == "daily_limit"
    with pytest.raises(ApiError) as e:
        raise_if_failed({"ok": False, "error": "503 UNAVAILABLE"})
    assert e.value.status_code == 502  # other failures are unchanged
