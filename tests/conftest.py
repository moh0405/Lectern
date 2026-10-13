"""Shared fixtures. Nothing here needs network access or a real Gemini key."""

from __future__ import annotations

import io
import shutil
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


from .fake_gemini import FakeGemini  # noqa: E402


@pytest.fixture(autouse=True)
def _never_load_torch(monkeypatch):
    """Tests use the dependency-free hashing embedder so they are fast and never import torch."""
    monkeypatch.setenv("EMBEDDER", "hashing")


@pytest.fixture
def fake_gemini(monkeypatch):
    FakeGemini.handler, FakeGemini.fail_with, FakeGemini.calls = None, None, []
    for target in (
        "backend.llm_providers.create_llm",
        "backend.api.routers.ask.create_llm",
        "backend.api.routers.tracking.create_llm",
        "backend.advanced_ai.create_llm",
        "backend.leetcode_handler.create_llm",
    ):
        monkeypatch.setattr(target, FakeGemini)
    return FakeGemini


def make_pdf(text: str) -> bytes:
    canvas = pytest.importorskip("reportlab.pdfgen.canvas")
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 800
    for line in text.splitlines():
        c.drawString(72, y, line)
        y -= 20
    c.save()
    return buf.getvalue()


@pytest.fixture
def pdf_bytes():
    return make_pdf


@pytest.fixture
def api(tmp_path, monkeypatch):
    """A TestClient for the real app, with every path, setting and cache pointed at tmp_path."""
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from backend.api import app
    from backend.api import deps
    from backend.api.settings import settings
    from backend.rag_engine import RAGEngine

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EMBEDDER", "hashing")
    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")
    monkeypatch.setattr(settings, "store_dir", tmp_path / "store")
    monkeypatch.setattr(settings, "analytics_db", tmp_path / "analytics.db")
    monkeypatch.setattr(settings, "study_db", tmp_path / "study.db")
    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "rate_limit_per_min", 1000)
    (tmp_path / "uploads").mkdir()
    src = REPO / "data" / "leetcode" / "normalized_problems.jsonl"
    if src.exists():
        (tmp_path / "data" / "leetcode").mkdir(parents=True)
        shutil.copy(src, tmp_path / "data" / "leetcode" / "normalized_problems.jsonl")
    for attr in ("engine", "jobs", "analytics", "leetcode", "answer_cache", "study"):
        setattr(app.state, attr, None)
    deps._rate_state.clear()
    RAGEngine.clear_shared()
    client = TestClient(app)
    client.app_state = app.state
    yield client
    jobs = getattr(app.state, "jobs", None)
    if jobs is not None:
        jobs.shutdown()


@pytest.fixture
def indexed(api, pdf_bytes):
    """The API with one small PDF about heaps already uploaded and indexed."""
    pdf = pdf_bytes("A binary heap is a complete binary tree used to implement a priority queue.")
    res = api.post("/api/v1/sources/files", files={"files": ("heaps.pdf", pdf, "application/pdf")})
    assert res.status_code == 202, res.text
    job = api.app_state.jobs.wait(res.json()["job_id"])
    assert job["status"] == "done", job
    return api
