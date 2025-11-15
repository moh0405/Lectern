from pathlib import Path
from typing import List, Dict, Any, Tuple

import numpy as np

try:
    import faiss
except Exception:
    faiss = None


class RAGEngine:
    def __init__(self, store_dir: str = "data/vector_store", model_name: str = "sentence-transformers/all-MiniLM-L6-v2", auto_embeddings: bool = False):
        self.store_dir = str(Path(store_dir).resolve())
        self.model_name = model_name
        self.index, self.meta = self._load_vector_store()
        self.embedder = None
        self.embeddings = None
        if auto_embeddings:
            try:
                self.embeddings = self._ensure_embeddings()
            except Exception:
                # Defer embedding generation; fallback retrieval will be used
                self.embeddings = None

    def _load_vector_store(self) -> Tuple[Any, Any]:
        out_path = Path(self.store_dir)
        index_path = out_path / "index.faiss"
        meta_path = out_path / "index.pkl"
        import pickle
        index = None
        obj = None
        # Load metadata if present
        if meta_path.exists():
            try:
                with open(meta_path, "rb") as f:
                    obj = pickle.load(f)
            except Exception:
                obj = None
        # Try to load FAISS index only if metadata loaded and faiss + file are present
        if obj is not None and faiss is not None and index_path.exists():
            try:
                index = faiss.read_index(str(index_path))
            except Exception:
                index = None
        # If neither exists, build a lightweight meta-only store from inputs directory
        if obj is None:
            try:
                from .document_processor import list_chunks_from_dir
                chunks = list_chunks_from_dir(str(Path("data/uploaded_files").resolve()))
                obj = {"metadata": chunks}
            except Exception:
                obj = {"metadata": []}
        return index, obj

    def _docstore_iter(self) -> List[Dict[str, Any]]:
        if isinstance(self.meta, tuple) and len(self.meta) == 2:
            docstore, index_to_id = self.meta
            inner = getattr(docstore, "_dict", {})
            items = []
            for idx in sorted(index_to_id.keys()):
                doc_id = index_to_id[idx]
                doc = inner.get(doc_id)
                if not doc:
                    continue
                text = getattr(doc, "page_content", "")
                meta = getattr(doc, "metadata", {})
                items.append({"text": text, "doc": Path(meta.get("source", "")).name, "page": meta.get("page", None)})
            return items
        elif isinstance(self.meta, dict):
            return self.meta.get("metadata", [])
        else:
            return []

    def _load_embedder(self):
        if self.embedder is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer  # lazy import to avoid segfaults
        except Exception as e:
            raise RuntimeError(f"sentence-transformers unavailable: {e}")
        self.embedder = SentenceTransformer(self.model_name, device="cpu")

    def _ensure_embeddings(self) -> np.ndarray:
        emb_path = Path(self.store_dir) / "embeddings.npy"
        if emb_path.exists():
            return np.load(str(emb_path))
        items = self._docstore_iter()
        texts = [it.get("text", "") for it in items]
        vecs = []
        for t in texts:
            if self.embedder is None:
                self._load_embedder()
            v = self.embedder.encode([t], normalize_embeddings=True, batch_size=1, show_progress_bar=False)
            vecs.append(np.asarray(v[0], dtype=np.float32))
        if not vecs:
            raise RuntimeError("No texts available to embed from vector store.")
        arr = np.stack(vecs, axis=0)
        np.save(str(emb_path), arr)
        return arr

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

    def _embed_query(self, query: str) -> np.ndarray:
        if self.embedder is None:
            self._load_embedder()
        emb = self.embedder.encode([query], normalize_embeddings=True, batch_size=1, show_progress_bar=False)
        return np.asarray(emb, dtype=np.float32)

    def retrieve_context(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        items = self._docstore_iter()
        if self.embeddings is None:
            # Fallback: keyword overlap scoring
            import re
            def toks(s: str):
                return set(re.findall(r"\b\w+\b", s.lower()))
            q_tokens = toks(query)
            scored = []
            for i, it in enumerate(items):
                t_tokens = toks(it.get("text", ""))
                inter = len(q_tokens & t_tokens)
                union = len(q_tokens | t_tokens) or 1
                s = inter / union
                scored.append((s, i))
            scored.sort(key=lambda x: x[0], reverse=True)
            top = [i for _, i in scored[:k]]
            results = []
            for idx in top:
                it = items[idx]
                results.append({"text": it.get("text", ""), "doc": it.get("doc", ""), "page": it.get("page", None), "score": float(0 if not scored else scored[0][0])})
            return results
        # Embedding path
        q = self._embed_query(query)[0]
        mat = self.embeddings
        sims = mat @ q  # cosine if normalized
        top_idx = np.argsort(-sims)[:k]
        results = []
        for idx in top_idx:
            it = items[idx]
            results.append({"text": it.get("text", ""), "doc": it.get("doc", ""), "page": it.get("page", None), "score": float(sims[idx])})
        return results

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

    def answer_with_ollama(self, question: str, k: int = 3, model: str = "llama3", temperature: float = 0.2, mode: str | None = None) -> Dict[str, Any]:
        chunks = self.retrieve_context(question, k=k)
        prompt = self.generate_prompt(question, chunks, mode=mode)
        from .llm_ollama import OllamaClient
        client = OllamaClient(model=model, temperature=temperature)
        result = client.generate(prompt)
        return {"prompt": prompt, "chunks": chunks, **result}

    def answer_with_gemini(self, question: str, k: int = 3, model: str | None = None, temperature: float = 0.2, mode: str | None = None) -> Dict[str, Any]:
        """Answer using Google Gemini API (cloud inference only).

        - Keeps retrieval and prompt formatting identical to Ollama path
        - Reads API key from environment; fails gracefully with clear error
        """
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
            return qs[:max_questions] or [
                "Explain dynamic programming",
                "Difference between BFS and DFS",
                "How do hash tables handle collisions?",
                "What is a balanced binary search tree?",
                "Describe Dijkstra vs Bellman-Ford",
            ]
        except Exception:
            return [
                "Explain dynamic programming",
                "Difference between BFS and DFS",
                "How do hash tables handle collisions?",
                "What is a balanced binary search tree?",
                "Describe Dijkstra vs Bellman-Ford",
            ]

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
        except Exception as e:
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