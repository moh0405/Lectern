from __future__ import annotations

from typing import Dict, Any, List
from urllib.parse import urlparse

from .base_source import BaseSource

try:
    import requests
except Exception:
    requests = None

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

try:
    from readability import Document
except Exception:
    Document = None


class WebSource(BaseSource):
    def __init__(self) -> None:
        self._meta: Dict[str, Any] = {}

    def validate(self, input_value: str) -> bool:
        try:
            p = urlparse(input_value)
            return p.scheme in {"http", "https"}
        except Exception:
            return False

    def _favicon_for(self, url: str) -> str | None:
        try:
            p = urlparse(url)
            domain = p.hostname or ""
            if not domain:
                return None
            return f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
        except Exception:
            return None

    def extract(self, input_value: str) -> List[Dict[str, Any]]:
        if requests is None:
            raise RuntimeError("requests not installed. Add it to requirements.")
        if BeautifulSoup is None:
            raise RuntimeError("beautifulsoup4 not installed. Add it to requirements.")
        if Document is None:
            raise RuntimeError("readability-lxml not installed. Add it to requirements.")

        resp = requests.get(input_value, timeout=20)
        resp.raise_for_status()

        # Use readability to get clean article text
        doc = Document(resp.text)
        html = doc.summary(html_partial=True)
        title = doc.short_title() or "Web Article"
        soup = BeautifulSoup(html, "html.parser")
        # Preserve code blocks by wrapping in backticks
        for pre in soup.find_all(["pre", "code"]):
            pre.string = f"\n```\n{pre.get_text()}\n```\n"

        clean_text = soup.get_text("\n")
        self._meta = {
            "source_type": "web",
            "url": input_value,
            "title": title,
            "favicon": self._favicon_for(input_value),
        }

        chunks: List[Dict[str, Any]] = []
        for i, c in enumerate(self.chunk_text(clean_text)):
            chunks.append({
                "text": c,
                "doc": title,
                "page": None,
                "chunk_id": f"web-{i}",
                "source_type": "web",
                "url": input_value,
                "extra": {},
            })
        return chunks

    def get_metadata(self) -> Dict[str, Any]:
        return dict(self._meta)