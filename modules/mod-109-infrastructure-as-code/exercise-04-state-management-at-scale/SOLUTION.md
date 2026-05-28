# SOLUTION — Exercise 04: Terraform State Management at Scale

> Read this after you have a working Terraform module and at least two
> environments to think about. The exercise is a *layout and operations*
> problem: design a state strategy that survives 50+ projects, 4
> environments, and a corrupted state file at 2 a.m. The worked strategy
> and the bootstrap stack ship alongside this file in
> [`STRATEGY.md`](./STRATEGY.md) and [`bootstrap/main.tf`](./bootstrap/main.tf).

## 1. Solution overview

Exercise 04 asks you to design a Terraform state strategy that scales to
roughly 50 projects × 4 environments without the failure modes that catch
small teams the first time a second engineer joins. A passing submission
demonstrates four properties:

1. **Remote state with locking, from the first commit** — S3 (or
   equivalent) for storage, DynamoDB (or equivalent) for the lock; never
   a local `terraform.tfstate` for anything shared.
2. **State split per blast-radius unit** — networking, k8s, data, and
   service layers each have their own state file, and environments are
   separated above that. A `terraform apply` to the "service" layer must
   not be able to touch the network layer.
3. **A bootstrap stack that creates the backend** — the S3 bucket,
   DynamoDB lock table, and KMS key for state encryption are themselves
   provisioned by Terraform (with a *local* backend), since the rest of
   the estate depends on them existing.
4. **A documented corruption-recovery and migration path** — S3 object
   versioning is the durable backup; `terraform state mv` is the
   migration tool; both are written down before they are needed.

This factors the module-level rationale (see
[`../SOLUTION.md`](../SOLUTION.md), Decisions 1 and 3, plus the
"one backend per environment, not one backend per state file" trade-off)
into the concrete artifacts the exercise asks you to produce.

## 2. Implementation

This is the worked answer — the model state layout, the bootstrap
stack, the per-project `backend.tf`, and the recovery procedures that
together constitute the implementation a passing submission must
reproduce.

### Layout: one backend, prefix-per-(env, project)

The S3 key layout in [`STRATEGY.md`](./STRATEGY.md) is the model:

```
s3://company-tf-state/
  prod/{network,eks,rds,...}/terraform.tfstate
  staging/{network,eks,...}/terraform.tfstate
  dev/{...}/terraform.tfstate
```

One bucket per organization; prefix separation per environment and per
project. The IAM boundary lives at the prefix, not the bucket: production
state is readable only by production-deploy roles, etc. This is the
trade-off called out in [`../SOLUTION.md`](../SOLUTION.md) — bucket
creation requires elevated permissions, prefixes are cheap.

50 projects × 4 environments = ~200 state files. Cross-stack reads use
explicit `data "terraform_remote_state"`; circular reads are forbidden.

### Bootstrap stack ([`bootstrap/main.tf`](./bootstrap/main.tf))

The chicken-and-egg problem: you cannot use an S3 backend before the S3
bucket exists. The bootstrap stack is the one place a *local* backend is
acceptable, and it provisions:

- the state bucket, with versioning enabled and all public access
  blocked,
- a KMS key (with rotation) for server-side encryption of state objects,
- the `terraform-locks` DynamoDB table (pay-per-request, `LockID`
  partition key).

Bucket versioning is the durable backup for state corruption recovery;
deletion protection and MFA-delete should be added on top for prod.

### Per-project `backend.tf`

Every other project under the org points at the bucket and lock table
with the matching prefix:

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

The `key` is the only thing that changes between projects/environments;
everything else is identical across the estate. This makes per-project
`backend.tf` files trivially DRY (or trivially templatable with
Terragrunt, if the team adopts it later — see
[`../SOLUTION.md`](../SOLUTION.md), "When to go beyond this
implementation").

### Workspace policy

Workspaces are used **only** for per-developer ephemeral test stacks.
Long-lived environments (prod / staging / dev) each have their own state
file — never a workspace inside a shared state. Conflating
workspaces with environments is one of the failure modes this layout
exists to avoid.

### State corruption recovery (runbook shape)

When state is corrupted or accidentally truncated:

1. **Freeze the world** — pause CI and tell the team to stop running
   `terraform`. Concurrent applies are how a single bad state becomes
   two.
2. **Restore from S3 versioning** —
   `aws s3api list-object-versions --bucket company-tf-state --prefix <key>`
   to find the last-good version, then `aws s3api copy-object` (or
   `get-object` + re-`put`) to promote it back to the current version.
3. **Validate** — `terraform plan` should show no unexpected changes.
   If it does, the wrong version was restored.
4. **Resume** — re-enable CI, post an incident note.

### State migration

When moving resources between modules (a refactor, not a re-create):

```bash
terraform state list                         # confirm the source address
terraform state mv module.old_vpc module.vpc # do the move
terraform plan                                # expect no changes
```

Tag a backup version of the state object in S3 before running
`state mv`; it is the rollback if the move is wrong. Use
`terraform import` only when adopting an existing resource into state,
and always follow it with a `plan` to confirm the configuration matches
the imported resource — see common mistake 4 in
[`../SOLUTION.md`](../SOLUTION.md).

## 3. Validation steps

These verify the bootstrap stack and a representative per-project
backend. Run them once after first apply and then as part of any
"is the foundation still healthy" check.

```bash
# 1. Bootstrap apply is clean and bucket is in the expected configuration.
cd bootstrap
terraform init
terraform validate
terraform fmt -check
terraform plan -out=tfplan
terraform apply tfplan

# 2. Versioning, public-access block, and SSE are actually enabled.
aws s3api get-bucket-versioning      --bucket company-tf-state \
  | grep -i '"Status": "Enabled"'
aws s3api get-public-access-block    --bucket company-tf-state \
  | grep -iE '"(BlockPublicAcls|IgnorePublicAcls|BlockPublicPolicy|RestrictPublicBuckets)": true'
aws s3api get-bucket-encryption      --bucket company-tf-state \
  | grep -i '"SSEAlgorithm": "aws:kms"'

# 3. Lock table exists and uses the expected partition key.
aws dynamodb describe-table --table-name terraform-locks \
  | grep -iE '"AttributeName": "LockID"|"BillingMode(Summary)?": "PAY_PER_REQUEST"'

# 4. A second concurrent apply on the same prefix is blocked by the lock.
cd ../  # any project pointing at the prefix
terraform init
terraform plan &                # in one shell
terraform plan                  # in another — expect a lock acquisition error

# 5. Cross-stack reads work without coupling configuration.
#    Consumers read producer outputs via data.terraform_remote_state.
terraform console <<<'data.terraform_remote_state.network.outputs.vpc_id'
```

A correct deployment shows: bucket versioning on, public access blocked,
SSE-KMS in force, DynamoDB lock table reachable, concurrent applies
serialized by the lock, and cross-stack reads returning real outputs.

## 4. Rubric / review checklist

| Criterion | Weight | Pass condition |
|---|---|---|
| Remote backend + locking | 20% | S3 (or equivalent) backend with a DynamoDB lock table; no local state for shared stacks |
| Bootstrap stack present | 15% | Bucket + lock table + KMS key provisioned by Terraform with a local backend; versioning + public-access block + SSE enabled |
| Prefix layout per (env, project) | 20% | One backend, one prefix per environment, one prefix per project; ~50×4 layout is explicitly described |
| Workspace discipline | 10% | Workspaces used only for ephemeral dev stacks; prod/staging/dev each have their own state file |
| Recovery runbook | 15% | Freeze → restore from S3 versioning → validate → resume; concrete commands, not vague intent |
| Migration / import safety | 10% | `terraform state mv` and `terraform import` documented with a pre-move state backup and a follow-up `plan` |
| Cross-stack reads | 10% | Uses `data.terraform_remote_state`; no circular reads between stacks |

Borderline cases: a submission with remote state but no bootstrap stack
fails the "Bootstrap stack present" criterion — the chicken-and-egg
problem is part of the exercise. A submission that uses workspaces for
prod/staging/dev fails "Workspace discipline" regardless of how clean
the rest is.

## 5. Common mistakes

1. **Local state for shared stacks.** Multiple engineers + a local
   `terraform.tfstate` = corrupted state by the end of the week. Remote
   state with locking, from the first commit (see
   [`../SOLUTION.md`](../SOLUTION.md), Decision 1).
2. **One giant state file for the whole environment.** A single state
   means a `terraform apply` to the service layer has IAM to touch
   networking. Split per blast-radius unit (Decision 3 in
   [`../SOLUTION.md`](../SOLUTION.md)).
3. **State committed to git.** State files contain resource attributes
   (and sometimes secrets). Always remote; backups are S3 object
   versions, not Git history (common mistake 3 in
   [`../SOLUTION.md`](../SOLUTION.md)).
4. **Workspaces as environments.** Workspaces share a state file with
   per-workspace key prefixes; an operator error can wipe the wrong
   environment. Use one state file per long-lived environment, and
   reserve workspaces for ephemeral dev stacks.
5. **`terraform import` without a follow-up `plan`.** The resource is in
   state but the configuration does not match; the next apply tries to
   recreate it (common mistake 4 in [`../SOLUTION.md`](../SOLUTION.md)).
6. **No bucket versioning.** S3 versioning is the durable backup for
   state corruption. Without it, the recovery path is "rebuild from
   memory."
7. **Circular `terraform_remote_state` reads.** Stack A reads Stack B
   reads Stack A. The apply order becomes undefined; break the cycle by
   moving the shared resource into a third stack consumed by both.
8. **No KMS-managed encryption on the state bucket.** State objects can
   contain secrets; relying on default S3 encryption alone foregoes the
   key-rotation and audit story that comes with a customer-managed key.

## 6. References

- Local exercise context: [`STRATEGY.md`](./STRATEGY.md) — the worked
  layout, locking design, recovery runbook, and migration commands.
- Local exercise context: [`bootstrap/main.tf`](./bootstrap/main.tf) —
  the bootstrap stack for state bucket, KMS key, and lock table.
- Module rationale: [`../SOLUTION.md`](../SOLUTION.md) — Decisions 1
  (remote state + locking) and 3 (state split per environment + per
  service), plus the "one backend per environment" trade-off.
- Learning exercise brief: `lessons/mod-109-infrastructure-as-code/exercises/exercise-04-state-management-at-scale`
  ([README](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-109-infrastructure-as-code/exercises/exercise-04-state-management-at-scale/README.md)).
- Official Terraform documentation — S3 backend:
  https://developer.hashicorp.com/terraform/language/backend/s3
- Official Terraform documentation — State and remote state data source:
  https://developer.hashicorp.com/terraform/language/state
  and https://developer.hashicorp.com/terraform/language/state/remote-state-data
- Official Terraform documentation — `terraform state mv` /
  `terraform import`:
  https://developer.hashicorp.com/terraform/cli/commands/state/mv
  and https://developer.hashicorp.com/terraform/cli/commands/import
- Official AWS documentation — S3 versioning:
  https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html
