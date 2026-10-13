# AWS infrastructure for the API. Two steps (see infra/README.md):
#   1. terraform apply                          -> bucket, registry, secrets, budget alert
#   2. push the image, then
#      terraform apply -var create_service=true -> App Runner service
terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
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
  default = 10
}

variable "create_service" {
  type        = bool
  default     = false
  description = "Create the App Runner service. Needs an image in the registry and the Gemini key stored first."
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

# --- App Runner --------------------------------------------------------------------------------
data "aws_iam_policy_document" "build_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["build.apprunner.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "tasks_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["tasks.apprunner.amazonaws.com"]
    }
  }
}

# lets App Runner pull the image
resource "aws_iam_role" "access" {
  name               = "${var.name}-apprunner-access"
  assume_role_policy = data.aws_iam_policy_document.build_trust.json
}

resource "aws_iam_role_policy_attachment" "access" {
  role       = aws_iam_role.access.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

# what the running container may do: its own bucket prefix and its own secret, nothing else
resource "aws_iam_role" "instance" {
  name               = "${var.name}-apprunner-instance"
  assume_role_policy = data.aws_iam_policy_document.tasks_trust.json
}

data "aws_iam_policy_document" "instance" {
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

resource "aws_iam_role_policy" "instance" {
  role   = aws_iam_role.instance.id
  policy = data.aws_iam_policy_document.instance.json
}

resource "aws_apprunner_service" "api" {
  count        = var.create_service ? 1 : 0
  service_name = var.name

  source_configuration {
    authentication_configuration { access_role_arn = aws_iam_role.access.arn }
    auto_deployments_enabled = false
    image_repository {
      image_identifier      = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
      image_repository_type = "ECR"
      image_configuration {
        port = "8000"
        runtime_environment_variables = {
          S3_BUCKET    = aws_s3_bucket.data.bucket
          S3_PREFIX    = var.name
          CORS_ORIGINS = var.cors_origins
          AWS_REGION   = var.region
        }
        runtime_environment_secrets = {
          GEMINI_API_KEY = aws_secretsmanager_secret.gemini.arn
        }
      }
    }
  }

  instance_configuration {
    cpu               = "1024"
    memory            = "2048"
    instance_role_arn = aws_iam_role.instance.arn
  }

  health_check_configuration {
    protocol = "HTTP"
    path     = "/health"
  }

  # one instance only: the SQLite study database and the index are single-writer
  auto_scaling_configuration_arn = aws_apprunner_auto_scaling_configuration_version.single[0].arn

  depends_on = [aws_iam_role_policy_attachment.access]
}

resource "aws_apprunner_auto_scaling_configuration_version" "single" {
  count                           = var.create_service ? 1 : 0
  auto_scaling_configuration_name = "${var.name}-single"
  min_size                        = 1
  max_size                        = 1
}

output "ecr_repository" { value = aws_ecr_repository.api.repository_url }
output "bucket" { value = aws_s3_bucket.data.bucket }
output "gemini_secret" { value = aws_secretsmanager_secret.gemini.name }
output "service_url" { value = var.create_service ? "https://${aws_apprunner_service.api[0].service_url}" : null }
