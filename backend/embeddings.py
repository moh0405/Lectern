"""Text embedders.

Two implementations share one tiny interface (`name`, `dim`, `encode`):

- `SentenceTransformerEmbedder`: real semantic embeddings (needs the
  `embeddings` extra). Imported lazily so that merely importing this module
  never pulls in torch.
- `HashingEmbedder`: dependency-free bag-of-words hashing. Not semantic, but
  deterministic, fast and much better than raw keyword overlap. Used when
  sentence-transformers is unavailable and in tests.

All embedders return L2-normalized float32 matrices, so a dot product is the
cosine similarity.

Environment:
    EMBEDDER=auto|sentence-transformers|hashing   (default: auto)
"""

from __future__ import annotations

import logging
import math
import os
import re
import zlib
from collections import Counter
from functools import lru_cache
from typing import Dict, List, Optional, Protocol

import numpy as np

logger = logging.getLogger("ai-study-mentor.embeddings")

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
_TOKEN_RE = re.compile(r"[a-z0-9_]+")


class Embedder(Protocol):
    name: str
    dim: int

    def encode(self, texts: List[str]) -> np.ndarray: ...


class HashingEmbedder:
    """Signed feature hashing over unigrams and bigrams (stable across runs)."""

    def __init__(self, dim: int = 512) -> None:
        self.dim = dim
        self.name = f"hashing-{dim}"

    def _features(self, text: str) -> Dict[str, float]:
        toks = _TOKEN_RE.findall(text.lower())
        counts = Counter(toks)
        counts.update(f"{a}_{b}" for a, b in zip(toks, toks[1:]))
        return {t: 1.0 + math.log(c) for t, c in counts.items()}

    def encode(self, texts: List[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for feat, weight in self._features(text).items():
                h = zlib.crc32(feat.encode("utf-8"))
                sign = 1.0 if zlib.crc32(b"#" + feat.encode("utf-8")) & 1 else -1.0
                out[row, h % self.dim] += sign * weight
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return out / norms


class SentenceTransformerEmbedder:
    """Lazy wrapper around a sentence-transformers model (CPU)."""

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        self.name = model_name
        self._model = None
        self._dim: Optional[int] = None

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except Exception as e:  # ImportError, or a broken torch install
                raise RuntimeError(f"sentence-transformers unavailable: {e}") from e
            os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
            self._model = SentenceTransformer(self.name, device="cpu")
        return self._model

    @property
    def dim(self) -> int:  # type: ignore[override]
        if self._dim is None:
            model = self._load()
            # renamed in sentence-transformers 5; support both
            get_dim = getattr(model, "get_embedding_dimension", None) or model.get_sentence_embedding_dimension
            self._dim = int(get_dim())
        return self._dim

    def encode(self, texts: List[str]) -> np.ndarray:
        model = self._load()
        try:
            arr = model.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False)
        except Exception:
            # Constrained environments: retry with small batches.
            arr = model.encode(texts, normalize_embeddings=True, batch_size=8, show_progress_bar=False)
        return np.asarray(arr, dtype=np.float32)

    def ensure_loaded(self) -> None:
        self._load()


@lru_cache(maxsize=8)
def _cached_embedder(name: str) -> Embedder:
    if name.startswith("hashing-"):
        return HashingEmbedder(dim=int(name.split("-", 1)[1]))
    return SentenceTransformerEmbedder(name)


def get_embedder_by_name(name: str) -> Embedder:
    """Return the embedder that produced vectors labelled `name`.

    Raises RuntimeError if it cannot be loaded (e.g. sentence-transformers is
    not installed), so callers can fall back to keyword retrieval.
    """
    emb = _cached_embedder(name)
    if isinstance(emb, SentenceTransformerEmbedder):
        emb.ensure_loaded()
    return emb


def get_embedder(model_name: str = DEFAULT_MODEL, prefer: Optional[str] = None) -> Embedder:
    """Pick an embedder for building a new index.

    `prefer` (or the EMBEDDER env var): "sentence-transformers", "hashing" or "auto".
    In auto mode sentence-transformers is used if it loads, else hashing.
    """
    choice = (prefer or os.getenv("EMBEDDER") or "auto").strip().lower()
    if choice == "hashing":
        return _cached_embedder("hashing-512")
    try:
        return get_embedder_by_name(model_name)
    except Exception as e:
        if choice in {"sentence-transformers", "st"}:
            raise
        logger.warning("Falling back to hashing embedder: %s", e)
        return _cached_embedder("hashing-512")


def embed_texts(texts: List[str], model_name: str = DEFAULT_MODEL) -> np.ndarray:
    """Encode texts with the best available embedder (kept for existing callers)."""
    return get_embedder(model_name).encode(texts)
