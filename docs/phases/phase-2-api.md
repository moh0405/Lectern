# Phase 2: A versioned, typed, secure API

## Goal

Every capability reachable over HTTP in a form a TypeScript client can use safely: stable routes, one error format, real streaming, background jobs, and a security baseline.

## What was built

- A FastAPI package under `/api/v1` split into routers (`sources`, `ask`, `tutor`, `leetcode`, `study`, `viz`) with shared dependencies ([backend stack](../concepts/07-backend-stack.md)).
- **26 operations** at the end of this phase (40 after Phase 5), listed in [API.md](../API.md).
- **Streaming**: `POST /ask/stream` over SSE with typed events `meta`, `token`, `done`, `error` ([LLMs](../concepts/06-llms-and-prompting.md)).
- **Ingestion as jobs**: upload returns `202` and a job id; the client polls `GET /jobs/{id}`.
- **Security**: sanitized file names, allow-listed types, `%PDF-` signature check, size and count limits, CORS limited to configured origins, optional `X-API-Key`, per-IP rate limit, one error schema with no internal exception text, `eval` replaced by a whitelist parser in a timed worker process, HTML export sanitizer.
- **Migrated to the `google-genai` SDK** behind the existing `GeminiClient` class: streaming, JSON mode, retries, cached model resolution.
- **OpenAPI export + generated TypeScript client** with an SSE reader; CI fails when they are stale.

## Technologies

FastAPI, Pydantic, Uvicorn, Server-Sent Events, `google-genai`, OpenAPI, `openapi-typescript`, `openapi-fetch`.

## Key ideas

1. **The schema is the contract.** Pydantic models produce the OpenAPI schema; the TypeScript types are generated from it. The frontend cannot call something that does not exist.
2. **Long work is a job.** Never hold an HTTP request open for minutes.
3. **Errors are data.** `{"error": {"code", "message"}}` everywhere; once a stream has started, errors are events because the HTTP status was already sent.
4. **Untrusted input everywhere:** file uploads, math expressions, model-written HTML.

## Bugs found by testing this phase

- Tutor tools used a different engine than the API, so adaptive explanations saw no material.
- The suggestions fallback ignored the requested count.
- `/search` echoed internal exception text.
- `semantic_ready` stayed false after indexing finished.
- A ReportLab PDF test compared bytes, which differ on every call; fixed to check structure.

## Result

Every prototype feature is reachable from the API; the schema generates a clean client.
