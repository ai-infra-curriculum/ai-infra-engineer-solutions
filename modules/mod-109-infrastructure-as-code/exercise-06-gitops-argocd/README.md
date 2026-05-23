# GitOps with ArgoCD — Solution

Reference for [learning exercise-06](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-109-infrastructure-as-code/exercises/exercise-06-gitops-argocd/README.md).

## Layout

```
exercise-06-gitops-argocd/
├── README.md
├── apps/
│   ├── app-of-apps.yaml       # root Application managing all child Apps
│   ├── iris-api.yaml
│   ├── prometheus.yaml
│   └── ingress.yaml
└── applicationsets/
    ├── multi-env.yaml          # one App per dev/stage/prod
    └── multi-cluster.yaml      # one App per registered cluster
```
