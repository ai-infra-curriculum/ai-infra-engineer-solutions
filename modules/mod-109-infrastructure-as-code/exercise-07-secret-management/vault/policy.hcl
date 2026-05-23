# Vault policy granting ESO read access on ml-platform secrets ONLY.
path "kv/data/ml-platform/*" {
  capabilities = ["read"]
}

path "kv/metadata/ml-platform/*" {
  capabilities = ["list", "read"]
}

# DB credentials are dynamic — read-only on the role
path "database/creds/iris-api" {
  capabilities = ["read"]
}

# No write, no list anywhere else.
