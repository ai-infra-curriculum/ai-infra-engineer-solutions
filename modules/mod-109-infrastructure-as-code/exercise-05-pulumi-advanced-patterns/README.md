# Pulumi Advanced Patterns — Solution

Reference for [learning exercise-05](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-109-infrastructure-as-code/exercises/exercise-05-pulumi-advanced-patterns/README.md).

Demonstrates: dynamic resources, ComponentResource, cross-stack reference, CrossGuard.

## Files

- `__main__.py` — entry point using all 4 patterns
- `components/ml_namespace.py` — ComponentResource: namespace + RBAC + secret + sa
- `policy_pack/__main__.py` — CrossGuard policy that requires `team` label
- `Pulumi.dev.yaml` — stack config
