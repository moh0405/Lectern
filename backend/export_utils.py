from __future__ import annotations

import io
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


def markdown_to_html(md_text: str) -> str:
    """
    Lightweight Markdown → HTML conversion.
    - Uses the 'markdown' package if available, or a naive converter.
    """
    try:
        import markdown as md
        return md.markdown(md_text)
    except Exception:
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


def _escape_html(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )