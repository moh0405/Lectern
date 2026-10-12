"""On-disk vector store: chunk metadata + embeddings + FAISS index.

Layout of a store directory (no pickle anywhere):

    manifest.json    version, embedder name/dim, per-source fingerprints
    chunks.jsonl     one JSON object per chunk (text, doc, page, ..., chunk_hash, source_key)
    embeddings.npy   float32 matrix, row i belongs to chunk i (L2-normalized)
    index.faiss      FAISS IndexFlatIP cache of embeddings.npy (rebuilt if stale or missing)

`embeddings.npy` + `chunks.jsonl` are the source of truth; the FAISS file is
only a cache. Chunks are de-duplicated by `chunk_hash`, and every chunk
remembers the `source_key` it came from so a source can be re-indexed or
deleted without touching the rest.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

try:
    import faiss
except Exception:  # optional dependency
    faiss = None

logger = logging.getLogger("ai-study-mentor.store")

STORE_VERSION = 1


def chunk_hash(chunk: Dict[str, Any]) -> str:
    """Stable identity of a chunk: where it came from and what it says."""
    key = "\x1f".join(
        [
            str(chunk.get("source_type") or ""),
            str(chunk.get("doc") or ""),
            str(chunk.get("page") if chunk.get("page") is not None else ""),
            str(chunk.get("text") or ""),
        ]
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


def _atomic_write(path: Path, write) -> None:
    tmp = path.with_name(path.name + ".tmp")
    write(tmp)
    os.replace(tmp, path)


class VectorStore:
    def __init__(self, store_dir: str | Path) -> None:
        self.dir = Path(store_dir)
        self.chunks: List[Dict[str, Any]] = []
        self.embeddings: np.ndarray = np.zeros((0, 0), dtype=np.float32)
        self.manifest: Dict[str, Any] = {"version": STORE_VERSION, "embedder": None, "dim": None, "sources": {}}
        self._hashes: set[str] = set()
        self._index = None
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Basic info
    # ------------------------------------------------------------------
    def __len__(self) -> int:
        return len(self.chunks)

    @property
    def embedder_name(self) -> Optional[str]:
        return self.manifest.get("embedder")

    @property
    def sources(self) -> Dict[str, Dict[str, Any]]:
        return self.manifest["sources"]

    def docs(self) -> List[str]:
        return sorted({c.get("doc", "") for c in self.chunks if c.get("doc")})

    def has_hash(self, h: str) -> bool:
        return h in self._hashes

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------
    @classmethod
    def load(cls, store_dir: str | Path) -> "VectorStore":
        """Load a store, or return an empty one if the directory has none."""
        store = cls(store_dir)
        manifest_path = store.dir / "manifest.json"
        chunks_path = store.dir / "chunks.jsonl"
        emb_path = store.dir / "embeddings.npy"
        if not (manifest_path.exists() and chunks_path.exists() and emb_path.exists()):
            return store
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("version") != STORE_VERSION:
                raise ValueError(f"unsupported store version {manifest.get('version')}")
            with chunks_path.open("r", encoding="utf-8") as f:
                chunks = [json.loads(line) for line in f if line.strip()]
            embeddings = np.load(str(emb_path), allow_pickle=False)
            if len(chunks) != embeddings.shape[0]:
                raise ValueError(f"{len(chunks)} chunks but {embeddings.shape[0]} embeddings")
        except Exception as e:
            logger.warning("Ignoring unreadable vector store at %s: %s", store.dir, e)
            return cls(store_dir)
        store.manifest = {"version": STORE_VERSION, "embedder": None, "dim": None, "sources": {}, **manifest}
        store.chunks = chunks
        store.embeddings = embeddings.astype(np.float32, copy=False)
        store._hashes = {c.get("chunk_hash", "") for c in chunks}
        index_path = store.dir / "index.faiss"
        if faiss is not None and index_path.exists():
            try:
                idx = faiss.read_index(str(index_path))
                if idx.ntotal == len(chunks):
                    store._index = idx
            except Exception:
                store._index = None
        return store

    def save(self) -> None:
        with self._lock:
            self.dir.mkdir(parents=True, exist_ok=True)

            def write_chunks(p: Path) -> None:
                with p.open("w", encoding="utf-8") as f:
                    for c in self.chunks:
                        f.write(json.dumps(c, ensure_ascii=False) + "\n")

            _atomic_write(self.dir / "chunks.jsonl", write_chunks)

            def write_embeddings(p: Path) -> None:
                with p.open("wb") as f:
                    np.save(f, self.embeddings)

            _atomic_write(self.dir / "embeddings.npy", write_embeddings)
            index = self._get_index()
            if index is not None:
                _atomic_write(self.dir / "index.faiss", lambda p: faiss.write_index(index, str(p)))
            elif (self.dir / "index.faiss").exists():
                (self.dir / "index.faiss").unlink()
            _atomic_write(
                self.dir / "manifest.json",
                lambda p: p.write_text(json.dumps(self.manifest, indent=2, sort_keys=True), encoding="utf-8"),
            )

    def clear(self) -> None:
        """Forget everything (in memory); call save() to persist."""
        with self._lock:
            self.chunks = []
            self.embeddings = np.zeros((0, 0), dtype=np.float32)
            self.manifest = {"version": STORE_VERSION, "embedder": None, "dim": None, "sources": {}}
            self._hashes = set()
            self._index = None

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------
    def set_embedder(self, name: str, dim: int) -> None:
        """Bind an empty store to an embedder; a populated store must already match."""
        with self._lock:
            if self.chunks and self.manifest.get("embedder") != name:
                raise ValueError(
                    f"store was built with embedder '{self.manifest.get('embedder')}', not '{name}'; rebuild it"
                )
            self.manifest["embedder"] = name
            self.manifest["dim"] = dim

    def add(
        self,
        chunks: List[Dict[str, Any]],
        embeddings: np.ndarray,
        source_key: str,
        fingerprint: Optional[str] = None,
    ) -> int:
        """Add pre-embedded chunks from one source. Returns how many were new.

        Chunks whose hash is already stored are skipped (so shared text is
        never embedded or stored twice). `chunks` and `embeddings` must align.
        """
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        with self._lock:
            keep_rows: List[int] = []
            records: List[Dict[str, Any]] = []
            for i, c in enumerate(chunks):
                h = c.get("chunk_hash") or chunk_hash(c)
                if h in self._hashes:
                    continue
                self._hashes.add(h)
                keep_rows.append(i)
                records.append({**c, "chunk_hash": h, "source_key": source_key})
            if records:
                new_emb = np.asarray(embeddings, dtype=np.float32)[keep_rows]
                if self.embeddings.shape[0] == 0:
                    self.embeddings = new_emb
                else:
                    self.embeddings = np.vstack([self.embeddings, new_emb])
                self.chunks.extend(records)
                self._index = None
            entry = self.sources.setdefault(source_key, {"fingerprint": None, "chunks": 0})
            entry["fingerprint"] = fingerprint
            entry["chunks"] = sum(1 for c in self.chunks if c.get("source_key") == source_key)
            return len(records)

    def _remove_where(self, keep) -> int:
        with self._lock:
            mask = np.array([keep(c) for c in self.chunks], dtype=bool)
            removed = int((~mask).sum())
            if removed:
                self.chunks = [c for c, k in zip(self.chunks, mask) if k]
                self.embeddings = self.embeddings[mask]
                self._hashes = {c["chunk_hash"] for c in self.chunks}
                self._index = None
            return removed

    def remove_source(self, source_key: str) -> int:
        """Delete every chunk that came from `source_key`. Returns chunks removed."""
        with self._lock:
            removed = self._remove_where(lambda c: c.get("source_key") != source_key)
            self.sources.pop(source_key, None)
            return removed

    def remove_doc(self, doc: str) -> int:
        """Delete every chunk whose document label is `doc`."""
        with self._lock:
            removed = self._remove_where(lambda c: c.get("doc") != doc)
            for key, entry in list(self.sources.items()):
                entry["chunks"] = sum(1 for c in self.chunks if c.get("source_key") == key)
            return removed

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def _get_index(self):
        if faiss is None or not len(self.chunks):
            return None
        if self._index is None:
            idx = faiss.IndexFlatIP(self.embeddings.shape[1])
            idx.add(np.ascontiguousarray(self.embeddings, dtype=np.float32))
            self._index = idx
        return self._index

    @property
    def uses_faiss(self) -> bool:
        return faiss is not None

    def search(self, query_vec: np.ndarray, k: int = 3) -> List[Tuple[int, float]]:
        """Top-k (chunk_index, cosine_score) for one normalized query vector."""
        with self._lock:
            n = len(self.chunks)
            if n == 0:
                return []
            k = max(1, min(k, n))
            q = np.ascontiguousarray(np.asarray(query_vec, dtype=np.float32).reshape(1, -1))
            if q.shape[1] != self.embeddings.shape[1]:
                raise ValueError(f"query has dim {q.shape[1]}, store has dim {self.embeddings.shape[1]}")
            index = self._get_index()
            if index is not None:
                scores, ids = index.search(q, k)
                return [(int(i), float(s)) for i, s in zip(ids[0], scores[0]) if i >= 0]
            sims = self.embeddings @ q[0]
            top = np.argsort(-sims)[:k]
            return [(int(i), float(sims[i])) for i in top]

    def iter_chunks(self) -> Iterable[Dict[str, Any]]:
        return iter(list(self.chunks))
