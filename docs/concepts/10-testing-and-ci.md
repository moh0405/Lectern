# 10. Testing, quality gates and CI

## The test pyramid used here

| Layer | Tool | Where | What it covers |
|---|---|---|---|
| Unit | **pytest** | `tests/test_*.py` (331 tests) | chunking, BM25, fusion, stemmer, citations, vector store, indexer, cache, safe math, eval metrics |
| API | pytest + FastAPI `TestClient` | `tests/test_api*.py` | every route, the error format, auth, rate limits, upload validation |
| Frontend unit/component | **Vitest** + Testing Library (jsdom) | `apps/web/**/*.test.ts(x)` | reducer, helpers, components |
| End to end | **Playwright** (real Chromium) | `apps/web/e2e/*.spec.ts` | real web app + real API, user flows |
| Accessibility | **axe-core** in Playwright | `e2e/a11y.spec.ts` | WCAG A/AA violations on every page |
| Retrieval quality | `eval/` | not a pass/fail test; reports numbers | see [evaluation](08-evaluation.md) |

## Testing without a paid model

Tests must be free, fast and deterministic, so the language model is replaced by a **fake**:

- Python: `tests/fake_gemini.py` returns canned text or JSON.
- End to end: `tests/e2e_server.py` starts the real API with a scripted model, so browser tests exercise streaming, citations, caching and errors with no API key.

The same idea powers `scripts/demo_server.py`, used to take the README screenshots. Important: those screenshots show **real retrieval but scripted answers**, and the README says so.

## Static checks

| Check | Tool |
|---|---|
| Python lint | `ruff check .` (blocking) |
| Python types | `mypy` (non-blocking while types are cleaned up) |
| TypeScript types | `tsc --noEmit`, strict |
| TS/React lint | `eslint` (Next.js config) |
| Schema in sync | `python scripts/export_openapi.py --check`, and regenerated `schema.d.ts` must match |

## GitHub Actions (`.github/workflows/ci.yml`)

Three jobs on every push and pull request:

1. **backend** (Python 3.10 and 3.12): install without torch or FAISS (so tests exercise the fallbacks), ruff, mypy, pytest, OpenAPI check.
2. **frontend**: `npm ci`, generated types match, client and web typecheck, lint, Vitest, production build.
3. **e2e**: install Chromium, build the web app against the test API address, run Playwright against the scripted-model server; keeps traces as artifacts on failure.

Merging is gated on these being green. The repository follows a **branch-per-phase, PR-per-phase** workflow.

## Real bugs these caught (examples)

- Browser tests reloaded the page before the final `done` event, and a half-finished answer is deliberately never saved: the test was racing the app. Fixed by waiting for the Copy button.
- axe found low-contrast text and a scrollable region that was not keyboard-focusable.
- A hydration bug wiped saved history because `localStorage` was read before the first render.
- A node-version quirk: Node 25 exposes a broken `localStorage` global that needed a test polyfill.

## Principles

- Test behaviour users or other modules rely on, not internals.
- A bug found in real output gets a regression test with the fix.
- Optional heavy dependencies must not be required to run the suite.
