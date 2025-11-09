from pathlib import Path
import pickle
import re
from typing import List, Dict, Any


def tokenize(text: str) -> List[str]:
    return re.findall(r"\b\w+\b", text.lower())


def load_doc_items(store_dir: str = "data/vector_store") -> List[Dict[str, Any]]:
    pkl = Path(store_dir) / "index.pkl"
    with open(pkl, "rb") as f:
        docstore, index_to_id = pickle.load(f)
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


def keyword_retrieve(items: List[Dict[str, Any]], query: str, k: int = 3) -> List[Dict[str, Any]]:
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


def build_prompt(question: str, chunks: List[Dict[str, Any]]) -> str:
    lines = []
    for c in chunks:
        src = f"{c['doc']} (page {c['page']})"
        lines.append(f"- [{src}] {c['text']}")
    context = "\n".join(lines)
    template = (
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
    return template.format(context=context, question=question)


def main():
    print("Loading doc items from vector store...")
    items = load_doc_items()
    print(f"Loaded {len(items)} chunks. Ready. Type questions, 'quit' to exit.")
    while True:
        try:
            q = input("You: ").strip()
        except EOFError:
            break
        if not q or q.lower() in {"quit", "exit"}:
            break
        chunks = keyword_retrieve(items, q, k=3)
        prompt = build_prompt(q, chunks)
        print("\nContext:")
        for c in chunks:
            print(f"- {c['doc']} (page {c['page']}) score={c['score']:.4f}\n  {c['text'][:300]}\n")
        print("Prompt preview:\n")
        print(prompt[:1200])
        print("\n")


if __name__ == "__main__":
    main()