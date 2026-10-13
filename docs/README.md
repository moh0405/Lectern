# Documentation

Start with the [project README](../README.md) for the overview, then read in this order if you want to understand everything.

## Reading order

1. **[Architecture](ARCHITECTURE.md)**: components, the two data flows (indexing, answering), where data lives, concurrency, design decisions, failure behaviour.
2. **Concepts** (teach each technology from first principles, with real numbers from this repo):
   1. [RAG](concepts/01-rag.md): the central idea
   2. [Embeddings](concepts/02-embeddings.md): text as vectors, cosine similarity
   3. [Vector databases](concepts/03-vector-databases.md): storing and searching vectors, exact vs approximate
   4. [Search and ranking](concepts/04-search-and-ranking.md): BM25, hybrid search, fusion, reranking
   5. [Chunking](concepts/05-chunking.md): cutting documents into passages
   6. [LLMs, prompting, streaming, citations](concepts/06-llms-and-prompting.md)
   7. [Backend stack](concepts/07-backend-stack.md): Python, FastAPI, Pydantic, OpenAPI, jobs, SQLite, security
   8. [Evaluation](concepts/08-evaluation.md): hit@k, MRR, confidence intervals, honesty
   9. [Frontend stack](concepts/09-frontend-stack.md): TypeScript, React, Next.js, TanStack Query, visualisation
   10. [Testing and CI](concepts/10-testing-and-ci.md)
   11. [Glossary](concepts/11-glossary.md)
3. **[Phase by phase](phases/README.md)**: how the project was built, in order, with the bugs and decisions of each phase.
4. **[API reference](API.md)**: all 26 operations with examples.

## Reference

- [REFERENCE.md](REFERENCE.md): configuration, environment variables, CLI tools, data directory, internals notes, troubleshooting (the former long README)
- [PLAN.md](PLAN.md): the completion plan, decisions, model strategy and per-phase results
- [LEARNING_GUIDE.md](LEARNING_GUIDE.md), [demo_guide.md](demo_guide.md): earlier guides
- [../eval/README.md](../eval/README.md): the retrieval evaluation, its results and its caveats

Numbers quoted across these docs come from `eval/reports/` and from running the code; if a number matters to you, regenerate it with `python -m eval.run`.
