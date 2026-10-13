# AWS: how the API runs in the cloud

This page explains what was built on AWS, why each piece exists, what it costs, and how to operate it.
Everything is defined as code in [`infra/main.tf`](../infra/main.tf); the commands are in [`infra/README.md`](../infra/README.md).

## The problem it solves

The API keeps two kinds of state on disk: the **search index** (`manifest.json`, `chunks.jsonl`, `embeddings.npy`) and the
**study database** (`study.db`: flashcards, LeetCode progress, history). A cloud container's disk is wiped every time it is
redeployed or restarted, so without help the tutor would forget every book and every flashcard. AWS gives us a place to
keep that state (S3), a place to store the program (ECR), somewhere to run it (App Runner), and a safe place for the API key
(Secrets Manager).

## Architecture

```
 you ──docker push──▶ ECR (registry, holds the image)
                         │ the image is the Lambda function's code
                         ▼
 browser ──HTTPS──▶ Lambda Function URL ──▶ Lambda (FastAPI + MiniLM, started on demand)
                                              │   ▲
                           restores at start  │   │ saves after any request that changes data
                                              ▼   │
                                           S3 bucket (index + study.db)

 Lambda ──reads at start──▶ Secrets Manager (GEMINI_API_KEY) ──▶ Google Gemini
 AWS Budgets ──email──▶ you, if spend passes the limit
```

Lambda runs the code only while a request is being handled and charges per millisecond, so there is no idle server bill.
The first request after a quiet period is slower (a "cold start") because a fresh copy has to start, restore the index from S3 and load the embedding model.

## The pieces, in plain terms

| AWS service | What it is | Role here | Resource name |
|---|---|---|---|
| **S3** | Object storage: files in "buckets" | Durable copy of the index and `study.db`. Private, encrypted, versioned (old versions expire after 14 days) | `ai-study-mentor-<account id>` |
| **ECR** | Private registry for Docker images | Holds the API image. Keeps the 5 newest, scans each for known vulnerabilities | `ai-study-mentor` |
| **Lambda** | Runs a function (here, a whole container) only while a request is being handled | Hosts the API: 2 GB memory, 2 GB scratch disk, 120 s timeout. A **Function URL** gives it a public HTTPS address and streams answers token by token. The **Lambda Web Adapter** (added to the image) lets Lambda talk to an ordinary web server | `ai-study-mentor` |
| **Secrets Manager** | Stores secrets, hands them to a service at start | Holds `GEMINI_API_KEY`; it never appears in the image, repo or Terraform state | `ai-study-mentor/GEMINI_API_KEY` |
| **IAM roles** | Permissions for AWS services themselves | One role for the function: write logs, read/write **only** its own bucket prefix, read **only** its own secret | `ai-study-mentor-lambda` |
| **Secrets Manager** (second secret) | Also holds the API key (`ai-study-mentor/API_KEY`) that callers must send | `ai-study-mentor/API_KEY` |
| **Budgets** | Spend alerts | Emails `mp2319@scarletmail.rutgers.edu` at 50% of actual and 100% of forecast spend of the monthly limit | `ai-study-mentor-monthly` |
| **Terraform** | Infrastructure as code | Describes all of the above in one file so it can be reviewed, repeated and deleted | `infra/` |

Region: `us-east-1`. Account: `249946084409`, IAM user `MohammadTest`.

## How the code uses S3 (`backend/cloud_sync.py`)

Set `S3_BUCKET` and the API does this:

1. **At startup** it fetches the Gemini key from Secrets Manager (if `GEMINI_SECRET_ID` is set), then downloads any index or database file missing locally, before the engine loads the index. It never overwrites a file that already exists.
2. **Saving changes** depends on where it runs. On a normal server, a background thread uploads changed files every `S3_SYNC_SECONDS` (default 30) and once more at shutdown. **On Lambda** the process is frozen between requests, so a timer cannot be trusted; instead the API uploads right after any request that is not a plain read (flashcard reviewed, progress saved, history saved).

Details that matter: the SQLite file is copied with SQLite's own backup API before upload so a half-written file is never sent; `manifest.json` is uploaded last and downloaded last because it says which version of the other files is current; a failed download goes to a `.part` file and is renamed only when complete. Without `S3_BUCKET` none of this runs, so local development is unchanged. `boto3` is an optional extra: `pip install 'ai-study-mentor[aws]'`.

**Building the index.** Indexing a PDF takes longer than one request, and Lambda would freeze the work after the response. So the index is built on your own computer and uploaded:

```bash
export S3_BUCKET=ai-study-mentor-249946084409 S3_PREFIX=ai-study-mentor
python -m backend.cloud_sync push      # upload data/vector_store and the study database
python -m backend.cloud_sync pull      # download them
```

The live index holds the three textbooks in `data/uploaded_files` (3,867 chunks, MiniLM embeddings). A new Lambda copy picks up a re-uploaded index on its next cold start.

**Known limits.**
- Several copies of the function can run at the same time when traffic overlaps, and each has its own disk. The last one to save wins, so one change could overwrite another. I tried to cap it at one copy (reserved concurrency), but this account's concurrency limit is 10 and AWS refuses to reserve below 10 unreserved, so it is not enforced. For a single-person demo this is unlikely to matter; for real users the study data would need DynamoDB.
- A change made in the instant before a copy is recycled, in a request that was a plain read (for example a streamed answer written to the answer cache), may not be saved.

## The Docker image

`Dockerfile` is a two-stage build: the first stage installs dependencies (CPU-only PyTorch, because the default wheel carries about 2 GB of GPU libraries a CPU container cannot use) and downloads the MiniLM embedding model; the second stage copies only the result. The model is baked in so the first question does not wait on a download. The container runs as a non-root user and listens on `$PORT`. Two variants: the full image (about 2.3 GB, semantic search) and `--build-arg EMBEDDINGS=0` (about 0.7 GB, keyword search only). The Lambda function is x86, so the pushed image is built with `--platform linux/amd64` (and `--provenance=false`, because Lambda wants a plain single-architecture image). The Lambda Web Adapter is copied in from AWS's public image and is ignored outside Lambda.

## What was done, in order

1. Added `backend/cloud_sync.py`, wired it into the API's startup and shutdown, with tests using a fake bucket.
2. Wrote the Dockerfile; built and ran both variants locally and checked `/health` and offline model loading.
3. Wrote the Terraform, ran `terraform plan` (read-only), then `terraform apply` for the bucket, registry, secret container, roles and budget alert.
4. Round-tripped a test index and database through the real bucket.
5. Stored the Gemini key in Secrets Manager with the CLI (kept out of Terraform state).
6. **App Runner was the first plan and did not work**: AWS answered `SubscriptionRequiredException` (this account is not enabled for it). I did not try to work around that. A read-only probe showed Lambda, EC2, ECS and Lightsail were available; EC2 was ruled out as too expensive (a server bills around the clock), and Lambda was chosen because it only bills while handling a request.
7. Added Lambda support (Web Adapter, save-after-request, secret lookup, push/pull command), rebuilt and pushed the image, replaced the App Runner part of the Terraform with the Lambda function, and applied it.
8. Built the index locally from the three textbooks and uploaded it with `python -m backend.cloud_sync push`.

## What was measured

| Check | Result |
|---|---|
| `GET /health` after a cold start | 200, `semantic_search: true`, 3,867 chunks |
| Cold start (steady state, model loaded) | about 23 s |
| Very first start after each new image is deployed | 114-125 s (seen twice), because Lambda fetches a large image lazily and this was the first run to read PyTorch |
| Warm request | about 0.13 s for `/health` |
| Request with no key / wrong key / right key | 401 / 401 / 200 |
| Daily call counter | `{"calls": 1}` written to S3 after one model call |
| `GET /api/v1/search?query=hash table collisions` | returns real passages from the textbooks |
| Gemini key read from Secrets Manager | works: Google accepted it and listed its models |
| `POST /api/v1/ask` end to end | **works**: "What is a hash table?" returned a cited answer from the textbooks (HTTP 200, 39.6 s on a copy that had to start up and retry). Earlier attempts failed with `503 UNAVAILABLE: high demand` from Google for both `gemini-3.8-flash` and `gemini-flash-latest`; that was Google's service, not AWS, and cleared later. During such spikes the API returns an error after about 70 s of retries |

Peak memory used was about 970 MB of the 2,048 MB allocated.

## Cost

Rough figures from AWS list prices as I remember them; check the AWS pricing pages and your Billing console for real numbers.

| Item | About |
|---|---|
| Lambda compute | $0 while idle. A 10-second question at 2 GB is a fraction of a cent, and the monthly free allowance (1M requests, 400,000 GB-seconds) likely covers a demo |
| S3, ECR, Secrets Manager (about $0.40 per secret), logs | $1 or less |
| **Total** | **about $1 a month** |

Gemini usage is billed by Google, not AWS. The budget alert is **$15 a month** and emails `mp2319@scarletmail.rutgers.edu`. A budget **alerts**, it does not stop spending; the API key and the daily call cap are what limit it.

## Operating it

```bash
# the live address, and calling it with the key
cd infra && terraform output api_url
curl -H "X-API-Key: $(cat ~/.ai-study-mentor-api-key)" <api_url>api/v1/stats

# deploy a new version of the code
REPO=249946084409.dkr.ecr.us-east-1.amazonaws.com/ai-study-mentor
aws ecr get-login-password | docker login --username AWS --password-stdin "${REPO%%/*}"
docker buildx build --platform linux/amd64 --provenance=false -t "${REPO}:latest" --push .
aws lambda update-function-code --function-name ai-study-mentor --image-uri "${REPO}:latest"

# logs
aws logs tail /aws/lambda/ai-study-mentor --since 15m

# delete everything
cd infra && terraform destroy -var budget_email=<email>
```

## The hosted web app (Vercel)

The Next.js app is deployed on Vercel (project `ai-study-mentor`, root directory `apps/web`). It is not an AWS service, but it is the front door to this API, so it is described here.

- **Why a proxy.** Anything in browser code can be read, so the API key cannot live there. The app's browser code calls its own `/api/backend/*` address (`NEXT_PUBLIC_API_URL=/api/backend`). A server-side route (`apps/web/app/api/backend/[...path]/route.ts`, logic in `lib/backend-proxy.ts`) forwards the call to the Lambda URL and adds `X-API-Key` from a secret Vercel setting (`BACKEND_API_KEY`). Streamed answers pass straight through.
- **Public demo rules.** The same page also decides what a stranger may do. Only reading and asking are allowed: search, documents, stats, suggestions, the embedding map, LeetCode search and explanations, ask (plain and streamed), the tutor tools and math. Everything that changes data or reveals other visitors' data is refused with `403 disabled_in_demo`: uploading or deleting sources, flashcards, progress, history, analytics, export, job status. All visitors share one study database, so these stay off. Set `BACKEND_ALLOW_WRITES=1` on a private deployment to lift the rule.
- **Settings on Vercel (production):** `BACKEND_URL` (the Lambda address), `BACKEND_API_KEY` (marked sensitive), `NEXT_PUBLIC_API_URL=/api/backend`. Preview deployments do not have them, so a preview shows an unconfigured API.
- **Shared rate limit.** The API limits requests per caller address. Because every visitor arrives through Vercel, they share one allowance (60 a minute), which is a deliberate extra brake.
- **Limits that remain.** Vercel limits request bodies to about 4.5 MB, so large uploads would not pass even if allowed. Google's free tier allows only a few model calls per minute on this key (5 per minute for `gemini-3.8-flash` at the time of testing), so busy moments show an error. A daily cap of 200 calls applies on top.
- **Deploy:** `vercel deploy --prod` from the repository root (the project's root directory setting points at `apps/web`). Remove with `vercel project rm ai-study-mentor`.

## Security notes

- The bucket blocks all public access and is encrypted at rest.
- The function's role is least-privilege: write logs, read/write its own prefix, read one secret.
- The Function URL itself is public (AWS does not check who calls it), so the **application** checks. Every `/api/v1` request must send `X-API-Key`; without it, or with a wrong one, the answer is `401`. `/health` and `/docs` stay open: they cost nothing and expose no data.
- The key is generated randomly, stored in Secrets Manager (not in the image, repo or Terraform state) and kept on your computer in `~/.ai-study-mentor-api-key` (readable only by you). Rotate it with `aws secretsmanager put-secret-value --secret-id ai-study-mentor/API_KEY --secret-string <new>` and also update the file; a fresh start of the function picks it up.
- A **daily cap on model calls** (`daily_llm_limit`, default 200 per UTC day, counted in S3 so every copy of the function shares it). Past the cap the API answers `429` with code `daily_limit`, and a streamed answer ends with an error event. If the counter itself cannot be read, calls are refused rather than allowed. The count is a guard rail, not exact accounting: two calls in the same instant can count as one. Calls Google rejects still count.
- This protects the AWS side. Google has its own spend limits in the Google Cloud / AI Studio billing settings; set a budget there too, because the cap limits how many calls the API makes, not what each costs.
- A web page cannot keep a key secret: anything in browser code can be read. The hosted web app (not built yet) should call the API from its own server side so the key never reaches the browser.
- The Gemini key was pasted into a chat session while setting this up. Rotate it in Google AI Studio and store the new value with `aws secretsmanager put-secret-value`.
- Terraform state (`terraform.tfstate`) is local and git-ignored. It does not contain the secret value, but it does list resource ids; do not commit it.

## Not done / honest gaps

- The web app (Next.js) is not hosted on AWS; only the API is.
- No custom domain, no WAF, no per-user keys (one shared key), no CI deploy (a GitHub Actions workflow using OIDC is the planned next step).
- The study data is not safe against overlapping copies of the function (see Known limits).
- The OpenAI-compatible provider has not been run against a live endpoint.
