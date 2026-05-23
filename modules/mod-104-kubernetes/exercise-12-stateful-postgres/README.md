# Stateful Postgres on K8s (CloudNative-PG) — Solution

Reference for [learning exercise-12](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-104-kubernetes/exercises/exercise-12-stateful-postgres/README.md).

3-replica streaming replication + S3 backups + PITR + monitoring.

## Files

- `cnpg-operator.sh` — install operator
- `cluster.yaml` — Cluster CR (3 replicas + backups + monitoring)
- `restore.yaml` — PITR restore demo
