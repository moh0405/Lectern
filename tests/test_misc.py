import pytest

from backend.export_utils import markdown_to_html, markdown_to_pdf


def test_markdown_to_html_renders_headings_and_lists():
    html = markdown_to_html("# Title\n\n- item")
    assert "<h1>Title</h1>" in html
    assert "<li>item</li>" in html


def test_markdown_to_pdf_returns_pdf_bytes():
    pytest.importorskip("reportlab")
    data = markdown_to_pdf("# Notes\n\n- one\n- two")
    assert data is not None and data.startswith(b"%PDF")


def test_math_solve_differentiate():
    pytest.importorskip("sympy")
    from backend.advanced_ai import math_solve

    res = math_solve("differentiate sin(x)")
    assert res["ok"] and "cos" in res["latex"]


def test_math_solve_solve_equation():
    pytest.importorskip("sympy")
    from backend.advanced_ai import math_solve

    res = math_solve("solve x^2 = 4 for x")
    assert res["ok"] and "2" in res["latex"]


def test_gemini_client_requires_api_key(monkeypatch):
    pytest.importorskip("google.generativeai")
    from backend.llm_config import GeminiClient

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        GeminiClient()
