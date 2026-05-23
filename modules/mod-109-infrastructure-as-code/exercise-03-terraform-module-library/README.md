# Terraform Module Library — Solution

Reference for [learning exercise-03](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-109-infrastructure-as-code/exercises/exercise-03-terraform-module-library/README.md).

## Layout

```
exercise-03-terraform-module-library/
├── README.md
├── modules/
│   ├── vpc/           # main.tf, variables.tf, outputs.tf, versions.tf
│   ├── eks/
│   └── rds/
├── examples/{vpc,eks,rds}/main.tf
└── test/test_vpc.go        # terratest example
```

## Versioning + publishing

```bash
git tag modules/vpc/v1.2.0
git push --tags
# Consumers:
# module "vpc" {
#   source  = "git::https://github.com/me/tf-modules.git//modules/vpc?ref=modules/vpc/v1.2.0"
# }
```

Generated docs via `terraform-docs markdown table modules/vpc > modules/vpc/README.md`.
