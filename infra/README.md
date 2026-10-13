# AWS deployment

Terraform for the API: an S3 bucket (search index + study database), an ECR registry, a Secrets Manager
secret for the Gemini key, a monthly budget alert, and an App Runner service.

Run in two steps because the service needs an image and a key to exist first. Use `--profile` or `AWS_PROFILE` if you have several.

```bash
cd infra
terraform init
terraform apply -var budget_email=you@example.com        # 1. bucket, registry, secret, budget alert

# store the key (kept out of Terraform state)
aws secretsmanager put-secret-value --secret-id ai-study-mentor/GEMINI_API_KEY --secret-string "$GEMINI_API_KEY"

# build and push the image (linux/amd64 is what App Runner runs)
REPO=$(terraform output -raw ecr_repository)
aws ecr get-login-password | docker login --username AWS --password-stdin "${REPO%%/*}"
docker buildx build --platform linux/amd64 -t "$REPO:latest" --push ..

terraform apply -var budget_email=you@example.com -var create_service=true   # 2. the service
terraform output service_url
```

Stop paying for compute between demos: `aws apprunner pause-service --service-arn ...` (resume with `resume-service`).
Remove everything: `terraform destroy -var budget_email=x`.

Design notes: one instance only, because SQLite and the index are single-writer. The container's role can read and
write only its own bucket prefix and read only its own secret. The bucket is private, encrypted and versioned.
