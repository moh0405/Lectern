# Lets GitHub Actions deploy the API without any stored AWS keys (OIDC). Off by default; see infra/README.md.
#   terraform apply -var enable_ci_deploy=true   -> then set the repo variable AWS_DEPLOY_ROLE_ARN to the output

variable "enable_ci_deploy" {
  type        = bool
  default     = false
  description = "Create the OIDC provider and the role GitHub Actions assumes to push the image and update the function."
}

variable "github_repo" {
  type        = string
  default     = "moh0405/Lectern"
  description = "owner/name allowed to assume the deploy role (main branch only)."
}

resource "aws_iam_openid_connect_provider" "github" {
  count          = var.enable_ci_deploy ? 1 : 0
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_policy_document" "ci_trust" {
  count = var.enable_ci_deploy ? 1 : 0
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github[0].arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repo}:ref:refs/heads/main"]
    }
  }
}

resource "aws_iam_role" "ci_deploy" {
  count              = var.enable_ci_deploy ? 1 : 0
  name               = "${var.name}-ci-deploy"
  assume_role_policy = data.aws_iam_policy_document.ci_trust[0].json
}

data "aws_iam_policy_document" "ci_deploy" {
  count = var.enable_ci_deploy ? 1 : 0
  statement {
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    actions = [
      "ecr:BatchCheckLayerAvailability", "ecr:InitiateLayerUpload", "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload", "ecr:PutImage", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer",
    ]
    resources = [aws_ecr_repository.api.arn]
  }
  statement {
    actions   = ["lambda:UpdateFunctionCode", "lambda:GetFunction", "lambda:GetFunctionConfiguration"]
    resources = ["arn:aws:lambda:${var.region}:${data.aws_caller_identity.me.account_id}:function:${var.name}"]
  }
}

resource "aws_iam_role_policy" "ci_deploy" {
  count  = var.enable_ci_deploy ? 1 : 0
  name   = "deploy"
  role   = aws_iam_role.ci_deploy[0].id
  policy = data.aws_iam_policy_document.ci_deploy[0].json
}

output "ci_deploy_role_arn" { value = var.enable_ci_deploy ? aws_iam_role.ci_deploy[0].arn : null }
