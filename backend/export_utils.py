from __future__ import annotations

import io
import re
from html.parser import HTMLParser
from typing import Optional


def markdown_to_pdf(md_text: str) -> Optional[bytes]:
    """
    Best‑effort PDF rendering from Markdown without external binaries.
    - Tries to use reportlab if available; otherwise returns None.
    - Simple line wrapping and basic heading sizing.
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import inch
    except Exception:
        return None

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter

    y = height - 1 * inch
    left_margin = 0.75 * inch
    right_margin = width - 0.75 * inch

    def draw_line(text: str, font_size: int = 11):
        nonlocal y
        c.setFont("Helvetica", font_size)
        # basic wrap by width
        max_chars = int((right_margin - left_margin) / (font_size * 0.6))
        for line in _wrap_text(text, max_chars):
            if y < 1 * inch:
                c.showPage()
                y = height - 1 * inch
            c.drawString(left_margin, y, line)
            y -= font_size + 4

    for raw in md_text.splitlines():
        s = raw.strip()
        if s.startswith("# "):
            draw_line(s[2:], 18)
        elif s.startswith("## "):
            draw_line(s[3:], 16)
        elif s.startswith("### "):
            draw_line(s[4:], 14)
        elif s.startswith("- ") or s.startswith("* "):
            draw_line(f"• {s[2:]}")
        elif s.startswith("```"):
            # fence markers: add spacing
            draw_line(" ")
        else:
            draw_line(s)

    c.save()
    buf.seek(0)
    return buf.getvalue()


_ALLOWED_TAGS = {
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "li", "strong", "em", "b", "i", "code", "pre",
    "blockquote", "a", "br", "hr", "table", "thead", "tbody", "tr", "th", "td", "del", "span",
}
_VOID_TAGS = {"br", "hr"}
_DROP_CONTENT_TAGS = {"script", "style", "iframe", "object", "embed", "noscript", "template"}
_SAFE_HREF = re.compile(r"^(https?://|mailto:|#|/)", re.IGNORECASE)
_SAFE_CLASS = re.compile(r"^language-[\w+#-]+$")


class _Sanitizer(HTMLParser):
    """Allow-list HTML sanitizer: unknown tags are dropped (text kept), scripts/styles are dropped
    with their content, and only safe `href`/`class` attributes survive."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.open: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in _DROP_CONTENT_TAGS:
            self.skip += 1
            return
        if self.skip or tag not in _ALLOWED_TAGS:
            return
        extra = ""
        for name, value in attrs:
            value = value or ""
            if tag == "a" and name == "href" and _SAFE_HREF.match(value.strip()):
                extra += f' href="{_escape_html(value.strip(), quote=True)}" rel="noopener noreferrer"'
            elif tag == "code" and name == "class" and _SAFE_CLASS.match(value):
                extra += f' class="{value}"'
        self.out.append(f"<{tag}{extra}>")
        if tag not in _VOID_TAGS:
            self.open.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in _DROP_CONTENT_TAGS:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip or tag not in _ALLOWED_TAGS or tag in _VOID_TAGS or tag not in self.open:
            return
        while self.open:  # close any unclosed children first
            top = self.open.pop()
            self.out.append(f"</{top}>")
            if top == tag:
                break

    def handle_data(self, data):
        if not self.skip:
            self.out.append(_escape_html(data))

    def result(self) -> str:
        while self.open:
            self.out.append(f"</{self.open.pop()}>")
        return "".join(self.out)


def sanitize_html(html: str) -> str:
    parser = _Sanitizer()
    parser.feed(html)
    parser.close()
    return parser.result()


def markdown_to_html(md_text: str) -> str:
    """
    Markdown -> safe HTML fragment.
    - Uses the 'markdown' package if available (with fenced code and tables), or a naive converter.
    - The result is passed through an allow-list sanitizer, so raw HTML or scripts in the input
      (for example from model output) cannot execute in the exported file.
    """
    try:
        import markdown as md

        return sanitize_html(md.markdown(md_text, extensions=["fenced_code", "tables"]))
    except ImportError:
        # Naive fallback: wrap lines in <p>, basic lists and headings
        lines = []
        for raw in md_text.splitlines():
            s = raw.rstrip()
            if s.startswith("# "):
                lines.append(f"<h1>{_escape_html(s[2:])}</h1>")
            elif s.startswith("## "):
                lines.append(f"<h2>{_escape_html(s[3:])}</h2>")
            elif s.startswith("### "):
                lines.append(f"<h3>{_escape_html(s[4:])}</h3>")
            elif s.startswith("- ") or s.startswith("* "):
                lines.append(f"<li>{_escape_html(s[2:])}</li>")
            else:
                if s:
                    lines.append(f"<p>{_escape_html(s)}</p>")
        return "\n".join(lines)


def markdown_to_html_document(md_text: str, title: str = "Study notes") -> str:
    """A complete, self-contained HTML page (no scripts, no external resources)."""
    body = markdown_to_html(md_text)
    return (
        "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{_escape_html(title)}</title>"
        "<style>body{font:16px/1.6 system-ui,sans-serif;max-width:46rem;margin:2rem auto;padding:0 1rem}"
        "pre{background:#f5f5f5;padding:.75rem;overflow:auto}code{font-family:ui-monospace,monospace}"
        "table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:.25rem .5rem}</style>"
        f"</head><body>{body}</body></html>"
    )


def _wrap_text(text: str, max_chars: int) -> list[str]:
    words = text.split()
    lines = []
    buf = []
    count = 0
    for w in words:
        if count + len(w) + 1 > max_chars:
            lines.append(" ".join(buf))
            buf = [w]
            count = len(w)
        else:
            buf.append(w)
            count += len(w) + 1
    if buf:
        lines.append(" ".join(buf))
    return lines


def _escape_html(s: str, quote: bool = False) -> str:
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return s.replace('"', "&quot;") if quote else s
