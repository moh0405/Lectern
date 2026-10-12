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


def test_gemini_client_requires_api_key(monkeypatch):
    pytest.importorskip("google.genai")
    from backend.llm_config import GeminiClient

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        GeminiClient()


@pytest.mark.parametrize(
    "payload",
    [
        "<script>alert(1)</script>",
        "<img src=x onerror=alert(1)>",
        "[click](javascript:alert(1))",
        "<a href=\"javascript:alert(1)\" onclick=\"x()\">hi</a>",
        "<iframe src=\"https://evil.example\"></iframe>",
        "<style>body{display:none}</style>",
        "<div onmouseover=alert(1)>hover</div>",
    ],
)
def test_html_export_strips_active_content(payload):
    html = markdown_to_html(f"# Title\n\n{payload}\n")
    lowered = html.lower()
    for bad in ("<script", "onerror", "onclick", "onmouseover", "javascript:", "<iframe", "<style", "<img"):
        assert bad not in lowered, (bad, html)
    assert "<h1>Title</h1>" in html


def test_html_export_keeps_safe_formatting_and_links():
    html = markdown_to_html("**bold** and `code`\n\n[site](https://example.com)\n\n```python\nx = 1 < 2\n```\n")
    assert "<strong>bold</strong>" in html and "<code>code</code>" in html
    assert 'href="https://example.com"' in html and 'rel="noopener noreferrer"' in html
    assert "x = 1 &lt; 2" in html


def test_html_document_wrapper_is_self_contained():
    from backend.export_utils import markdown_to_html_document

    doc = markdown_to_html_document("# Hi <script>x</script>", title="A <b> title")
    assert doc.startswith("<!doctype html>") and "<script" not in doc.lower()
    assert "A &lt;b&gt; title" in doc
