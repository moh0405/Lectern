# Lectern: notes for AI coding assistants

Lectern is a retrieval-augmented tutor for Computer Science study material (FastAPI backend in `backend/`, Next.js/TypeScript web app in `apps/web`, typed API client in `packages/api-client`). Start with `README.md`, then `docs/ARCHITECTURE.md`. `CONTRIBUTING.md` lists every check to run.

Private deployment notes (account details, endpoints, key locations, the maintainer's working rules) live in `CLAUDE.local.md`, which is gitignored and not part of the repository.

## Setup and checks
- Python: `python3.13 -m venv .venv && .venv/bin/pip install -e ".[api,math,export,anki,agent,mcp,dev]"`, then `.venv/bin/python -m pytest` and `ruff check .`.
- Web: `npm install`, then `npm run web:typecheck && npm run web:lint && npm run web:test`.
- Browser tests (no key needed): `cd apps/web && E2E_PYTHON=$PWD/../../.venv/bin/python npx playwright test`, and `-c playwright.demo.config.ts` for the public-demo mode.
- Real-model tests are opt-in (`playwright.real.config.ts`, needs `GEMINI_API_KEY`).
- After changing a route or model: `python scripts/export_openapi.py` and `npm run client:generate`, and commit both outputs (CI fails when they are stale).

## Conventions that are easy to break
- Tests never call a paid model: the scripted `FakeGemini` (`tests/fake_gemini.py`) stands in, including for tool calling.
- The public demo refuses anything that touches the shared database (`apps/web/lib/backend-proxy.ts`); flashcards, LeetCode progress and a visitor's own documents live in the browser there.
- Internal identifiers are deliberately not renamed with the brand (package names, logger names, browser-storage keys, AWS and Terraform names): changing them would erase visitors' saved data or recreate infrastructure.
- Model calls: the server default (`gemini-3.6-flash`) fails over to `gemini-flash-lite-latest` then `gemini-2.5-flash` when overloaded or out of quota; a model named in the request is never swapped. Every model turn counts against the daily cap (`DAILY_LLM_LIMIT`).
- The tool-using agent's write tools exist only when `AGENT_ALLOW_WRITES=1`; never set it on a public deployment.
- Do not commit secrets, `.env` files or Terraform state (all gitignored); keep personal or account details out of docs.
