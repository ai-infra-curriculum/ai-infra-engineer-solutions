data "aws_caller_identity" "current" {}

output "cluster_name" {
  value = aws_eks_cluster.this.name
}

output "cluster_endpoint" {
  value = aws_eks_cluster.this.endpoint
}

# IRSA trust anchor: the IAM OIDC provider ARN derived from the cluster's
# OIDC issuer. Consumed by callers wiring service-account IAM roles.
output "oidc_provider_arn" {
  value = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/${replace(aws_eks_cluster.this.identity[0].oidc[0].issuer, "https://", "")}"
}
