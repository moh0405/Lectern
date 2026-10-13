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
| 5 | study tools: flashcards (SM-2), LeetCode progress and plan, server-side history, LLM providers | #16 | [phase-5-study-tools.md](phase-5-study-tools.md) |
| 6 | deploy and operate: the API on AWS Lambda, S3, ECR, Terraform (hosted web app, CI deploy and hardening still open) | #17 (partial) | [../AWS.md](../AWS.md), issue #8 |
| 7 | docs and v1.0 release | open | issue #9 |

Every write-up has the same shape: **goal, what was built, how it works, technologies, decisions and trade-offs, bugs found, result.** Technologies are explained in depth in [../concepts/](../concepts/).

The order matters, and it is a good general pattern: **make it reliable (0), make it correct (1), expose it cleanly (2), make it usable (3), then measure and improve it (4).** Measuring only came after there was something stable to measure.
