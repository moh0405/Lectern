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
 you ──git push──▶ Docker image ──push──▶ ECR (registry)
                                            │ pulled by
                                            ▼
 browser ──HTTPS──▶ App Runner service (1 container, FastAPI + MiniLM)
                       │   ▲
        reads at start │   │ saves changes every 30 s and at shutdown
                       ▼   │
                    S3 bucket (index + study.db)

 App Runner ──reads──▶ Secrets Manager (GEMINI_API_KEY) ──▶ Google Gemini
 AWS Budgets ──email──▶ you, if spend passes the limit
```

## The pieces, in plain terms

| AWS service | What it is | Role here | Resource name |
|---|---|---|---|
| **S3** | Object storage: files in "buckets" | Durable copy of the index and `study.db`. Private, encrypted, versioned (old versions expire after 14 days) | `ai-study-mentor-<account id>` |
| **ECR** | Private registry for Docker images | Holds the API image. Keeps the 5 newest, scans each for known vulnerabilities | `ai-study-mentor` |
| **App Runner** | Runs a container and gives it a public HTTPS URL | Hosts the API. One instance, 1 vCPU / 2 GB. Health check on `/health` | `ai-study-mentor` |
| **Secrets Manager** | Stores secrets, hands them to a service at start | Holds `GEMINI_API_KEY`; it never appears in the image, repo or Terraform state | `ai-study-mentor/GEMINI_API_KEY` |
| **IAM roles** | Permissions for AWS services themselves | Two roles: one lets App Runner pull the image; the other lets the running container touch **only** its own bucket prefix and **only** its own secret | `ai-study-mentor-apprunner-*` |
| **Budgets** | Spend alerts | Emails `mp2319@scarletmail.rutgers.edu` at 50% of actual and 100% of forecast spend of the monthly limit | `ai-study-mentor-monthly` |
| **Terraform** | Infrastructure as code | Describes all of the above in one file so it can be reviewed, repeated and deleted | `infra/` |

Region: `us-east-1`. Account: `249946084409`, IAM user `MohammadTest`.

## How the code uses S3 (`backend/cloud_sync.py`)

Set `S3_BUCKET` and the API does three things:

1. **At startup** it downloads any index or database file that is missing locally (before the engine loads the index). It never overwrites a file that already exists.
2. **While running** a background thread checks every `S3_SYNC_SECONDS` (default 30) and uploads files whose size or modified time changed.
3. **At shutdown** it uploads once more.

Details that matter: the SQLite file is copied with SQLite's own backup API before upload so a half-written file is never sent; `manifest.json` is uploaded last and downloaded last because it says which version of the other files is current; a failed download is written to a `.part` file and renamed only when complete. Without `S3_BUCKET` none of this runs, so local development is unchanged. The `boto3` library is an optional extra: `pip install 'ai-study-mentor[aws]'`.

Limits you should know: **one instance only**, because SQLite and the index have a single writer (the service is configured with min 1 and max 1). Anything written in the last 30 seconds before a crash can be lost. This is a portfolio-scale design, not a multi-user one.

## The Docker image

`Dockerfile` is a two-stage build: the first stage installs dependencies (CPU-only PyTorch, because the default wheel carries about 2 GB of GPU libraries a CPU container cannot use) and downloads the MiniLM embedding model; the second stage copies only the result. The model is baked in so the first question does not wait on a download. The container runs as a non-root user and listens on `$PORT`. Two variants: the full image (about 2.3 GB, semantic search) and `--build-arg EMBEDDINGS=0` (about 0.7 GB, keyword search only). App Runner runs on x86, so the pushed image is built with `--platform linux/amd64`.

## What was done, in order

1. Added `backend/cloud_sync.py`, wired it into the API's startup and shutdown, and added 9 tests using a fake bucket.
2. Wrote the Dockerfile; built and ran both variants locally and checked `/health` and offline model loading.
3. Wrote the Terraform, validated it, and ran `terraform plan` (read-only) to preview 13 resources.
4. Ran `terraform apply`: created the bucket, registry, secret container, roles and budget.
5. Round-tripped a test index and database through the real bucket, then deleted the test objects.
6. Stored the Gemini key in Secrets Manager with the CLI (kept out of Terraform state).
7. Built the amd64 image, pushed it to ECR, and created the App Runner service.

## Cost

Rough monthly figures from AWS list prices as I remember them; check the AWS pricing pages and your Billing console for real numbers.

| Item | About |
|---|---|
| App Runner, one 2 GB instance provisioned (idle) | $10 |
| App Runner CPU while serving requests | cents at demo traffic |
| S3, ECR, Secrets Manager, logs | $1 or less |
| **Total if left running** | **$10-15** |

Gemini usage is billed by Google, not AWS. The budget alert is set to **$15 a month**. A budget **alerts**, it does not stop spending, so the real protection is pausing the service when you are not demoing.

## Operating it

```bash
# stop compute charges (state in S3 is kept) / start again
aws apprunner pause-service  --service-arn <arn>
aws apprunner resume-service --service-arn <arn>

# deploy a new version
docker buildx build --platform linux/amd64 -t <ecr repo>:latest --push .
aws apprunner start-deployment --service-arn <arn>

# logs: CloudWatch log groups named /aws/apprunner/ai-study-mentor/...
# delete everything
cd infra && terraform destroy -var budget_email=<email>
```

## Security notes

- The bucket blocks all public access and is encrypted at rest.
- The container's role is least-privilege: read/write its own prefix, read one secret.
- The API URL is public. Protection today is the per-IP rate limit and CORS. Set `API_KEY` if you want every request authenticated.
- The Gemini key was pasted into a chat session while setting this up. Rotate it in Google AI Studio and store the new value with `aws secretsmanager put-secret-value`.
- Terraform state (`terraform.tfstate`) is local and git-ignored. It does not contain the secret value, but it does list resource ids; do not commit it.

## Not done / honest gaps

- The web app (Next.js) is not hosted on AWS; only the API is.
- No custom domain, no WAF, no CI deploy (a GitHub Actions workflow using OIDC is the planned next step).
- The OpenAI-compatible provider has not been run against a live endpoint.
