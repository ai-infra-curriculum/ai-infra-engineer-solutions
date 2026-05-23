# Multi-Environment Promotion Pipeline — Solution

Reference for [learning exercise-10](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-109-infrastructure-as-code/exercises/exercise-10-multi-environment-promotion/README.md).

```
exercise-10-multi-environment-promotion/
├── README.md
├── envs/{dev,staging,prod}/terraform.tfvars
├── main.tf, variables.tf
├── ci-examples/{plan-on-pr.yml, apply-on-merge.yml}
└── promotion-flow.md
```

## Flow

```
git push branch → PR → plan(dev) + plan(staging) + plan(prod) posted as comments
              → review
              → merge to main → apply(dev)            [auto]
              → tag v0.X.Y                              → apply(staging)         [auto]
              → manual approval (GitHub environment)   → apply(prod)              [gated]
```
