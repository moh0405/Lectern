"""Shared fixtures. Nothing here needs network access or a real Gemini key."""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


class FakeGemini:
    """Stand-in for GeminiClient. Override `FakeGemini.handler` in a test to script replies."""

    handler = None  # callable(prompt, json_mode) -> str
    fail_with = None  # set to an Exception to make every call fail
    calls: list = []

    def __init__(self, model=None, temperature=0.2, **kw):
        if FakeGemini.fail_with is not None and isinstance(FakeGemini.fail_with, RuntimeError):
            raise FakeGemini.fail_with
        self.model = model or "fake-model"
        self.temperature = temperature

    @staticmethod
    def default_reply(prompt: str, json_mode: bool) -> str:
        if json_mode and "concept" in prompt.lower():
            return json.dumps({
                "nodes": [{"id": "list", "label": "Linked list"}, {"id": "node", "label": "Node"},
                          {"id": "list", "label": "dup"}],
                "edges": [{"from": "list", "to": "node", "label": "has"}, {"from": "list", "to": "ghost"}],
            })
        if json_mode and "socratic" in prompt.lower():
            return json.dumps({"questions": ["What is a node?", "How are nodes linked?"], "hints": ["h1", "h2", "h3"]})
        if json_mode and "synthesizer" in prompt.lower():
            return json.dumps({"similarities": ["both define it"], "conflicts": [], "synthesis": "Unified view.",
                               "citations": [{"doc": "a.pdf", "point": "defines it"}, "loose citation"]})
        return "A linked list is a chain of nodes. [heaps.pdf (page 1)]"

    def _reply(self, prompt, json_mode):
        FakeGemini.calls.append(prompt)
        if FakeGemini.fail_with is not None:
            raise FakeGemini.fail_with
        return (FakeGemini.handler or FakeGemini.default_reply)(prompt, json_mode)

    def generate(self, prompt, temperature=None, json_mode=False):
        try:
            return {"ok": True, "model": self.model, "answer": self._reply(prompt, json_mode)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def stream(self, prompt, temperature=None, json_mode=False):
        text = self._reply(prompt, json_mode)
        words = text.split(" ")
        for i, w in enumerate(words):
            yield w + ("" if i == len(words) - 1 else " ")


@pytest.fixture(autouse=True)
def _never_load_torch(monkeypatch):
    """Tests use the dependency-free hashing embedder so they are fast and never import torch."""
    monkeypatch.setenv("EMBEDDER", "hashing")


@pytest.fixture
def fake_gemini(monkeypatch):
    FakeGemini.handler, FakeGemini.fail_with, FakeGemini.calls = None, None, []
    for target in (
        "backend.llm_config.GeminiClient",
        "backend.api.routers.ask.GeminiClient",
        "backend.advanced_ai.GeminiClient",
        "backend.leetcode_handler.GeminiClient",
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
    monkeypatch.setattr(settings, "api_key", None)
    monkeypatch.setattr(settings, "rate_limit_per_min", 1000)
    (tmp_path / "uploads").mkdir()
    src = REPO / "data" / "leetcode" / "normalized_problems.jsonl"
    if src.exists():
        (tmp_path / "data" / "leetcode").mkdir(parents=True)
        shutil.copy(src, tmp_path / "data" / "leetcode" / "normalized_problems.jsonl")
    for attr in ("engine", "jobs", "analytics", "leetcode"):
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
