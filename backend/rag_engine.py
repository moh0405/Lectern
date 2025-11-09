from pathlib import Path
from typing import List, Dict, Any, Tuple

import numpy as np

try:
    import faiss
except Exception:
    faiss = None

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None


class RAGEngine:
    def __init__(self, store_dir: str = "data/vector_store", model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        if faiss is None:
            raise RuntimeError("faiss is not installed. Install requirements first.")
        if SentenceTransformer is None:
            raise RuntimeError("sentence-transformers is not installed. Install requirements first.")
        self.store_dir = str(Path(store_dir).resolve())
        self.index, self.meta = self._load_vector_store()
        self.embedder = SentenceTransformer(model_name, device="cpu")

    def _load_vector_store(self) -> Tuple[Any, List[Dict[str, Any]]]:
        out_path = Path(self.store_dir)
        index = faiss.read_index(str(out_path / "index.faiss"))
        import pickle

        with open(out_path / "index.pkl", "rb") as f:
            meta = pickle.load(f)["metadata"]
        return index, meta

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
        emb = self.embedder.encode([query], normalize_embeddings=True, batch_size=1, show_progress_bar=False)
        return np.asarray(emb, dtype=np.float32)

    def retrieve_context(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        q = self._embed_query(query)
        scores, ids = self.index.search(q, k)
        results = []
        for score, idx in zip(scores[0], ids[0]):
            if idx < 0:
                continue
            m = self.meta[idx]
            results.append({"text": m["text"], "doc": m["doc"], "page": m["page"], "score": float(score)})
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
    engine = RAGEngine()
    q = "What is a linked list?"
    out = engine.answer_question(q, k=3)
    print("Prompt preview:\n")
    print(out["prompt"][:1000])
    print("\nTop chunks:")
    for c in out["chunks"]:
        print(f"score={c['score']:.4f} doc={c['doc']} page={c['page']} text={c['text'][:120]}...")