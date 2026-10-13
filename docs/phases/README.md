# Phase by phase: how the project was built

The project began as a hackathon prototype (a Streamlit app calling Gemini over FAISS), and was rebuilt in phases, each on its own branch, each merged by pull request only when CI was green. The plan is `docs/PLAN.md`; each phase has a GitHub issue.

| Phase | Goal | PR | Write-up |
|---|---|---|---|
| (start) | the hackathon prototype | | [phase-0](phase-0-hygiene.md#where-it-started) |
| 0 | repo hygiene: dependencies, lint, tests, CI | #10 | [phase-0-hygiene.md](phase-0-hygiene.md) |
| 1 | retrieval core: own vector store, incremental indexing | #11 | [phase-1-retrieval-core.md](phase-1-retrieval-core.md) |
| 2 | a versioned, typed, secure API with streaming | #12 | [phase-2-api.md](phase-2-api.md) |
| 3 | the TypeScript/Next.js frontend | #13 | [phase-3-frontend.md](phase-3-frontend.md) |
| 4 | answer quality: evaluation, hybrid search, chunking, citation checks | #14 | [phase-4-retrieval-quality.md](phase-4-retrieval-quality.md) |
| 5 | product extras: flashcards, progress tracking, providers | open | issue #7 |
| 6 | deploy and operate | open | issue #8 |
| 7 | docs and v1.0 release | open | issue #9 |

Every write-up has the same shape: **goal, what was built, how it works, technologies, decisions and trade-offs, bugs found, result.** Technologies are explained in depth in [../concepts/](../concepts/).

The order matters, and it is a good general pattern: **make it reliable (0), make it correct (1), expose it cleanly (2), make it usable (3), then measure and improve it (4).** Measuring only came after there was something stable to measure.
