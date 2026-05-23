terraform {
  required_providers {
    vault = { source = "hashicorp/vault", version = "~> 4.2" }
    aws   = { source = "hashicorp/aws",   version = "~> 5.50" }
  }
}

# Read OpenAI API key from Vault; consumed by application config
data "vault_kv_secret_v2" "openai" {
  mount = "kv"
  name  = "ml-platform/openai"
}

# Pass via ssm parameter so it never lives in Terraform state plaintext
resource "aws_ssm_parameter" "openai" {
  name        = "/ml-platform/openai-key"
  type        = "SecureString"
  value       = data.vault_kv_secret_v2.openai.data["api_key"]
  description = "Synced from Vault; do not modify by hand"
  tags        = { ManagedBy = "terraform", Source = "vault" }
}
