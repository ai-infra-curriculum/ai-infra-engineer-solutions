# Multi-Tenancy — Solution

Reference for [learning exercise-14](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-104-kubernetes/exercises/exercise-14-resource-quotas-multitenancy/README.md).

3 teams; each gets namespace + ResourceQuota + LimitRange + NetworkPolicy + RBAC.

```
exercise-14-resource-quotas-multitenancy/
├── README.md
├── apply.sh             # idempotent setup for all 3 teams
├── team-template/
│   ├── namespace.yaml
│   ├── resource-quota.yaml
│   ├── limit-range.yaml
│   ├── network-policy.yaml
│   └── rbac.yaml
└── teams.yaml           # team config
```
