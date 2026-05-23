# Policy as Code — Solution

Reference for [learning exercise-08](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-109-infrastructure-as-code/exercises/exercise-08-policy-as-code/README.md).

## Layout

```
exercise-08-policy-as-code/
├── README.md
├── opa/                       # Conftest policies for Terraform plans
│   ├── security.rego
│   ├── cost.rego
│   ├── naming.rego
│   └── compliance.rego
├── kyverno/                   # Kubernetes admission policies
│   ├── require-resource-limits.yaml
│   ├── disallow-host-namespace.yaml
│   └── require-image-signature.yaml
└── ci-examples/conftest.yml   # gate on every Terraform PR
```
