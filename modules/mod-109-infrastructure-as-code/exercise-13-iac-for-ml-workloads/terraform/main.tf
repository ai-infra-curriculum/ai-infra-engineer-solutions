terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.50" }
  }
}

provider "aws" { region = var.region }

module "vpc" {
  source = "git::https://github.com/me/tf-modules.git//modules/vpc?ref=modules/vpc/v1.2.0"
  name   = "ml-platform-${var.environment}"
  tags   = local.common_tags
}

module "eks" {
  source      = "git::https://github.com/me/tf-modules.git//modules/eks?ref=modules/eks/v1.4.0"
  name        = "ml-platform-${var.environment}"
  subnet_ids  = module.vpc.private_subnets
  k8s_version = "1.30"
  tags        = local.common_tags
  node_groups = {
    cpu = {
      instance_types = ["m5.xlarge"]
      desired_size = 3, min_size = 1, max_size = 8
      labels = { workload = "cpu" }
    }
    gpu = {
      instance_types = ["g5.xlarge"]
      desired_size = 1, min_size = 0, max_size = 4
      labels = { workload = "gpu", "nvidia.com/gpu" = "true" }
      taints = [{ key = "nvidia.com/gpu", value = "true", effect = "NO_SCHEDULE" }]
    }
  }
}

resource "aws_s3_bucket" "artifacts" {
  bucket = "ml-platform-${var.environment}-artifacts"
  tags   = local.common_tags
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_ecr_repository" "iris_api" {
  name                 = "ml-platform-iris-api"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
}

resource "aws_iam_role" "iris_api_irsa" {
  name = "ml-platform-${var.environment}-iris-api"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "sts:AssumeRoleWithWebIdentity"
      Principal = { Federated = module.eks.oidc_provider_arn }
      Condition = {
        StringEquals = {
          "${replace(module.eks.oidc_provider_arn, "/^arn:aws:iam::[0-9]+:oidc-provider\\//", "")}:sub" = "system:serviceaccount:iris:iris-api"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "iris_api_artifacts" {
  role = aws_iam_role.iris_api_irsa.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["s3:GetObject", "s3:ListBucket"]
      Resource = [
        aws_s3_bucket.artifacts.arn,
        "${aws_s3_bucket.artifacts.arn}/*",
      ]
    }]
  })
}

locals {
  common_tags = {
    Environment = var.environment
    Team        = "ml-platform"
    ManagedBy   = "terraform"
    CostCenter  = "ml-001"
  }
}
