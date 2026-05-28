# SOLUTION — Exercise 04: Terraform State Management at Scale

> Per-exercise solution for
> [learning exercise-04](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-109-infrastructure-as-code/exercises/exercise-04-state-management-at-scale/README.md).
> This factors the relevant pieces of the
> [module-level SOLUTION.md](../SOLUTION.md) (state-split rationale)
> together with the worked layout in
> [`STRATEGY.md`](./STRATEGY.md) and the bootstrap Terraform under
> [`bootstrap/`](./bootstrap/). Read it *after* attempting your own
> design.

## 1. Solution overview

This exercise is a **state-architecture design + bootstrap
implementation**: lay out remote state for a fleet of Terraform
projects (≈50 projects × 4 environments) so that runs are locked,
state is recoverable, and the IAM blast radius of any single apply
is bounded.

The reference answer is **one state file per (project,
environment)** stored under prefix-based separation in a single
S3 bucket, with DynamoDB locking and KMS-encrypted state. The full
prefix layout, locking table, backend stanza, workspace policy,
corruption-recovery runbook, and state-migration recipe are in
[`STRATEGY.md`](./STRATEGY.md). The bootstrap stack that creates
the bucket and lock table — the only stack allowed to use a
`local` backend — is in [`bootstrap/main.tf`](./bootstrap/main.tf).

This document explains *why* the layout is shaped that way, ties
each piece to the module-level architectural decisions, and gives
graders a rubric.

## 2. Worked answer or implementation

The complete worked layout lives in [`STRATEGY.md`](./STRATEGY.md);
the runnable bootstrap is in [`bootstrap/`](./bootstrap/). The
summary below ties each component to the architectural decision
that motivates it (decisions are drawn from the
[module-level SOLUTION.md](../SOLUTION.md)).

### Prefix-based layout: `<env>/<project>/terraform.tfstate`

```text
s3://company-tf-state/
  prod/{network,eks,rds}/terraform.tfstate
  staging/{network,eks,...}/terraform.tfstate
  dev/...
```

50 projects × 4 environments = 200 state files in a single bucket.
Cross-project reads go through explicit
`data.terraform_remote_state`; there is no implicit sharing.

**Decision 3 — state split per environment + per service.** An
apply to the service layer must not have permission to touch the
networking layer; the state split is the boundary that enforces
that, and IAM policies attach to the prefix.

**Trade-off — one bucket, many prefixes (not one bucket per
state).** Bucket creation requires elevated permissions; prefix
separation is a string change. The module-level rationale calls
this out explicitly: the IAM boundary is at the prefix.

### Per-project `backend.tf`

Each project pins its own key under the shared bucket:

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

**Decision 1 — remote state with locking from the first commit.**
Local state files desync the first time a second engineer joins;
the S3 backend + DynamoDB lock prevents that class of failure
entirely.

### DynamoDB lock table

One table, `terraform-locks`, partition key `LockID`, TTL on
`Expiration` (~15 min) so a crashed client releases its lock
without manual intervention. Provisioned in the bootstrap stack
under [`bootstrap/main.tf`](./bootstrap/main.tf) with
`billing_mode = "PAY_PER_REQUEST"` so it costs effectively nothing
at idle.

### Bucket hardening (in bootstrap)

The bootstrap stack creates the state bucket with:

- **Versioning** enabled — every state write is a recoverable
  object version. This is the corruption-recovery primitive.
- **KMS encryption** at rest with a dedicated CMK
  (`enable_key_rotation = true`,
  `deletion_window_in_days = 30`).
- **Public-access block** with all four flags on.

For production, also enable bucket deletion protection and
MFA-delete (per [`STRATEGY.md`](./STRATEGY.md) §Best practices —
MFA-delete is a one-time root-credential operation and so is not
managed by the Terraform stack itself).

### Workspace policy: ephemeral only

`terraform workspace` is used **only** for short-lived
per-developer test stacks. Every long-lived environment
(prod/staging/dev) gets its own discrete state file under its own
prefix — not a workspace inside a shared state. Workspaces inside
a shared state file are the most common way teams accidentally
re-couple environments they tried to separate.

### State-corruption recovery (runbook)

When state is corrupted or accidentally truncated, the documented
sequence is:

1. **Stop everything** — pause CI; tell the team to stop running
   `terraform`.
2. **Restore from S3 versioning** —
   `aws s3api list-object-versions ...`, pick the last-known-good
   version, restore it as the current object.
3. **Validate** — `terraform plan` shows no unexpected changes
   before resuming.
4. **Resume** — re-enable CI, post the incident note.

Versioning + KMS is the *only* backup. State files are never
committed to Git.

### State migration between modules

When moving resources between modules (e.g. extracting a sub-
module), the pattern is:

```bash
terraform state list                       # inspect first
terraform state mv module.old_vpc module.vpc
```

Always tag a backup S3 object version before the `mv` so a
rollback is one `aws s3api copy-object` away.

### The bootstrap chicken-and-egg

The bootstrap stack is the one piece of the system that *cannot*
live in the S3 backend it is creating, so it uses
`backend "local"` (see line 7 of
[`bootstrap/main.tf`](./bootstrap/main.tf)). Its `terraform.tfstate`
is checked into a tightly-scoped admin repository, not the
application repos. Once bootstrap has run, every other project
uses the S3 backend.

## 3. Validation steps

This is a mixed design + implementation artifact. Validation
runs in two phases.

### Static validation (no AWS account required)

1. **Terraform formatting and syntax** —
   `terraform -chdir=bootstrap fmt -check`
   and `terraform -chdir=bootstrap validate` (after
   `terraform -chdir=bootstrap init -backend=false`). Both must
   pass before the bootstrap is reviewable.
2. **Markdown** — `markdownlint-cli2` passes on this file and
   `STRATEGY.md`; see repo
   [`.markdownlint.jsonc`](../../../.markdownlint.jsonc).
3. **Decision trace** — for each piece of the design (prefix
   layout, lock table, bucket hardening, workspace policy), the
   reviewer can name which module-level decision it instantiates.

### Live validation (with an AWS account)

1. **Apply bootstrap** —
   `terraform -chdir=bootstrap init && terraform -chdir=bootstrap apply -var=state_bucket_name=<name>`.
   Confirm: S3 bucket created, versioning on, public access
   blocked, KMS CMK rotation on, DynamoDB lock table present.
2. **Configure a downstream project** to use the S3 backend with
   a key under a prefix and run `terraform init` followed by
   `terraform plan`. Confirm a lock entry appears in the
   `terraform-locks` DynamoDB table while the plan is running.
3. **Concurrent lock test** — run a second `terraform plan` from
   another shell against the same key while the first one is
   holding the lock; confirm the second client blocks on the lock
   with a clear error referencing `LockID`.
4. **Recovery drill** — list object versions for one state file
   (`aws s3api list-object-versions --bucket <name> --prefix <key>`);
   confirm at least two versions exist after a second apply, and
   that restoring the prior version brings the state back.

## 4. Rubric or review checklist

Score each dimension; a strong submission addresses all six.
Point weights are pedagogical scaffolding for graders, not
external metrics.

| Dimension | Looking for | Weight |
|---|---|---|
| State split & blast radius | One state file per (project, environment); cross-project access only via `data.terraform_remote_state` (Decision 3) | 20 |
| Remote backend & locking | S3 backend wired in every project from day one; DynamoDB lock table with `LockID` partition key (Decision 1) | 20 |
| Bucket hardening | Versioning, KMS encryption with rotation, public-access block, deletion protection, MFA-delete called out for prod | 15 |
| Bootstrap stack | A dedicated `backend "local"` bootstrap that creates the bucket + lock table and is the *only* stack to use local state | 10 |
| Workspace policy | Workspaces restricted to ephemeral per-dev stacks; long-lived envs each get their own discrete state file | 10 |
| Recovery & migration runbooks | A documented corruption-recovery sequence using S3 versioning, and a `terraform state mv` migration recipe with pre-move backup | 15 |
| Documentation discipline | `STRATEGY.md` reads as a runbook a teammate could execute solo; key names, table names, and IAM-boundary intent are explicit | 10 |

Review checklist (binary):

- [ ] One state file per (project, environment); no shared
      multi-env state.
- [ ] S3 backend wired in every project; DynamoDB lock table
      present.
- [ ] State bucket has versioning, KMS encryption with rotation,
      and a public-access block.
- [ ] Bootstrap stack uses `backend "local"` and provisions the
      bucket + lock table.
- [ ] Workspaces are not used for prod/staging/dev.
- [ ] Corruption-recovery runbook present and references S3 object
      versions.
- [ ] State-migration recipe present and recommends backing up the
      object version before `terraform state mv`.
- [ ] State files are never committed to Git.

## 5. Common mistakes

Drawn from the module-level grader notes
([SOLUTION.md](../SOLUTION.md) §"Common mistakes graders see"),
specialized to state management:

1. **State file committed to git** — state files contain secrets;
   always use a remote backend (module mistake #3).
2. **Shared single state for all environments** — collapses
   Decision 3's IAM blast-radius boundary; one bad apply touches
   every environment.
3. **Workspaces used for prod/staging/dev** — re-couples the
   environments the prefix layout was designed to separate.
4. **Missing DynamoDB lock table** — two engineers run
   `terraform apply` concurrently and the second clobbers the
   first's state.
5. **No bucket versioning** — there is no recovery primitive when
   state is corrupted; the bucket's object history *is* the
   backup.
6. **`terraform import` with no follow-up** — the imported
   resource lives in state but the configuration doesn't match;
   next apply tries to recreate it (module mistake #4).
7. **Manual changes outside Terraform** — drift accumulates
   silently; always include `terraform plan` in incident response
   (module mistake #5).
8. **Bootstrap stack stored in the S3 backend it creates** — a
   chicken-and-egg that locks teams out of recovery when the
   bucket is gone.

## 6. References

Local exercise context:

- Learning exercise README —
  <https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-109-infrastructure-as-code/exercises/exercise-04-state-management-at-scale/README.md>
- Module rationale — [`../SOLUTION.md`](../SOLUTION.md)
- Reference layout & runbooks — [`./STRATEGY.md`](./STRATEGY.md)
- Bootstrap Terraform — [`./bootstrap/main.tf`](./bootstrap/main.tf)

Official project / standard documentation:

- Terraform — Backends (S3 backend, locking semantics) —
  <https://developer.hashicorp.com/terraform/language/settings/backends/s3>
- Terraform — `terraform state` command reference —
  <https://developer.hashicorp.com/terraform/cli/commands/state>
- Terraform — Workspaces —
  <https://developer.hashicorp.com/terraform/language/state/workspaces>
- AWS S3 — Object versioning —
  <https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html>
- AWS S3 — Default encryption (SSE-KMS) —
  <https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucket-encryption.html>
- AWS S3 — Block public access —
  <https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html>
- AWS DynamoDB — TTL —
  <https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html>
- AWS KMS — Key rotation —
  <https://docs.aws.amazon.com/kms/latest/developerguide/rotate-keys.html>
- NIST AI Risk Management Framework (governance / configuration
  management context for IaC change control) —
  <https://www.nist.gov/itl/ai-risk-management-framework>
