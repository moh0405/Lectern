"""Build or update the vector store from `data/uploaded_files/`.

Outputs under `data/vector_store/`: manifest.json, chunks.jsonl,
embeddings.npy and index.faiss (see backend/vector_store.py).

Incremental by default: unchanged files and already-indexed URLs are skipped.

    python scripts/preprocess_all_documents.py               # update
    python scripts/preprocess_all_documents.py --rebuild     # start over
    python scripts/preprocess_all_documents.py --refresh-urls

This is a thin wrapper around `python -m backend.indexer`.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.indexer import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
