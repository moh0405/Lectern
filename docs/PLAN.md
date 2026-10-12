# AI Study Mentor: Completion Plan

Goal: take AI Study Mentor from a hackathon prototype to a polished, deployable **portfolio project**: a reliable RAG backend, a TypeScript (Next.js) frontend, measurable answer quality, and clear documentation.

Status of this plan: drafted October 2026. Each phase has a matching GitHub issue.

---

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Frontend | **Next.js (App Router) + strict TypeScript**, Tailwind + shadcn/ui, TanStack Query | Covers tabs, forms, streaming and charts; deploys easily on Vercel. |
| Backend | Keep **Python + FastAPI** | All RAG and ML code is Python; rewriting it adds no value. |
| API contract | FastAPI OpenAPI schema → generated TS client (`openapi-typescript`) | Frontend types stay in sync with the backend. |
| LLM | **Gemini Flash, default `gemini-3.8-flash`** (see [Model strategy](#model-strategy)) | Latest GA Flash model. Use a Flash-Lite model for cheap tasks. |
| Customization | **Prompting + retrieval, no fine-tuning** | See [Model strategy](#model-strategy). |
| Scope | Portfolio project: **no accounts or multi-user features** for v1 | Keeps the work focused (see Phase 5, deferred). |
| Streamlit | Frozen, then deleted once the new frontend has parity | Avoid maintaining two UIs. |
| Secrets | Gemini key stays server-side only | The browser never sees it. |

---

## Model strategy

**Question:** is a foundation model enough, or does this project need fine-tuning?

**Recommendation: use a foundation model with retrieval (RAG). Do not fine-tune.**

Reasons:
1. **What the app needs is knowledge, not a new behavior.** The value is answering from *your* sources with citations. Retrieval provides that and keeps answers traceable; fine-tuning bakes knowledge into weights, can't cite a page or timestamp, and goes stale when sources change. General guidance in 2026 write-ups is consistent: fine-tune to change *behavior* (strict format, voice, narrow skill), use RAG to supply *knowledge*, and exhaust prompting and retrieval first.
2. **The behaviors you want are promptable.** The study modes (ELI5, technical, interview, summary), Socratic hints, and JSON outputs for concept maps are all achievable with prompts, few-shot examples and structured output.
3. **The tuning path doesn't fit the model choice.** Google's documented supervised tuning is on Vertex AI and lists the Gemini 2.5 family (Pro, Flash, Flash-Lite). I found no evidence that Gemini 3.x Flash models are tunable or that tuning is available on the plain Gemini Developer API. Fine-tuning would mean being on an older model, on a different platform, for a likely small gain.
4. **Cost and risk.** Tuning needs a curated dataset, training spend, evaluation, and re-tuning when the base model changes. Small datasets risk overfitting.
5. **Retrieval quality is the real bottleneck.** In this codebase the biggest quality risks are chunking, retrieval scoring and citations, not model capability. That is Phase 4.

**When to revisit fine-tuning** (only if the eval set in Phase 4 shows it):
- Answers stay stylistically inconsistent despite prompts and few-shot examples, or
- You want a much cheaper or smaller model to match Flash quality on one narrow task (for example, generating Socratic hint ladders), using Flash outputs as training data.

Even then, try these first: better system prompts, few-shot examples, structured output schemas, reranking, and a Flash-Lite model for simple tasks.

**Model notes (verified against Google's docs, Oct 2026):**
- `gemini-3.8-flash` is the newest Flash model and is GA.
- `gemini-3.5-flash` is deprecated and now routes to `gemini-3.6-flash`; `gemini-3.7-flash` is listed as stable.
- Flash-Lite variants exist for low-cost use.
- Pricing and names change often. Keep the model ID in config (`GEMINI_MODEL`), not in code, and re-check before release.
- The current `google-generativeai` package is old. Migrate to Google's current Gen AI SDK behind the existing `GeminiClient` interface in Phase 2.

---

## Phase 0: Repo hygiene (1–2 days)
- [ ] Complete and pin dependencies; move to `pyproject.toml` with dev extras. Remove or isolate unused `langchain` and Ollama code.
- [ ] Remove tracked `.DS_Store`; stop tracking large data (PDFs, `data/vector_store`, `data/repos`). Move PDFs to Git LFS or a download script.
- [ ] Add `ruff`, `mypy` (lenient to start), `pytest`, and pre-commit.
- [ ] Add GitHub Actions: lint + tests (+ frontend typecheck once it exists).
- [ ] Add `OPENAI_API_KEY` (optional) to `.env.example`.

**Done when:** a fresh clone installs and passes CI with one command.

## Phase 1: Retrieval core (about 1 week)
Builds on the open work in PR #1 (FAISS document-processing pipeline).
- [ ] Make FAISS the real retrieval path; fix the keyword fallback so each result reports its own score.
- [ ] Replace pickle metadata with JSONL or Parquet next to `index.faiss`.
- [ ] Incremental indexing: chunk hashing, embed only new chunks, support delete.
- [ ] One shared engine at API startup (FastAPI lifespan) instead of one per request.
- [ ] Fix the macOS segfault properly (pinned torch, or a lighter embedder such as ONNX or fastembed).
- [ ] Tests: chunking, retrieval ranking, prompt modes, source handlers (mocked network), store round-trip.

**Done when:** retrieval has tests and no request re-parses PDFs.

## Phase 2: API v1 for a TypeScript client (about 1 week)
- [ ] Endpoints for every feature: `/ask` (with `mode`), `/concept-map`, `/socratic`, `/synthesis`, `/adaptive`, `/math`, `/leetcode/search`, `/leetcode/{id}/explain`, `/suggestions`, `/notes`, `/export`, `/analytics`.
- [ ] Real streaming from Gemini over SSE with typed events (`meta`, `token`, `done`, `error`).
- [ ] Ingestion as jobs: `POST /sources` returns a job id; `GET /jobs/{id}` reports progress.
- [ ] Security: sanitize upload filenames, enforce size/type limits, restrict CORS to the frontend origin, replace `sympify` with a restricted parser run with a timeout, consistent error schema.
- [ ] Migrate to the current Google Gen AI SDK behind `GeminiClient`; default model `gemini-3.8-flash`.
- [ ] Publish the OpenAPI schema and generate `packages/api-client`.

**Done when:** every Streamlit capability is reachable from the API and the schema generates a clean TS client.

## Phase 3: TypeScript frontend (about 2–3 weeks)
Layout: `apps/web` (Next.js) and `packages/api-client` (generated); `backend/` stays as is.

Migrate in this order; each step should be shippable:
1. [ ] **Shell**: layout, dark glass theme, sidebar settings, command palette (`cmdk`), typed API client with TanStack Query.
2. [ ] **Ask**: SSE streaming hook, context cards with score and keyword highlights, mode picker, `react-markdown` + KaTeX, citation links (page numbers and YouTube timestamps).
3. [ ] **Sources**: PDF drag and drop, URL list, audio upload, job progress, document list with delete.
4. [ ] **LeetCode**: filtered search, problem view, AI study guide with syntax highlighting.
5. [ ] **Tutor tools**: Concept Map (React Flow, JSON/DOT export), Socratic, Synthesis, Adaptive, Math (KaTeX).
6. [ ] **Analytics**: persist events in the backend, charts, report export.
7. [ ] **3D Viz**: real embeddings projected by the backend (UMAP or PCA).
8. [ ] **Parity check**, delete `frontend/*.py`, update the README.

Quality gates: `tsc --strict`, ESLint, Vitest (components and hooks), Playwright end-to-end for "upload → ask → cited answer".

**Done when:** the Next.js app matches or beats the Streamlit app and Streamlit is removed.

## Phase 4: Answer quality (about 1 week; overlaps Phase 3)
- [ ] Build an eval set of 30–50 questions with expected sources; track recall@k and citation correctness.
- [ ] Hybrid retrieval (BM25 + dense) and optionally a reranker.
- [ ] Better chunking: respect headings and sentences; treat code differently from prose.
- [ ] Flag answers that cite sources not in the retrieved chunks.
- [ ] Cache by (question, mode, store version).
- [ ] Re-evaluate the fine-tuning question using these numbers (see [Model strategy](#model-strategy)).

**Done when:** each retrieval or prompt change shows up as a number in an eval report.

## Phase 5: Product extras (deferred, post-v1)
Out of scope for the portfolio v1. Possible later work:
- Accounts and persistent history.
- Flashcards with spaced repetition and Anki export (`genanki` is already a dependency).
- LeetCode progress tracking and study plans from weak topics.
- Multiple model providers behind one interface.

## Phase 6: Deploy and operate (3–4 days)
- [ ] Backend Dockerfile deployed to a container host (Cloud Run, Fly or Render); frontend on Vercel.
- [ ] Secrets in the host's secret store; a Gemini spend cap; rate limiting.
- [ ] Structured logging and a health/readiness endpoint.
- [ ] Preview deployments per PR.
- [ ] A live demo link in the README.

## Phase 7: Docs and release
- [ ] Fill in `docs/ARCHITECTURE.md`; add an API guide and a contributor guide.
- [ ] Refresh README screenshots and update "Known limitations".
- [ ] Short demo video or GIF for the portfolio.
- [ ] Tag `v1.0`.

---

## Order and timeline
Phases 0 → 1 → 2 are sequential. Frontend work can begin on the shell once the API schema is stable, and Phase 4 overlaps Phase 3. Estimated total for one person: **about 6–8 weeks** to parity and deployment.

## Risks
| Risk | Mitigation |
|---|---|
| Embedding stack crashes on macOS | Fix in Phase 1 before the frontend depends on it. |
| Gemini model and SDK churn | Model ID in config; SDK behind `GeminiClient`; re-check names before release. |
| Large data in git history | Fix in Phase 0 before it grows. |
| Scope creep from the nine tabs | Ship Ask, Sources and LeetCode first; the rest are follow-ups. |
| Gemini cost on a public demo | Spend cap, rate limits, and Demo Mode as a no-cost fallback. |
