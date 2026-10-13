from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from urllib.parse import urlparse

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None  # Allows import even if pypdf missing

from .embeddings import embed_texts  # noqa: F401  (re-exported for existing callers)

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
    """Legacy fixed-window chunker (800 characters, 160 overlap). Kept as the evaluation baseline;
    indexing uses backend/chunking.py."""
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
    """Chunk a PDF with the structure-aware chunker: running headers and licence boilerplate are removed,
    paragraphs may continue across a page break, and a chunk records the page it starts on (plus
    `extra.end_page` when it runs onto the next one)."""
    from .chunking import chunk_pages

    doc_name = Path(pdf_path).name
    chunks: List[Dict[str, Any]] = []
    for idx, item in enumerate(chunk_pages(read_pdf(pdf_path))):
        page = item["page"]
        chunks.append(
            {
                "text": item["text"],
                "doc": doc_name,
                "page": page,
                "chunk_id": f"{doc_name}-p{page}-c{idx}",
                "source_type": "pdf",
                "url": None,
                "extra": {"end_page": item["end_page"]} if item.get("end_page") else {},
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


AUDIO_EXTS = ("*.mp3", "*.mp4", "*.wav", "*.m4a")


def discover_inputs(input_dir: str, include_urls: bool = True) -> List[str]:
    """List indexable inputs in a directory: PDFs, audio/video, and URLs from sources.txt."""
    input_path = Path(input_dir)
    inputs: List[str] = []
    if not input_path.exists():
        return inputs
    inputs.extend(str(p) for p in sorted(input_path.glob("*.pdf")))
    for ext in AUDIO_EXTS:
        inputs.extend(str(p) for p in sorted(input_path.glob(ext)))
    sources_file = input_path / "sources.txt"
    if include_urls and sources_file.exists():
        try:
            for line in sources_file.read_text().splitlines():
                url = line.strip()
                if url and not url.startswith("#"):
                    inputs.append(url)
        except Exception:
            pass
    return inputs


def _chunks_from_inputs(inputs: List[str]) -> List[Dict[str, Any]]:
    all_chunks: List[Dict[str, Any]] = []
    for inp in inputs:
        try:
            all_chunks.extend(build_chunks_from_input(inp))
        except Exception:
            continue
    return all_chunks


def list_chunks_from_dir(input_dir: str) -> List[Dict[str, Any]]:
    """Collect chunks from all supported sources in a directory without embedding them.

    Includes URLs from sources.txt (network). Prefer the vector store for normal use.
    """
    return _chunks_from_inputs(discover_inputs(input_dir, include_urls=True))


def list_chunks_from_dir_local(input_dir: str) -> List[Dict[str, Any]]:
    """Like list_chunks_from_dir but local files only (no network)."""
    return _chunks_from_inputs(discover_inputs(input_dir, include_urls=False))
