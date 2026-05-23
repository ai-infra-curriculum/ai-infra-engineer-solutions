# Terraform State Management at Scale — Strategy

Reference for [learning exercise-04](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-109-infrastructure-as-code/exercises/exercise-04-state-management-at-scale/README.md).

## Layout: backend per (project, environment)

```
s3://company-tf-state/
  prod/
    network/terraform.tfstate
    eks/terraform.tfstate
    rds/terraform.tfstate
  staging/
    network/terraform.tfstate
    eks/terraform.tfstate
    ...
  dev/
    ...
```

50 projects × 4 environments = 200 state files. No project depends on another's
state file except via explicit `data.terraform_remote_state`.

## Locking

DynamoDB table `terraform-locks`:
- partition key: `LockID`
- TTL on `Expiration` to recover from crashed clients (15 min)

## backend.tf per project

```hcl
terraform {
  backend "s3" {
    bucket         = "company-tf-state"
    key            = "prod/eks/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
    kms_key_id     = "arn:aws:kms:us-east-1:111122223333:key/abc-def"
  }
}
```

## Workspace pattern (used sparingly)

Use workspaces ONLY for per-developer ephemeral test stacks; never for prod/staging/dev.
Each long-lived environment gets its own state file (not a workspace).

## State corruption recovery

1. **Stop everything**: pause CI; tell team to not run terraform.
2. **Restore from S3 versioning**: `aws s3api list-object-versions ...` → pick last-good version.
3. **Validate**: `terraform plan` shows no unexpected changes.
4. **Resume**: re-enable CI, post incident note.

## State migration

When moving resources between modules:
```bash
terraform state mv module.old_vpc module.vpc
# Inspect with `terraform state list` first; always tag a backup version of state.
```

## Best practices

- One state per blast-radius unit (network, k8s cluster, db are separate).
- `data.terraform_remote_state` is fine for cross-stack reads, but DON'T create circular reads.
- Bucket versioning ON, deletion protection ON, MFA-delete ON for prod.
- State files never committed to Git; backups are S3 object versions, not Git history.
