# AI Study Mentor: session notes for Claude

Portfolio RAG tutor: FastAPI backend (`backend/`) + Next.js/TypeScript web app (`apps/web`). Plan in `docs/PLAN.md`; phase issues #2-#9. AWS details in `docs/AWS.md`.

## Where things stand (2026-10-24)

- Phases 0-6 done except automatic deploys (written, opt-in). Phase 7 (docs, v1.0) is issue #9: docs, screenshots and demo video are done (`docs/demo/ai-study-mentor-demo.mp4`); the `v1.0` tag is still to do, only when the user says so.
- Merged: AWS Lambda/S3/Terraform (#17), README AWS section (#18), API key + daily cap (#19), Vercel app (#20), openapi/CLAUDE.md (#21), LeetCode on Lambda (#22), demo 403/mobile fix (#23), npm audit fix with Next.js 16.4.3 (#24), browser-stored LeetCode progress (#25) and flashcards (#27) in the public demo, OIDC deploy workflow (#26, off until `terraform apply -var enable_ci_deploy=true` and the repo variable `AWS_DEPLOY_ROLE_ARN`), Phase 7 docs (#28), demo video (#29).
- Live API (Lambda `ai-study-mentor`, us-east-1): `https://abkrinzbvtuem5ihomtm42pnba0brazm.lambda-url.us-east-1.on.aws/`
- Live web app (Vercel project `ai-study-mentor`, root `apps/web`): `https://ai-study-mentor-two.vercel.app`. It calls `/api/backend/*`, which proxies to AWS and adds the API key. The public demo allow-list is in `apps/web/lib/backend-proxy.ts`.
- AWS account is `MohammadTest` (249946084409), owned by mp2319@scarletmail.rutgers.edu. Budget alerts go to that address. ECR repo: `249946084409.dkr.ecr.us-east-1.amazonaws.com/ai-study-mentor`. S3 bucket: `ai-study-mentor-249946084409`.
- API key is in `~/.ai-study-mentor-api-key` and in Secrets Manager. The Gemini key is in Secrets Manager (`ai-study-mentor/GEMINI_API_KEY`).

## DONE: Lambda image redeployed (verified 2026-10-19)

The Lambda runs the fixed image: its code SHA matches ECR `latest` (pushed 2026-10-14 17:30 EDT). Live checks on 2026-10-19: `POST /api/v1/math` with `2+3*4` returns `kind`/`latex`/`steps`; `GET /health` is ok (3867 chunks; cold start about 35 s); `GET /api/v1/search?query=...` returns chunks (the parameter is `query`, not `q`); `POST /ask/stream` returns the `meta` event with sources, then a `quota_exhausted` error event because the Gemini free quota was used up.

**2026-10-19 later:** `/leetcode` was returning 500 (LeetCodeHandler did `mkdir` on Lambda's read-only filesystem, and the image lacked the dataset). Fixed in PR #22 (`fix/leetcode-lambda`) and deployed from that branch (image digest `9959bb12...`, pushed 11:46 EDT). Verified live: stats (1,825 problems), search, problem detail, and the page. LeetCode search is keyword-only (no embeddings in the image). PR #21 fixes the openapi test on Python 3.13. #22 is merged, so deploying from `main` is safe. Fixed in #23: the demo 403 console noise and the Ask-page sideways scroll. Still open: Tutor tools were not seen succeeding (Gemini quota/503); `/visualize` crashed once with `toLocaleString` of undefined and could not be reproduced.

To redeploy later (`docker version` must show a Server section; run `open -a Docker` first):

```sh
cd ~/Documents/GitHub/AI-study-mentor-
git checkout main && git pull
REPO=249946084409.dkr.ecr.us-east-1.amazonaws.com/ai-study-mentor
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 249946084409.dkr.ecr.us-east-1.amazonaws.com
docker buildx build --platform linux/amd64 --provenance=false --sbom=false -t "${REPO}:latest" --push .   # slow: several minutes, run in background
aws lambda update-function-code --function-name ai-study-mentor --image-uri "${REPO}:latest" --region us-east-1
aws lambda wait function-updated --function-name ai-study-mentor --region us-east-1
```

zsh note: always write `"${REPO}:latest"` (a bare `$REPO:latest` becomes `...atest` via the `:l` modifier). The first request after a new image can take about 2 minutes.

## Local dev

`.venv` (Python 3.13, gitignored): `python3.13 -m venv .venv && .venv/bin/pip install -e ".[api,math,export,anki,dev]"`. The system `python3` is 3.14 and has no deps. `ruff check .` passes. `.venv/bin/python -m pytest` gives 422 passed, 3 skipped. Browser tests: `cd apps/web && E2E_PYTHON=$PWD/../../.venv/bin/python npx playwright test` (46) and `-c playwright.demo.config.ts` (demo mode, 3; `E2E_REAL_EMBEDDINGS=1` also runs 2 more that use the real MiniLM download and a blocked-download fallback). (Python 3.13 renamed the HTTPStatus phrases for 413/422; `scripts/export_openapi.py` pins the old wording so `openapi.json` is identical on every Python version.)

## Known state / limits (be honest about these)

- Tutor tools (socratic, adaptive, synthesis, concept-map) call Gemini. On 2026-10-13 the free-tier daily quota (20 calls/day on `gemini-3.8-flash`) was used up, so they returned 429 until it reset. That is a quota, not a code bug. Request fields: socratic and adaptive take `question`; synthesis and concept-map take `topic`; math takes `input`.
- Public demo disables sources, history, analytics and the LeetCode study plan (shared database). Flashcards and LeetCode progress still work, stored in the visitor's browser (`apps/web/lib/local-cards.ts`, `local-progress.ts`), and visitors can add their own PDFs processed fully in the browser (`apps/web/lib/browser-rag/`, `/ask` accepts `context` passages; the tutor tools do not use them yet). `BACKEND_ALLOW_WRITES=1` on a private deployment lifts all of it.
- Reserved concurrency of 1 is impossible (account limit 10), so several Lambda copies could race on the SQLite file; documented in `docs/AWS.md`.
- Cost figures (about $1/month) are estimates, not checked against a real bill.

- Agentic mode: `POST /ask/agent/stream` (LangGraph, `backend/agent.py`, optional `agent` extra, in the Docker image and CI). Up to 6 model calls per question, counted against the daily cap; always uses the server index (not the browser documents); not evaluated, only behaviour-tested. The proxy allow-list includes it, so it works in the public demo and burns the Gemini quota faster.

- Real-model checks: `tests/real_server.py` + `apps/web/playwright.real.config.ts` + `e2e-real/` (12 tests, opt-in, `GEMINI_API_KEY` needed; passed 12/12 on `gemini-flash-lite-latest` on 2026-11-02 after fixes). Free-tier Gemini keys allow 5 requests a minute and (for `gemini-3.6-flash`) 20 a day per model; the quota is per model, so switch `GEMINI_MODEL` when one is spent. A second key pasted in chat on 2026-11-02 lives in `~/.ai-study-mentor-gemini-key-2` (outside the repo).
- Tool-using agent: `POST /agent/run/stream` (ReAct, Gemini function calling, `backend/react_agent.py`, `tools.py`, `tool_chat.py`; Agent page in the web app) and an MCP server (`python -m backend.mcp_server`, `docs/MCP.md`, optional `mcp` extra, not in the Docker image). Tested with a scripted model and the SDK's MCP client over stdio; run against real Gemini only by hand. A key pasted in chat on 2026-11-02 lives in `~/.ai-study-mentor-gemini-key` (outside the repo); its quota was exhausted quickly, so it is not a billed key.

## Remaining work (only with the user's go-ahead)

- Re-check ask answers on the live site once the Gemini quota resets (only the retrieval/meta part was verified).
- Phase 6 leftover: enable the OIDC deploy (creates an IAM role; show the plan first).
- User-only actions: rotate the Gemini key that was pasted into chat (store the new one with `aws secretsmanager put-secret-value --secret-id ai-study-mentor/GEMINI_API_KEY --secret-string ...`); set a spend limit in Google's billing settings.
- Phase 7 (issue #9): docs polish and v1.0 release.

## Working rules from the user

- Commit often; merge a PR only when the user says so explicitly ("merge N").
- Be honest about limits and mistakes; never work around a permission denial.
- Do nothing with EC2 (expensive). Budget $15/month; about $100 total in the account.
- Never ask for AWS keys in chat (use `aws configure --profile ...` or OIDC). Accounts and logins are out of scope for the app.
- Use the Rutgers email for AWS budget alerts, not gmail.
- Commit messages end with the Co-Authored-By and Claude-Session lines; PR bodies end with the Claude Code line.
