# K8s Fundamentals — Solution

Reference for [learning exercise-01](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-104-kubernetes/exercises/exercise-01-k8s-fundamentals/README.md).

```
exercise-01-k8s-fundamentals/
├── README.md
├── namespace.yaml, configmap.yaml, secret.yaml
├── deployment.yaml, service.yaml, ingress.yaml, hpa.yaml
└── apply.sh
```

```bash
./apply.sh
kubectl get pods,svc,ingress,hpa -n iris
```
