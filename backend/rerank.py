"""Optional cross-encoder reranking.

Bi-encoders (the embedding model) compare a query and a passage through two separate vectors, which is
fast but coarse. A cross-encoder reads the query and the passage together and scores the pair directly,
which is slower and more precise, so it is used only to reorder a short list of candidates.

Needs sentence-transformers; the model is downloaded on first use. Enable with RERANKER=cross-encoder
(or the model name) and see eval/reports for whether it earns its latency.
"""

from __future__ import annotations

import logging
import threading
from typing import List, Optional, Sequence

logger = logging.getLogger("ai-study-mentor.rerank")

DEFAULT_RERANKER = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_models: dict = {}
_lock = threading.Lock()


class Reranker:
    def __init__(self, model_name: str = DEFAULT_RERANKER) -> None:
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            with _lock:
                if self._model is None:
                    try:
                        from sentence_transformers import CrossEncoder
                    except Exception as e:
                        raise RuntimeError(f"sentence-transformers unavailable: {e}") from e
                    self._model = _models.get(self.model_name) or CrossEncoder(self.model_name, device="cpu")
                    _models[self.model_name] = self._model
        return self._model

    def score(self, query: str, passages: Sequence[str]) -> List[float]:
        """Relevance score per passage (higher is better; not bounded to 0..1)."""
        if not passages:
            return []
        scores = self._load().predict([(query, p) for p in passages], batch_size=16, show_progress_bar=False)
        return [float(s) for s in scores]

    def order(self, query: str, passages: Sequence[str]) -> List[int]:
        """Indexes of `passages`, best first."""
        scores = self.score(query, passages)
        return sorted(range(len(passages)), key=lambda i: -scores[i])


def get_reranker(name: Optional[str]) -> Optional[Reranker]:
    """RERANKER=cross-encoder -> the default model; any other non-empty value is a model name."""
    if not name or name.lower() in {"0", "off", "none", "false"}:
        return None
    return Reranker(DEFAULT_RERANKER if name.lower() in {"1", "on", "true", "cross-encoder"} else name)
