# Local stand-in for the published EKS module (see ../../main.tf for the
# version-pinned registry source it represents). Exposes the same interface the
# root stack consumes so the configuration validates without network access.

variable "name"        { type = string }
variable "subnet_ids"  { type = list(string) }
variable "k8s_version" { type = string }
variable "node_groups" { type = any }

variable "tags" {
  type    = map(string)
  default = {}
}

output "oidc_provider_arn" {
  description = "IAM OIDC provider ARN used for IRSA role trust policies."
  value       = "arn:aws:iam::000000000000:oidc-provider/${var.name}"
}
