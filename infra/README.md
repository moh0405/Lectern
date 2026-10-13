# AWS deployment

Terraform for the API, which runs as an AWS Lambda function with a public HTTPS Function URL. It also creates an S3 bucket
(search index + study database), an ECR registry, a Secrets Manager secret for the Gemini key, and a monthly budget alert.
See [docs/AWS.md](../docs/AWS.md) for the explanation.

Two steps, because the function needs an image and a key to exist first. Use `AWS_PROFILE` if you have several profiles.

```bash
cd infra
terraform init
terraform apply -var budget_email=you@example.com        # 1. bucket, registry, secret, budget alert

# store the key (kept out of Terraform state)
aws secretsmanager put-secret-value --secret-id ai-study-mentor/GEMINI_API_KEY --secret-string "$GEMINI_API_KEY"

# build and push the image (Lambda here is x86; use --provenance=false)
REPO=$(terraform output -raw ecr_repository)
aws ecr get-login-password | docker login --username AWS --password-stdin "${REPO%%/*}"
docker buildx build --platform linux/amd64 --provenance=false -t "${REPO}:latest" --push ..

terraform apply -var budget_email=you@example.com -var create_function=true   # 2. the function
terraform output api_url

# upload the search index built on your computer
S3_BUCKET=$(terraform output -raw bucket) S3_PREFIX=ai-study-mentor python -m backend.cloud_sync push
```

After step 2, store an API key (the API refuses requests without it):

```bash
python3 -c "import secrets;print(secrets.token_urlsafe(32))" > ~/.ai-study-mentor-api-key && chmod 600 ~/.ai-study-mentor-api-key
aws secretsmanager put-secret-value --secret-id ai-study-mentor/API_KEY --secret-string "$(cat ~/.ai-study-mentor-api-key)"
```

Variables: `monthly_budget_usd` (default 15), `daily_llm_limit` (default 200), `memory_mb` (default 2048), `cors_origins`, `region`.
Remove everything: `terraform destroy -var budget_email=x`.

Note the shell quirk: write `"${REPO}:latest"`, not `$REPO:latest`; zsh reads `:l` as a lowercase modifier.
