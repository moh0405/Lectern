from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any, List


class BaseSource(ABC):
    """
    Abstract interface for content sources.

    Each implementation must:
    - validate(input) -> bool
    - extract(input) -> List[Dict[str, Any]]  (returns chunk dicts)
    - get_metadata() -> Dict[str, Any]

    Chunk schema (minimum):
    - text: str
    - doc: str            # human-friendly document label
    - page: int | None    # page or None
    - chunk_id: str       # unique id
    - source_type: str    # e.g., "pdf", "youtube", "web", "github", "audio"
    - url: str | None     # canonical URL to cite
    - extra: Dict[str, Any]  # optional fields (e.g., timestamps)
    """

    @abstractmethod
    def validate(self, input_value: str) -> bool:
        pass

    @abstractmethod
    def extract(self, input_value: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        pass

    # Shared helper: conservative text chunking
    def chunk_text(self, text: str, chunk_size: int = 800, overlap: int = 160) -> List[str]:
        chunks: List[str] = []
        start = 0
        tlen = len(text)
        while start < tlen:
            end = min(start + chunk_size, tlen)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end == tlen:
                break
            start = max(0, end - overlap)
        return chunks