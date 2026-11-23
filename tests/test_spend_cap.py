import io
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

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
        return {"Body": io.BytesIO(self.objects[Key]), "ETag": '"e"'}

    def put_object(self, Bucket, Key, Body, **condition):
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


def test_provider_quota_errors_become_a_short_429():
    from backend.api.deps import QUOTA_MESSAGE, raise_if_failed
    from backend.api.errors import ApiError

    raw = "429 RESOURCE_EXHAUSTED. {'error': {'message': 'You exceeded your current quota ... limit: 20'}}"
    with pytest.raises(ApiError) as e:
        raise_if_failed({"ok": False, "error": raw})
    assert e.value.status_code == 429 and e.value.code == "quota_exhausted" and e.value.detail == QUOTA_MESSAGE


# ---------------------------------------------------------------- atomicity and per-attempt counting
class Conflict(Exception):
    response = {"Error": {"Code": "PreconditionFailed"}}


class CasBucket:
    """S3 with conditional writes, slowed so that concurrent read-then-write calls really overlap."""

    def __init__(self):
        self.lock = threading.Lock()
        self.objects = {}
        self.version = 0
        self.conflicts = 0

    def get_object(self, Bucket, Key):
        with self.lock:
            if Key not in self.objects:
                raise NoSuchKey()
            body, etag = self.objects[Key]
        time.sleep(0.001)
        return {"Body": io.BytesIO(body), "ETag": etag}

    def put_object(self, Bucket, Key, Body, IfMatch=None, IfNoneMatch=None):
        time.sleep(0.001)
        with self.lock:
            current = self.objects.get(Key)
            if (IfNoneMatch == "*" and current) or (IfMatch and (not current or current[1] != IfMatch)):
                self.conflicts += 1
                raise Conflict()
            self.version += 1
            self.objects[Key] = (Body, f'"{self.version}"')


def _hammer(caps, calls):
    results = []

    def one(cap):
        try:
            results.append(cap.reserve())
        except DailyLimitReached as e:
            results.append(str(e))

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(one, [caps[i % len(caps)] for i in range(calls)]))
    return results


def test_concurrent_instances_never_lose_a_count_or_pass_the_limit(monkeypatch):
    monkeypatch.setattr(sc, "CAS_ATTEMPTS", 200)
    bucket = CasBucket()
    caps = [DailyCap(20, bucket, "b") for _ in range(8)]  # eight Lambda instances, each with its own lock
    results = _hammer(caps, 48)
    granted = sorted(r for r in results if isinstance(r, int))
    assert granted == list(range(1, 21))  # each count handed out exactly once
    assert all("Daily limit" in r for r in results if isinstance(r, str))
    (body, _etag), = bucket.objects.values()
    assert json.loads(body) == {"calls": 20} and bucket.conflicts > 0  # the race really happened


def test_threads_of_one_instance_share_the_count_exactly():
    cap = DailyCap(10)
    assert sorted(r for r in _hammer([cap], 40) if isinstance(r, int)) == list(range(1, 11))


def test_writes_are_conditional():
    seen = []

    class Spy(CasBucket):
        def put_object(self, **kw):
            seen.append({k: v for k, v in kw.items() if k.startswith("If")})
            super().put_object(**kw)

    cap = DailyCap(5, Spy(), "b")
    cap.reserve()
    cap.reserve()
    assert seen == [{"IfNoneMatch": "*"}, {"IfMatch": '"1"'}]


def test_losing_every_race_refuses_the_call(monkeypatch):
    class AlwaysLoses(CasBucket):
        def put_object(self, **kw):
            raise Conflict()

    monkeypatch.setattr(sc.time, "sleep", lambda s: None)
    with pytest.raises(DailyLimitReached, match="paused"):
        DailyCap(5, AlwaysLoses(), "b").reserve()


class ApiErr(Exception):
    def __init__(self, code, text):
        super().__init__(f"{code} {text}")
        self.code = code


class Models:
    def __init__(self, script):
        self.script, self.calls = list(script), []

    def list(self):
        return []

    def generate_content(self, model, contents, config):
        self.calls.append(model)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return type("R", (), {"text": item})()


def _capped(script, limit, model=None):
    from backend.llm_config import GeminiClient

    sdk = type("SDK", (), {})()
    sdk.models = Models(script)
    cap = DailyCap(limit)
    return CappedLLM(GeminiClient(model=model, client=sdk), cap), cap, sdk.models


def test_a_billable_failover_attempt_counts(monkeypatch):
    llm, cap, models = _capped([ApiErr(503, "UNAVAILABLE"), "ok"], 5)
    assert llm.generate("q")["ok"] and len(models.calls) == 2
    assert cap._memory[cap._today()] == 2


def test_a_rejected_attempt_does_not_use_up_allowance():
    llm, cap, models = _capped([ApiErr(429, "RESOURCE_EXHAUSTED quota"), "ok"], 5)
    assert llm.generate("q")["ok"] and len(models.calls) == 2
    assert cap._memory[cap._today()] == 1  # nothing was generated by the refused request


def test_failover_stops_at_the_cap():
    llm, cap, models = _capped([ApiErr(503, "UNAVAILABLE"), "never"], 1)
    res = llm.generate("q")
    assert res["ok"] is False and "Daily limit" in res["error"] and len(models.calls) == 1
