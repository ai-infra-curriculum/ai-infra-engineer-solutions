# Cross-account role for CI/CD to deploy into a workload account.
# This file goes in the WORKLOAD account, not management.
# Shown here as a reference; in real use, apply via terraform-workspaces per account.

variable "shared_services_account_id" {
  type = string
  default = "123456789012"
}

variable "cicd_external_id" {
  type = string
  default = "ml-cicd-prod"
}

resource "aws_iam_role" "cicd_deployer" {
  count = 0   # disabled by default; enable per-account
  name = "cicd-deployer"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "sts:AssumeRole"
      Principal = { AWS = "arn:aws:iam::${var.shared_services_account_id}:role/github-actions" }
      Condition = {
        StringEquals = { "sts:ExternalId" = var.cicd_external_id }
      }
    }]
  })
}

resource "aws_iam_role_policy" "cicd_deployer" {
  count = 0
  role = aws_iam_role.cicd_deployer[0].id
  name = "deploy-only"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ecr:*",
        "ecs:UpdateService", "ecs:DescribeServices",
        "eks:DescribeCluster", "eks:UpdateNodegroupConfig",
        "s3:GetObject", "s3:PutObject",
      ]
      Resource = "*"   # scope down further per real ARNs
    }]
  })
}
