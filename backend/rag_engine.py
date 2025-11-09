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
        index = faiss.read_index(str(out_path / "index.faiss"))
        import pickle

        with open(out_path / "index.pkl", "rb") as f:
            obj = pickle.load(f)
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

    def generate_prompt(self, question: str, chunks: List[Dict[str, Any]]) -> str:
        template = self._create_prompt_template()
        context = self.format_context(chunks)
        return template.format(context=context, question=question)

    def answer_question(self, question: str, k: int = 3) -> Dict[str, Any]:
        chunks = self.retrieve_context(question, k=k)
        prompt = self.generate_prompt(question, chunks)
        return {"prompt": prompt, "chunks": chunks}


if __name__ == "__main__":
    engine = RAGEngine(auto_embeddings=False)
    q = "What is a linked list?"
    out = engine.answer_question(q, k=3)
    print("Prompt preview:\n")
    print(out["prompt"][:1000])
    print("\nTop chunks:")
    for c in out["chunks"]:
        print(f"score={c['score']:.4f} doc={c['doc']} page={c['page']} text={c['text'][:120]}...")