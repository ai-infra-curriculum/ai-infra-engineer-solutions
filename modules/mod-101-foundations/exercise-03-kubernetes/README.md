# Exercise 03: Kubernetes Walkthrough — Reference Materials

Reference for [learning exercise-03-kubernetes.md](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-101-foundations/exercises/exercise-03-kubernetes.md).

Reference manifests for deploying the hello-flask service (from ex-02) to a kind cluster.

## Files

```
exercise-03-kubernetes/
├── README.md
├── kind-config.yaml         # cluster with port-forward 8080→30080
├── deployment.yaml          # Deployment + readiness/liveness
├── service.yaml             # NodePort
└── scripts/
    └── run-end-to-end.sh    # create cluster, load image, apply, smoke test
```

## Quick start

```bash
./scripts/run-end-to-end.sh
curl http://localhost:8080/health
```
