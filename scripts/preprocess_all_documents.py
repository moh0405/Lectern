"""
Preprocess all documents once to build a fast vector store.

Outputs under `data/vector_store/`:
- index.faiss : FAISS index for fast similarity search
- index.pkl   : metadata list for each chunk
- embeddings.npy : normalized embeddings (for fallback retrieval)

Run:
    python scripts/preprocess_all_documents.py

This script scans `data/uploaded_files/` including PDFs, audio/video, and URLs
from `sources.txt`, then builds the vector store using backend.document_processor.
"""
from pathlib import Path
import sys

# Ensure project root on sys.path when running as a script
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.document_processor import build_vector_store_from_dir


def main() -> None:
    input_dir = str(Path("data/uploaded_files").resolve())
    out_dir = str(Path("data/vector_store").resolve())
    print(f"Scanning sources in: {input_dir}")
    try:
        processed, chunks = build_vector_store_from_dir(input_dir, out_dir)
        print(f"Built vector store at {out_dir}: {processed} sources → {chunks} chunks")
        print("Done. App will load instantly using cached index and embeddings.")
    except Exception as e:
        print(f"Preprocessing failed: {e}")


if __name__ == "__main__":
    main()