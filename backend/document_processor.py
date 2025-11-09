from pathlib import Path
from typing import List, Dict, Any, Tuple

import numpy as np

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None  # Allows import even if pypdf missing

try:
    import faiss
except Exception:
    faiss = None

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None


def read_pdf(path: str) -> List[Tuple[int, str]]:
    if PdfReader is None:
        raise RuntimeError("pypdf is not installed. Install requirements first.")
    reader = PdfReader(path)
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages.append((i + 1, text))
    return pages


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 160) -> List[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
        if start < 0:
            start = 0
    return [c.strip() for c in chunks if c.strip()]


def build_chunks_from_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    doc_name = Path(pdf_path).name
    page_texts = read_pdf(pdf_path)
    chunks: List[Dict[str, Any]] = []
    for page_num, text in page_texts:
        for idx, c in enumerate(chunk_text(text)):
            chunks.append(
                {
                    "text": c,
                    "doc": doc_name,
                    "page": page_num,
                    "chunk_id": f"{doc_name}-p{page_num}-c{idx}",
                }
            )
    return chunks


def embed_texts(texts: List[str], model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> np.ndarray:
    if SentenceTransformer is None:
        raise RuntimeError("sentence-transformers is not installed. Install requirements first.")
    model = SentenceTransformer(model_name, device="cpu")
    emb = model.encode(texts, show_progress_bar=False, normalize_embeddings=True, batch_size=1)
    return np.asarray(emb, dtype=np.float32)


def save_vector_store(embeddings: np.ndarray, metadata: List[Dict[str, Any]], out_dir: str) -> None:
    if faiss is None:
        raise RuntimeError("faiss is not installed. Install requirements first.")
    d = embeddings.shape[1]
    index = faiss.IndexFlatIP(d)
    index.add(embeddings)

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(out_path / "index.faiss"))

    import pickle

    with open(out_path / "index.pkl", "wb") as f:
        pickle.dump({"metadata": metadata}, f)


def build_vector_store_from_dir(input_dir: str, out_dir: str) -> Tuple[int, int]:
    input_path = Path(input_dir)
    pdfs = sorted(input_path.glob("*.pdf"))
    all_chunks: List[Dict[str, Any]] = []
    for pdf in pdfs:
        all_chunks.extend(build_chunks_from_pdf(str(pdf)))

    texts = [c["text"] for c in all_chunks]
    if not texts:
        raise RuntimeError("No text extracted from PDFs. Ensure they are not scanned images.")
    emb = embed_texts(texts)
    save_vector_store(emb, all_chunks, out_dir)
    return len(pdfs), len(all_chunks)


def load_vector_store(out_dir: str) -> Tuple[Any, List[Dict[str, Any]]]:
    if faiss is None:
        raise RuntimeError("faiss is not installed. Install requirements first.")
    out_path = Path(out_dir)
    index = faiss.read_index(str(out_path / "index.faiss"))
    import pickle

    with open(out_path / "index.pkl", "rb") as f:
        meta = pickle.load(f)["metadata"]
    return index, meta


if __name__ == "__main__":
    input_dir = str(Path("data/uploaded_files").resolve())
    out_dir = str(Path("data/vector_store").resolve())
    index_f = Path(out_dir) / "index.faiss"
    meta_f = Path(out_dir) / "index.pkl"
    if index_f.exists() and meta_f.exists():
        print(f"Vector store already exists at: {out_dir}. Skipping rebuild.")
    else:
        print(f"Building vector store from: {input_dir}")
        try:
            n_docs, n_chunks = build_vector_store_from_dir(input_dir, out_dir)
            print(f"Done. PDFs: {n_docs}, chunks: {n_chunks}")
            print(f"Saved to: {out_dir}")
        except Exception as e:
            print(f"Error: {e}")
            raise