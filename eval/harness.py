"""Build an index for a retrieval configuration and run the questions through it."""

from __future__ import annotations

import json
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


from backend.embeddings import HashingEmbedder, get_embedder_by_name
from backend.rag_engine import RAGEngine
from backend.vector_store import VectorStore, chunk_hash

from .metrics import QuestionResult, evidence_coverage, first_relevant_rank, norm, summarize

ROOT = Path(__file__).resolve().parent
MINILM = "sentence-transformers/all-MiniLM-L6-v2"
TOP_N = 10


@dataclass(frozen=True)
class Config:
    """One retrieval setup to evaluate."""

    name: str
    embedder: str = "hashing-512"  # "hashing-512" or a sentence-transformers model name
    chunker: str = "v1"  # see CHUNKERS
    retrieval: str = "dense"  # "dense", "keyword", later "bm25" / "hybrid"
    rerank: bool = False

    def describe(self) -> str:
        parts = [self.embedder.split("/")[-1], f"chunks {self.chunker}", self.retrieval]
        if self.rerank:
            parts.append("rerank")
        return ", ".join(parts)


# Named configurations. Later steps of Phase 4 add chunking v2, BM25, hybrid fusion and a reranker.
CONFIGS: Dict[str, Config] = {
    "keyword": Config("keyword", embedder="hashing-512", retrieval="keyword"),
    "hashing-dense": Config("hashing-dense", embedder="hashing-512", retrieval="dense"),
    "minilm-dense": Config("minilm-dense", embedder=MINILM, retrieval="dense"),
    # chunking v2: sentences and headings, boilerplate stripped, paragraphs may cross pages
    "keyword-v2": Config("keyword-v2", embedder="hashing-512", chunker="v2", retrieval="keyword"),
    "hashing-dense-v2": Config("hashing-dense-v2", embedder="hashing-512", chunker="v2", retrieval="dense"),
    "minilm-dense-v2": Config("minilm-dense-v2", embedder=MINILM, chunker="v2", retrieval="dense"),
    "minilm-dense-v2-perpage": Config("minilm-dense-v2-perpage", embedder=MINILM, chunker="v2-perpage", retrieval="dense"),
    # chunk-size sweep for v2 (target characters per chunk)
    "keyword-v2-600": Config("keyword-v2-600", embedder="hashing-512", chunker="v2-600", retrieval="keyword"),
    "minilm-dense-v2-600": Config("minilm-dense-v2-600", embedder=MINILM, chunker="v2-600", retrieval="dense"),
    "keyword-v2-400": Config("keyword-v2-400", embedder="hashing-512", chunker="v2-400", retrieval="keyword"),
    "minilm-dense-v2-400": Config("minilm-dense-v2-400", embedder=MINILM, chunker="v2-400", retrieval="dense"),
}


def load_questions(path: Path) -> List[Dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ----------------------------------------------------------------------------- chunkers
Pages = List[Tuple[Optional[int], str]]


def chunk_v1(doc: str, pages: Pages) -> List[Dict[str, Any]]:
    """The original chunker: fixed 800-character windows (160 overlap), page by page."""
    from backend.document_processor import chunk_text

    return [
        {"text": c, "doc": doc, "page": page, "source_type": "text", "url": None, "extra": {}}
        for page, text in pages
        for c in chunk_text(text)
    ]


def make_chunk_v2(max_chars: int) -> Callable[[str, Pages], List[Dict[str, Any]]]:
    """Structure-aware chunking (backend/chunking.py): sentences, headings, boilerplate stripped."""

    def chunk(doc: str, pages: Pages) -> List[Dict[str, Any]]:
        from backend.chunking import chunk_document, chunk_pages

        if len(pages) == 1 and pages[0][0] is None:  # a Markdown/web document
            items = [{"text": t, "page": None, "end_page": None} for t in chunk_document(pages[0][1], max_chars=max_chars)]
        else:  # a paged document (PDF)
            items = chunk_pages(pages, max_chars=max_chars)
        return [
            {"text": it["text"], "doc": doc, "page": it["page"], "source_type": "text", "url": None,
             "extra": {"end_page": it["end_page"]} if it.get("end_page") else {}}
            for it in items
        ]

    return chunk


def chunk_v2_per_page(doc: str, pages: Pages) -> List[Dict[str, Any]]:
    """Ablation: v2's sentence packing, but page by page (nothing crosses a page break)."""
    from backend.chunking import chunk_document

    out: List[Dict[str, Any]] = []
    for page, text in pages:
        for t in chunk_document(text, max_chars=900):
            out.append({"text": t, "doc": doc, "page": page, "source_type": "text", "url": None, "extra": {}})
    return out


CHUNKERS: Dict[str, Callable[[str, Pages], List[Dict[str, Any]]]] = {
    "v2-perpage": chunk_v2_per_page,
    "v1": chunk_v1,
    "v2": make_chunk_v2(900),
    "v2-600": make_chunk_v2(600),
    "v2-400": make_chunk_v2(400),
}


# ----------------------------------------------------------------------------- corpora
@dataclass(frozen=True)
class Corpus:
    name: str
    questions: Path

    def documents(self) -> List[Tuple[str, List[Tuple[Optional[int], str]]]]:
        """[(doc name, [(page or None, text), ...]), ...]"""
        raise NotImplementedError

    def available(self) -> Optional[str]:
        """None if usable, else why not."""
        return None

    loose = False  # relevance by page (paged documents) instead of by phrase inside the chunk

    def resolve(self, questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Hook to enrich the questions' evidence (the real corpus adds the pages where each phrase occurs)."""
        return questions


class SyntheticCorpus(Corpus):
    def documents(self):
        return [(p.name, [(None, p.read_text(encoding="utf-8"))]) for p in sorted((ROOT / "corpus").glob("*.md"))]


REAL_DOCS = ["Data Structures Using Python.pdf", "Dsa.pdf", "Introduction to Computer Science.pdf"]
_pdf_cache: Dict[str, List[Tuple[Optional[int], str]]] = {}


class RealCorpus(Corpus):
    """The three textbooks the project was developed with (not redistributed; place them in data/uploaded_files)."""

    dir = ROOT.parent / "data" / "uploaded_files"
    loose = True

    def resolve(self, questions):
        """Attach to every piece of evidence the pages where its key phrases appear (a phrase that
        straddles a page break counts for both pages)."""
        pages_by_doc = {doc: pages for doc, pages in self.documents()}
        for q in questions:
            for e in q["expect"]:
                pages = pages_by_doc[e["doc"]]
                texts = [norm(t) for _, t in pages]
                found = set()
                for i, (pg, _) in enumerate(pages):
                    straddle = texts[i] + " " + texts[i + 1] if i + 1 < len(texts) else texts[i]
                    for phrase in e["any"]:
                        ph = norm(phrase)
                        if ph in texts[i]:
                            found.add(pg)
                        elif ph in straddle:
                            found.add(pg)
                            found.add(pages[i + 1][0])
                e["pages"] = sorted(found)
        return questions

    def available(self) -> Optional[str]:
        missing = [d for d in REAL_DOCS if not (self.dir / d).exists()]
        return f"missing PDFs in data/uploaded_files: {', '.join(missing)}" if missing else None

    def documents(self):
        from backend.document_processor import read_pdf

        out = []
        for d in REAL_DOCS:
            if d not in _pdf_cache:
                _pdf_cache[d] = [(pg, txt) for pg, txt in read_pdf(str(self.dir / d))]
            out.append((d, _pdf_cache[d]))
        return out


CORPORA: Dict[str, Corpus] = {
    "synthetic": SyntheticCorpus("synthetic", ROOT / "synthetic_questions.jsonl"),
    "real": RealCorpus("real", ROOT / "real_questions.jsonl"),
}


# ----------------------------------------------------------------------------- indexing
def make_embedder(name: str):
    if name.startswith("hashing-"):
        return HashingEmbedder(dim=int(name.split("-", 1)[1]))
    return get_embedder_by_name(name)


def build_engine(corpus: Corpus, config: Config, store_dir: Path) -> RAGEngine:
    """Chunk and embed every document of `corpus` with `config` and wrap it in an engine."""
    chunker = CHUNKERS[config.chunker]
    embedder = make_embedder(config.embedder)
    store = VectorStore(store_dir)
    store.set_embedder(embedder.name, embedder.dim)
    for doc, pages in corpus.documents():
        chunks = chunker(doc, pages)
        for c in chunks:
            c["chunk_hash"] = chunk_hash(c)
        store.add(chunks, embedder.encode([c["text"] for c in chunks]), doc)
    store.save()
    return make_engine(store_dir, config, embedder)


def make_engine(store_dir: Path, config: Config, embedder) -> RAGEngine:
    engine = RAGEngine(store_dir=str(store_dir), embedder=embedder, input_dir=str(store_dir / "none"))
    if config.retrieval == "keyword":
        engine.use_embeddings = False
    elif config.retrieval != "dense":
        engine.retrieval_mode = config.retrieval  # filled in by later steps
    if config.rerank:
        engine.rerank = True
    return engine


# ----------------------------------------------------------------------------- running
def run_questions(engine: RAGEngine, questions: List[Dict[str, Any]], k: int = TOP_N, loose: bool = False) -> List[QuestionResult]:
    out: List[QuestionResult] = []
    for q in questions:
        chunks = engine.retrieve_context(q["question"], k=k)
        top = chunks[0]["score"] if chunks else 0.0
        out.append(
            QuestionResult(
                id=q["id"],
                category=q["category"],
                question=q["question"],
                answerable=q["answerable"],
                rank=first_relevant_rank(chunks, q["expect"], loose) if q["answerable"] else None,
                rank_strict=first_relevant_rank(chunks, q["expect"], False) if q["answerable"] else None,
                top_score=float(top),
                coverage_at_5=evidence_coverage(chunks[:5], q["expect"], loose) if q["answerable"] else 0.0,
                retrieved=[{"doc": c["doc"], "page": c.get("page"), "score": round(float(c["score"]), 3)} for c in chunks[:5]],
            )
        )
    return out


def evaluate(corpus: Corpus, config: Config) -> Dict[str, Any]:
    questions = corpus.resolve(load_questions(corpus.questions))
    with tempfile.TemporaryDirectory(prefix="asm-eval-") as tmp:
        t0 = time.time()
        engine = build_engine(corpus, config, Path(tmp) / "store")
        build_s = time.time() - t0
        t1 = time.time()
        results = run_questions(engine, questions, loose=corpus.loose)
        query_ms = (time.time() - t1) * 1000 / max(len(questions), 1)
        n_chunks = len(engine.store)
    return {"config": config, "summary": summarize(results), "results": results, "chunks": n_chunks,
            "build_s": build_s, "query_ms": query_ms, "loose": corpus.loose}
