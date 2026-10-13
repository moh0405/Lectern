# AI Study Mentor: Reference

> The project overview is in the [README](../README.md). This page keeps the detailed configuration, CLI, data and internals notes. Some sections predate the later phases; where they disagree with the README or the other docs, those are newer.

> A domain-specific **Retrieval-Augmented Generation (RAG)** tutor for Computer Science learning, built with Python, FastAPI, Next.js (TypeScript), sentence-transformers (with optional FAISS) and Google Gemini.

AI Study Mentor was my first project for learning AI engineering, and it grew into a hackathon-style demo. You feed it study material (textbook PDFs, YouTube lectures, web articles, GitHub repos, audio recordings). It chunks and indexes that material, then answers questions **only from your sources, with citations**. On top of Q&A it adds tutoring tools (concept maps, a Socratic tutor, adaptive explanations, math solving) and a searchable LeetCode problem bank with AI-generated study guides.

---

## Table of Contents

1. [Features](#features)
2. [How it works](#how-it-works)
3. [Architecture](#architecture)
4. [Repository layout](#repository-layout)
5. [Tech stack](#tech-stack)
6. [Getting started](#getting-started)
7. [Configuration](#configuration)
8. [Adding study material](#adding-study-material)
9. [Running the app](#running-the-app)
10. [Using the UI](#using-the-ui)
11. [Retrieval quality](#retrieval-quality)
12. [REST API](#rest-api)
13. [Command-line tools](#command-line-tools)
14. [Core concepts and internals](#core-concepts-and-internals)
15. [LeetCode module](#leetcode-module)
16. [Datasets and data directory](#datasets-and-data-directory)
17. [Trying it without an API key](#trying-it-without-an-api-key)
18. [Documentation in this repo](#documentation-in-this-repo)
19. [Project history and status](#project-history-and-status)
20. [Known limitations](#known-limitations)
21. [Roadmap](#roadmap)
22. [License](#license)

---

## Features

### Core RAG
- **Multi-source ingestion**: PDFs, YouTube transcripts, web articles, GitHub repos (READMEs, docs and Python docstrings/comments), and audio/video files transcribed with Whisper. Indexing is incremental: only new or changed files are processed.
- **Hybrid retrieval**: BM25 keyword ranking and `all-MiniLM-L6-v2` vector search, fused with reciprocal rank fusion. On the real-textbook evaluation this finds the right passage in the top 3 for 94% of questions, against 82% for vector search alone. Without a neural model the app uses BM25 alone, which is nearly as good on that evaluation. See [Retrieval quality](#retrieval-quality).
- **Grounded, checked answers**: prompts tell Gemini to use only the retrieved context and to cite it. Answers **stream** token by token and can be stopped. Every citation is **checked against the passages the model was actually given**; an invented source or a page it never saw is flagged in the UI.
- **Answer cache**: repeating a question reuses the answer (never after the sources change); "Fresh answer" asks the model again.
- **Visible evidence**: every answer shows its sources as citation chips, with expandable passages, relevance scores and highlighted query terms. YouTube citations link to the exact timestamp.
- **Four study modes** that change the prompt style: *ELI5*, *Technical*, *Interview prep*, *Quick summary*. Optionally show the exact prompt sent to the model, pick the model, or skip the model and just list matching passages.

### Tutoring tools
A missing `GEMINI_API_KEY` is explained in the UI (retrieval keeps working), and built-in offline fallbacks are labelled as such.

| Tool | What it does |
|---|---|
| **Concept map** | A graph of how a topic's ideas connect (React Flow). Click a concept to highlight its neighbours; export JSON or Graphviz DOT. |
| **Socratic tutor** | Guiding questions plus a hint ladder revealed one hint at a time; never the answer up front. |
| **Compare sources** | How each of your documents explains a topic: agreements, differences, a combined explanation and who said what. |
| **Explain at my level** | The same answer at ELI5, ELI10, undergraduate, graduate or expert level, with sources. |
| **Math** | Differentiate, integrate, simplify, expand, factor or solve, typeset with KaTeX. Input is whitelisted and computed in a sandboxed worker with a timeout. |
| **Embedding map** | Your passages in 3D, projected with PCA from the real embeddings (with the variance each axis keeps, and a warning when the index is not semantic). |
| **Analytics** | Persistent usage stats: questions, relevance, response time, most-used sources, streak; export a report or CSV. |

### LeetCode practice + mentor
- A normalized bank of 1,825 problems with 43 topics, merged from public datasets.
- Search by idea (title-weighted keyword ranking, semantic when embeddings are cached) with difficulty and topic filters; the filters live in the URL so a view can be shared.
- One-click AI study guide: observations, approach, complexity, pitfalls, hints and a Python solution.

### Study aids and export
- **Question suggestions** generated from your own material.
- **Study notes** from a session, downloadable as Markdown, HTML (sanitized) or PDF.
- **Flashcards** as a front/back CSV (importable into Anki).

### Engineering
- **FastAPI backend** (`/api/v1`): OpenAPI docs, one typed error format, restricted CORS, rate limiting, optional API key, background indexing jobs and Server-Sent-Events streaming.
- **Next.js frontend** (`apps/web`): strict TypeScript, Tailwind, TanStack Query, and a client generated from the API's OpenAPI schema so the two cannot drift. Keyboard-first (Ctrl/⌘ + K palette), responsive, and checked for WCAG A/AA with axe.
- **Resilient Gemini client**: picks a model the key can use, retries only transient errors, streams, and supports JSON mode.
- **Tested end to end**: Python unit tests, Vitest, and Playwright against the real API in a real browser.

---

## How it works

```
 Sources (PDF / YouTube / Web / GitHub / Audio)
        │  extract text per source type
        ▼
 Chunking (sentences, headings, boilerplate stripped)  ──►  chunk dicts {text, doc, page, chunk_id, source_type, url, extra}
        │
        ▼
 Embeddings (all-MiniLM-L6-v2, normalized; chunks de-duplicated by hash)
        │
        ▼
 Vector store (manifest.json + chunks.jsonl + embeddings.npy; no pickle)  +  BM25 index (built in memory)
        │
 Query ─► vector search ─┐
                         ├─► reciprocal rank fusion ─► top-k   (BM25 alone when the index is not semantic)
 Query ─► BM25 ──────────┘
        │
        ▼
 Prompt builder (mode: default / eli5 / technical / interview / summary)
        │
        ▼
 Gemini (google-genai)  ──►  answer  ──►  citation check against the retrieved passages  ──►  Next.js UI / FastAPI / CLI
```

1. **Ingest**: each input is routed to a source handler by type (see [Core concepts](#core-concepts-and-internals)).
2. **Chunk**: text is split on sentence and paragraph boundaries into passages of up to ~900 characters, with one sentence of overlap. Running page headers and licence boilerplate are removed, paragraphs may continue across a page break (a chunk records its page range), Markdown headings become context ("Hash Tables > Collisions"), and code blocks stay whole.
3. **Embed**: chunks are encoded in batches (32, falling back to 8) and L2-normalized, so the dot product equals cosine similarity.
4. **Retrieve**: the query is searched two ways, by meaning (vectors) and by words (BM25), and the two rankings are merged. The top-k passages (default 3) come back with scores.
5. **Prompt**: chunks are formatted as `- [doc (page N)] text` and inserted into a mode-specific template.
6. **Generate and check**: Gemini produces the answer, and each citation in it is verified against the passages the model was given. If generation fails, the UI still shows the retrieved context.

---

## Architecture

```mermaid
flowchart LR
    subgraph Sources
        PDF[PDF]:::s --- YT[YouTube]:::s --- WEB[Web article]:::s --- GH[GitHub repo]:::s --- AU[Audio / Video]:::s
    end
    Sources --> SM[source handlers<br/>backend/sources/*]
    SM --> DP[document_processor<br/>chunk + dedupe]
    DP --> IX[indexer<br/>incremental, fingerprinted]
    IX --> VS[(data/vector_store<br/>manifest.json, chunks.jsonl, embeddings.npy)]
    VS --> RAG[RAGEngine<br/>retrieve + prompt]
    RAG --> LLM[GeminiClient]
    ADV[advanced_ai<br/>concept map, Socratic, synthesis, adaptive, math] --> RAG
    ADV --> LLM
    LC[LeetCodeHandler] --> LLM
    LLM --> UI[Next.js app<br/>apps/web]
    RAG --> API[FastAPI<br/>backend/api/]
    RAG --> CLI[CLIs]
    classDef s fill:#eef,stroke:#88a;
```

**Design principles**
- **Graceful degradation everywhere**: optional imports are wrapped in `try/except`, so a missing library disables a feature rather than crashing the app. This was added after segfaults from PyTorch/Accelerate on macOS.
- **Lazy loading**: `sentence-transformers` is imported only when embeddings are actually needed.
- **Pluggable sources**: every source implements the `BaseSource` interface (`validate`, `extract`, `get_metadata`) and returns the same chunk schema.
- **Cloud inference only**: Gemini is the supported LLM (default `gemini-3.8-flash`).

---

## Repository layout

```
AI-study-mentor-/
├── backend/
│   ├── api/                    # FastAPI app: app.py, settings, errors, deps, jobs, schemas, routers/
│   ├── safe_math.py            # Whitelisted SymPy parser + worker process with timeout
│   ├── rag_engine.py           # RAGEngine: load store, retrieve, prompt modes, Gemini answers, suggestions, notes, synthesis
│   ├── embeddings.py           # Sentence-transformers and dependency-free hashing embedders
│   ├── lexical.py              # BM25 keyword ranking and reciprocal rank fusion
│   ├── chunking.py             # Structure-aware chunking (sentences, headings, code, boilerplate)
│   ├── rerank.py               # Optional cross-encoder reranker
│   ├── citations.py            # Checks an answer's citations against the retrieved passages
│   ├── vector_store.py         # Pickle-free on-disk store: add, dedupe, remove, search (NumPy or FAISS)
│   ├── indexer.py              # Incremental indexing: fingerprints, skip unchanged, prune, CLI
│   ├── document_processor.py   # PDF reading, chunking, source routing, input discovery
│   ├── llm_config.py           # GeminiClient: model resolution, retry/backoff, fallback
│   ├── advanced_ai.py          # Concept map, Socratic tutor, multi-doc synthesis, adaptive explain, math solver
│   ├── leetcode_handler.py     # LeetCodeHandler: load/normalize/search/explain LeetCode problems
│   ├── export_utils.py         # Markdown → PDF (ReportLab) and Markdown → HTML
│   ├── source_manager.py       # detect_source_type / get_handler / process_url / process_file
│   └── sources/
│       ├── base_source.py      # BaseSource ABC + shared chunk_text()
│       ├── youtube_source.py   # Transcript + oEmbed metadata, timestamped citation URLs
│       ├── web_source.py       # requests + readability-lxml + BeautifulSoup
│       ├── github_source.py    # README via API, else clone; .md/.rst/.txt/.py
│       └── audio_source.py     # OpenAI Whisper transcription with segment timestamps
├── apps/web/                   # Next.js app (App Router, strict TypeScript, Tailwind)
│   ├── app/                    # routes: /ask /sources /leetcode /tutor /math /visualize /analytics
│   ├── features/               # one folder per feature (ask, sources, leetcode, tutor, math, visualize, analytics)
│   ├── components/             # shell, command palette, markdown, UI primitives
│   ├── lib/                    # typed API helpers, URL state, formatting
│   └── e2e/                    # Playwright specs (incl. axe accessibility checks)
├── packages/api-client/        # generated TypeScript client + SSE reader (from openapi.json)
├── scripts/
│   ├── preprocess_all_documents.py  # Build the vector store once for fast startup
│   └── prepare_leetcode_data.py     # Download/normalize LeetCode datasets
├── data/
│   ├── uploaded_files/         # PDFs, audio, and sources.txt (URLs)
│   └── leetcode/               # Kaggle CSVs + normalized_problems.jsonl
├── docs/
│   ├── LEARNING_GUIDE.md       # Step-by-step RAG tutorial using this codebase
│   ├── demo_guide.md           # 3-minute demo script
│   └── ARCHITECTURE.md         # architecture deep dive
├── eval/                       # Retrieval evaluation: corpora, questions, metrics, committed reports
├── tests/                      # pytest suite (chunking, retrieval, prompt modes, API, exports, LeetCode)
├── pyproject.toml              # dependencies (core + extras), ruff, mypy, pytest config
├── Makefile                    # make install / lint / test / check
├── .github/workflows/ci.yml    # CI: ruff + pytest on Python 3.10 and 3.12
├── .pre-commit-config.yaml
├── chat_cli.py                 # Interactive retrieval CLI (semantic with keyword fallback)
├── test_real_pdf.py            # Quick PDF text-extraction smoke test
├── Emergency Hackathon Context.md  # Hackathon-day planning notes and pitch
├── requirements.txt            # shim: installs .[all]
├── .env.example
└── LICENSE (MIT)
```

---

## Tech stack

| Area | Tools |
|---|---|
| Language | Python 3.10+ (uses `X \| None` type syntax) |
| Frontend | Next.js 16, React 19, TypeScript (strict), Tailwind v4, TanStack Query, React Flow, Plotly (3D), KaTeX, cmdk |
| API | FastAPI, Uvicorn, Pydantic, python-multipart |
| LLM | Google Gemini via the `google-genai` SDK, default model `gemini-3.8-flash` |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`) |
| Vector search | Exact cosine similarity: NumPy by default, optional FAISS (`faiss-cpu`) |
| Ingestion | `pypdf`, `youtube-transcript-api`, `requests`, `beautifulsoup4`, `readability-lxml`, `gitpython`, `openai` (Whisper) |
| Math | SymPy |
| ML utils | scikit-learn (t-SNE/PCA for the 3D view) |
| Export | ReportLab (PDF), `markdown` (HTML), `genanki` (listed dependency) |
| Datasets | HuggingFace Hub, Kaggle API, pandas |

---

## Getting started

### Prerequisites
- Python 3.10 or newer
- A **Gemini API key** from Google AI Studio (needed for generated answers and the tutoring tools)
- Optional: an **OpenAI API key** (only for audio/video transcription)
- Optional: Kaggle credentials at `~/.kaggle/kaggle.json` (only to download LeetCode datasets; a normalized copy is already in the repo)

### Install

```bash
git clone https://github.com/moh0405/AI-study-mentor-.git
cd AI-study-mentor-

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -e ".[all,dev]"        # everything (includes torch via sentence-transformers; large download)
# or: pip install -r requirements.txt   # same as .[all] without the dev tools
```

Dependencies are declared in `pyproject.toml` as a small core plus optional extras, so you can install only what you need:

| Extra | Adds |
|---|---|
| *(core)* | numpy, pypdf, python-dotenv, requests, Gemini SDK |
| `embeddings` | sentence-transformers (semantic retrieval; without it the engine uses keyword overlap) |
| `faiss` | Optional FAISS search backend (`VECTOR_BACKEND=faiss`); see the note below |
| `api` | FastAPI, Uvicorn, python-multipart, Pydantic |
| `sources` | YouTube, web, GitHub and audio ingestion |
| `leetcode` | pandas, huggingface_hub, kaggle |
| `math` | SymPy |
| `export` | ReportLab, markdown |
| `dev` | pytest, ruff, mypy, pre-commit, httpx |

Example for backend development without the heavy ML stack: `pip install -e ".[api,sources,leetcode,math,export,dev]"`.

### Check your setup

```bash
make check        # ruff + pytest, same as CI
```

### Configure

```bash
cp .env.example .env
# then edit .env and set GEMINI_API_KEY
```

---

## Configuration

Environment variables (loaded from `.env` via `python-dotenv`):

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `LLM_PROVIDER` | No | `gemini` | Which language-model backend answers: `gemini` or `openai` (any OpenAI-compatible server) |
| `GEMINI_API_KEY` | Yes, with `gemini` | none | Google Gemini API key |
| `GEMINI_MODEL` | No | `gemini-3.8-flash` | Preferred model. The client verifies it supports `generateContent` and falls back automatically. |
| `GEMINI_TEMPERATURE` | No | `0.2` | Default sampling temperature |
| `EMBEDDER` | No | `auto` | `auto`, `sentence-transformers` or `hashing` |
| `RETRIEVAL_MODE` | No | `auto` | `auto` (hybrid with a semantic index, else BM25), `hybrid`, `dense` or `bm25` |
| `RERANKER` | No | off | `cross-encoder` to rerank the top candidates (slower, see Retrieval quality) |
| `VECTOR_BACKEND` | No | `numpy` | `numpy` or `faiss` (see "Search backend") |
| `CORS_ORIGINS` | No | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated origins allowed by CORS |
| `API_KEY` | No | none | If set, `/api/v1` requires this value in `X-API-Key` |
| `MAX_UPLOAD_MB` | No | `50` | Per-file upload limit |
| `RATE_LIMIT_PER_MIN` | No | `60` | Per-IP request limit for `/api/v1` |
| `UPLOAD_DIR`, `STORE_DIR`, `ANALYTICS_DB`, `STUDY_DB` | No | `data/uploaded_files`, `data/vector_store`, `data/analytics.db`, `data/study.db` | Where the API keeps files, the index, analytics, and your flashcards / LeetCode progress / saved history |
| `OPENAI_API_KEY` | With `LLM_PROVIDER=openai`; also for audio | none | OpenAI key, also used for Whisper transcription of `.mp3/.mp4/.wav/.m4a` |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | Model for the `openai` provider (change it to whatever your server offers) |
| `OPENAI_BASE_URL` | No | OpenAI | Point at Ollama, vLLM, LM Studio, OpenRouter...; no real key is needed for local servers |

Never commit `.env`. It is already in `.gitignore`.

---

## Adding study material

Everything lives under `data/uploaded_files/`.

| Type | How to add it |
|---|---|
| **PDF** | Drop `.pdf` files into `data/uploaded_files/`, or use the sidebar uploader / `POST /api/v1/sources/files`. |
| **Audio / video** | Drop `.mp3`, `.mp4`, `.wav` or `.m4a` into the folder, or use the sidebar "Upload audio" expander. Requires `OPENAI_API_KEY`. |
| **URLs** | Add one URL per line to `data/uploaded_files/sources.txt` (or edit it in the sidebar "Add URLs" expander). Supported: YouTube videos, GitHub repos, and generic web articles. |

The repo ships with:
- No PDFs. Add your own to `data/uploaded_files/` (they are gitignored; see `data/README.md`). The project was developed with *Data Structures Using Python*, *Dsa* and *Introduction to Computer Science*.
- `sources.txt` pointing to a YouTube lecture, the Python tutorial, and several algorithm repos (`pypa/sampleproject`, `dsc-iem/TheAlgorithms`, `akshitagit/Python`, `mitcc/AlgoSolutions`, `alfaarghya/alfa-leetcode-api`) plus a YouTube playlist link.

### Build the index (recommended)

```bash
python scripts/preprocess_all_documents.py      # same as: python -m backend.indexer
```

This scans `data/uploaded_files/` and writes `data/vector_store/`:

| File | Contents |
|---|---|
| `manifest.json` | store version, embedder name/dimension, and a fingerprint per source |
| `chunks.jsonl` | one JSON object per chunk (text, document, page, citation info, hash) |
| `embeddings.npy` | normalized embedding matrix, row *i* belongs to chunk *i* |
| `index.faiss` | only with `VECTOR_BACKEND=faiss` |

The indexer is **incremental**:
- A file's fingerprint is the SHA-256 of its content. Unchanged files are skipped, changed files are replaced, and files that were removed from the folder are pruned.
- URLs from `sources.txt` are fetched once and then skipped (`--refresh-urls` re-fetches them).
- Chunks are hashed, so text that is already stored is never embedded twice.
- A source that fails to parse is reported and leaves its previously indexed chunks untouched.

Useful flags: `--rebuild` (start over, needed if you change the embedder), `--no-prune`, `--embedder auto|sentence-transformers|hashing`.

Measured on the three textbooks this project was developed with: 4,715 chunks, about 43 s for the first build (MiniLM on CPU), about 0.5 s for a no-change re-run, and 4–26 ms per query once the model is loaded.

Without a prebuilt store, the engine falls back to scanning **local files only** (PDFs and audio) once and uses BM25 keyword ranking. The API also indexes uploads automatically and removes a document's chunks when you delete it.

**Search backend.** Retrieval is exact cosine similarity over normalized vectors. `VECTOR_BACKEND=numpy` (default) uses a NumPy matrix product; `VECTOR_BACKEND=faiss` uses a FAISS `IndexFlatIP` (install the `faiss` extra). Both return the same results, and NumPy takes about a millisecond at this scale. FAISS is refused automatically when torch is loaded in the same process, because on macOS the two bundle separate OpenMP runtimes and the process aborts on the first multithreaded call.

**Embedders.** `EMBEDDER=auto` (default) uses sentence-transformers if it loads, else a dependency-free hashing embedder (not semantic, but better than keyword overlap). A store records which embedder built it; if that one cannot be loaded later, retrieval falls back to keywords instead of mixing incompatible vectors.

---

## Running the app

You run two processes: the API and the web app. You need Node.js 20 or newer for the web app.

### 1. API

```bash
uvicorn backend.api:app --reload --port 8000
```

Interactive docs: <http://localhost:8000/docs> (Swagger) and <http://localhost:8000/redoc>.

### 2. Web app

```bash
npm install                                        # once, at the repo root (npm workspaces)
cp apps/web/.env.example apps/web/.env.local       # NEXT_PUBLIC_API_URL, default http://localhost:8000
npm run web:dev                                    # http://localhost:3000
```

The API must list the web origin in `CORS_ORIGINS` (the default already includes `http://localhost:3000`).

Production build: `npm run web:build && npm run start -w apps/web`. Note that `NEXT_PUBLIC_API_URL` is baked in at build time.

### Tests

```bash
make check                      # Python: ruff + pytest
npm run web:test                # Vitest unit/component tests
npm run web:typecheck && npm run web:lint
cd apps/web && npx playwright install chromium
E2E_PYTHON=$(which python) npx playwright test     # browser tests against the real API (scripted model, no key needed)
```

---

## Using the UI

| Page | What you do there |
|---|---|
| **Ask** | Type a question (or click a suggestion) and watch the answer stream in, with its sources underneath. *Advanced* has temperature, model, "only show matching passages" and "show the prompt". Your session is remembered in the browser; generate study notes or flashcards from it. |
| **Sources** | Drop PDFs or audio, paste YouTube/GitHub/web links, watch indexing progress, delete sources. |
| **LeetCode** | Search the problem bank, filter by difficulty and topic, read a problem, generate a study guide. |
| **Tutor tools** | Concept map, Socratic tutor, compare sources, explain at my level (tabs). |
| **Math** | Type or click an example such as `differentiate sin(x)`, `solve x^2 - 5x + 6 = 0`, `factor x^3 - x`. |
| **Embedding map** | Rotate and zoom your passages in 3D; click a point to read it. |
| **Analytics** | See what you asked and which sources answered; export a report or CSV. |

**Keyboard:** `Ctrl/⌘ + K` opens the command palette (pages, tutor tools, shortcuts); `Ctrl/⌘ + Enter` sends a question.

### Study modes (Ask tab / `RAGEngine`)
| Mode | Output style |
|---|---|
| default | Concise answer from context only, cites sources |
| `eli5` | Short sentences, no jargon, a friendly analogy, one-sentence recap |
| `technical` | Precise definitions, complexity, code/pseudocode if in context, trade-offs, edge cases |
| `interview` | 2-sentence overview, bullets for approach/complexity/edge cases, pitfalls, short example |
| `summary` | 5–8 one-sentence bullets, no speculation |

---

## Retrieval quality

Retrieval is measured, not assumed. `eval/` holds two question sets (a committed synthetic corpus and your own textbooks), the metrics, and reports; `python -m eval.run` reproduces them. Headline result on the real textbooks (33 answerable questions; see `eval/README.md` for method, caveats and the ablations):

| | hit@3 | MRR | ms/query |
|---|---:|---:|---:|
| old keyword scorer | 64% | 0.58 | 75 |
| BM25 | 82% | 0.71 | 0.3 |
| vector search only (MiniLM) | 82% | 0.78 | 3 |
| **default: hybrid + structure-aware chunks** | **94%** | 0.78 | 3.5 |
| default + cross-encoder reranker (opt-in) | 94% | 0.86 | 337 |

What was decided from this, and what was not:

- **Hybrid search with structure-aware chunks is the default** (+12 points at hit@3, 95% interval +3 to +24). Each half helps little alone.
- **Hybrid is only used with a semantic index.** With the non-semantic fallback embedder, fusing is worse than BM25 alone, so `RETRIEVAL_MODE=auto` picks BM25 there.
- **The cross-encoder reranker is off by default** (`RERANKER=cross-encoder`): it improves the top-1 passage but not the top 3 that the prompt uses, at about 100 times the latency.
- **Still failing:** 2 of 33 questions, both paraphrases where first-in/last-out style wording confuses the embedder. Citation checking catches invented sources, not a wrong claim attributed to a real one.
- **Not measured:** answer faithfulness (needs a model and a key). A "no good match" cut-off looks possible (unanswerable questions score far lower) but 6 examples are too few to choose a threshold.

Environment: `RETRIEVAL_MODE=auto|hybrid|dense|bm25`, `RERANKER=cross-encoder`. After upgrading, the next index run re-chunks existing sources automatically (each source records which chunker made it).

---

## REST API

Start it with `uvicorn backend.api:app --reload --port 8000`. Interactive docs: <http://localhost:8000/docs> (Swagger) and `/redoc`; the schema is at `/openapi.json`.

All `/api/v1` routes are rate limited per IP (`RATE_LIMIT_PER_MIN`, default 60). If the server sets `API_KEY`, clients must send it as `X-API-Key`. CORS allows only `CORS_ORIGINS` (default: `http://localhost:3000`).

**Errors** always look like `{"error": {"code": "...", "message": "...", "details": ...}}`. Codes include `validation_error` (422), `not_found`, `rate_limited` (429), `unauthorized` (401), `payload_too_large` (413), `llm_unavailable` (503, no `GEMINI_API_KEY`), `llm_error` (502, upstream failure) and `math_error` (422). Internal exception text is never returned.

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness, version, chunk count, whether semantic search is ready. |
| `POST` | `/api/v1/sources/files` | Upload PDFs or audio (`multipart`, field `files`). Validates type, PDF signature, size (`MAX_UPLOAD_MB`, default 50) and count; sanitizes file names. Returns **202** with a `job_id`. |
| `POST` | `/api/v1/sources/urls` | Add YouTube / GitHub / web URLs (`{"urls": [...]}`). Returns **202** with a `job_id`. |
| `GET` | `/api/v1/jobs/{id}` | Background job status: `queued`, `running`, `done` or `failed`, with progress messages and the indexing report. |
| `GET` | `/api/v1/documents` | Indexed sources with chunk counts. |
| `DELETE` | `/api/v1/sources?key=...` | Remove a source (file name or URL) from disk, `sources.txt` and the index. |
| `GET` | `/api/v1/stats` | Documents, chunks, page range, embedder, whether search is semantic. |
| `POST` | `/api/v1/ask` | Answer a question. Body: `{question, k=3, mode?, model?, temperature=0.2, include_prompt=false, no_cache=false}`. Returns `{answer, chunks, model, prompt?, citations, unverified_citations, uncited, cached}`: each citation in the answer is checked against the retrieved passages (`ok`, `page_not_retrieved`, `unknown_source`). |
| `POST` | `/api/v1/ask/stream` | Same input, streamed as Server-Sent Events: `meta` (retrieved chunks), `token` (text fragments), then `done` (with the citation check and whether it was cached) or `error`. |
| `GET` | `/api/v1/search?query=&k=` | Retrieval only (no model call). |
| `GET` | `/api/v1/suggestions?n=` | Study questions suggested from your material. |
| `POST` | `/api/v1/concept-map` | `{topic}` → nodes, edges and Graphviz DOT. |
| `POST` | `/api/v1/socratic` | `{question, depth}` → guiding questions and hints. |
| `POST` | `/api/v1/synthesis` | `{topic}` → how documents agree and differ. |
| `POST` | `/api/v1/adaptive` | `{question, level}` → explanation at ELI5 … Expert level. |
| `POST` | `/api/v1/math` | `{input}` → LaTeX and steps (see Safety below). |
| `GET` | `/api/v1/leetcode/stats`, `/search`, `/problems/{pid}` | Browse and search the problem bank. |
| `POST` | `/api/v1/leetcode/problems/{pid}/explain` | AI study guide for a problem. |
| `POST` | `/api/v1/notes` | Q&A history → Markdown study notes. |
| `POST` | `/api/v1/export` | Markdown → downloadable `pdf`, `html` or `md`. |
| `GET` / `DELETE` | `/api/v1/analytics` | Persistent usage stats (SQLite) for asked questions; delete to reset. |

```bash
# add a PDF, wait for indexing, then ask
curl -F "files=@notes.pdf" http://localhost:8000/api/v1/sources/files        # -> {"job_id": "..."}
curl http://localhost:8000/api/v1/jobs/<job_id>                               # -> {"status": "done", ...}
curl -X POST http://localhost:8000/api/v1/ask -H "Content-Type: application/json" \
  -d '{"question": "What is a linked list?", "k": 3, "mode": "technical"}'

# stream the answer
curl -N -X POST http://localhost:8000/api/v1/ask/stream -H "Content-Type: application/json" \
  -d '{"question": "What is a linked list?"}'
```

**Safety.** Math input is validated against a whitelist and computed in a separate worker process with a 5 s timeout (no `eval` of user text). Exported HTML passes through an allow-list sanitizer, so scripts and event handlers in model output cannot execute. Retrieval and indexing run in worker threads, so a slow request does not block the server.

### TypeScript client

`packages/api-client` is generated from the API's OpenAPI schema (`openapi.json`) and is what the Next.js app will use:

```ts
import { createApiClient } from "@ai-study-mentor/api-client";

const api = createApiClient({ baseUrl: "http://localhost:8000" });
const { data, error } = await api.http.POST("/api/v1/ask", { body: { question: "What is a heap?" } });

for await (const ev of api.askStream({ question: "What is a heap?" })) {
  if (ev.event === "token") process.stdout.write(ev.data.text);   // fully typed per event
}
```

After changing an endpoint or schema, regenerate: `python scripts/export_openapi.py && (cd packages/api-client && npm run generate)`. CI fails if the committed schema or generated types are out of date.

---

## Command-line tools

| Command | Description |
|---|---|
| `python chat_cli.py [--keyword] [-k N]` | Interactive loop: prints retrieved context and the final prompt for each question. Semantic retrieval with a keyword fallback; `--keyword` skips embeddings entirely. |
| `python test_real_pdf.py` | Extracts and previews text from `data/uploaded_files/Dsa.pdf` to check PDF parsing. |
| `python scripts/preprocess_all_documents.py` | Build or incrementally update the vector store (wrapper for `python -m backend.indexer`). |
| `python scripts/prepare_leetcode_data.py` | Download and normalize LeetCode datasets. |
| `python -m backend.rag_engine` | Prints a sample prompt and top chunks for "What is a linked list?". |
| `python -m backend.leetcode_handler` | Loads the problem set, prints stats, and runs a sample search. |

---

## Core concepts and internals

### Source handlers (`backend/sources/`)
All handlers extend `BaseSource` and return chunks in this schema:

```python
{
  "text": str,            # chunk content
  "doc": str,             # human-friendly document label
  "page": int | None,     # page number (PDFs) or None
  "chunk_id": str,        # unique id
  "source_type": str,     # "pdf" | "youtube" | "web" | "github" | "audio"
  "url": str | None,      # canonical URL for citation
  "extra": dict,          # e.g. timestamps, citation_url, file_path
}
```

| Handler | Behaviour |
|---|---|
| **PDF** (`document_processor.py`) | Extracts text per page with `pypdf`, chunks each page, records page numbers. |
| **YouTubeSource** | Fetches the transcript with timestamps, merges segments into ~800-character chunks, fetches title/thumbnail via oEmbed, and builds timestamped citation URLs (`...watch?v=ID&t=NNs`). |
| **WebSource** | Downloads the page, extracts the article body with `readability-lxml`, keeps code blocks in fenced backticks, and records a favicon. |
| **GitHubSource** | Tries the GitHub API for the README first; otherwise clones into `data/repos/`. Indexes `.md`, `.rst`, `.txt` and `.py` (for Python it keeps comments and docstrings only). |
| **AudioSource** | Transcribes with OpenAI Whisper (`verbose_json` for timestamps, plain-text fallback), then chunks by segment. |

Source type is detected in `document_processor._detect_source` (and `source_manager.detect_source_type`): local `.pdf` → PDF, local audio extensions → audio, `youtube.com`/`youtu.be` → YouTube, `github.com` → GitHub, other `http(s)` → web.

### `RAGEngine` (`backend/rag_engine.py`)
- `retrieve_context(query, k)`: in `auto` mode, hybrid search (vector search and BM25, merged with reciprocal rank fusion) when the index has semantic embeddings, BM25 alone otherwise. Each result's `score` is its cosine similarity (or normalized BM25), and carries its page range. Details: `backend/lexical.py`, `backend/chunking.py`, `backend/rerank.py`, `backend/citations.py`.
- `RAGEngine.shared()`: one engine per store directory, used by the API. `add_sources()` / `remove_source()` update the live index and persist it.
- `generate_prompt(question, chunks, mode)`: builds the mode-specific prompt.
- `answer_with_gemini(...)`: retrieve → prompt → Gemini. `generate_answer(...)` synthesizes from caller-supplied context.
- `generate_query_suggestions(...)`: proposes study questions from the corpus (static fallback list on failure).
- `summarize_chat(history)`: turns the last 20 Q&A turns into Markdown study notes (heuristic fallback).
- `multi_source_synthesis(question)`: top chunks per document, then Gemini compares and cites.

### `GeminiClient` (`backend/llm_config.py`)
1. Reads `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_TEMPERATURE`.
2. `_resolve_model`: uses the requested model if it supports `generateContent`; otherwise the first available of `gemini-3.8-flash`, `3.7`, `3.6`, `gemini-flash-latest`, `gemini-pro-latest`, else any supported model. The result is cached per key, so models are not listed on every call.
3. `generate`: tries the chosen model, then the default. Transient errors (429, 5xx, timeouts) are retried up to 3 times with backoff; auth errors fail fast. `json_mode=True` requests a JSON response. `stream()` yields text deltas, retrying only before the first one.

### Advanced AI (`backend/advanced_ai.py`)
- `build_concept_map` and `concept_map_to_dot`: JSON graph from Gemini; falls back to a keyword-frequency chain.
- `socratic_tutor`: questions and hints as JSON; canned questions as fallback.
- `multi_document_synthesis`: similarities, conflicts, synthesis and citations as JSON.
- `adaptive_explain`: five `ELI_LEVELS` plus a 3-question quiz.
- `math_solve`: SymPy-backed `simplify`, `differentiate`/`derivative`, `integrate`, `solve ... for ...`, or plain LaTeX rendering.

### Exports (`backend/export_utils.py`)
`markdown_to_pdf` (ReportLab, headings/bullets/simple wrapping, returns `None` if ReportLab is missing) and `markdown_to_html` (uses `markdown` if installed, otherwise a small built-in converter).

---

## LeetCode module

`LeetCodeHandler` (`backend/leetcode_handler.py`) merges several datasets into one searchable bank.

**Sources (best effort, each with a graceful fallback)**
1. HuggingFace: `kaysss/leetcode-problem-set`
2. Kaggle: `gzipchrist/leetcode-problem-dataset`
3. Kaggle: `mohitkumar282/leetcode-questions-dataset`
4. Any local CSV/JSON/JSONL under `data/leetcode/`

**Pipeline**
- Reads `data/leetcode/normalized_problems.jsonl` first (fast path). If it's missing, downloads or parses the raw sources and writes it.
- Normalizes many column-name variants (`id`/`question_id`/`slug`, `tags`/`topic_tags`, `content`/`body`, and so on) into an `LCProblem` (`pid`, `title`, `difficulty`, `topics`, `description`, `url`, `acceptance`, `likes`, `dislikes`, `source`).
- De-duplicates by lower-cased title and merges metadata from duplicates.
- Optionally embeds `title + description` into `data/leetcode/embeddings.npy`.

**API**
- `load_all(force=False, generate_embeddings=True)` → `(count, status)`
- `search(query, top_k=10, difficulty=[...], topics=[...])`
- `explain_problem(pid)` → Markdown study guide
- `get_stats()` → totals, by-difficulty counts, top topics
- `get_by_id(pid)`

`scripts/prepare_leetcode_data.py` runs the loader with embeddings disabled (to avoid macOS segfaults), so search uses keyword scoring unless embeddings already exist.

---

## Datasets and data directory

| Path | Contents |
|---|---|
| `data/uploaded_files/` | `sources.txt` (tracked). PDFs and audio you add are gitignored. |
| `data/leetcode/kaggle/` | Three raw Kaggle CSVs |
| `data/leetcode/normalized_problems.jsonl` | 1,825 normalized problems |
| `data/vector_store/` | *Generated.* `manifest.json`, `chunks.jsonl`, `embeddings.npy` |
| `data/repos/` | *Generated.* Cloned GitHub repos used as sources |

---

## Trying it without an API key

The model is only needed to *write* things. Without `GEMINI_API_KEY`:

- **Works fully**: adding sources, search and retrieval (Ask → Advanced → "only show matching passages"), LeetCode search and browsing, Math, the Embedding map, Analytics.
- **Explained, not broken**: Ask, the tutor tools and study guides show a notice that the server has no key, and Ask still lists the passages it found.
- **Offline fallbacks**: some tutor tools return a basic built-in result, clearly labelled as a fallback.

The browser tests run the real API with a scripted stand-in for the model (`tests/e2e_server.py`), which is also a handy way to explore the UI offline.

The canned-answer "Demo Mode" from the original Streamlit app was not carried over. `docs/demo_guide.md` has a short script for presenting the project, and `Emergency Hackathon Context.md` holds the planning notes from the hackathon day.

---

## Documentation in this repo

- [`docs/LEARNING_GUIDE.md`](LEARNING_GUIDE.md): a step-by-step RAG tutorial that maps each concept (ingestion, chunking, embeddings, vector stores, retrieval, prompting, LLM integration, evaluation) to code in this repository.
- [`docs/demo_guide.md`](demo_guide.md): a short script for presenting the project.
- [`docs/PLAN.md`](PLAN.md): the completion plan and what was decided along the way.
- [`eval/README.md`](../eval/README.md): how retrieval is evaluated, what it found, and the caveats.
- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md): the full architecture write-up.

---

## Project history and status

- **Origin**: the first AI-engineering project, started in October 2025 to learn RAG with LangChain, ChromaDB/FAISS and LLMs on CS material.
- **Nov 2025**: pipeline working end to end without a UI, caching and preprocessing for fast startup, custom CSS, demo mode, batch-processing optimizations. Built under a hackathon deadline (see the context file).
- **Jan 2026**: added transient retry logic to the Gemini client and re-applied the Demo Mode refactor.
- **Open work**: see the phase issues (#2–#9) and `docs/PLAN.md`. [PR #1](https://github.com/moh0405/AI-study-mentor-/pull/1) (an early FAISS pipeline) predates the current code and is superseded by the vector store.

---

## Known limitations

Documented honestly so you know what to expect. These come from reading the code, not from a test run.

- **Tests and evaluation exist but have limits**: 340 backend tests, frontend unit tests, browser tests and a retrieval evaluation (small sample, one labeller). Answer faithfulness is not measured.
- **Type checking is non-blocking in CI**: the optional-import pattern produces about 30 mypy errors.
- **Retrieval is good, not solved**: on the real-textbook evaluation 2 of 33 questions still miss (paraphrases where "last" and "first" look alike to the embedder). The evaluation is small, so every claim carries an interval, and it measures retrieval only, not whether the model's answer is faithful. Answer faithfulness is unmeasured; citation checking catches invented sources, not misattributed claims.
- **PDF extraction quality varies**: some pages come out garbled (math or code fonts); `fonttools` helps but does not fix everything.
- **The embedding map is only as semantic as the index**: with the fallback `hashing` embedder, closeness reflects shared words. The page warns when that is the case.
- **Security is portfolio-grade, not hardened**: the rate limiter is in-memory per process (and keyed by the connecting IP, so it needs adjusting behind a proxy), there are no user accounts (just an optional shared `API_KEY`), and uploads are not virus-scanned. Remaining Phase 6 work: spend caps and deployment hardening.
- **Background jobs are in memory**: job records are lost on restart (the index itself is persisted), and indexing runs one job at a time.
- **PDF export** uses ReportLab's built-in font, so non-Latin characters may not render.
- **Git history**: the textbook PDFs and `.DS_Store` files are no longer tracked, but they remain in earlier commits, so the repo is still large to clone.
- **Source quirks**: YouTube playlist URLs (as in the sample `sources.txt`) have no `v=` video id and are skipped. Python files from GitHub repos are indexed as comments/docstrings only, not code.
- **Stale hackathon numbers**: figures like "977 docs / 12K chunks" and "2000+ problems" in the demo script and context file describe the hackathon corpus. The shipped LeetCode file has 1,825 problems.

---

## Roadmap

See [PLAN.md](PLAN.md). Done: Phases 0 to 4. Next: Phase 5 (flashcards with spaced repetition, LeetCode progress, multi-provider LLM interface), Phase 6 (deployment), Phase 7 (release). Research candidates: a larger evaluation set with answer-faithfulness checks, a calibrated "no good match" threshold, a stronger embedding model or query rewriting for the remaining paraphrase failures.

---

## License

Released under the [MIT License](../LICENSE). Copyright (c) 2025 moh0405.
