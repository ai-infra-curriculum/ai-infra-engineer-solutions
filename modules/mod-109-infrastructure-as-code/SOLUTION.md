# SOLUTION — Infrastructure as Code

> Read this *after* you have provisioned the reference
> infrastructure yourself. This document explains *why* the IaC
> patterns are shaped the way they are and which Terraform
> conventions actually matter at scale.

## What this module is really teaching

Most engineers learn Terraform syntax. The harder skill is
Terraform *organization*:

- How to split state so blast radius is bounded.
- How to manage module dependencies without tangling them.
- How to handle secrets without committing them.
- How to test IaC before applying it.

The reference solutions are opinionated about layout because the
layout you choose at the start determines what's painful at scale.

## Architectural decisions and *why*

### Decision 1: Remote state with locking, from the first commit

Every reference module uses an S3 + DynamoDB backend (or its GCP /
Azure equivalents). The reason: local state files get out of sync
the first time a second engineer joins, and the recovery is
manual diff-and-merge. Remote state with locking prevents that
class of failure entirely.

### Decision 2: Three-layer module hierarchy

The reference layout is:

```
infrastructure/
├── modules/          # Reusable, parameterized
├── stacks/           # Environment-specific compositions
└── platforms/        # Cross-stack platform bootstrapping
```

The reason: flat repos become unmanageable past ~10 services.
The three-layer hierarchy keeps blast radius bounded — a change
to one stack doesn't affect another — while letting modules
remain DRY.

### Decision 3: State split per environment + per service

Production / staging / dev each have their own state. Within
each environment, networking / data / compute / services live in
separate state files. The reason: a Terraform apply to "the
service layer" should never have permissions to touch the
networking layer. State splits are how IaC enforces that.

### Decision 4: Variables vs. locals discipline

Reference modules use:

- **Variables**: things the caller has to supply (environment,
  region).
- **Locals**: derived values computed from variables (tags,
  computed names, decisions based on environment).

The anti-pattern is using variables for everything; the result is
a 50-input module nobody can use without reading the source.

### Decision 5: ``terraform-docs`` + pre-commit hooks

Every module ships with auto-generated ``README.md`` from
``terraform-docs``. The reason: hand-maintained module docs go
stale within a week. Auto-generated docs stay in sync.

### Decision 6: ``checkov`` / ``tfsec`` in CI, not local

Static analysis runs in CI, not on every local plan. The reason:
local runs slow down iteration; CI runs catch problems before
merge. Both surfaces use the same rule set so engineers can
shift-left if they want to.

## Trade-offs we deliberately accepted

### Terraform over Pulumi / CDK

Terraform's HCL is less expressive than Pulumi's TypeScript or
AWS CDK's whatever. The reason for choosing it anyway: HCL forces
constraints. Engineers can't sneak a ``for`` loop into a Terraform
module that nobody understands. The trade-off is real but the
operational simplicity at scale is real too.

### One backend per environment, not one backend per state file

We use S3 prefix-based separation rather than separate S3 buckets
per state. The reason: bucket creation requires elevated
permissions; prefix separation is just a string change. The IAM
boundary is at the prefix.

### No multi-cloud-abstracted modules

Modules are cloud-specific. A team needing multi-cloud writes
provider-specific modules and composes them at the stack layer.
Trying to abstract cloud provider differences inside modules
produces lowest-common-denominator interfaces that aren't useful.

## Common mistakes graders see

1. **Hardcoded resource names**: ``foo-prod-db`` baked into the
   module makes it unreusable in another environment.
2. **Wide IAM policies**: ``ec2:*`` because nobody knew exactly
   what was needed. Least-privilege from the start; expand
   surgically.
3. **State file committed to git**: state files contain secrets.
   Always use remote backends.
4. **``terraform import`` with no follow-up**: the imported
   resource lives in state but the configuration doesn't match;
   next apply tries to recreate it.
5. **Manual changes outside Terraform**: drift accumulates
   silently. Always use ``terraform plan`` as part of incident
   response to detect drift.
6. **No ``terraform fmt`` enforcement**: every PR has formatting
   noise on top of real changes. Wire ``terraform fmt`` into
   pre-commit.

## When to go beyond this implementation

- Adopt **Terragrunt** for DRY backend / provider configuration
  across stacks.
- Move to **Atlantis** or **Spacelift** for PR-driven Terraform
  apply with proper approvals.
- Add **policy-as-code** (OPA / Sentinel) for pre-apply policy
  checks beyond what tfsec / checkov catch.

## Related curriculum touchpoints

- ``engineer/mod-102-cloud-computing`` — the cloud primitives
  these IaC modules provision.
- ``engineer/mod-104-kubernetes`` — Kubernetes clusters
  provisioned via Terraform here.
- ``architect/projects/project-302-multicloud-infra`` — the
  architectural pattern for multi-cloud IaC.
- ``ml-platform/mod-001-platform-fundamentals`` — IaC patterns
  applied at platform scale.
