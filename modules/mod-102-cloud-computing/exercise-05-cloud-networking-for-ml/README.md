# ML-Aware VPC — Solution

Reference solution for [learning exercise-05-cloud-networking-for-ml](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/tree/main/lessons/mod-102-cloud-computing/exercises/exercise-05-cloud-networking-for-ml/README.md).

A Terraform module producing a 3-AZ VPC with public + private-app + private-data subnet tiers, per-AZ NAT, VPC Endpoints (S3, ECR, CloudWatch, SSM, Secrets Manager), per-tier security groups, and Flow Logs.

## Layout

```
exercise-05-cloud-networking-for-ml/
├── README.md
├── terraform/
│   ├── main.tf, variables.tf, outputs.tf, versions.tf
│   ├── endpoints.tf
│   └── security_groups.tf
└── scripts/
    ├── test-connectivity.sh   # smoke test from each tier
    └── apply.sh
```

## Quick start

```bash
cd terraform
terraform init
terraform apply -var name=ml-dev -var-file=../tfvars/dev.tfvars
```

## Test connectivity

```bash
./scripts/test-connectivity.sh
```

Spawns one tiny EC2 in each subnet tier and verifies expected reachability per `NETWORK.md`.

## Cost projection

Approximate monthly cost for prod-shape (3-AZ, multi-NAT, 5 interface endpoints):

| Item | Monthly |
|---|---|
| NAT Gateway × 3 | ~$98 |
| Interface Endpoints × 5 × 3 AZ | ~$110 |
| Flow Logs to CloudWatch | ~$10 |
| **Total** | **~$220** |

(Plus per-byte data charges; modest for ML workloads with S3 Gateway Endpoint.)
