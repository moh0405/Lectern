"""Cold start on Lambda: cheap import, one load however many requests arrive, and nothing served before it is safe."""

import importlib
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from backend.api.startup import LAMBDA_INVOKE_HEADER, DeferredStartup

REPO = Path(__file__).resolve().parents[1]
INVOKE = {LAMBDA_INVOKE_HEADER: "{}"}


class FakeEngine:
    store = [1, 2, 3]
    semantic_search = True

    def warm(self):
        return True


@pytest.fixture
def lambda_app(tmp_path, monkeypatch):
    pytest.importorskip("httpx")
    import backend.cloud_sync as cs
    from backend.api.settings import settings

    app_mod = importlib.import_module("backend.api.app")
    monkeypatch.setattr(cs, "ON_LAMBDA", True)
    monkeypatch.setattr(settings, "s3_bucket", None)
    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")
    monkeypatch.setattr(settings, "study_db", tmp_path / "study.db")
    monkeypatch.setattr(settings, "analytics_db", tmp_path / "analytics.db")
    monkeypatch.setattr(settings, "health_startup_wait_s", 0.05)
    monkeypatch.setattr(settings, "startup_wait_s", 0.05)
    return app_mod


def test_importing_the_api_loads_no_heavy_library():
    code = (
        "import sys, backend.api\n"
        "heavy = ['torch', 'sentence_transformers', 'transformers', 'langgraph', 'google.genai', 'openai', 'boto3', 'bs4', 'git']\n"
        "print([m for m in heavy if m in sys.modules])"
    )
    out = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True, timeout=60, check=True)
    assert out.stdout.strip() == "[]"


def test_concurrent_callers_share_one_load():
    calls = []
    release = threading.Event()

    def load():
        calls.append(1)
        release.wait(5)

    startup = DeferredStartup(load)
    futures = []
    threads = [threading.Thread(target=lambda: futures.append(startup.begin())) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    release.set()
    futures[0].result(5)
    assert len(calls) == 1 and len({id(f) for f in futures}) == 1 and startup.ready


def test_a_failed_load_is_tried_again():
    attempts = []

    def load():
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("s3 unavailable")

    startup = DeferredStartup(load)
    with pytest.raises(RuntimeError):
        startup.begin().result(5)
    assert startup.failed and not startup.ready
    startup.begin().result(5)
    assert startup.ready and len(attempts) == 2


def test_readiness_check_is_instant_and_does_not_start_the_load(lambda_app, monkeypatch):
    from fastapi.testclient import TestClient

    made = []
    monkeypatch.setattr(lambda_app, "make_engine", lambda: made.append(1) or FakeEngine())
    with TestClient(lambda_app.create_app()) as client:
        res = client.get("/health")  # no invoke header: this is the adapter's own check
        assert res.status_code == 200
        assert res.json()["status"] == "starting" and res.json()["chunks"] is None and res.json()["semantic_search"] is None
        assert res.headers["cache-control"] == "no-store"
        time.sleep(0.05)
        assert made == []


def test_health_reports_starting_then_the_real_status(lambda_app, monkeypatch):
    from fastapi.testclient import TestClient

    release = threading.Event()

    def slow_engine():
        release.wait(5)
        return FakeEngine()

    monkeypatch.setattr(lambda_app, "make_engine", slow_engine)
    app = lambda_app.create_app()
    with TestClient(app) as client:
        assert client.get("/health", headers=INVOKE).json()["status"] == "starting"
        release.set()
        app.state.startup.begin().result(5)
        body = client.get("/health", headers=INVOKE).json()
        assert body["status"] == "ok" and body["chunks"] == 3 and body["semantic_search"] is True


def test_health_reports_a_failed_start_as_unavailable(lambda_app, monkeypatch):
    from fastapi.testclient import TestClient

    def broken():
        raise RuntimeError("secret detail")

    monkeypatch.setattr(lambda_app, "make_engine", broken)
    with TestClient(lambda_app.create_app()) as client:
        res = client.get("/health", headers=INVOKE)
        assert res.status_code == 503 and res.json()["error"]["code"] == "startup_failed"
        assert "secret detail" not in res.text


def test_api_routes_wait_and_touch_no_database_before_the_restore(lambda_app, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    release = threading.Event()

    def slow_engine():
        release.wait(5)
        return FakeEngine()

    monkeypatch.setattr(lambda_app, "make_engine", slow_engine)
    app = lambda_app.create_app()
    with TestClient(app) as client:
        res = client.get("/api/v1/cards")
        assert res.status_code == 503 and res.json()["error"]["code"] == "starting" and res.headers["retry-after"] == "3"
        assert not (tmp_path / "study.db").exists()  # a database made now would overwrite the saved one
        release.set()
        app.state.startup.begin().result(5)


def test_the_api_key_is_enforced_as_soon_as_a_request_is_served(lambda_app, monkeypatch):
    """The key arrives during startup, so a request must not slip through while it is still unset."""
    from fastapi.testclient import TestClient

    from backend.api.settings import settings

    def load_key_then_engine():
        monkeypatch.setattr(settings, "api_key", "s3cret")
        return FakeEngine()

    monkeypatch.setattr(lambda_app, "make_engine", load_key_then_engine)
    monkeypatch.setattr(settings, "startup_wait_s", 5)
    with TestClient(lambda_app.create_app()) as client:
        assert client.get("/api/v1/stats").status_code == 401


def test_every_api_route_waits_for_startup():
    from backend.api import app
    from backend.api.deps import wait_until_started

    routers = [r.original_router for r in app.routes if hasattr(r, "original_router")]
    assert len(routers) == 9  # including attempt (Try first)
    for router in routers:
        assert router.prefix.startswith("/api/v1")
        assert router.dependencies[0].dependency is wait_until_started, router.prefix


def test_outside_lambda_startup_still_finishes_before_serving(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import backend.cloud_sync as cs
    from backend.api.settings import settings

    app_mod = importlib.import_module("backend.api.app")
    monkeypatch.setattr(cs, "ON_LAMBDA", False)
    monkeypatch.setattr(settings, "s3_bucket", None)
    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")
    monkeypatch.setattr(app_mod, "make_engine", FakeEngine)
    app = app_mod.create_app()
    with TestClient(app) as client:
        assert app.state.startup is None
        assert client.get("/health").json()["status"] == "ok"
