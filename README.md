# Lectern

> Formerly *AI Study Mentor*. The GitHub repository, app and documentation now use the name Lectern.

**A retrieval-augmented tutor for Computer Science study material: ask questions of your own textbooks, lectures and repos, and get answers with citations that are checked against the passages the model actually saw.**

Full stack: Python/FastAPI backend with a hand-built vector store and hybrid search, a TypeScript/Next.js frontend, and an evaluation harness that measures every retrieval decision.

**Live demo: [ai-study-mentor-two.vercel.app](https://ai-study-mentor-two.vercel.app)**: ask questions of three CS textbooks, with streamed cited answers. It is a read-and-ask demo: uploading sources, history and analytics are switched off because they would be shared between all visitors. Flashcards and LeetCode progress still work, saved in your own browser only, and you can add your own PDFs and ask about them: they are read, embedded and searched inside your browser and never uploaded. It has a daily cap on model calls and sits on Google's free tier, so it can answer "busy, try again" at times. The first question after a quiet period takes up to about 30 seconds while the API wakes up.

![Ask page: a streamed answer with verified citations and retrieved passages](docs/images/ask.png)

**Demo video (51 s):** [docs/demo/lectern-demo.mp4](docs/demo/lectern-demo.mp4). Recorded with Playwright against the local demo server (scripted model, as below); regenerate with `cd apps/web && npx playwright test -c playwright.video.config.ts`.

> **About the screenshots.** They are captured from `scripts/demo_server.py`, which runs the real API, real chunking, real MiniLM embeddings and real hybrid retrieval over a small committed corpus, but uses a **scripted stand-in for the language model** (no API key). Answer text in the screenshots is therefore not model output. Run the app with a `GEMINI_API_KEY` for real answers.

---

## What it does

- **Ingests** PDFs, YouTube transcripts, web pages, GitHub repos and audio, as background jobs with progress. In the public demo, visitors can instead add their own PDF, TXT or Markdown files that stay in the browser (text extraction with pdf.js, MiniLM embeddings with transformers.js, hybrid search in TypeScript); only the few matching passages are sent with a question.
- **Tool-using agent (the Agent page):** give it a task and the *model* decides which tools to call, in a ReAct loop (reason, act, observe, repeat) using Gemini function calling: search your documents, list them, read a page, solve math in the sandboxed solver, find a LeetCode problem. Each call and result streams to the page, the final answer's citations are checked against what the tools returned, and the loop is bounded (a step limit, then a forced wrap-up; every model turn counts against the daily cap). Tools that change data (saving flashcards) exist only when a deployment turns them on.
- **MCP server:** the same tools are available to Claude Desktop, Claude Code, Cursor or any MCP client (`python -m backend.mcp_server`, see [docs/MCP.md](docs/MCP.md)).
- **Agentic mode (optional, LangGraph):** for harder questions the Ask page can run a small workflow that rewrites the search query, asks the model whether the retrieved passages are enough (searching once more if not), writes the answer, and re-checks its citations (rewriting once if it cited sources it was never given). The steps are shown with the answer. It is slower and uses up to 6 model calls per question; its benefit has not been measured (see Status and limits).
- **Answers only from your sources**, streamed token by token, with `[document (page N)]` citations. Each citation is **verified** against the retrieved passages and flagged if the document or page was never retrieved.
- **Retrieves with hybrid search**: embeddings (meaning) + BM25 (exact terms), merged by reciprocal rank fusion. Measured, not assumed.
- **Tutors**: concept maps, a Socratic tutor that gives hints not answers, cross-source synthesis, level-adaptive explanations, symbolic math.
- **LeetCode mentor**: 1,825 searchable problems with AI-written study guides, progress tracking (todo / attempted / solved, with notes) and a study plan built from your weak topics.
- **Flashcards with spaced repetition**: SM-2 scheduling, cards written from your material by the model or saved from any answer, exported to Anki (CSV or `.apkg`).
- **Remembers your work**: Ask history is saved on the server and comes back even if you clear the browser.
- **Shows its work**: retrieved passages with scores, a 3D map of your document embeddings, and an analytics dashboard.

| | |
|---|---|
| ![Sources and jobs](docs/images/sources.png) | ![Concept map](docs/images/concept-map.png) |
| Sources: upload, URLs, indexed documents | Concept map (React Flow + dagre) |
| ![Embedding map](docs/images/embedding-map.png) | ![LeetCode](docs/images/leetcode.png) |
| 3D map of the real embeddings (PCA) | LeetCode search and study guide |

More: [Flashcards](docs/images/flashcards.png) · [Socratic tutor](docs/images/socratic.png) · [Math](docs/images/math.png) · [Analytics](docs/images/analytics.png) · [Command palette](docs/images/command-palette.png) · [Mobile](docs/images/mobile.png)

---

## Results

Retrieval was evaluated on three real CS textbooks (about 4,700 passages, 33 answerable questions). Every change below was measured; intervals are paired-bootstrap 95%.

| Configuration | hit@3 | MRR | ms/query |
|---|---:|---:|---:|
| Original keyword overlap | 64% | 0.58 | 75 |
| BM25 (own implementation) | 82% | 0.71 | 0.3 |
| Dense MiniLM embeddings | 82% | 0.78 | 3 |
| **Default: hybrid + structure-aware chunking** | **94%** | 0.78 | 3.5 |
| Default + cross-encoder reranker (opt-in) | 94% | 0.86 | 337 |

- Default vs dense: **+12 points at hit@3 (95% interval +3 to +24)**, the only change whose interval excluded zero.
- Negative results are reported too: new chunking alone hurts MRR, hybrid with a non-semantic embedder is worse than BM25, chunk size barely matters.
- **Fine-tuning was evaluated and rejected**: the remaining misses are retrieval failures, where the right passage never reaches the model.
- Limits are stated: small sample, one labeller, tuned on the data it measures, retrieval only (answer faithfulness is not measured). See [`eval/README.md`](eval/README.md).

---

## Architecture

![Architecture](docs/images/architecture.png)

```mermaid
flowchart LR
  subgraph Index["Indexing (background job)"]
    S[PDF / YouTube / web / GitHub / audio] --> X[Extract text]
    X --> C[Chunk v2<br/>sentences, headings, code]
    C --> E[Embed<br/>MiniLM 384-d]
    E --> V[(Vector store<br/>chunks.jsonl + embeddings.npy)]
  end
  subgraph Answer["Answering"]
    Q[Question] --> D[Dense search]
    Q --> B[BM25]
    V --> D
    V --> B
    D --> F[Reciprocal rank fusion]
    B --> F
    F --> P[Prompt with labelled passages]
    P --> G[Gemini, streamed over SSE]
    G --> K[Citation check]
  end
  K --> UI[Next.js app]
```

How the pieces fit:

| Layer | Technology | Role |
|---|---|---|
| Web app | Next.js 16, React 19, TypeScript (strict), Tailwind v4, TanStack Query | UI, streaming, state |
| Typed client | OpenAPI → `openapi-typescript` + `openapi-fetch`, custom SSE reader | Frontend types generated from the backend |
| API | FastAPI, Pydantic, Uvicorn, Server-Sent Events | 42 operations under `/api/v1` |
| Retrieval | NumPy exact search (FAISS opt-in), BM25, RRF, optional cross-encoder | Hybrid search |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` (384-d), hashing fallback | Meaning as vectors |
| Generation | Provider interface: Google Gemini (`google-genai`) or any OpenAI-compatible server | Answers, tutor tools, JSON mode |
| Agents | LangGraph (`langgraph`, `langchain-core`), Gemini function calling, MCP (`mcp`) | A fixed workflow (rewrite, grade, verify) and a tool-using ReAct agent; the tools also served over MCP |
| Storage | JSONL + NumPy + JSON manifest; SQLite for analytics | No pickle, no server |
| Cloud | AWS Lambda (container), S3, ECR, Secrets Manager, Budgets, Terraform | API hosting, durable state, infrastructure as code |
| Quality | pytest (422), Vitest (142), Playwright (46 + 3 in demo mode, plus an opt-in 12-test suite against a real Gemini model) + axe, GitHub Actions, evaluation harness | CI gates |

Deep dive: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

### Engineering highlights

- **Own vector store** with atomic writes, content-hash de-duplication, incremental indexing (SHA-256 fingerprints) and a manifest that refuses to mix embedders.
- **A real debugging story**: a macOS crash traced to FAISS and PyTorch each bundling an OpenMP runtime; resolved by making exact NumPy search the default (about 1 ms at this scale) and FAISS opt-in.
- **Citation verification**: catches invented documents and pages in model output.
- **Safe by design**: sanitized uploads, optional API key, restricted CORS, rate limiting, one error schema with no internal text, math in a sandboxed worker process with a timeout (no `eval`), allow-list HTML sanitizer.
- **Schema as contract**: CI fails if the OpenAPI file or generated TypeScript types are stale.
- **Tested without a paid model**: a scripted model drives end-to-end browser tests with accessibility scans.

---

## API at a glance

All under `/api/v1` except `/health`. Interactive docs at `/docs`. Full detail and examples: [`docs/API.md`](docs/API.md).

| Area | Operations |
|---|---|
| Health and corpus | `GET /health` · `GET /stats` · `GET /documents` · `DELETE /sources?key=` |
| Ingestion | `POST /sources/files` · `POST /sources/urls` · `GET /jobs/{job_id}` |
| Ask and search | `POST /ask` · `POST /ask/stream` (SSE) · `POST /ask/agent/stream` (SSE, agentic) · `POST /agent/run/stream` (SSE, tool-using agent) · `GET /search` · `GET /suggestions` · `GET /models` |
| Tutor tools | `POST /concept-map` · `/socratic` · `/synthesis` · `/adaptive` · `/math` |
| LeetCode | `GET /leetcode/stats` · `/leetcode/search` · `/leetcode/problems/{pid}` · `POST /leetcode/problems/{pid}/explain` |
| Flashcards | `GET` / `POST /cards` · `POST /cards/generate` · `GET /cards/export` · `POST /cards/{id}/review` · `DELETE /cards/{id}` |
| LeetCode progress | `GET /leetcode/progress` · `PUT` / `DELETE /leetcode/progress/{pid}` · `GET /leetcode/plan` |
| History | `GET` / `POST /history` · `DELETE /history` · `DELETE /history/{id}` |
| Notes and export | `POST /notes` · `POST /export` |
| Analytics and viz | `GET` / `DELETE /analytics` · `GET /embeddings/projection` |

Streaming events from `POST /ask/stream`: `meta` (retrieved passages) → `token`* → `done` (model, checked citations, cached) or `error`. The agentic endpoint adds `step` events (what the workflow is doing) and `replace` (discard the answer so far; a corrected one follows).

---

## Deployed on AWS

The API runs in the cloud as a **container on AWS Lambda**, with its state in **S3**, infrastructure written as **Terraform**, and a spend alert on the account. The web app is hosted on **Vercel** and reaches the API through a server-side proxy, so the API key never reaches a visitor's browser.

```mermaid
flowchart LR
  Dev[docker build + push] --> ECR[(ECR<br/>image registry)]
  ECR --> L
  W[Browser] --> V[Vercel<br/>Next.js + proxy adds the key]
  V -->|HTTPS + key| FU[Lambda Function URL<br/>streams answers]
  FU --> L[Lambda<br/>FastAPI + MiniLM, 2 GB]
  L <-->|restore at start,<br/>save after changes| S3[(S3<br/>index + study.db)]
  L -->|reads key at start| SM[Secrets Manager]
  L --> G[Gemini]
  B[AWS Budgets] -.->|email alert| Me[Owner]
```

| AWS service | Why it is here |
|---|---|
| **Lambda** (container image) | Runs the API only while a request is handled, so there is no idle server bill. A Function URL gives it public HTTPS and streams answers token by token. |
| **S3** | Container disks are wiped on restart; the search index and the flashcard/progress database are restored from S3 at start and saved back after changes. Private, encrypted, versioned. |
| **ECR** | Holds the Docker image (CPU-only PyTorch, the MiniLM model baked in so there is no download at runtime). |
| **Secrets Manager** | Holds the Gemini API key; it never appears in the image, the repo or Terraform state. |
| **IAM** | One least-privilege role: write logs, use its own bucket prefix, read its own secret. |
| **Budgets** | A monthly spend alert ($15) by email. |
| **Vercel** (not AWS) | Hosts the Next.js app. Its `/api/backend` route forwards calls to the API, adds the key, and only lets read and ask routes through. |
| **API key + daily cap** | Callers must send `X-API-Key`; model calls are capped per day (counted in S3). |
| **Terraform** | The whole setup is one reviewable file (`infra/main.tf`); `terraform destroy` removes it. |

Measured on the live deployment: a cold start takes about 23 s (loading the model and restoring the index), a warm request about 0.13 s, peak memory about 970 MB of 2 GB. The estimated cost is about $1 a month (AWS list prices, not yet checked against a bill).

Honest limits: Lambda can run several copies at once and this account's quota does not allow capping it at one, so overlapping writes to the study database could overwrite each other (fine for one person, not for many). Every API call needs a secret key (stored in Secrets Manager) and the model is capped at a fixed number of calls per day, so a leaked address cannot run up the bill; the address is still not published here because visitors would not have a key. There is no automatic deploy from GitHub yet. Full explanation, including a first attempt on App Runner that this account could not use: [`docs/AWS.md`](docs/AWS.md).

---

## Quick start

Requires Python 3.10+, Node 20+, and a [Gemini API key](https://aistudio.google.com/) (or an OpenAI-compatible endpoint, see `LLM_PROVIDER`) for generated answers (retrieval, LeetCode, math and the embedding map work without one).

```bash
git clone https://github.com/moh0405/Lectern.git && cd Lectern
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all,dev]"
cp .env.example .env            # set GEMINI_API_KEY

uvicorn backend.api:app --reload --port 8000     # API  → http://localhost:8000/docs

# in a second terminal
npm install
cp apps/web/.env.example apps/web/.env.local
npm run web:dev                                   # web  → http://localhost:3000
```

No key and just want to look around? `python scripts/demo_server.py` runs the real pipeline over the committed sample corpus with a scripted model.

Tests: `make check` (Python), `npm run web:test`, and `cd apps/web && npx playwright test` (browser, no key needed). Evaluation: `python -m eval.run`.

Everything else (configuration, CLI tools, data directory, troubleshooting): [`docs/REFERENCE.md`](docs/REFERENCE.md).

---

## Learn how it works

This project was built to be understood. The docs teach each technology from first principles, using real numbers from this repo.

- **[Docs index](docs/README.md)**: reading order
- **[AWS deployment](docs/AWS.md)**: what runs in the cloud, why, what it costs, how to operate it
- **[Phase by phase](docs/phases/README.md)**: how the project was built and what each stage taught
- **Concepts**: [RAG](docs/concepts/01-rag.md) · [Embeddings](docs/concepts/02-embeddings.md) · [Vector databases](docs/concepts/03-vector-databases.md) · [Search and ranking](docs/concepts/04-search-and-ranking.md) · [Chunking](docs/concepts/05-chunking.md) · [LLMs and prompting](docs/concepts/06-llms-and-prompting.md) · [Backend stack](docs/concepts/07-backend-stack.md) · [Evaluation](docs/concepts/08-evaluation.md) · [Frontend stack](docs/concepts/09-frontend-stack.md) · [Testing and CI](docs/concepts/10-testing-and-ci.md) · [Glossary](docs/concepts/11-glossary.md) · [Spaced repetition and LLM providers](docs/concepts/12-study-features.md)

## Repository layout

```
backend/         Python: API (api/), retrieval, indexing, LLM client, tutor tools
apps/web/        Next.js app (app/, features/, components/, lib/, e2e/)
packages/api-client/   OpenAPI schema + generated TypeScript client + SSE reader
eval/            retrieval evaluation: corpora, questions, metrics, committed reports
tests/           pytest suite, scripted model, e2e API server
scripts/         OpenAPI export, preprocessing, demo server
infra/           Terraform for the AWS deployment
Dockerfile       the API image (also what Lambda runs)
docs/            architecture, concepts, phases, API, plan
```

## Status and honest limits

Phases 0 to 5 are done (hygiene, retrieval core, API, frontend, answer quality, study tools). Phase 6 (deployment) is done except automatic deploys: the API runs on AWS and the web app on Vercel, and a GitHub-OIDC deploy workflow is written but opt-in (see `infra/README.md`). Phase 7 is release polish: docs are filled in and screenshots refreshed; a demo video and the v1.0 tag are what remain. See [`docs/PLAN.md`](docs/PLAN.md). Contributions: [`CONTRIBUTING.md`](CONTRIBUTING.md).

- **Free Gemini keys are tight.** One tested free key allowed 5 requests a minute and 20 a day per model. A plain question uses 1 call, but agentic mode uses up to 6 and the tool-using agent up to 9, so on a free key they can hit the per-minute limit (the server waits out short limits, up to 30 s) or the daily one (it stops and says so). A billed key avoids this.
- The AWS deployment is a single-user demo design: study data is a SQLite file synced through S3, not a database that several users can write to at once.
- Single process and single user: in-memory jobs and rate limits, and flashcards, progress and history live in one SQLite file with no accounts (a deliberate portfolio-scope decision).
- Exact search is right up to roughly 100k passages; beyond that you would want an approximate index.
- Evaluation measures retrieval, not whether a generated claim is faithful to its source; citation checks catch invented sources only. The agentic workflow and the tool-using agent have no evaluation of their own: they are tested for behaviour (steps, retries, tool use, bounded model calls) with a scripted model, and the tool-using agent was run against real Gemini by hand on a handful of tasks, but neither is shown to improve answers. The agent can be prompt-injected by text inside a document; the default tools are read-only to limit the damage.
- The demo screenshots use a scripted model, as noted above.

## License

MIT, see [LICENSE](LICENSE).
