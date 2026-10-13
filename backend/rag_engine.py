import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from .embeddings import DEFAULT_MODEL, Embedder, get_embedder_by_name
from .lexical import BM25Index, reciprocal_rank_fusion
from .rerank import Reranker, get_reranker
from .vector_store import VectorStore

logger = logging.getLogger("ai-study-mentor.rag")

_STOPWORDS = frozenset(
    "a an the is are was were be been being of in on at to for from by with and or not as it its this that "
    "these those what which who whom how why when where do does did can could should would will you your i we "
    "they he she them his her our us about into than then so if".split()
)


def _tokens(text: str) -> set:
    return {t for t in re.findall(r"\b\w+\b", text.lower()) if t not in _STOPWORDS}


_FALLBACK_QUESTIONS = [
    "Explain dynamic programming",
    "Difference between BFS and DFS",
    "How do hash tables handle collisions?",
    "What is a balanced binary search tree?",
    "Describe Dijkstra vs Bellman-Ford",
]

_shared: Dict[str, "RAGEngine"] = {}
_shared_lock = threading.Lock()


class RAGEngine:
    """Retrieval + prompt building + Gemini answers on top of a `VectorStore`.

    Retrieval is semantic when the store has embeddings and the embedder that
    produced them can be loaded; otherwise it falls back to keyword coverage
    over the stored chunks (or over local PDFs when no store has been built).
    """

    def __init__(
        self,
        store_dir: str = "data/vector_store",
        model_name: str = DEFAULT_MODEL,
        auto_embeddings: bool = False,
        use_embeddings: bool = True,
        embedder: Optional[Embedder] = None,
        input_dir: str = "data/uploaded_files",
        retrieval_mode: Optional[str] = None,
    ):
        self.store_dir = str(Path(store_dir).resolve())
        self.input_dir = str(Path(input_dir).resolve())
        self.model_name = model_name
        self.use_embeddings = use_embeddings
        self._embedder = embedder
        self._embedder_failed = False
        self._fallback_items: Optional[List[Dict[str, Any]]] = None
        # "auto" (default): hybrid search when the index has semantic embeddings, BM25 otherwise.
        # Or force "dense" (vector search), "bm25" (keyword ranking), "hybrid" (both, fused), or "keyword"
        # (the original term-coverage scorer, kept only as an evaluation baseline).
        # Override with the RETRIEVAL_MODE environment variable.
        self.retrieval_mode = retrieval_mode or os.getenv("RETRIEVAL_MODE", "auto")
        self._lexical_cache: Optional[tuple] = None
        self._reranker: Optional[Reranker] = get_reranker(os.getenv("RERANKER"))
        self.store = VectorStore.load(self.store_dir)
        if auto_embeddings:
            self.warm()

    # ------------------------------------------------------------------
    # Shared instance (one per store directory, e.g. for the API process)
    # ------------------------------------------------------------------
    @classmethod
    def shared(cls, store_dir: str = "data/vector_store", **kwargs: Any) -> "RAGEngine":
        key = str(Path(store_dir).resolve())
        with _shared_lock:
            eng = _shared.get(key)
            if eng is None:
                eng = _shared[key] = cls(store_dir=store_dir, **kwargs)
            return eng

    @classmethod
    def clear_shared(cls) -> None:
        with _shared_lock:
            _shared.clear()

    def reload(self) -> None:
        """Re-read the store from disk (e.g. after the indexer script ran)."""
        self.store = VectorStore.load(self.store_dir)
        self._fallback_items = None
        self._embedder_failed = False

    # ------------------------------------------------------------------
    # Embedder / semantic readiness
    # ------------------------------------------------------------------
    def _get_embedder(self) -> Optional[Embedder]:
        """Embedder matching the store, or None if semantic search is unavailable."""
        if not self.use_embeddings or not len(self.store) or self._embedder_failed:
            return None
        if self._embedder is not None:
            if self._embedder.name != self.store.embedder_name:
                logger.warning(
                    "Store was built with '%s' but embedder is '%s'; using keyword retrieval",
                    self.store.embedder_name,
                    self._embedder.name,
                )
                self._embedder_failed = True
                return None
            return self._embedder
        try:
            self._embedder = get_embedder_by_name(self.store.embedder_name or self.model_name)
        except Exception as e:
            logger.warning("Semantic search unavailable (%s); using keyword retrieval", e)
            self._embedder_failed = True
            return None
        return self._embedder

    def warm(self) -> bool:
        """Load the embedder now so the first query is fast. Returns True if semantic search is ready."""
        return self._get_embedder() is not None

    @property
    def semantic_ready(self) -> bool:
        return self.use_embeddings and self._embedder is not None and not self._embedder_failed and bool(len(self.store))

    # ------------------------------------------------------------------
    # Corpus access
    # ------------------------------------------------------------------
    def _docstore_iter(self) -> List[Dict[str, Any]]:
        """All chunks as dicts with at least text/doc/page.

        Uses the vector store; if none has been built yet, falls back to
        scanning local PDFs/audio once (the result is cached on the engine).
        """
        if len(self.store):
            return self.store.chunks
        if self._fallback_items is None:
            try:
                from .document_processor import list_chunks_from_dir_local

                self._fallback_items = list_chunks_from_dir_local(self.input_dir)
            except Exception:
                self._fallback_items = []
        return self._fallback_items

    # ------------------------------------------------------------------
    # Indexing (used by the API)
    # ------------------------------------------------------------------
    def add_sources(self, inputs: List[str], refresh_urls: bool = False, save: bool = True, progress=None):
        """Index files/URLs into the live store and persist it. Returns an IndexReport."""
        from .indexer import index_inputs

        report = index_inputs(
            self.store, inputs, embedder=self._embedder, refresh_urls=refresh_urls, progress=progress
        )
        self._fallback_items = None
        self._embedder_failed = False
        if len(self.store):
            self._get_embedder()  # indexing just loaded it; bind it so semantic search is ready
        if save:
            self.store.save()
        return report

    def remove_source(self, source_key: str, save: bool = True) -> int:
        removed = self.store.remove_source(source_key)
        if save:
            self.store.save()
        return removed

    def _create_prompt_template(self) -> str:
        """Default prompt when no mode is specified."""
        return (
            "You are a helpful Computer Science tutor. Answer the question based ONLY on the context provided below.\n\n"
            "Context:\n{context}\n\n"
            "Question: {question}\n\n"
            "Instructions:\n"
            "1. Answer clearly and concisely\n"
            "2. Use ONLY information from the context\n"
            "3. If insufficient info, say so\n"
            "4. Cite sources when possible\n\n"
            "Answer:"
        )

    def _prompt_for_mode(self, mode: str | None = None) -> str:
        """Return a prompt template based on study mode.

        Modes:
        - eli5: simple explanation, analogies
        - technical: detailed, include complexity and code snippets
        - interview: structured answer with bullet points and edge cases
        - summary: short bullet list summary
        """
        m = (mode or "").strip().lower()
        if m in {"eli5", "eli 5", "explain like i'm 5"}:
            return (
                "Explain like I'm 5 (ELI5). Use simple language and analogies.\n\n"
                "Context:\n{context}\n\nQuestion: {question}\n\n"
                "Instructions:\n- Use short sentences\n- Avoid jargon\n- Include a friendly analogy\n- End with a one-sentence recap\n\nAnswer:"
            )
        if m in {"technical", "detailed"}:
            return (
                "Technical mode: provide a rigorous explanation using ONLY the context.\n\n"
                "Context:\n{context}\n\nQuestion: {question}\n\n"
                "Instructions:\n- Define terms precisely\n- Include time/space complexity where relevant\n- Provide a short pseudocode or code example if present in context\n- Mention trade-offs and edge cases\n- Cite sources\n\nAnswer:"
            )
        if m in {"interview", "interview prep"}:
            return (
                "Interview Prep mode: produce a concise, structured answer.\n\n"
                "Context:\n{context}\n\nQuestion: {question}\n\n"
                "Instructions:\n- Start with a 2-sentence overview\n- Bullet points: approach, complexity, edge cases\n- Common pitfalls\n- Short example if in context\n- Cite sources\n\nAnswer:"
            )
        if m in {"summary", "quick summary"}:
            return (
                "Quick Summary mode: produce bullet points only from context.\n\n"
                "Context:\n{context}\n\nQuestion: {question}\n\n"
                "Instructions:\n- 5–8 bullets\n- Each bullet one sentence\n- No speculation beyond context\n- Cite sources if possible\n\nAnswer:"
            )
        return self._create_prompt_template()

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------
    def _lexical_index(self) -> tuple:
        """(BM25 index, items) over the current corpus, rebuilt only when the corpus changes."""
        items = self._docstore_iter()
        key = (id(self.store), self.store.revision, id(items), len(items))
        if self._lexical_cache is None or self._lexical_cache[0] != key:
            self._lexical_cache = (key, BM25Index(i.get("text", "") for i in items), items)
        return self._lexical_cache[1], self._lexical_cache[2]

    def _bm25_retrieve(self, query: str, k: int) -> List[Dict[str, Any]]:
        index, items = self._lexical_index()
        return [self._result(items[i], score) for i, score in index.search(query, k)]

    def retrieve_context(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """Top-k chunks for a query, best first. `score` is each chunk's own relevance in 0..1: cosine
        similarity when embeddings are in use, normalized BM25 otherwise."""
        mode = self.retrieval_mode
        if mode == "keyword":
            return self._keyword_retrieve(query, k)
        embedder = None if mode == "bm25" else self._get_embedder()
        if mode == "auto":
            # Fusing in a non-semantic (hashing) ranker is worse than BM25 alone (see eval/reports), so
            # hybrid search is only used when the index really has semantic embeddings.
            mode = "hybrid" if embedder is not None and not embedder.name.startswith("hashing") else "bm25"
        if mode in {"dense", "hybrid"} and embedder is None:
            mode = "bm25"  # no semantic search available
        if mode == "bm25":
            return self._bm25_retrieve(query, k)
        qv = embedder.encode([query])[0]
        pool = max(50, k * 10)
        if mode == "hybrid":
            dense = [i for i, _ in self.store.search(qv, pool)]
            index, _items = self._lexical_index()
            lexical = [i for i, _ in index.search(query, pool)]
            order = [i for i, _ in reciprocal_rank_fusion([dense, lexical])]
        else:
            order = [i for i, _ in self.store.search(qv, pool if self._reranker else k)]
        if self._reranker is not None and order:
            candidates = order[: max(20, k * 4)]
            try:
                ranked = self._reranker.order(query, [self.store.chunks[i].get("text", "") for i in candidates])
                order = [candidates[j] for j in ranked]
            except Exception as e:  # reranking is an enhancement: never fail a search because of it
                logger.warning("Reranker unavailable (%s); keeping the first-stage order", e)
                self._reranker = None
        # each chunk shows its cosine similarity: one semantic scale, whichever stage ranked it
        return [self._result(self.store.chunks[i], float(self.store.embeddings[i] @ qv)) for i in order[:k]]

    @staticmethod
    def _result(item: Dict[str, Any], score: float) -> Dict[str, Any]:
        return {
            "text": item.get("text", ""),
            "doc": item.get("doc", ""),
            "page": item.get("page", None),
            # set when a passage runs onto the next page of a PDF
            "end_page": (item.get("extra") or {}).get("end_page"),
            "score": float(score),
            "url": item.get("url"),
            # Deep link when the source has one (e.g. a YouTube URL with &t=SECONDS)
            "citation_url": (item.get("extra") or {}).get("citation_url") or item.get("url"),
        }

    def _keyword_retrieve(self, query: str, k: int) -> List[Dict[str, Any]]:
        """Fallback: rank by the share of query terms found in the chunk (stopwords ignored)."""
        q = _tokens(query)
        if not q:
            return []
        scored = []
        for item in self._docstore_iter():
            t = _tokens(item.get("text", ""))
            inter = len(q & t)
            if not inter:
                continue
            coverage = inter / len(q)
            jaccard = inter / len(q | t)
            scored.append((coverage, jaccard, item))
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [self._result(item, cov) for cov, _j, item in scored[:k]]

    def format_context(self, chunks: List[Dict[str, Any]]) -> str:
        lines = []
        for c in chunks:
            src = f"{c['doc']} (page {c['page']})"
            lines.append(f"- [{src}] {c['text']}")
        return "\n".join(lines)

    def generate_prompt(self, question: str, chunks: List[Dict[str, Any]], mode: str | None = None) -> str:
        template = self._prompt_for_mode(mode)
        context = self.format_context(chunks)
        return template.format(context=context, question=question)

    def generate_answer(self, question: str, context: str, model: str | None = None, temperature: float = 0.2, mode: str | None = "technical") -> Dict[str, Any]:
        """Synthesize ONE coherent answer from provided context using Gemini.

        - Uses tutor-style prompt with explicit instructions
        - Does not perform retrieval; callers provide `context`
        - Returns {"ok": bool, "answer": str, "model": str?, "error": str?}
        """
        template = self._prompt_for_mode(mode)
        prompt = template.format(context=context, question=question)
        try:
            from .llm_config import GeminiClient
            client = GeminiClient(model=model, temperature=temperature)
            res = client.generate(prompt, temperature=temperature)
            return {"ok": bool(res.get("ok", True)), "answer": res.get("answer", ""), "model": res.get("model"), "prompt": prompt}
        except Exception as e:
            return {"ok": False, "answer": "", "error": str(e), "model": model, "prompt": prompt}

    def answer_question(self, question: str, k: int = 3, mode: str | None = None) -> Dict[str, Any]:
        chunks = self.retrieve_context(question, k=k)
        prompt = self.generate_prompt(question, chunks, mode=mode)
        return {"prompt": prompt, "chunks": chunks}

    def answer_with_gemini(self, question: str, k: int = 3, model: str | None = None, temperature: float = 0.2, mode: str | None = None, chunks: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
        """Answer using Google Gemini API (cloud inference only).

        - Pass `chunks` to reuse an earlier retrieval instead of retrieving again
        - Reads API key from environment; fails gracefully with clear error
        """
        if chunks is None:
            chunks = self.retrieve_context(question, k=k)
        prompt = self.generate_prompt(question, chunks, mode=mode)
        try:
            from .llm_config import GeminiClient
            client = GeminiClient(model=model, temperature=temperature)
        except Exception as e:
            return {"prompt": prompt, "chunks": chunks, "ok": False, "error": str(e), "model": model}
        result = client.generate(prompt, temperature=temperature)
        return {"prompt": prompt, "chunks": chunks, **result}

    # -----------------------------------------------------
    # Extras for hackathon killer features
    # -----------------------------------------------------
    def _collect_context_snippet(self, max_chars: int = 4000) -> str:
        items = self._docstore_iter()
        texts: List[str] = []
        size = 0
        for it in items:
            t = (it.get("text") or "").strip()
            if not t:
                continue
            if size + len(t) > max_chars:
                break
            texts.append(t)
            size += len(t)
        return "\n\n".join(texts)

    def generate_query_suggestions(self, max_questions: int = 5, model: str | None = None, temperature: float = 0.2) -> List[str]:
        """Use Gemini to propose study questions from current corpus.

        Falls back to static examples on error.
        """
        ctx = self._collect_context_snippet(max_chars=2500)
        prompt = (
            "From the following study corpus, propose {n} diverse, high-impact questions "
            "about data structures & algorithms. Cover fundamentals and advanced topics. "
            "Return as a numbered list, one question per line.\n\nCorpus:\n{ctx}"
        ).format(n=max_questions, ctx=ctx or "(empty)")
        try:
            from .llm_config import GeminiClient
            client = GeminiClient(model=model, temperature=temperature)
            res = client.generate(prompt, temperature=temperature)
            text = (res.get("answer") or "").strip()
            qs = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                # strip leading numbering
                line = line.split(". ", 1)[-1] if line[0].isdigit() else line
                qs.append(line)
            return (qs or _FALLBACK_QUESTIONS)[:max_questions]
        except Exception:
            return _FALLBACK_QUESTIONS[:max_questions]

    def summarize_chat(self, history: List[Dict[str, Any]], model: str | None = None, temperature: float = 0.2) -> Dict[str, Any]:
        """
        Produce concise study notes and summary bullets from the chat history.
        Uses Gemini if available; otherwise returns a heuristic Markdown summary.
        """
        # Build compact transcript
        transcript = []
        for item in history[-20:]:  # last 20 turns
            q = (item.get("q") or "").strip()
            a = (item.get("answer") or "").strip()
            if q:
                transcript.append(f"Q: {q}")
            if a:
                transcript.append(f"A: {a}")
        joined = "\n\n".join(transcript) or "No chat history yet."

        prompt = (
            "You are a study note generator. Convert the following Q&A transcript "
            "into helpful study notes in Markdown: include a short summary, 6–10 key bullets, "
            "and a short 'Next questions' section. Use concise phrasing and preserve code blocks if present.\n\n"
            f"Transcript:\n{joined}\n\n"
        )
        try:
            from .llm_config import GeminiClient
            client = GeminiClient(model=model, temperature=temperature)
            res = client.generate(prompt, temperature=temperature)
            text = (res.get("answer") or res.get("text") or "").strip()
            if text:
                return {"ok": True, "markdown": text}
        except Exception:
            # Fall through to heuristic
            pass

        # Fallback: simple heuristic summary
        bullets = []
        for item in history[-10:]:
            q = (item.get("q") or "").strip()
            if q:
                bullets.append(f"- {q}")
        md = [
            "# Study Notes\n",
            "## Summary\n",
            "This session covered multiple topics. Consider reviewing the items below.\n",
            "## Key Questions\n",
            *bullets,
            "\n## Next Questions\n",
            "- Explain time complexity tradeoffs\n",
            "- Contrast BFS vs DFS on weighted graphs\n",
        ]
        return {"ok": True, "markdown": "\n".join(md)}

    def multi_source_synthesis(self, question: str, k_per_doc: int = 2, model: str | None = None, temperature: float = 0.2) -> Dict[str, Any]:
        """Compare answers across sources and highlight agreements/conflicts.

        Retrieves top chunks per document and asks Gemini to synthesize.
        Returns {'ok': bool, 'answer': str, 'citations': List[Dict], 'error': str?}
        """
        items = self._docstore_iter()
        # Group by doc
        by_doc: Dict[str, List[Dict[str, Any]]] = {}
        import re as _re
        q_tokens = set(_re.findall(r"\b\w+\b", question.lower()))
        for it in items:
            doc = it.get("doc") or ""
            if not doc:
                continue
            # simple overlap score
            t_tokens = set(_re.findall(r"\b\w+\b", (it.get("text") or "").lower()))
            inter = len(q_tokens & t_tokens)
            by_doc.setdefault(doc, []).append({"score": inter, **it})
        # pick top k per doc
        chosen: List[Dict[str, Any]] = []
        for doc, arr in by_doc.items():
            arr.sort(key=lambda x: x.get("score", 0), reverse=True)
            chosen.extend(arr[:k_per_doc])
        # build context
        context = self.format_context([{"text": c.get("text",""), "doc": c.get("doc",""), "page": c.get("page")} for c in chosen])
        synth_prompt = (
            "Synthesize an answer to the question by comparing information across sources.\n\n"
            "Context (multi-source):\n{context}\n\nQuestion: {question}\n\n"
            "Instructions:\n- Note where sources agree\n- Highlight conflicting claims\n- Provide citations like [doc (page N)] after statements\n- Be concise\n\nAnswer:"
        ).format(context=context, question=question)
        try:
            from .llm_config import GeminiClient
            client = GeminiClient(model=model, temperature=temperature)
            res = client.generate(synth_prompt, temperature=temperature)
            ans = res.get("answer") or ""
            # naive citations list
            cites = [{"doc": c.get("doc"), "page": c.get("page")} for c in chosen]
            return {"ok": True, "answer": ans, "citations": cites}
        except Exception as e:
            return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    engine = RAGEngine(auto_embeddings=False)
    q = "What is a linked list?"
    out = engine.answer_question(q, k=3)
    print("Prompt preview:\n")
    print(out["prompt"][:1000])
    print("\nTop chunks:")
    for c in out["chunks"]:
        print(f"score={c['score']:.4f} doc={c['doc']} page={c['page']} text={c['text'][:120]}...")