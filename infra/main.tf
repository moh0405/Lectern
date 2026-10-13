# AWS infrastructure for the API, running as a Lambda function. Two steps (see infra/README.md):
#   1. terraform apply                           -> bucket, registry, secret, budget alert
#   2. push the image, then
#      terraform apply -var create_function=true -> Lambda function + public HTTPS URL
terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}

provider "aws" {
  region = var.region
  default_tags { tags = { Project = "ai-study-mentor" } }
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "name" {
  type    = string
  default = "ai-study-mentor"
}

variable "budget_email" {
  type        = string
  description = "Where spend alerts are sent."
}

variable "monthly_budget_usd" {
  type    = number
  default = 15
}

variable "create_function" {
  type        = bool
  default     = false
  description = "Create the Lambda function. Needs an image in the registry and the Gemini key stored first."
}

variable "memory_mb" {
  type        = number
  default     = 2048
  description = "Lambda memory. CPU scales with it; the embedding model needs about 1 GB."
}

variable "image_tag" {
  type    = string
  default = "latest"
}

variable "cors_origins" {
  type        = string
  default     = "http://localhost:3000"
  description = "Comma-separated origins allowed to call the API (the deployed web app)."
}

data "aws_caller_identity" "me" {}

locals {
  bucket = "${var.name}-${data.aws_caller_identity.me.account_id}"
}

# --- Storage: the search index and study database --------------------------------------------
resource "aws_s3_bucket" "data" {
  bucket = local.bucket
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket     = aws_s3_bucket.data.id
  depends_on = [aws_s3_bucket_versioning.data]
  rule {
    id     = "expire-old-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration { noncurrent_days = 14 }
  }
}

# --- Container registry ------------------------------------------------------------------------
resource "aws_ecr_repository" "api" {
  name         = var.name
  force_delete = true # lets `terraform destroy` remove it even when images are inside
  image_scanning_configuration { scan_on_push = true }
}

resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "keep the 5 newest images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 5 }
      action       = { type = "expire" }
    }]
  })
}

# --- Secrets: containers only. Values are set with the CLI so they never enter Terraform state. --
resource "aws_secretsmanager_secret" "gemini" {
  name                    = "${var.name}/GEMINI_API_KEY"
  recovery_window_in_days = 0
}

# --- Spend alert -------------------------------------------------------------------------------
resource "aws_budgets_budget" "monthly" {
  name         = "${var.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 50
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_email]
  }
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.budget_email]
  }
}

# --- Lambda ------------------------------------------------------------------------------------
data "aws_iam_policy_document" "lambda_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# what the running function may do: write logs, use its own bucket prefix, read its own secret
resource "aws_iam_role" "function" {
  name               = "${var.name}-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

resource "aws_iam_role_policy_attachment" "logs" {
  role       = aws_iam_role.function.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "function" {
  statement {
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.data.arn}/${var.name}/*"]
  }
  statement {
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.data.arn]
  }
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.gemini.arn]
  }
}

resource "aws_iam_role_policy" "function" {
  role   = aws_iam_role.function.id
  policy = data.aws_iam_policy_document.function.json
}

resource "aws_lambda_function" "api" {
  count         = var.create_function ? 1 : 0
  function_name = var.name
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
  role          = aws_iam_role.function.arn
  memory_size   = var.memory_mb
  timeout       = 120
  architectures = ["x86_64"]

  ephemeral_storage { size = 2048 }

  environment {
    variables = {
      S3_BUCKET        = aws_s3_bucket.data.bucket
      S3_PREFIX        = var.name
      GEMINI_SECRET_ID = aws_secretsmanager_secret.gemini.name
      CORS_ORIGINS     = var.cors_origins
      # Lambda only allows writing under /tmp
      UPLOAD_DIR   = "/tmp/data/uploaded_files"
      STORE_DIR    = "/tmp/data/vector_store"
      ANALYTICS_DB = "/tmp/data/analytics.db"
      STUDY_DB     = "/tmp/data/study.db"
      # Lambda Web Adapter: stream answers token by token, and wait for /health before serving
      AWS_LWA_INVOKE_MODE          = "response_stream"
      AWS_LWA_READINESS_CHECK_PATH = "/health"
      AWS_LWA_PORT                 = "8000"
    }
  }

  depends_on = [aws_iam_role_policy_attachment.logs, aws_iam_role_policy.function]
}

resource "aws_lambda_function_url" "api" {
  count              = var.create_function ? 1 : 0
  function_name      = aws_lambda_function.api[0].function_name
  authorization_type = "NONE"
  invoke_mode        = "RESPONSE_STREAM"
}

# A public function URL needs both permissions since late 2025.
resource "aws_lambda_permission" "url" {
  count                  = var.create_function ? 1 : 0
  statement_id           = "AllowPublicUrl"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.api[0].function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "invoke" {
  count                    = var.create_function ? 1 : 0
  statement_id             = "AllowPublicInvoke"
  action                   = "lambda:InvokeFunction"
  function_name            = aws_lambda_function.api[0].function_name
  principal                = "*"
  invoked_via_function_url = true
}

output "ecr_repository" { value = aws_ecr_repository.api.repository_url }
output "bucket" { value = aws_s3_bucket.data.bucket }
output "gemini_secret" { value = aws_secretsmanager_secret.gemini.name }
output "api_url" { value = var.create_function ? aws_lambda_function_url.api[0].function_url : null }
