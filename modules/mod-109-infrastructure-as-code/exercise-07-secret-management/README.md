# Secret Management (Vault + ESO) — Solution

Reference for [learning exercise-07](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-109-infrastructure-as-code/exercises/exercise-07-secret-management/README.md).

## Files

- `vault/policy.hcl` — minimal-privilege policy for the ESO service principal
- `terraform/vault.tf` — Terraform reads Vault during provisioning (no plaintext in state)
- `k8s/external-secret.yaml` — Kubernetes-side: ESO syncs secret from Vault
- `k8s/cluster-secret-store.yaml` — ESO ClusterSecretStore pointing at Vault
- `k8s/store-rotation-cronjob.yaml` — every 24h, Vault rotates the secret
