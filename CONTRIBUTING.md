# Contributing

Thanks for looking. This is a portfolio project, but it is kept in a state where a stranger can clone it, run it and change it.

## Set up

Python 3.10+ and Node 20+.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all,dev]"
npm install
cp .env.example .env                       # GEMINI_API_KEY is optional; see below
cp apps/web/.env.example apps/web/.env.local
```

Run it: `uvicorn backend.api:app --reload --port 8000` and, in a second terminal, `npm run web:dev`.
No API key? `python scripts/demo_server.py` runs the real pipeline over a small committed corpus with a scripted model.

## Before you open a pull request

CI runs all of this; run it locally first.

| Check | Command |
|---|---|
| Python lint and tests | `make check` (ruff + pytest) |
| Web types, lint, unit tests | `npm run web:typecheck && npm run web:lint && npm run web:test` |
| Browser tests (no key needed) | `cd apps/web && E2E_PYTHON=$(which python) npx playwright test` |
| Public-demo mode in a browser | `cd apps/web && E2E_PYTHON=$(which python) npx playwright test -c playwright.demo.config.ts` |
| Whole app against a real Gemini model (opt-in, needs a key with quota) | `cd apps/web && GEMINI_API_KEY=... GEMINI_MODEL=gemini-flash-lite-latest E2E_PYTHON=$(which python) npx playwright test -c playwright.real.config.ts` |
| Retrieval quality (if you touched retrieval) | `python -m eval.run`, and commit the report |

## Conventions

- **The API schema is the contract.** After changing a route or model, run `python scripts/export_openapi.py` and `npm run client:generate`, and commit both outputs. CI fails when they are stale.
- **Tests without a paid model.** Python tests use a scripted model (`tests/`); browser tests run a real API with that model. Do not add tests that call Gemini.
- **Measure retrieval changes.** A change to chunking, embeddings or ranking needs numbers from `eval/` (including when it makes things worse). See `eval/README.md`.
- **No pickle, no `eval`.** Stored data is JSONL/NumPy/JSON/SQLite; math goes through `backend/safe_math.py`.
- **Demo mode.** The hosted demo refuses anything that touches the shared database (`apps/web/lib/backend-proxy.ts`). If you add a feature that writes data, decide what it does in the demo and add it to `apps/web/e2e-demo/`.
- **Honest docs.** State limits plainly. If a number is an estimate, say so.

## Layout

See the repository layout in the [README](README.md#repository-layout) and the deeper tour in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Configuration, CLI tools and troubleshooting are in [docs/REFERENCE.md](docs/REFERENCE.md).

## Commits and pull requests

Small, focused commits with a message that says why. Open the PR against `main`; describe what you checked and what you did not.
