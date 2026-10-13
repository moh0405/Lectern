# 7. The backend stack

Everything under `backend/` is Python. This page explains each technology, what it is for, and where it appears.

## Python 3.10+ with type hints

All modules use type hints (`from __future__ import annotations`). They document intent and let Pydantic and FastAPI generate validation and API schemas. CI runs on Python 3.10 and 3.12.

## FastAPI

A web framework for building HTTP APIs. You write a function, annotate its parameters with types, and FastAPI:

- parses and **validates** the request (wrong type → automatic `422` error),
- **serializes** the response,
- generates an **OpenAPI** schema and interactive docs at `/docs`.

`backend/api/app.py` creates the app (CORS, rate limiting, error handlers, routers). `backend/api/routers/` holds one module per area: `sources`, `ask`, `tutor`, `leetcode`, `study`, `viz`. `backend/api/deps.py` provides shared objects (the engine, the answer cache, analytics) through FastAPI **dependency injection**, which is also how tests swap in fakes.

Why sync endpoints? Most work here is CPU-bound or blocking (NumPy, model inference, file IO). FastAPI runs plain `def` endpoints in a thread pool, so the server stays responsive.

## Pydantic

Defines the shape of every request and response as a class (`backend/api/schemas.py`):

```python
class AskRequest(BaseModel):
    question: str
    k: int = 3
    mode: str | None = None
```

Invalid input is rejected before your code runs. Because the same classes produce the OpenAPI schema, they are the single source of truth that the frontend's generated types derive from.

## OpenAPI and the generated client

`scripts/export_openapi.py` writes `packages/api-client/openapi.json`. `openapi-typescript` turns it into `schema.d.ts`; `openapi-fetch` gives a typed `fetch` wrapper. Change an endpoint's response in Python and the frontend stops compiling until it is updated. A pytest test (`tests/test_openapi_sync.py`) and a CI step fail if the committed files are stale.

## Uniform errors (`backend/api/errors.py`)

Every failure becomes `{"error": {"code": "...", "message": "...", "details": ...}}`: HTTP errors, validation errors and unexpected exceptions alike. Unexpected exceptions return a generic message and are logged server-side with details, so internals never leak (an early bug: `/search` returned exception text).

## Background jobs (`backend/api/jobs.py`)

Indexing a 300-page PDF takes too long for one HTTP request. The upload endpoint saves the file, submits a job to a **single-worker thread pool**, and immediately returns `202` with a `job_id`. The client polls `GET /jobs/{id}` for `queued → running → done|failed` plus progress messages and a final report (`indexed`, `skipped`, `failed`, `chunks_added`). One worker, because jobs mutate the shared store. Job state is in memory (lost on restart; the index itself is on disk).

## Document and source processing (`backend/sources/`, `document_processor.py`)

| Source | Library / approach |
|---|---|
| PDF | `pypdf` text extraction per page, page numbers kept (`fonttools` helps decode embedded fonts) |
| Markdown / text | read directly |
| YouTube | `youtube-transcript-api` |
| Web page | `requests` + `readability-lxml` + `beautifulsoup4` (main article text) |
| GitHub repo | `gitpython` clone, then README/code files |
| Audio | OpenAI Whisper transcription (`openai` package) |

Each returns the same structure, so chunking and indexing do not care about the origin. Uploads are validated: allowed extension, `%PDF-` signature for PDFs, a maximum size and file count, and file names are sanitized (no path traversal).

## SQLite (`backend/api/analytics_store.py`)

A zero-setup embedded SQL database in one file (`data/analytics.db`). Each asked question is one row: question, mode, latency, how many passages, top score, cache hit, citation counts. `GET /analytics` aggregates it; `DELETE /analytics` clears it. Chosen over a server database because it needs nothing running and the data is small and single-writer.

## Safe math (`backend/safe_math.py`)

The Math tool evaluates user-typed expressions, which is dangerous with `eval`. The approach has three layers: a **whitelist validator** (only numbers, operators, and allowed functions), a **parser with empty builtins** (`parse_expr`), and execution in a **separate spawned process with a 5-second timeout** that is killed and replaced if it hangs. This stops both code execution and denial of service by huge expressions like `9**9**9`.

## Export and sanitizing (`backend/export_utils.py`)

Notes and answers can be exported to Markdown, PDF (ReportLab) or HTML. Model-written Markdown is untrusted, so HTML output passes through an **allow-list sanitizer** (known-safe tags and attributes only; scripts and event handlers are dropped).

## Security and operations settings (`backend/api/settings.py`)

Configured by environment variables:

| Setting | Effect |
|---|---|
| `GEMINI_API_KEY`, `GEMINI_MODEL` | model access |
| `API_KEY` | if set, requests must send `X-API-Key` |
| `CORS_ORIGINS` | which web origins may call the API |
| `RATE_LIMIT_PER_MIN` | per-IP request limit (default 60) |
| `MAX_UPLOAD_MB` | upload size limit (default 50) |
| `UPLOAD_DIR`, `STORE_DIR`, `ANALYTICS_DB` | where data lives |
| `VECTOR_BACKEND` | `numpy` (default) or `faiss` |
| `RETRIEVAL_MODE`, `RERANKER` | retrieval behaviour |

## LeetCode data (`backend/leetcode_handler.py`)

1,825 problems normalized from public Kaggle CSVs into `data/leetcode/normalized_problems.jsonl` (committed, so the app needs no Kaggle account). Search ranks title, then topics, then description. Topics are parsed from the source's inconsistent formats (a bug found in Phase 2).

## Embedding projection (`backend/projection.py`)

**PCA** (principal component analysis) finds the 3 directions in which the 384-dimensional vectors vary the most and projects onto them, so you can plot them. Implemented with NumPy's SVD. It powers `GET /embeddings/projection`.

## Dependencies you can run without

Heavy optional pieces are optional: `sentence-transformers` (semantic embeddings), `faiss` (ANN), reranker models, audio. The app degrades gracefully when they are missing (see the table in [Architecture](../ARCHITECTURE.md#11-what-happens-when-something-is-missing)).
