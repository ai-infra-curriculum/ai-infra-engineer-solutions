# SOLUTION — Exercise 04: Terraform State Management at Scale

> Read this *after* you have produced your own state-management layout
> for a fleet of ~50 projects across prod / staging / dev. The
> reference design and the bootstrap stack already live alongside this
> file in [`STRATEGY.md`](./STRATEGY.md) and
> [`bootstrap/main.tf`](./bootstrap/main.tf); this document explains
> *why* that shape is the one to copy.

## 1. Solution overview

The exercise is a *layout and operations* problem, not a syntax problem.
A passing submission has three non-negotiable properties:

1. **One state file per blast-radius unit.** Network, EKS cluster, and
   data tier each get their own state file. A `terraform apply` to the
   service layer must not have permissions to touch networking.
2. **Remote backend with locking, from the first commit.** S3 +
   DynamoDB (encrypted, versioned, lock-table-backed). No local
   `terraform.tfstate` for anything shared.
3. **A defined recovery path.** State corruption, accidental
   deletion, and resource-move operations all have written procedures
   that a teammate could execute under pressure.

The reference layout — `s3://company-tf-state/<env>/<project>/terraform.tfstate`
with a single DynamoDB lock table — yields 50 projects × 4 environments
= 200 state files, each independently lockable, each behind its own
IAM prefix boundary.

## 2. Implementation

The worked design is [`STRATEGY.md`](./STRATEGY.md); the
chicken-and-egg "who creates the bucket" answer is
[`bootstrap/main.tf`](./bootstrap/main.tf). The pieces:

### Backend layout (one state per project × environment)

```
s3://company-tf-state/
  prod/{network,eks,rds,...}/terraform.tfstate
  staging/{network,eks,rds,...}/terraform.tfstate
  dev/{network,eks,rds,...}/terraform.tfstate
```

Cross-stack reads go through `data.terraform_remote_state` — never
through implicit assumptions. Circular reads are prohibited; if two
stacks need to read each other, one of them is mis-scoped.

### `backend.tf` per project

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

The `key` is the only thing that changes per project. The bucket,
lock table, and KMS key are shared across every project in the
account.

### Bootstrap stack (`bootstrap/main.tf`)

The bootstrap stack is the *only* stack that uses a local backend,
because something has to create the remote backend itself. It
provisions:

- An S3 bucket (versioning on, public access blocked, KMS-encrypted).
- A customer-managed KMS key with rotation enabled and a 30-day
  deletion window.
- A DynamoDB lock table on `LockID` with on-demand billing.

After the first `terraform apply`, the bootstrap state itself should
be moved into the new bucket (or held in a separately-protected
location); subsequent state changes to the bootstrap itself are
rare and reviewed.

### Workspaces — where they are and are not used

`terraform workspace` is reserved for *ephemeral, per-developer test
stacks*. Long-lived environments (prod / staging / dev) each get
their own state file under their own key prefix — they are not
workspaces. The reason is IAM: workspaces share a single state
object, so prod-vs-dev separation degrades to "the trusted user
typed the right name." Prefix separation makes the boundary an IAM
policy on `arn:aws:s3:::company-tf-state/prod/*`.

### State migration between modules

Refactoring that moves a resource between modules is a *state
operation*, not a code change. The procedure:

```bash
terraform state list           # confirm the source address
terraform state mv module.old_vpc module.vpc
terraform plan                 # MUST show zero changes
```

Always tag the prior S3 object version before the move so the
rollback is a single `aws s3api copy-object` away.

### Corruption recovery runbook

1. **Stop everything.** Pause CI; tell the team not to run
   Terraform against the affected key.
2. **Restore from S3 versioning.** `aws s3api list-object-versions
   --bucket company-tf-state --prefix prod/eks/terraform.tfstate`,
   pick the last-good version, copy it back as the current object.
3. **Validate.** `terraform plan` against the restored state must
   show no unexpected changes.
4. **Resume.** Re-enable CI and post an incident note that names
   the restored version ID.

## 3. Validation steps

These are *verification gates*, not a one-shot script. Run each
after the relevant change; stop if any fails.

```bash
# Bootstrap stack is healthy and the backend exists.
aws s3api get-bucket-versioning --bucket company-tf-state \
  | grep -i enabled
aws s3api get-bucket-encryption --bucket company-tf-state
aws dynamodb describe-table --table-name terraform-locks \
  | grep -E '"TableStatus": "ACTIVE"'
aws s3api get-public-access-block --bucket company-tf-state

# A project stack uses the remote backend, not local state.
grep -A6 'backend "s3"' backend.tf            # present
test ! -f terraform.tfstate                   # absent locally

# Locking actually engages.
terraform plan &                              # run 1
terraform plan                                # run 2: should block on the lock

# State is encrypted with the project KMS key.
aws s3api head-object --bucket company-tf-state \
  --key prod/eks/terraform.tfstate \
  | grep -E 'ServerSideEncryption|SSEKMSKeyId'

# Cross-stack reads are explicit, not assumed.
grep -R 'data "terraform_remote_state"' .     # every cross-stack read shows up
```

## 4. Rubric / review checklist

| Criterion | Weight | Pass condition |
|---|---|---|
| State split per blast radius | 20% | Network / cluster / data / services each have their own state file; no single `apply` spans them |
| Remote backend with locking | 20% | S3 backend with DynamoDB lock table; no local state for shared stacks |
| Encryption + versioning + public-access block | 15% | KMS encryption (CMK with rotation), bucket versioning on, public access fully blocked |
| Bootstrap chain solved | 10% | A dedicated bootstrap stack (local backend) provisions bucket + lock table + KMS; documented as "run once per account" |
| Workspace discipline | 10% | Workspaces only for ephemeral developer stacks; prod / staging / dev are separate state files, not workspaces |
| Migration procedure | 10% | A written `terraform state mv` procedure with a pre-move version-ID backup |
| Corruption recovery runbook | 15% | An ordered, executable runbook — pause, restore from S3 version, validate, resume — not "restore from backup" as a vague intent |

Borderline: a submission that has remote state but no documented
recovery path, or that uses workspaces to separate prod from staging,
is not safe to operate at this scale and should not pass — those are
the properties the exercise exists to teach.

## 5. Common mistakes

1. **Workspaces for environment separation.** Workspaces share a
   single state object; the prod/dev boundary collapses to a string
   typed at the CLI. Use distinct backend `key`s instead.
2. **Single mega-state for the whole environment.** A
   `prod/terraform.tfstate` that holds network + cluster + data means
   every apply has permission to wreck everything. Split per blast
   radius.
3. **No bootstrap story.** "How does the S3 backend get created?" with
   no answer leaves a chicken-and-egg crater. The reference answer is
   a dedicated bootstrap stack with a local backend, run once.
4. **State file committed to git.** State contains secrets in plain
   text. Always remote, always KMS-encrypted, never in version
   control.
5. **`terraform state mv` without a versioned backup.** The S3 object
   version *before* the move is the only safe rollback. Note the
   version ID first, then move.
6. **Circular `data.terraform_remote_state` reads.** If stack A reads
   stack B and B reads A, one of the boundaries is wrong; merge the
   two or invert the dependency.
7. **Wide IAM on the state bucket.** A single IAM role with
   `s3:*` on the whole bucket defeats the point of prefix separation.
   Roles should be scoped to their `<env>/<project>/*` prefix.

## 6. References

- Local exercise context:
  - [`STRATEGY.md`](./STRATEGY.md) — the reference layout, locking
    table schema, workspace rule, and migration / recovery
    procedures.
  - [`bootstrap/main.tf`](./bootstrap/main.tf) — the bootstrap stack
    that provisions the bucket, KMS key, and lock table with a local
    backend.
- Module rationale: [`../SOLUTION.md`](../SOLUTION.md) — Decisions 1
  ("remote state with locking from the first commit") and 3 ("state
  split per environment + per service") are the module-level form of
  the policies applied here.
- Learning exercise brief: `lessons/mod-109-infrastructure-as-code/exercises/exercise-04-state-management-at-scale`
  ([README](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-109-infrastructure-as-code/exercises/exercise-04-state-management-at-scale/README.md)).
- Official Terraform documentation — S3 backend:
  https://developer.hashicorp.com/terraform/language/backend/s3
- Official Terraform documentation — State and `terraform state` CLI:
  https://developer.hashicorp.com/terraform/language/state
  and https://developer.hashicorp.com/terraform/cli/commands/state
- Official Terraform documentation — Workspaces:
  https://developer.hashicorp.com/terraform/language/state/workspaces
- Official Terraform documentation — Remote state data source:
  https://developer.hashicorp.com/terraform/language/state/remote-state-data
