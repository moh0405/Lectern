from pathlib import Path
import re
from typing import List, Dict, Any

from backend.rag_engine import RAGEngine


def tokenize(text: str) -> List[str]:
    return re.findall(r"\b\w+\b", text.lower())


def keyword_retrieve(engine: RAGEngine, query: str, k: int = 3) -> List[Dict[str, Any]]:
    items = engine._docstore_iter()
    q_tokens = set(tokenize(query))
    scored = []
    for it in items:
        t_tokens = set(tokenize(it.get("text", "")))
        inter = len(q_tokens & t_tokens)
        union = len(q_tokens | t_tokens) or 1
        score = inter / union
        scored.append((score, it))
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for s, it in scored[:k]:
        out.append({"text": it.get("text", ""), "doc": it.get("doc", ""), "page": it.get("page", None), "score": float(s)})
    return out


def main():
    print("Initializing RAG engine (embedding may be skipped if environment issues)...")
    engine = RAGEngine()
    print("Ready. Type questions, 'quit' to exit.")
    while True:
        try:
            q = input("You: ").strip()
        except EOFError:
            break
        if not q or q.lower() in {"quit", "exit"}:
            break
        try:
            chunks = engine.retrieve_context(q, k=3)
        except Exception:
            chunks = keyword_retrieve(engine, q, k=3)
        prompt = engine.generate_prompt(q, chunks)
        print("\nContext:")
        for c in chunks:
            print(f"- {c['doc']} (page {c['page']}) score={c['score']:.4f}\n  {c['text'][:300]}\n")
        print("Prompt preview:\n")
        print(prompt[:1200])
        print("\n")


if __name__ == "__main__":
    main()