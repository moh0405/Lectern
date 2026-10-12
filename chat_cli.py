"""Interactive retrieval CLI: prints the retrieved context and the final prompt.

    python chat_cli.py            # semantic retrieval when a vector store exists
    python chat_cli.py --keyword  # keyword retrieval only (no ML libraries needed)
"""
import argparse

from backend.rag_engine import RAGEngine


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keyword", action="store_true", help="skip embeddings, use keyword overlap")
    ap.add_argument("-k", type=int, default=3, help="number of chunks to retrieve")
    args = ap.parse_args()

    engine = RAGEngine(use_embeddings=not args.keyword)
    mode = "semantic" if engine.warm() else "keyword"
    print(f"Ready ({mode} retrieval, {len(engine._docstore_iter())} chunks). Type questions, 'quit' to exit.")
    while True:
        try:
            q = input("You: ").strip()
        except EOFError:
            break
        if not q or q.lower() in {"quit", "exit"}:
            break
        chunks = engine.retrieve_context(q, k=args.k)
        prompt = engine.generate_prompt(q, chunks)
        print("\nContext:")
        for c in chunks:
            print(f"- {c['doc']} (page {c['page']}) score={c['score']:.4f}\n  {c['text'][:300]}\n")
        print("Prompt preview:\n")
        print(prompt[:1200])
        print("\n")


if __name__ == "__main__":
    main()
