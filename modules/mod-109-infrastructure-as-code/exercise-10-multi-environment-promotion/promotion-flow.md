# Promotion Flow

## Stage 1 — PR
- Engineer pushes branch
- CI: `terraform plan -var-file=envs/dev/terraform.tfvars`
- CI: `terraform plan -var-file=envs/staging/terraform.tfvars`
- CI: `terraform plan -var-file=envs/prod/terraform.tfvars`
- Each posted as separate PR comment
- Reviewer checks: no unexpected destroys, costs look right, security policies pass

## Stage 2 — Merge → dev
- Auto-apply on `main` push
- Smoke tests run; if fail, auto-revert (revert PR opened)

## Stage 3 — Tag → staging
- Engineer cuts release: `git tag v0.4.0 && git push --tags`
- GitHub release workflow applies to staging
- 24h soak period; integration tests run

## Stage 4 — Approval → prod
- After staging soak: workflow paused on GitHub `production` environment
- Two designated approvers must approve in GitHub UI
- Apply runs; on failure, auto-revert via `terraform apply` of previous tagged state
