# SCP 1: deny disabling CloudTrail in all workload accounts
resource "aws_organizations_policy" "deny_cloudtrail_disable" {
  name = "deny-cloudtrail-disable"
  type = "SERVICE_CONTROL_POLICY"
  content = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Deny"
      Action = ["cloudtrail:StopLogging", "cloudtrail:DeleteTrail"]
      Resource = "*"
    }]
  })
}

resource "aws_organizations_policy_attachment" "deny_cloudtrail_disable_workloads" {
  policy_id = aws_organizations_policy.deny_cloudtrail_disable.id
  target_id = aws_organizations_organizational_unit.workloads.id
}

# SCP 2: production OU forbids creating IAM users (must use SSO)
resource "aws_organizations_policy" "no_iam_users_in_prod" {
  name = "no-iam-users-in-prod"
  type = "SERVICE_CONTROL_POLICY"
  content = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Deny"
      Action = ["iam:CreateUser", "iam:CreateAccessKey"]
      Resource = "*"
    }]
  })
}

resource "aws_organizations_policy_attachment" "no_iam_users_in_prod_attach" {
  policy_id = aws_organizations_policy.no_iam_users_in_prod.id
  target_id = aws_organizations_organizational_unit.prod.id
}

# SCP 3: region restriction (only allow us-west-2 and us-east-1)
resource "aws_organizations_policy" "region_restriction" {
  name = "region-restriction"
  type = "SERVICE_CONTROL_POLICY"
  content = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Deny"
      NotAction = [
        "iam:*", "organizations:*", "route53:*", "cloudfront:*", "support:*",
      ]
      Resource = "*"
      Condition = {
        StringNotEquals = {
          "aws:RequestedRegion" = ["us-west-2", "us-east-1"]
        }
      }
    }]
  })
}

resource "aws_organizations_policy_attachment" "region_restriction_attach" {
  policy_id = aws_organizations_policy.region_restriction.id
  target_id = aws_organizations_organizational_unit.workloads.id
}

# SCP 4: deny launching extreme instance types
resource "aws_organizations_policy" "deny_extreme_instance_types" {
  name = "deny-extreme-instance-types"
  type = "SERVICE_CONTROL_POLICY"
  content = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Deny"
      Action = "ec2:RunInstances"
      Resource = "arn:aws:ec2:*:*:instance/*"
      Condition = {
        StringEquals = {
          "ec2:InstanceType" = ["x1.32xlarge", "x1e.32xlarge", "u-24tb1.metal"]
        }
      }
    }]
  })
}

resource "aws_organizations_policy_attachment" "deny_extreme_instance_types_attach" {
  policy_id = aws_organizations_policy.deny_extreme_instance_types.id
  target_id = aws_organizations_organizational_unit.workloads.id
}
