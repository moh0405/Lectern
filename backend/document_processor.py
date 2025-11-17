from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from urllib.parse import urlparse

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

# Lazy import of modular sources to work both as package and script
try:
    from backend.sources import YouTubeSource, WebSource, GitHubSource, AudioSource  # type: ignore
except Exception:
    try:
        from .sources import YouTubeSource, WebSource, GitHubSource, AudioSource  # type: ignore
    except Exception:
        YouTubeSource = WebSource = GitHubSource = AudioSource = None  # type: ignore


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
                    "source_type": "pdf",
                    "url": None,
                    "extra": {},
                }
            )
    return chunks


def _detect_source(input_value: str) -> Optional[str]:
    p = urlparse(input_value)
    path = Path(input_value)
    if path.exists() and path.suffix.lower() == ".pdf":
        return "pdf"
    if path.exists() and path.suffix.lower() in {".mp3", ".mp4", ".wav", ".m4a"}:
        return "audio"
    if p.scheme in {"http", "https"}:
        host = (p.hostname or "").lower()
        if "youtube.com" in host or "youtu.be" in host:
            return "youtube"
        if "github.com" in host:
            return "github"
        return "web"
    return None


def build_chunks_from_input(input_value: str) -> List[Dict[str, Any]]:
    src = _detect_source(input_value)
    if src == "pdf":
        return build_chunks_from_pdf(input_value)
    if src == "youtube":
        if YouTubeSource is None:
            raise RuntimeError("youtube-transcript-api not installed or import failed.")
        handler = YouTubeSource()
        return handler.extract(input_value)
    if src == "web":
        if WebSource is None:
            raise RuntimeError("web scraping modules not installed (requests/bs4/readability).")
        handler = WebSource()
        return handler.extract(input_value)
    if src == "github":
        if GitHubSource is None:
            raise RuntimeError("gitpython or requests not installed for GitHub source.")
        handler = GitHubSource()
        return handler.extract(input_value)
    if src == "audio":
        if AudioSource is None:
            raise RuntimeError("openai not installed for Audio source.")
        handler = AudioSource()
        return handler.extract(input_value)
    raise ValueError(f"Could not detect source type for input: {input_value}")


def embed_texts(texts: List[str], model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> np.ndarray:
    if SentenceTransformer is None:
        raise RuntimeError("sentence-transformers is not installed. Install requirements first.")
    model = SentenceTransformer(model_name, device="cpu")
    # Use batched encoding for significant speedup on large corpora
    try:
        emb = model.encode(texts, show_progress_bar=False, normalize_embeddings=True, batch_size=32)
    except Exception:
        # Fallback to smaller batch size to accommodate constrained environments
        emb = model.encode(texts, show_progress_bar=False, normalize_embeddings=True, batch_size=8)
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


def build_vector_store(inputs: List[str], out_dir: str) -> Tuple[int, int]:
    """Build a FAISS vector store from a mixed list of inputs.

    Each input can be:
    - Path to a local PDF (.pdf)
    - Path to a local audio/video file (.mp3/.mp4/.wav/.m4a)
    - A URL (YouTube, GitHub repo, or generic web article)
    """
    all_chunks: List[Dict[str, Any]] = []
    processed = 0
    for inp in inputs:
        try:
            chunks = build_chunks_from_input(inp)
            all_chunks.extend(chunks)
            processed += 1
        except Exception:
            # Skip invalid input but continue building
            continue

    texts = [c.get("text", "") for c in all_chunks]
    if not texts:
        raise RuntimeError("No text extracted from inputs. Ensure sources are accessible.")
    emb = embed_texts(texts)
    save_vector_store(emb, all_chunks, out_dir)
    return processed, len(all_chunks)


def list_chunks_from_dir(input_dir: str) -> List[Dict[str, Any]]:
    """Collect chunks from all supported sources in a directory without building embeddings.

    Used for meta-only fallback when FAISS/embeddings are unavailable.
    """
    input_path = Path(input_dir)
    inputs: List[str] = []
    inputs.extend([str(p) for p in sorted(input_path.glob("*.pdf"))])
    for ext in ["*.mp3", "*.mp4", "*.wav", "*.m4a"]:
        inputs.extend([str(p) for p in sorted(input_path.glob(ext))])
    sources_file = input_path / "sources.txt"
    if sources_file.exists():
        try:
            for line in sources_file.read_text().splitlines():
                url = line.strip()
                if url:
                    inputs.append(url)
        except Exception:
            pass
    all_chunks: List[Dict[str, Any]] = []
    for inp in inputs:
        try:
            all_chunks.extend(build_chunks_from_input(inp))
        except Exception:
            continue
    return all_chunks


def list_chunks_from_dir_local(input_dir: str) -> List[Dict[str, Any]]:
    """Collect chunks only from local files to avoid slow network sources.

    Scans PDFs and audio/video files, skipping `sources.txt` URLs.
    """
    input_path = Path(input_dir)
    inputs: List[str] = []
    inputs.extend([str(p) for p in sorted(input_path.glob("*.pdf"))])
    for ext in ["*.mp3", "*.mp4", "*.wav", "*.m4a"]:
        inputs.extend([str(p) for p in sorted(input_path.glob(ext))])
    all_chunks: List[Dict[str, Any]] = []
    for inp in inputs:
        try:
            all_chunks.extend(build_chunks_from_input(inp))
        except Exception:
            continue
    return all_chunks


def build_vector_store_from_dir(input_dir: str, out_dir: str) -> Tuple[int, int]:
    input_path = Path(input_dir)
    inputs: List[str] = []
    # PDFs
    inputs.extend([str(p) for p in sorted(input_path.glob("*.pdf"))])
    # Audio/video lectures
    for ext in ["*.mp3", "*.mp4", "*.wav", "*.m4a"]:
        inputs.extend([str(p) for p in sorted(input_path.glob(ext))])
    # Optional: sources.txt containing URLs (one per line)
    sources_file = input_path / "sources.txt"
    if sources_file.exists():
        try:
            for line in sources_file.read_text().splitlines():
                url = line.strip()
                if url:
                    inputs.append(url)
        except Exception:
            pass
    return build_vector_store(inputs, out_dir)


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
        print(f"Building vector store from directory: {input_dir}")
        try:
            n_inputs, n_chunks = build_vector_store_from_dir(input_dir, out_dir)
            print(f"Done. Inputs processed: {n_inputs}, chunks: {n_chunks}")
            print(f"Saved to: {out_dir}")
        except Exception as e:
            print(f"Error: {e}")
            raise