# Lectern: Completion Plan

Goal: take Lectern (then called AI Study Mentor) from a hackathon prototype to a polished, deployable **portfolio project**: a reliable RAG backend, a TypeScript (Next.js) frontend, measurable answer quality, and clear documentation.

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

**Phase 4 update: the numbers, and the answer stays the same.**

- With hybrid retrieval, the right passage is in the top 3 for 94% of real-textbook questions (33 questions), and in the top 5 for 94%. Of the 6% that miss, the evidence never reaches the model. **No change to the generator, including fine-tuning it, can answer from a passage it was never shown.** Those misses are retrieval problems.
- The levers that moved retrieval were all cheap and reversible (BM25 + fusion, better chunks), and each is measured. The next candidates are also retrieval-side: a stronger embedding model, query rewriting, reranking.
- The one place fine-tuning could still apply is the **embedding model** (training it on domain question and passage pairs), not the answer model. That needs a few hundred labelled pairs; the current evaluation (33 + 44 questions) is far too small to train on *and* to test on. Revisit only after growing the evaluation set and trying a stronger off-the-shelf embedder.
- **Answer faithfulness is still unmeasured** (it needs a model call, and a key was not available while building this). If answers turn out to ignore or distort their sources, fix it first with stricter prompts, structured output, and the citation check, which already catches invented sources.

**When to revisit fine-tuning** (only if the evaluation shows it):
- Answers stay stylistically inconsistent despite prompts and few-shot examples, or
- You want a much cheaper or smaller model to match Flash quality on one narrow task (for example, generating Socratic hint ladders), using Flash outputs as training data.

Even then, try these first: better system prompts, few-shot examples, structured output schemas, a stronger embedder or reranker, and a Flash-Lite model for simple tasks.

**Model notes (verified against Google's docs, Oct 2026):**
- `gemini-3.8-flash` is the newest Flash model and is GA.
- `gemini-3.5-flash` is deprecated and now routes to `gemini-3.6-flash`; `gemini-3.7-flash` is listed as stable.
- Flash-Lite variants exist for low-cost use.
- Pricing and names change often. Keep the model ID in config (`GEMINI_MODEL`), not in code, and re-check before release.
- The current `google-generativeai` package is old. Migrate to Google's current Gen AI SDK behind the existing `GeminiClient` interface in Phase 2.

---

## Phase 0: Repo hygiene (1–2 days)
- [x] Complete dependencies; move to `pyproject.toml` with extras and dev tools. Remove unused `langchain` and Ollama code. (Versions are lower-bounded, not pinned; a lockfile can come with deployment in Phase 6.)
- [x] Remove tracked `.DS_Store`; stop tracking PDFs and generated data (`data/vector_store`, `data/repos`). PDFs are user-supplied (copyrighted textbooks) and documented in `data/README.md`; history is not rewritten.
- [x] Add `ruff`, `mypy` (lenient to start), `pytest`, and pre-commit.
- [x] Add GitHub Actions: lint + tests on Python 3.10 and 3.12 (frontend typecheck to be added in Phase 3).
- [x] Add `OPENAI_API_KEY` (optional) to `.env.example`.

**Done when:** a fresh clone installs and passes CI with one command.

## Phase 1: Retrieval core (about 1 week)
Builds on the open work in PR #1 (FAISS document-processing pipeline).
- [x] Retrieval goes through the new `VectorStore`; the keyword fallback now reports per-result scores (query-term coverage, stopwords ignored). **Deviation:** FAISS is an opt-in backend (`VECTOR_BACKEND=faiss`), not the default. On macOS, FAISS and torch each bundle an OpenMP runtime and the process aborts on the first multithreaded call whichever is imported first (reproduced with all four import-order/thread-count combinations). Exact NumPy search returns identical results in about a millisecond at this scale, so FAISS is refused automatically when torch is loaded.
- [x] Replace pickle metadata with `chunks.jsonl` + `embeddings.npy` + `manifest.json` (no pickle anywhere).
- [x] Incremental indexing: content-fingerprinted sources, chunk hashing, embed only new chunks, replace changed sources, prune removed ones, delete via the API.
- [x] One shared engine at API startup (FastAPI lifespan); the API also runs blocking work in a threadpool and retrieves once per query.
- [x] Fix the macOS segfault: root cause was faiss + torch OpenMP clash (see above), not torch alone; current sentence-transformers/torch run fine on their own.
- [x] Tests: embedders, store round-trip/dedupe/remove/backends, indexer (incremental, prune, failure, rebuild), engine (semantic, keyword, fallback, reload), API (upload → index → search → delete).

**Done when:** retrieval has tests and no request re-parses PDFs.

Found while verifying on the real corpus: retrieval works (4–26 ms/query) but ambiguous acronyms mislead it ("BFS vs DFS" returned distributed-file-system passages). That is Phase 4 material (hybrid retrieval, eval set).

## Phase 2: API v1 for a TypeScript client (about 1 week)
- [x] Endpoints for every feature (under `/api/v1`; see README for the final list): `/ask` (with `mode`), `/concept-map`, `/socratic`, `/synthesis`, `/adaptive`, `/math`, `/leetcode/search`, `/leetcode/{id}/explain`, `/suggestions`, `/notes`, `/export`, `/analytics`.
- [x] Real streaming from Gemini over SSE (`POST /ask/stream`) with typed events (`meta`, `token`, `done`, `error`), verified through the TS client against a live server.
- [x] Ingestion as jobs: `POST /sources/files` and `/sources/urls` return 202 + job id; `GET /jobs/{id}` reports progress and the indexing report.
- [x] Security: sanitized upload filenames, allow-listed types + PDF signature + size/count limits, CORS restricted to configured origins, optional `X-API-Key`, math moved to a whitelisted parser in a timed worker process, HTML export sanitized, one error schema with no internal exception text.
- [x] Migrated to `google-genai` behind `GeminiClient`; default model `gemini-3.8-flash`; streaming, JSON mode, cached model resolution.
- [x] OpenAPI schema committed (`packages/api-client/openapi.json`), typed client + SSE reader generated/built in `packages/api-client`; CI checks the schema and generated types are up to date.

**Done when:** every Streamlit capability is reachable from the API and the schema generates a clean TS client.

Bugs found and fixed while testing this phase: tutor tools used a different engine than the API (so adaptive explanations saw no material), the suggestions fallback ignored `n`, and `/search` echoed internal exception text.

## Phase 3: TypeScript frontend (about 2–3 weeks)
Layout: `apps/web` (Next.js) and `packages/api-client` (generated); `backend/` stays as is.

Migrate in this order; each step should be shippable:
1. [x] **Shell**: layout, dark glass theme, sidebar settings, command palette (`cmdk`), typed API client with TanStack Query.
2. [x] **Ask**: SSE streaming hook, context cards with score and keyword highlights, mode picker, `react-markdown` + KaTeX, citation links (page numbers and YouTube timestamps).
3. [x] **Sources**: PDF drag and drop, URL list, audio upload, job progress, document list with delete.
4. [x] **LeetCode**: filtered search, problem view, AI study guide with syntax highlighting.
5. [x] **Tutor tools**: Concept Map (React Flow, JSON/DOT export), Socratic, Synthesis, Adaptive, Math (KaTeX).
6. [x] **Analytics**: persist events in the backend, charts, report export.
7. [x] **3D Viz**: real embeddings projected by the backend (UMAP or PCA).
8. [x] **Parity check**, delete `frontend/*.py`, update the README.

Quality gates: `tsc --strict`, ESLint, Vitest (components and hooks), Playwright end-to-end for "upload → ask → cited answer".

**Done when:** the Next.js app matches or beats the Streamlit app and Streamlit is removed.

### What happened in Phase 3

- Shipped a Next.js 16 app in `apps/web` (strict TypeScript, Tailwind v4, TanStack Query) over a typed client generated from the API's OpenAPI schema, with a Ctrl/Cmd+K command palette, error boundaries and a 404 page.
- Tests: Vitest unit and component tests, and Playwright end-to-end tests that run the real API (scripted model) in a real browser, including axe WCAG A/AA checks on every page.
- **Parity with the Streamlit app**, then removal (`frontend/` deleted in its own commit so it is easy to revert):
  - Ported: Ask (now streaming, with citation chips and YouTube deep links), concept map, Socratic tutor, source comparison, adaptive explanations, Math, 3D view, LeetCode, analytics, source management, model picker, show-prompt, retrieval-only mode, study notes, flashcards CSV, command palette.
  - Improved: the 3D view now projects the real embeddings (PCA) instead of SHA-256 hashes; analytics persist on the server; failures are explained instead of silently falling back.
  - **Not ported: Demo Mode** (canned answers for presenting without a key or network). Without a key, retrieval, LeetCode, Math, the embedding map and analytics still work, and the e2e server shows how to run against a scripted model. Say if you want a canned demo mode back.
- Bugs found and fixed while building it: LeetCode topics were never parsed (0 of 1,825 problems had any); "two sum" ranked "Combine Two Tables" first; every `load_all` re-hit Kaggle and rewrote the dataset; the Ask session was wiped from localStorage on mount; `apps/web/lib` was silently excluded by the Python `lib/` gitignore rule; the accent colour and a scrollable region failed WCAG.

## Phase 4: Answer quality (about 1 week; overlaps Phase 3)
- [x] Build an eval set of 30–50 questions with expected sources; track recall@k and citation correctness. *Two sets (50 synthetic, 39 on the real textbooks), hit@k / MRR / evidence coverage / answerable-vs-unanswerable AUROC, paired-bootstrap intervals, committed reports (`eval/`). Citation correctness is checked per answer at runtime (see below), not as an offline metric: measuring it offline needs a model.*
- [x] Hybrid retrieval (BM25 + dense) and optionally a reranker. *Hybrid is the default with a semantic index; BM25 alone otherwise; the cross-encoder reranker is built and measured but opt-in.*
- [x] Better chunking: respect headings and sentences; treat code differently from prose. *`backend/chunking.py`, adopted because it helps hybrid retrieval (it does not help vector-only search).*
- [x] Flag answers that cite sources not in the retrieved chunks. *`backend/citations.py`; the API and UI report `ok` / `page_not_retrieved` / `unknown_source`.*
- [x] Cache by (question, mode, store version). *Also keyed by k, model and temperature; failures never cached; "Fresh answer" bypasses it.*
- [x] Re-evaluate the fine-tuning question using these numbers (see [Model strategy](#model-strategy)).

**Done when:** each retrieval or prompt change shows up as a number in an eval report. *Met: `python -m eval.run` regenerates the reports, and CI guards the cheap configurations.*

### What Phase 4 found (real textbooks, 33 answerable questions)

| | hit@3 | MRR | ms/query |
|---|---:|---:|---:|
| old keyword scorer | 64% | 0.58 | 75 |
| BM25 | 82% | 0.71 | 0.3 |
| vector search only (Phase 1 baseline) | 82% | 0.78 | 3 |
| **hybrid + v2 chunks (new default)** | **94%** | 0.78 | 3.5 |
| + cross-encoder reranker | 94% | 0.86 | 337 |

- The default is **+12 points at hit@3 (95% interval +3 to +24)**. It is the only change whose interval excludes zero. MRR and hit@1 are unchanged within noise.
- **Surprises worth keeping:** v2 chunking alone *hurts* MRR (-0.12); hybrid with the non-semantic hashing embedder is *worse* than BM25 alone; the original keyword fallback was 18 points worse and 250 times slower than BM25; and several of my first hypotheses (chunk size, page attribution) were tested and ruled out.
- **The evaluation itself needed fixing twice:** the first phrase-in-chunk labels depended on chunk boundaries (valid neighbouring chunks counted as misses), and a label audit added 11 valid alternative passages. Both are disclosed in `eval/README.md`, which also lists the caveats (small n, one labeller, tuned on what it measures).
- **Remaining failures (2 of 33)** are paraphrases the embedder confuses ("added *last*" retrieves *queue* passages).
- **Not done, deliberately:** a "no good match" threshold (unanswerable questions score far lower, AUROC 1.0, but 6 examples cannot set a threshold), and answer-faithfulness measurement (needs a model and a key).

## Phase 5: Study tools
Originally deferred; done after v1's core because the user asked for it. **Accounts are deliberately out of scope**: this is a single-user tool, and a login system would add a lot of security surface for no portfolio value. State lives in one SQLite file.
- [x] Flashcards with spaced repetition (SM-2), model-written or saved from an answer, Anki export. *CSV always; `.apkg` through the optional `anki` extra (`genanki` was not actually a dependency yet).*
- [x] LeetCode progress (todo / attempted / solved, notes) and a study plan from weak topics.
- [x] Multiple model providers behind one interface (`LLM_PROVIDER=gemini|openai`; the OpenAI client also works with any OpenAI-compatible server through `OPENAI_BASE_URL`). Tested with fake SDK clients only; **not run against a live OpenAI endpoint**.
- [x] Server-side persistent history (no accounts): saved when an answer finishes, restored when the browser has none.

**Done when:** each feature has API tests, frontend tests and a browser test. *Met (see `docs/phases/phase-5-study-tools.md`).*

## Phase 6: Deploy and operate (3–4 days)
- [x] Backend Dockerfile (CPU torch, model baked in, non-root). **Deviation:** deployed to AWS Lambda (container image + Function URL), not Cloud Run/Fly/Render, because a cloud-provider portfolio piece was wanted. App Runner was tried first and is not enabled on the account; EC2 was ruled out as an always-on cost. See `docs/AWS.md`.
- [x] State in S3 (index and study database), restored at start and saved after changes; secrets in Secrets Manager; infrastructure as Terraform (`infra/`); monthly budget alert ($15).
- [x] Frontend on Vercel (`ai-study-mentor-two.vercel.app`). **Deviation:** the browser does not call the API directly; a server-side proxy adds the API key and restricts the public demo to read and ask routes (no CORS change needed). See `docs/AWS.md`.
- [x] An API key on the public endpoint (Secrets Manager) and a daily cap on model calls (counted in S3). **Still to do:** a spend limit in Google's own billing settings. Known gap: the function cannot be capped at one copy on this account, so overlapping writes can race.
- [ ] CI deploy on merge (GitHub Actions with OIDC, no stored AWS keys); preview deployments per PR.
- [x] A live demo link in the README.

## Phase 7: Docs and release
- [x] Fill in `docs/ARCHITECTURE.md` (now with deployment and demo mode); API guide in `docs/API.md`; contributor guide in `CONTRIBUTING.md`.
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
