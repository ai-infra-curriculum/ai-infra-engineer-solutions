# Core Resources Mastery — Solution

Reference for [learning exercise-03](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-104-kubernetes/exercises/exercise-03-core-resources-mastery/README.md).

One manifest per resource with a real ML-infra use case.

## Files

| Resource | File | Use case |
|---|---|---|
| Pod | `pod.yaml` | one-off debug pod with curl + dig |
| ReplicaSet | (skipped — Deployment uses it; not authored directly) | |
| Deployment | `deployment.yaml` | stateless serving |
| StatefulSet | `statefulset.yaml` | Postgres with stable network identity |
| DaemonSet | `daemonset.yaml` | per-node GPU exporter |
| Job | `job.yaml` | one-shot training |
| CronJob | `cronjob.yaml` | nightly batch eval |
| ConfigMap | `configmap.yaml` | non-secret app config |
| Secret | `secret.yaml` | API keys |
| PV | `pv.yaml` | manually-provisioned EBS |
| PVC | `pvc.yaml` | claim against StorageClass |
| Service | `service.yaml` | ClusterIP + headless |
| Ingress | `ingress.yaml` | external HTTP routing |
| ServiceAccount + RBAC | `rbac.yaml` | pod-scoped permissions |
