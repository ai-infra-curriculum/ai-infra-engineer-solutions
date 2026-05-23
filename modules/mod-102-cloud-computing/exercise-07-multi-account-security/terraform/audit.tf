# Org-wide CloudTrail writing to a central audit bucket (in the management account here for simplicity).
# In production, target a separate audit account.

resource "aws_s3_bucket" "audit" {
  bucket = "company-org-cloudtrail-${data.aws_caller_identity.current.account_id}"
  force_destroy = false
}

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket_versioning" "audit" {
  bucket = aws_s3_bucket.audit.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_policy" "audit" {
  bucket = aws_s3_bucket.audit.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = { Service = "cloudtrail.amazonaws.com" }
        Action = ["s3:GetBucketAcl", "s3:PutObject"]
        Resource = [aws_s3_bucket.audit.arn, "${aws_s3_bucket.audit.arn}/*"]
        Condition = { StringEquals = { "AWS:SourceArn" = "arn:aws:cloudtrail:*:*:trail/org-audit" } }
      },
    ]
  })
}

resource "aws_cloudtrail" "org" {
  name = "org-audit"
  s3_bucket_name = aws_s3_bucket.audit.id
  is_organization_trail = true
  is_multi_region_trail = true
  include_global_service_events = true
  enable_logging = true
  depends_on = [aws_s3_bucket_policy.audit]
}
