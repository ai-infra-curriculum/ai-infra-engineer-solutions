# Local stand-in for the published VPC module (see ../../main.tf for the
# version-pinned registry source it represents). Exposes the same interface the
# root stack consumes so the configuration validates without network access.

variable "name" { type = string }

variable "tags" {
  type    = map(string)
  default = {}
}

output "private_subnets" {
  description = "Private subnet IDs consumed by downstream modules."
  value       = []
}
