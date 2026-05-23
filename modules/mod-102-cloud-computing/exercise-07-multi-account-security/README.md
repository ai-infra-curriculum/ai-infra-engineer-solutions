# Multi-Account Security Architecture — Solution

Reference solution for [learning exercise-07-multi-account-security](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/tree/main/lessons/mod-102-cloud-computing/exercises/exercise-07-multi-account-security/README.md).

Terraform module + scripts for AWS Organizations with OUs, SCPs, central CloudTrail audit, IAM Identity Center permission sets, and a cross-account CI/CD role.

## Layout

```
exercise-07-multi-account-security/
├── README.md
├── terraform/
│   ├── organizations.tf        # OUs + accounts
│   ├── scps.tf                 # service control policies
│   ├── audit.tf                # central CloudTrail + S3
│   ├── identity_center.tf      # SSO permission sets
│   └── cicd_role.tf            # cross-account deployer role
└── scripts/
    └── test-controls.sh        # verify SCPs actually block forbidden actions
```

## Quick start

```bash
cd terraform
terraform init
terraform apply -var management_account_email=admin@example.com
```

This creates the OU structure and applies SCPs. You'll need to verify SCPs in a workload account afterward (see scripts/test-controls.sh).
