# Helm Chart — Solution

Reference for [learning exercise-07](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-104-kubernetes/exercises/exercise-07-helm-chart-authoring/README.md).

```
exercise-07-helm-chart-authoring/
├── Chart.yaml
├── values.yaml
├── values.prod.yaml
├── templates/
│   ├── _helpers.tpl
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── hpa.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── servicemonitor.yaml
│   ├── serviceaccount.yaml
│   ├── NOTES.txt
│   └── tests/connection-test.yaml
└── ci-examples/helm-validate.yml
```
