# SOLUTION — Cloud Computing

> Read this *after* you have stood up the reference cloud
> deployments yourself. This document explains the *why* behind
> the architectural choices: when to pick which compute primitive,
> how to think about cloud-cost vs. control trade-offs, and which
> patterns transfer across AWS/GCP/Azure.

## What this module is really teaching

The cloud is not "Linux but on someone else's server." It is a
**menu of trade-offs** between control, cost, operational burden,
and lock-in. Engineers who don't understand the menu end up
running EC2 fleets where Lambda would do, or chasing Kubernetes
when ECS Fargate would have shipped in a week.

The exercises in this module force you to make the menu choice
deliberately — and to defend the choice in writing.

## Architectural decisions and *why*

### Decision 1: Multi-cloud abstractions are not the default

The reference solutions are deliberately **single-cloud** in their
default. Multi-cloud abstractions (Terraform with provider-
agnostic modules, custom orchestration layers) add complexity
that's only justified when the business actually serves
multi-cloud workloads.

**Anti-pattern to avoid**: writing every deployment "multi-cloud-
ready from day one." 99% of the time the second cloud never
happens, and the abstraction tax is paid forever.

### Decision 2: Start with managed services; fall back to raw IaaS

For each workload, the reference solutions try managed services
first (RDS over self-managed Postgres, SQS over Kafka, ECS Fargate
over self-managed EC2), and only drop to raw IaaS when there's a
specific reason (cost at scale, custom kernel requirements,
specific networking).

The reason: managed services trade money for operational burden.
At small scale, the burden is the bigger cost. At large scale, the
money is. Cross the threshold deliberately.

### Decision 3: Compute primitive selection by workload shape

The exercises explicitly map workload shape to compute primitive:

| Workload | First choice | Why |
|---|---|---|
| Stateless HTTP | ECS Fargate / Cloud Run / Container Apps | Managed scaling |
| Async batch | Lambda / Cloud Functions | Pay-per-execution |
| Long-running ML training | EC2 spot + autoscaling group | Cost + GPU access |
| Stateful service | ECS on EC2 with EBS | Persistent local storage |
| Multi-tenant orchestration | EKS / GKE / AKS | Real workloads need it |

The choice is rarely "Kubernetes by default." Kubernetes is the
right answer for #5; for #1-4 it's usually overkill.

### Decision 4: Networking-as-code from the start

VPCs, subnets, security groups, and NACLs are defined in Terraform
in the reference solutions — not clicked through the console.
The reason: networking changes are the most expensive mistakes to
revert. Code makes them reviewable and reproducible.

### Decision 5: One AWS account per environment (or its equivalent)

The reference architecture puts production, staging, and dev in
separate AWS accounts (or GCP projects, or Azure subscriptions).
The reason: account-level boundaries are the only ones cloud
providers actually enforce. VPC-level boundaries leak via IAM,
shared services, and the inevitable "let me just put this in
prod-vpc for a minute" pattern.

## Trade-offs we deliberately accepted

### Terraform over CloudFormation / Bicep

The reference solutions use Terraform across all clouds, even
when the cloud-native IaC (CloudFormation, ARM, Bicep) is
arguably better integrated. The reason: a team that knows
Terraform can work on any cloud. A team that knows CloudFormation
*only* is locked in.

### Spot instances with explicit eviction handling

Spot/preemptible instances cut costs 60-80% but require designing
for eviction. The reference solutions wire up eviction notice
handlers and require workloads to be either stateless or
checkpointed. We treat eviction handling as a normal operating
condition, not an exception.

### English-language tagging conventions

All resources are tagged with ``env``, ``service``, ``owner``,
``cost-center`` in English. Multi-locale tagging is possible but
adds complexity that's not justified for a teaching curriculum.

## Common mistakes graders see

1. **No tagging discipline**: untagged resources are unattributable
   at cost-allocation time and become "who owns this?" mysteries.
2. **Default VPC for production**: AWS's default VPC has overly
   permissive routes and no flow logs. Always create a custom VPC.
3. **Hardcoded AWS account IDs**: makes the Terraform unrunnable
   in a different account. Parameterize.
4. **Security groups with ``0.0.0.0/0``**: works once, becomes a
   security incident later. Reference other security groups, not
   IP ranges.
5. **No state backend for Terraform**: local state file gets lost
   the first time a teammate clones the repo. Always configure
   remote state with locking (S3 + DynamoDB, GCS, Azure Storage).
6. **Forgetting cost alerts**: cloud bills surprise teams that
   didn't set them up. Budget alerts cost nothing.

## When to go beyond this implementation

- Add **AWS Config / GCP Asset Inventory** for compliance-as-code.
- Move to **service control policies (SCPs)** at the org level so
  account-level limits can't be bypassed.
- Implement **automated cost anomaly detection** — your CFO will
  thank you.

## Related curriculum touchpoints

- ``engineer/mod-103-containerization`` — what runs on top of the
  cloud foundation.
- ``engineer/mod-104-kubernetes`` — the orchestrator layer.
- ``engineer/mod-109-infrastructure-as-code`` — deeper Terraform
  patterns.
- ``architect/projects/project-302-multicloud-infra`` — the
  architecture-level companion.
