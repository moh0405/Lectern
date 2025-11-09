from backend.rag_engine import RAGEngine


def main():
    print("Initializing RAG engine with keyword fallback...")
    engine = RAGEngine(auto_embeddings=False)
    print("Ask a question, or type 'quit' to exit.")
    while True:
        try:
            q = input("You: ").strip()
        except EOFError:
            break
        if not q or q.lower() in {"quit", "exit"}:
            break
        res = engine.answer_with_ollama(q, k=3)
        if res.get("ok"):
            print("\nAnswer:\n")
            print(res.get("answer", ""))
        else:
            print("\nOllama error:")
            print(res.get("error", "Unknown error"))
        print("\nContext chunks:")
        for c in res.get("chunks", [])[:3]:
            print(f"- {c['doc']} (page {c['page']}) score={c.get('score', 0):.4f}\n  {c['text'][:300]}\n")


if __name__ == "__main__":
    main()