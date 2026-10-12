"""Incremental indexing into a `VectorStore`.

Each input (a local file or a URL) is a *source*. A file's fingerprint is the
SHA-256 of its content, so re-running the indexer only re-processes files that
changed; URLs are fetched once and skipped afterwards unless `refresh_urls`
is set. Chunks are hashed, and only chunks the store has not seen are embedded.
Sources that disappeared from the input directory are pruned.

CLI:
    python -m backend.indexer                       # incremental update
    python -m backend.indexer --rebuild             # start from scratch
    python -m backend.indexer --refresh-urls        # re-fetch URLs too
"""

from __future__ import annotations

import argparse
import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

import numpy as np

from .document_processor import build_chunks_from_input, discover_inputs
from .embeddings import Embedder, get_embedder, get_embedder_by_name
from .vector_store import VectorStore, chunk_hash

logger = logging.getLogger("ai-study-mentor.indexer")

EMBED_BATCH = 256


@dataclass
class IndexReport:
    indexed: List[str] = field(default_factory=list)   # sources (re)processed
    skipped: List[str] = field(default_factory=list)   # unchanged sources
    pruned: List[str] = field(default_factory=list)    # sources removed from disk
    failed: Dict[str, str] = field(default_factory=dict)
    chunks_added: int = 0
    chunks_removed: int = 0

    def summary(self) -> str:
        return (
            f"{len(self.indexed)} indexed, {len(self.skipped)} unchanged, {len(self.pruned)} pruned, "
            f"{len(self.failed)} failed; +{self.chunks_added} / -{self.chunks_removed} chunks"
        )


def is_url(inp: str) -> bool:
    return inp.startswith(("http://", "https://"))


def source_key(inp: str) -> str:
    """Identity of a source: the URL, or the file name for local files."""
    return inp if is_url(inp) else Path(inp).name


def fingerprint(inp: str) -> Optional[str]:
    """Content hash for local files; None for URLs."""
    if is_url(inp):
        return None
    h = hashlib.sha256()
    with open(inp, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def resolve_embedder(store: VectorStore, embedder: Optional[Embedder] = None) -> Embedder:
    """Embedder to use when writing: explicit > the one the store was built with > best available."""
    if embedder is not None:
        return embedder
    if len(store) and store.embedder_name:
        return get_embedder_by_name(store.embedder_name)
    return get_embedder()


def _embed(embedder: Embedder, texts: List[str]) -> np.ndarray:
    parts = [embedder.encode(texts[i : i + EMBED_BATCH]) for i in range(0, len(texts), EMBED_BATCH)]
    return np.concatenate(parts, axis=0) if parts else np.zeros((0, embedder.dim), dtype=np.float32)


def index_inputs(
    store: VectorStore,
    inputs: List[str],
    embedder: Optional[Embedder] = None,
    refresh_urls: bool = False,
    progress: Optional[Callable[[str], None]] = None,
) -> IndexReport:
    """Add or update sources in `store` (in memory; call `store.save()` to persist)."""
    report = IndexReport()
    emb: Optional[Embedder] = None
    say = progress or (lambda _msg: None)

    for inp in inputs:
        key = source_key(inp)
        existing = store.sources.get(key)
        try:
            fp = fingerprint(inp)
        except OSError as e:
            report.failed[key] = f"cannot read file: {e}"
            continue
        if existing is not None and (is_url(inp) and not refresh_urls or fp is not None and existing.get("fingerprint") == fp):
            report.skipped.append(key)
            continue

        say(f"extracting {key}")
        try:
            chunks = [c for c in build_chunks_from_input(inp) if (c.get("text") or "").strip()]
        except Exception as e:
            report.failed[key] = str(e)  # keep whatever was indexed for this source before
            continue

        # Replace the old version of this source only once extraction succeeded.
        if existing is not None:
            report.chunks_removed += store.remove_source(key)

        for c in chunks:
            c["chunk_hash"] = chunk_hash(c)
        new_chunks = []
        seen = set()
        for c in chunks:
            if not store.has_hash(c["chunk_hash"]) and c["chunk_hash"] not in seen:
                seen.add(c["chunk_hash"])
                new_chunks.append(c)

        if new_chunks:
            if emb is None:
                emb = resolve_embedder(store, embedder)
            store.set_embedder(emb.name, emb.dim)
            say(f"embedding {len(new_chunks)} chunks from {key}")
            vectors = _embed(emb, [c["text"] for c in new_chunks])
            report.chunks_added += store.add(new_chunks, vectors, key, fp)
        else:
            store.add([], np.zeros((0, 0), dtype=np.float32), key, fp)
        report.indexed.append(key)
    return report


def index_directory(
    input_dir: str,
    store_dir: str,
    embedder: Optional[Embedder] = None,
    rebuild: bool = False,
    refresh_urls: bool = False,
    prune: bool = True,
    save: bool = True,
    progress: Optional[Callable[[str], None]] = None,
) -> IndexReport:
    """Bring the store in `store_dir` up to date with the sources in `input_dir`."""
    store = VectorStore.load(store_dir)
    if rebuild:
        store.clear()
    inputs = discover_inputs(input_dir)
    report = index_inputs(store, inputs, embedder=embedder, refresh_urls=refresh_urls, progress=progress)
    if prune:
        wanted = {source_key(i) for i in inputs}
        for key in list(store.sources):
            if key not in wanted:
                report.chunks_removed += store.remove_source(key)
                report.pruned.append(key)
    if save:
        store.save()
    return report


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Build or update the vector store from data/uploaded_files.")
    ap.add_argument("--input-dir", default="data/uploaded_files")
    ap.add_argument("--store-dir", default="data/vector_store")
    ap.add_argument("--rebuild", action="store_true", help="discard the existing store first")
    ap.add_argument("--refresh-urls", action="store_true", help="re-fetch URLs that are already indexed")
    ap.add_argument("--no-prune", action="store_true", help="keep sources whose files were removed")
    ap.add_argument("--embedder", choices=["auto", "sentence-transformers", "hashing"], default=None)
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    embedder = get_embedder(prefer=args.embedder) if args.embedder else None
    report = index_directory(
        str(Path(args.input_dir).resolve()),
        str(Path(args.store_dir).resolve()),
        embedder=embedder,
        rebuild=args.rebuild,
        refresh_urls=args.refresh_urls,
        prune=not args.no_prune,
        progress=lambda m: print(m, flush=True),
    )
    print(report.summary())
    for key, err in report.failed.items():
        print(f"  failed: {key}: {err}")
    return 0 if not report.failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
