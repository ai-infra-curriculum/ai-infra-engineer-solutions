# Deployment Guide

This document covers running the stack on Kubernetes for production-ish use. It assumes you already know how to read a Helm chart and that you have a cluster (EKS, GKE, AKS, or a self-managed Kubeadm cluster ≥ 1.27) ready.

The components, in dependency order:

1. **Postgres** — backend store for MLflow and metadata DB for Airflow
2. **MinIO** — S3-compatible artifact and feature storage
3. **MLflow tracking server** — depends on Postgres + MinIO
4. **Airflow** — depends on Postgres + MinIO; talks to MLflow
5. **Predictor service** — depends on MLflow registry
6. **Prometheus + Grafana** — scrape all of the above

For development you can use the bundled `docker-compose.yml` (single command, no K8s). For production, follow the K8s path below.

---

## 1. Namespaces and isolation

```
mlops-system        # Postgres, MinIO, MLflow
airflow             # Airflow scheduler, webserver, workers, triggerer
ml-staging          # Staging predictor for new versions
ml-serving          # Production predictor (blue/green)
monitoring          # Prometheus, Grafana, Alertmanager
```

Each namespace has a `NetworkPolicy` that defaults to deny-all ingress, with explicit allows:

- `ml-serving` → `mlops-system:5000` (MLflow registry read)
- `ml-serving` → `mlops-system:9000` (MinIO artifact read)
- `airflow` → `mlops-system:5000` (MLflow read/write)
- `airflow` → `mlops-system:9000` (MinIO read/write)
- `monitoring` → all namespaces on metrics ports (`/metrics`)

Without these policies, a compromised predictor pod could exfiltrate the entire `s3://mlflow/` bucket. With them, it can only read what it needs.

---

## 2. Postgres

We run **Postgres 14.10** via the [Bitnami Postgres HA chart](https://github.com/bitnami/charts/tree/main/bitnami/postgresql-ha) (version 12.x). Two databases: `mlflow` and `airflow`, each with their own user.

### 2.1 Helm values

```yaml
# kubernetes/postgres/values.yaml
postgresql:
  username: postgres
  existingSecret: postgres-credentials
  database: postgres
  repmgrPassword: ""        # from existingSecret
  postgresqlPassword: ""    # from existingSecret

pgpool:
  replicaCount: 2
  adminUsername: admin
  existingSecret: postgres-credentials

persistence:
  enabled: true
  storageClass: gp3         # AWS EBS gp3; substitute for your provider
  size: 100Gi

resources:
  requests:
    cpu: 1
    memory: 2Gi
  limits:
    cpu: 4
    memory: 8Gi

metrics:
  enabled: true             # exposes /metrics for Prometheus
  serviceMonitor:
    enabled: true
```

The HA chart gives you streaming replication and automatic failover via repmgr. For a small deployment (<10 K runs/month), a single Postgres instance is fine — use the non-HA `bitnami/postgresql` chart instead and skip pgpool.

### 2.2 Initial database setup

After the chart installs, create the two app databases:

```bash
kubectl -n mlops-system exec -it postgres-postgresql-ha-postgresql-0 -- bash -c "
  PGPASSWORD=\$POSTGRES_PASSWORD psql -U postgres <<'SQL'
    CREATE DATABASE mlflow;
    CREATE DATABASE airflow;
    CREATE USER mlflow WITH PASSWORD 'CHANGE_ME_VIA_SECRET';
    CREATE USER airflow WITH PASSWORD 'CHANGE_ME_VIA_SECRET';
    GRANT ALL PRIVILEGES ON DATABASE mlflow TO mlflow;
    GRANT ALL PRIVILEGES ON DATABASE airflow TO airflow;
SQL
"
```

In production, the passwords come from External Secrets Operator pulling from AWS Secrets Manager / Vault — never inline.

### 2.3 Backups

Nightly logical backups via a CronJob:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
  namespace: mlops-system
spec:
  schedule: "0 3 * * *"        # 03:00 UTC, after data_pipeline finishes
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: pg-dump
            image: postgres:14.10
            command:
            - /bin/bash
            - -c
            - |
              for db in mlflow airflow; do
                PGPASSWORD=$PG_PASSWORD pg_dump -h postgres-postgresql-ha-pgpool \
                  -U postgres -F c -Z 9 $db | \
                aws s3 cp - s3://backups/postgres/${db}/$(date +%Y-%m-%d).dump \
                  --endpoint-url $S3_ENDPOINT
              done
          restartPolicy: OnFailure
```

Combine with WAL-G or pgBackRest for point-in-time recovery if your RPO is tighter than 24 hours.

---

## 3. MinIO

We use [MinIO Operator](https://github.com/minio/operator) version 5.x to manage MinIO Tenants. A single tenant with 4 servers × 4 drives gives you EC:2 erasure coding (tolerates 2 drive failures).

### 3.1 Tenant manifest

```yaml
apiVersion: minio.min.io/v2
kind: Tenant
metadata:
  name: mlops-minio
  namespace: mlops-system
spec:
  configuration:
    name: minio-creds
  pools:
  - servers: 4
    name: pool-0
    volumesPerServer: 4
    volumeClaimTemplate:
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: gp3
        resources:
          requests:
            storage: 250Gi
  requestAutoCert: false       # we terminate TLS at Ingress
  exposeServices:
    minio: true
    console: true
```

Resulting capacity: 16 drives × 250 GiB ÷ EC overhead ≈ 3 TiB usable. Adjust for your data volume — the customer-churn use case at 10 K rows/day fits easily under 100 GiB.

### 3.2 Bucket layout and lifecycle

Buckets, created once via `mc mb`:

| Bucket | Purpose | Lifecycle |
|--------|---------|-----------|
| `raw` | Raw ingestion outputs | Transition to STANDARD_IA after 30 d; delete after 90 d |
| `features` | Versioned feature snapshots | Delete `ds=` partitions older than 180 d; keep all `v=` directories |
| `mlflow` | MLflow artifacts | No expiration — versioned models are the source of truth for rollback |
| `predictions` | Batch inference outputs | Delete after 30 d |
| `backups` | Postgres dumps, manifest copies | Versioned objects; delete non-current versions after 60 d |
| `dvc-cache` | DVC remote storage | Garbage collect via `dvc gc` weekly |

Lifecycle policies are applied via `mc ilm import` from JSON files under `kubernetes/minio/lifecycle/`.

### 3.3 HA considerations

- 4 server pods are spread across 4 nodes via `topologySpreadConstraints`. Losing 1 node degrades but does not fail.
- `requestAutoCert: false` because we terminate TLS at the Ingress. For pod-to-pod TLS, set this to `true` and let the operator manage certs via cert-manager.
- The MinIO Console is only reachable from inside the cluster; expose it via `kubectl port-forward` rather than an Ingress.

### 3.4 Backups

Bucket replication to a secondary cluster or a different region:

```bash
mc admin replicate add primary/mlflow secondary/mlflow
```

This is asynchronous. For a tighter RPO, use server-side replication with bandwidth limits configured to not starve the primary.

---

## 4. MLflow tracking server

Custom Helm chart in `kubernetes/mlflow/` (no upstream chart is mature enough as of MLflow 2.8). The relevant manifest pieces:

### 4.1 Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mlflow
  namespace: mlops-system
spec:
  replicas: 2
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    spec:
      serviceAccountName: mlflow
      containers:
      - name: mlflow
        image: ghcr.io/mlflow/mlflow:v2.8.1
        command:
        - mlflow
        - server
        - --host=0.0.0.0
        - --port=5000
        - --backend-store-uri=$(MLFLOW_BACKEND_STORE_URI)
        - --default-artifact-root=$(MLFLOW_DEFAULT_ARTIFACT_ROOT)
        - --serve-artifacts
        - --app-name=basic-auth
        env:
        - name: MLFLOW_BACKEND_STORE_URI
          valueFrom:
            secretKeyRef:
              name: mlflow-config
              key: backend-uri
        - name: MLFLOW_DEFAULT_ARTIFACT_ROOT
          value: s3://mlflow/artifacts/
        - name: MLFLOW_S3_ENDPOINT_URL
          value: http://minio.mlops-system.svc.cluster.local:9000
        - name: AWS_ACCESS_KEY_ID
          valueFrom:
            secretKeyRef:
              name: minio-mlflow-credentials
              key: access-key
        - name: AWS_SECRET_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: minio-mlflow-credentials
              key: secret-key
        resources:
          requests:
            cpu: 500m
            memory: 1Gi
          limits:
            cpu: 2
            memory: 2Gi
        readinessProbe:
          httpGet:
            path: /health
            port: 5000
          initialDelaySeconds: 10
          periodSeconds: 5
        livenessProbe:
          httpGet:
            path: /health
            port: 5000
          initialDelaySeconds: 60
          periodSeconds: 30
```

Two replicas with `maxUnavailable: 0` give zero-downtime upgrades. The `--serve-artifacts` flag is on so the UI's "Download artifact" button works (otherwise the browser tries to fetch directly from MinIO with no credentials).

### 4.2 Service and Ingress

```yaml
apiVersion: v1
kind: Service
metadata:
  name: mlflow
  namespace: mlops-system
spec:
  selector:
    app: mlflow
  ports:
  - port: 5000
    targetPort: 5000
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mlflow
  namespace: mlops-system
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  ingressClassName: nginx
  tls:
  - hosts: [mlflow.example.com]
    secretName: mlflow-tls
  rules:
  - host: mlflow.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: mlflow
            port:
              number: 5000
```

### 4.3 HA considerations

- The 2 replicas share the same Postgres backend; any writes are immediately visible to either replica.
- Session state (e.g. basic auth login) is stored in Postgres, so a request can hit either pod.
- If the Postgres primary fails over, MLflow tracking calls fail until pgpool routes to the new primary (~30 s with the HA chart). Treat this as a known interruption window.
- Artifact uploads bypass the tracking server (clients upload directly to MinIO), so tracking-server load is mostly read traffic.

---

## 5. Airflow

We use the [official Airflow Helm chart](https://airflow.apache.org/docs/helm-chart/stable/index.html) version 1.11.0 with executor `KubernetesExecutor`. The chart is well-maintained; we override only what's necessary.

### 5.1 Key values

```yaml
# kubernetes/airflow/values.yaml
airflowVersion: "2.7.3"
defaultAirflowRepository: ghcr.io/your-org/mlops-airflow   # custom image with our deps
defaultAirflowTag: "2.7.3-mlops-1"

executor: KubernetesExecutor

postgresql:
  enabled: false              # we use the external Postgres
data:
  metadataConnection:
    user: airflow
    pass: ""                  # from metadataSecret
    protocol: postgresql
    host: postgres-postgresql-ha-pgpool.mlops-system
    port: 5432
    db: airflow
  metadataSecretName: airflow-metadata-credentials

dags:
  gitSync:
    enabled: true
    repo: https://github.com/your-org/mlops-pipeline.git
    branch: main
    subPath: dags
    wait: 30
    credentialsSecret: airflow-git-credentials

webserver:
  replicas: 2
  service:
    type: ClusterIP

scheduler:
  replicas: 2                 # active/standby; HA mode in Airflow 2

triggerer:
  enabled: true
  replicas: 2

workers:
  keda:
    enabled: false            # KubernetesExecutor scales naturally

config:
  core:
    parallelism: "64"
    dag_concurrency: "16"
    max_active_runs_per_dag: "1"     # critical for our DAGs — no overlapping ds runs
  kubernetes_executor:
    namespace: airflow
    worker_container_repository: ghcr.io/your-org/mlops-airflow
    worker_container_tag: "2.7.3-mlops-1"
    delete_worker_pods: "True"
```

### 5.2 Custom worker image

The worker image bakes in our `requirements.txt` plus the `src/` package as an installable wheel. Rebuilt on every merge to `main` via GitHub Actions, tagged `2.7.3-mlops-${SHORT_SHA}`. The Helm value `defaultAirflowTag` is bumped via PR.

This is preferable to mounting source code at runtime: image versioning gives you exact reproducibility of any historical DAG run.

### 5.3 Connections and Variables

Set via the chart's `secret.connections` block, populated from External Secrets:

| Airflow Connection | Type | Used by |
|--------------------|------|---------|
| `minio_default` | aws | `S3Hook` in data tasks |
| `mlflow_default` | http | `SimpleHttpOperator` for registry calls |
| `kubernetes_default` | kubernetes | `KubernetesPodOperator` |
| `slack_default` | http | `SlackWebhookOperator` for notifications |

Variables (visible in the UI for ops use):

- `FORCE_RETRAIN` — manual override
- `DRIFT_THRESHOLD` — feature drift cutoff
- `MIN_F1_SCORE`, `MIN_ACCURACY` — promotion gates
- `INGEST_ALLOW_PARTIAL` — incident-mode flag
- `ROLLBACK_WINDOW_MINUTES` — how long to keep blue/green available

---

## 6. Predictor service

Deployed twice in `ml-serving` as `predictor-blue` and `predictor-green`. Both reference the same image but different model versions via env vars. Single `Service` with selector based on `color` label, flipped during cutover.

### 6.1 Deployment template

```yaml
# kubernetes/predictor/deployment-template.yaml.j2
apiVersion: apps/v1
kind: Deployment
metadata:
  name: predictor-{{ color }}
  namespace: ml-serving
  labels:
    app: predictor
    color: {{ color }}
spec:
  replicas: {{ replicas | default(3) }}
  selector:
    matchLabels:
      app: predictor
      color: {{ color }}
  template:
    metadata:
      labels:
        app: predictor
        color: {{ color }}
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
    spec:
      containers:
      - name: predictor
        image: ghcr.io/your-org/churn-predictor:{{ image_tag }}
        env:
        - name: MODEL_NAME
          value: churn-classifier
        - name: MODEL_VERSION
          value: "{{ model_version }}"
        - name: MLFLOW_TRACKING_URI
          value: http://mlflow.mlops-system.svc.cluster.local:5000
        resources:
          requests:
            cpu: 500m
            memory: 1Gi
          limits:
            cpu: 2
            memory: 2Gi
        readinessProbe:
          httpGet:
            path: /healthz
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8000
          initialDelaySeconds: 60
```

`MODEL_VERSION` is a string version (e.g. `"7"`) — never the stage alias. This pins the deployment to an exact artifact, which is what makes the blue/green flip safe.

### 6.2 HPA

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: predictor-active
  namespace: ml-serving
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: predictor-blue           # patched by deployment DAG to match active color
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60
```

Only the *active* color has an HPA — the inactive color holds at a fixed replica count for quick cutback.

---

## 7. Secrets management

We use [External Secrets Operator](https://external-secrets.io/) (v0.9+) with AWS Secrets Manager (or Vault for on-prem). Pattern:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: postgres-credentials
  namespace: mlops-system
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: postgres-credentials
    template:
      data:
        postgres-password: "{{ .password }}"
  data:
  - secretKey: password
    remoteRef:
      key: mlops/postgres/postgres
      property: password
```

Rotation: AWS Secrets Manager rotates the secret; ESO picks it up within `refreshInterval`; Postgres has its password updated by an out-of-band CronJob that reads the new value and runs `ALTER USER`. The window where the K8s Secret has the new value but Postgres has the old one is a known caveat — we rotate during low-traffic windows.

**Never** put credentials in Git, even in encrypted form (this includes SOPS-encrypted YAML — it's better than plaintext but easier to leak via accidental decrypt logs). External Secrets keeps the source of truth out of the repo entirely.

---

## 8. Bringing the cluster up from scratch

The full bootstrap script lives in `scripts/deploy.sh`. The summary:

```bash
# 1. Namespaces and network policies
kubectl apply -f kubernetes/namespaces.yaml
kubectl apply -f kubernetes/network-policies.yaml

# 2. External Secrets Operator (chart install once per cluster)
helm install external-secrets external-secrets/external-secrets -n external-secrets --create-namespace

# 3. Cluster secret store wiring (depends on cloud provider)
kubectl apply -f kubernetes/cluster-secret-store.yaml

# 4. Postgres
helm install postgres bitnami/postgresql-ha -n mlops-system -f kubernetes/postgres/values.yaml

# 5. MinIO Operator + Tenant
kubectl apply -k kubernetes/minio/operator/   # operator install via kustomize
kubectl apply -f kubernetes/minio/tenant.yaml

# 6. Wait for both to be Ready, then create DBs and buckets
./scripts/init-postgres.sh
./scripts/init-minio.sh

# 7. MLflow
kubectl apply -f kubernetes/mlflow/

# 8. Airflow
helm install airflow apache-airflow/airflow -n airflow -f kubernetes/airflow/values.yaml

# 9. Predictor (initial bootstrap — both colors point at the same model)
kubectl apply -f kubernetes/predictor/

# 10. Monitoring
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack -n monitoring -f monitoring/values.yaml
kubectl apply -f monitoring/dashboards/
```

Expect the full bootstrap to take ~15 minutes; most of that is waiting for `pg_init` and the MinIO tenant to come up.

---

## 9. Smoke check after deploy

```bash
# Tracking server reachable
curl -s -u admin:$MLFLOW_ADMIN_PASSWORD https://mlflow.example.com/api/2.0/mlflow/experiments/search \
  -X POST -H "Content-Type: application/json" -d '{"max_results": 1}' | jq .

# Airflow webserver reachable
curl -s -u admin:$AIRFLOW_ADMIN_PASSWORD https://airflow.example.com/health | jq .

# Predictor returns a prediction
kubectl -n ml-serving port-forward svc/predictor 8000:8000 &
curl -s -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/inference_payloads.json | jq .

# Prometheus is scraping everything
curl -s http://prometheus.monitoring:9090/api/v1/targets | jq '.data.activeTargets[] | select(.health != "up")'
```

If all four return as expected, the stack is up. From there, trigger `data_pipeline` manually from the Airflow UI and watch the cascade.

For failure modes, see `TROUBLESHOOTING.md`.
