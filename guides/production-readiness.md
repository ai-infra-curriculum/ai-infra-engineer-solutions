# Production Readiness Guide

> **A comprehensive guide to preparing AI infrastructure systems for production deployment**

---

## Table of Contents

1. [Introduction](#introduction)
2. [Production Readiness Checklist](#production-readiness-checklist)
3. [Security Best Practices](#security-best-practices)
   - [Secrets Management](#secrets-management)
   - [RBAC and Authentication](#rbac-and-authentication)
   - [Network Security](#network-security)
   - [Container Security](#container-security)
   - [Security Scanning](#security-scanning)
4. [High Availability and Disaster Recovery](#high-availability-and-disaster-recovery)
   - [Redundancy](#redundancy)
   - [Backup and Restore](#backup-and-restore)
   - [Disaster Recovery Planning](#disaster-recovery-planning)
5. [Scalability Considerations](#scalability-considerations)
6. [Monitoring and Alerting](#monitoring-and-alerting)
   - [Application Metrics](#application-metrics)
   - [Infrastructure Metrics](#infrastructure-metrics)
   - [Alerting Strategy](#alerting-strategy)
7. [Logging and Observability](#logging-and-observability)
   - [Structured Logging](#structured-logging)
   - [Log Aggregation](#log-aggregation)
   - [Distributed Tracing](#distributed-tracing)
8. [Testing Requirements](#testing-requirements)
   - [Unit Testing](#unit-testing)
   - [Integration Testing](#integration-testing)
   - [End-to-End Testing](#end-to-end-testing)
   - [Load Testing](#load-testing)
   - [Chaos Engineering](#chaos-engineering)
9. [CI/CD Pipeline](#cicd-pipeline)
10. [Deployment Strategies](#deployment-strategies)
    - [Blue-Green Deployment](#blue-green-deployment)
    - [Canary Deployment](#canary-deployment)
    - [Rolling Updates](#rolling-updates)
11. [Incident Response](#incident-response)
12. [Cost Management](#cost-management)
13. [Compliance and Governance](#compliance-and-governance)
14. [Documentation Requirements](#documentation-requirements)
15. [Project-Specific Checklists](#project-specific-checklists)
16. [Launch Checklist](#launch-checklist)
17. [Resources and References](#resources-and-references)

---

## Introduction

### What is Production Readiness?

Production readiness is the state where a system is fully prepared to serve real users in a production environment with:

- **Reliability**: System works consistently as expected
- **Availability**: System is accessible when needed (99.9%+ uptime)
- **Security**: System protects data and prevents unauthorized access
- **Scalability**: System handles growth in traffic and data
- **Maintainability**: System can be updated and debugged easily
- **Observability**: System behavior is measurable and understandable

### Production Readiness Framework

```
┌─────────────────────────────────────────────────────────┐
│                   PRODUCTION READY                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │ Security │  │   H/A    │  │  Scale   │            │
│  └──────────┘  └──────────┘  └──────────┘            │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │ Monitor  │  │  Logging │  │  Testing │            │
│  └──────────┘  └──────────┘  └──────────┘            │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │  CI/CD   │  │   Docs   │  │ Incident │            │
│  └──────────┘  └──────────┘  └──────────┘            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Stages of Production Readiness

1. **Development**: Feature complete, basic testing
2. **Staging**: Production-like environment, integration testing
3. **Pre-Production**: Final validation, load testing
4. **Production**: Live with real users
5. **Post-Launch**: Monitoring, optimization, iteration

---

## Production Readiness Checklist

### Master Checklist

```markdown
## Core Requirements
- [ ] All code reviewed and approved
- [ ] Test coverage >80%
- [ ] Security vulnerabilities addressed
- [ ] Performance benchmarks met
- [ ] Documentation complete
- [ ] Monitoring and alerting configured
- [ ] Incident response plan documented
- [ ] Runbooks created
- [ ] Disaster recovery tested
- [ ] Cost estimates validated

## Security
- [ ] All secrets in secret management system
- [ ] RBAC configured and tested
- [ ] Network policies defined
- [ ] Container images scanned
- [ ] TLS/SSL certificates configured
- [ ] Security audit completed
- [ ] Compliance requirements met
- [ ] Data encryption at rest and in transit
- [ ] Authentication and authorization implemented
- [ ] Rate limiting configured

## Reliability
- [ ] High availability configured (multi-AZ/region)
- [ ] Automatic failover tested
- [ ] Backup strategy implemented
- [ ] Restore procedures tested
- [ ] Circuit breakers implemented
- [ ] Retry logic with exponential backoff
- [ ] Graceful degradation
- [ ] Resource limits defined
- [ ] Health checks configured
- [ ] Readiness probes configured

## Scalability
- [ ] Horizontal pod autoscaling configured
- [ ] Vertical pod autoscaling evaluated
- [ ] Cluster autoscaling configured
- [ ] Database connection pooling
- [ ] Caching strategy implemented
- [ ] Load testing completed
- [ ] Performance optimization done
- [ ] Resource quotas set
- [ ] Rate limiting implemented
- [ ] CDN configured (if applicable)

## Observability
- [ ] Application metrics exposed
- [ ] Infrastructure metrics collected
- [ ] Logs centralized and searchable
- [ ] Distributed tracing configured
- [ ] Dashboards created
- [ ] Alerts configured
- [ ] SLIs/SLOs defined
- [ ] Error tracking implemented
- [ ] Performance monitoring active
- [ ] Cost tracking enabled

## Deployment
- [ ] CI/CD pipeline automated
- [ ] Deployment strategy defined
- [ ] Rollback procedure tested
- [ ] Feature flags implemented
- [ ] Database migrations automated
- [ ] Zero-downtime deployment verified
- [ ] Smoke tests automated
- [ ] Deployment notifications configured
- [ ] Change management process defined
- [ ] Environment parity maintained

## Compliance
- [ ] Data privacy requirements met
- [ ] Audit logging enabled
- [ ] Compliance certifications obtained
- [ ] Data retention policies implemented
- [ ] Access controls documented
- [ ] Vendor security reviewed
- [ ] Legal review completed
- [ ] Terms of service updated
- [ ] Privacy policy updated
- [ ] Incident notification plan ready
```

---

## Security Best Practices

### Secrets Management

#### Never Hardcode Secrets

```python
# BAD: Hardcoded secrets
DATABASE_URL = "postgresql://admin:password123@db.example.com/mydb"
API_KEY = "sk-1234567890abcdef"

# GOOD: Environment variables
import os

DATABASE_URL = os.environ["DATABASE_URL"]
API_KEY = os.environ["API_KEY"]

# BETTER: Secret management system
from kubernetes import client, config

def get_secret(name, namespace="default"):
    config.load_incluster_config()
    v1 = client.CoreV1Api()
    secret = v1.read_namespaced_secret(name, namespace)
    return secret.data

DATABASE_PASSWORD = get_secret("db-credentials")["password"]
```

#### Kubernetes Secrets

```yaml
# Create secret from file
apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
  namespace: production
type: Opaque
data:
  username: YWRtaW4=  # base64 encoded "admin"
  password: cGFzc3dvcmQxMjM=  # base64 encoded "password123"

---
# Use secret in pod
apiVersion: v1
kind: Pod
metadata:
  name: model-serving
spec:
  containers:
  - name: app
    image: model-serving:latest
    env:
    - name: DB_USERNAME
      valueFrom:
        secretKeyRef:
          name: db-credentials
          key: username
    - name: DB_PASSWORD
      valueFrom:
        secretKeyRef:
          name: db-credentials
          key: password
```

**Create secrets from command line:**

```bash
# From literal values
kubectl create secret generic db-credentials \
  --from-literal=username=admin \
  --from-literal=password=password123 \
  --namespace=production

# From file
kubectl create secret generic api-credentials \
  --from-file=api-key.txt \
  --namespace=production

# From env file
kubectl create secret generic app-config \
  --from-env-file=production.env \
  --namespace=production
```

#### External Secret Management

**Using HashiCorp Vault:**

```python
import hvac

# Connect to Vault
client = hvac.Client(url='https://vault.example.com')
client.token = os.environ['VAULT_TOKEN']

# Read secret
secret = client.secrets.kv.v2.read_secret_version(
    path='database/credentials'
)

db_username = secret['data']['data']['username']
db_password = secret['data']['data']['password']
```

**Using AWS Secrets Manager:**

```python
import boto3
import json

def get_secret(secret_name, region_name="us-west-2"):
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

credentials = get_secret('prod/db/credentials')
db_password = credentials['password']
```

### RBAC and Authentication

#### Kubernetes RBAC

```yaml
# Service Account
apiVersion: v1
kind: ServiceAccount
metadata:
  name: model-serving
  namespace: production

---
# Role (namespace-scoped)
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: model-serving-role
  namespace: production
rules:
- apiGroups: [""]
  resources: ["configmaps", "secrets"]
  verbs: ["get", "list"]
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch"]

---
# RoleBinding
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: model-serving-binding
  namespace: production
subjects:
- kind: ServiceAccount
  name: model-serving
  namespace: production
roleRef:
  kind: Role
  name: model-serving-role
  apiGroup: rbac.authorization.k8s.io

---
# Use ServiceAccount in Pod
apiVersion: v1
kind: Pod
metadata:
  name: model-serving
  namespace: production
spec:
  serviceAccountName: model-serving
  containers:
  - name: app
    image: model-serving:latest
```

#### API Authentication

```python
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from datetime import datetime, timedelta

app = FastAPI()
security = HTTPBearer()

SECRET_KEY = os.environ["JWT_SECRET_KEY"]
ALGORITHM = "HS256"

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

@app.post("/predict")
async def predict(
    data: dict,
    user: dict = Depends(verify_token)
):
    # user is authenticated
    result = model.predict(data)
    return result
```

### Network Security

#### Network Policies

```yaml
# Default deny all traffic
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: production
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress

---
# Allow ingress from specific namespaces
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-from-ingress
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: model-serving
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8080

---
# Allow egress to database
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-to-database
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: model-serving
  policyTypes:
  - Egress
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: postgres
    ports:
    - protocol: TCP
      port: 5432
  # Allow DNS
  - to:
    - namespaceSelector:
        matchLabels:
          name: kube-system
    - podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
    - protocol: UDP
      port: 53
```

#### TLS/SSL Configuration

```yaml
# Certificate (using cert-manager)
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: model-serving-tls
  namespace: production
spec:
  secretName: model-serving-tls
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
  - api.example.com
  - www.api.example.com

---
# Ingress with TLS
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: model-serving
  namespace: production
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
spec:
  tls:
  - hosts:
    - api.example.com
    secretName: model-serving-tls
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: model-serving
            port:
              number: 8080
```

### Container Security

#### Security Context

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: model-serving
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    fsGroup: 1000
    seccompProfile:
      type: RuntimeDefault
  containers:
  - name: app
    image: model-serving:latest
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop:
        - ALL
    volumeMounts:
    - name: tmp
      mountPath: /tmp
    - name: cache
      mountPath: /app/cache
  volumes:
  - name: tmp
    emptyDir: {}
  - name: cache
    emptyDir: {}
```

#### Dockerfile Security

```dockerfile
# Use specific version, not latest
FROM python:3.11.5-slim

# Run as non-root user
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app && \
    chown -R appuser:appuser /app

# Install dependencies as root
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

# Switch to non-root user
USER appuser

WORKDIR /app
COPY --chown=appuser:appuser . .

# Don't run as PID 1 (use tini or similar)
ENTRYPOINT ["python"]
CMD ["app.py"]
```

### Security Scanning

#### Image Scanning

```bash
# Scan with Trivy
trivy image model-serving:latest

# Scan with high severity only
trivy image --severity HIGH,CRITICAL model-serving:latest

# Fail on vulnerabilities
trivy image --exit-code 1 --severity CRITICAL model-serving:latest

# Scan in CI/CD
# .github/workflows/security-scan.yml
name: Security Scan
on: [push]
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Build image
      run: docker build -t model-serving:${{ github.sha }} .
    - name: Run Trivy scanner
      uses: aquasecurity/trivy-action@master
      with:
        image-ref: model-serving:${{ github.sha }}
        format: 'sarif'
        output: 'trivy-results.sarif'
    - name: Upload results
      uses: github/codeql-action/upload-sarif@v2
      with:
        sarif_file: 'trivy-results.sarif'
```

#### Code Scanning

```bash
# Scan Python code with Bandit
bandit -r src/ -f json -o bandit-report.json

# Scan for secrets with git-secrets
git secrets --scan

# Scan dependencies with Safety
safety check --json

# Comprehensive scan
# .github/workflows/code-scan.yml
name: Code Security Scan
on: [push]
jobs:
  security:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    - name: Install dependencies
      run: |
        pip install bandit safety
    - name: Run Bandit
      run: bandit -r src/ -f json -o bandit-report.json
    - name: Run Safety
      run: safety check --json
```

---

## High Availability and Disaster Recovery

### Redundancy

#### Multi-Zone Deployment

```yaml
# Deployment with pod anti-affinity
apiVersion: apps/v1
kind: Deployment
metadata:
  name: model-serving
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: model-serving
  template:
    metadata:
      labels:
        app: model-serving
    spec:
      affinity:
        # Spread across availability zones
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchExpressions:
              - key: app
                operator: In
                values:
                - model-serving
            topologyKey: topology.kubernetes.io/zone
        # Prefer different nodes
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - model-serving
              topologyKey: kubernetes.io/hostname
      containers:
      - name: app
        image: model-serving:latest
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "4Gi"
            cpu: "2"
```

#### Database High Availability

```yaml
# PostgreSQL with replication
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: postgres-ha
  namespace: production
spec:
  instances: 3
  primaryUpdateStrategy: unsupervised

  bootstrap:
    initdb:
      database: mydb
      owner: myuser

  storage:
    size: 100Gi
    storageClass: fast-ssd

  postgresql:
    parameters:
      max_connections: "200"
      shared_buffers: "2GB"

  monitoring:
    enablePodMonitor: true

  backup:
    barmanObjectStore:
      destinationPath: s3://backups/postgres
      s3Credentials:
        accessKeyId:
          name: s3-credentials
          key: ACCESS_KEY_ID
        secretAccessKey:
          name: s3-credentials
          key: ACCESS_SECRET_KEY
    retentionPolicy: "30d"
```

### Backup and Restore

#### Automated Backups

```yaml
# Velero backup schedule
apiVersion: velero.io/v1
kind: Schedule
metadata:
  name: daily-backup
  namespace: velero
spec:
  schedule: "0 2 * * *"  # 2 AM daily
  template:
    includedNamespaces:
    - production
    excludedResources:
    - events
    - events.events.k8s.io
    storageLocation: default
    volumeSnapshotLocations:
    - default
    ttl: 720h  # 30 days
```

**Backup Script:**

```bash
#!/bin/bash
# backup.sh - Automated backup script

set -e

DATE=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="/backups"
NAMESPACE="production"

echo "Starting backup at $(date)"

# 1. Backup Kubernetes resources
echo "Backing up Kubernetes resources..."
kubectl get all -n $NAMESPACE -o yaml > "$BACKUP_DIR/k8s-resources-$DATE.yaml"
kubectl get configmap -n $NAMESPACE -o yaml > "$BACKUP_DIR/configmaps-$DATE.yaml"
kubectl get secret -n $NAMESPACE -o yaml > "$BACKUP_DIR/secrets-$DATE.yaml"

# 2. Backup PostgreSQL database
echo "Backing up database..."
kubectl exec -n $NAMESPACE postgres-0 -- pg_dumpall -U postgres | \
  gzip > "$BACKUP_DIR/postgres-$DATE.sql.gz"

# 3. Backup persistent volumes
echo "Backing up volumes..."
velero backup create "backup-$DATE" \
  --include-namespaces $NAMESPACE \
  --wait

# 4. Upload to S3
echo "Uploading to S3..."
aws s3 sync $BACKUP_DIR s3://my-backups/$(date +%Y/%m/%d)/

# 5. Clean up old backups (keep last 30 days)
echo "Cleaning up old backups..."
find $BACKUP_DIR -type f -mtime +30 -delete

echo "Backup completed at $(date)"
```

#### Restore Procedures

```bash
#!/bin/bash
# restore.sh - Restore from backup

set -e

BACKUP_DATE=$1
BACKUP_DIR="/backups"
NAMESPACE="production"

if [ -z "$BACKUP_DATE" ]; then
  echo "Usage: $0 <backup-date>"
  echo "Example: $0 20251016-020000"
  exit 1
fi

echo "Starting restore from backup $BACKUP_DATE"

# 1. Download from S3
echo "Downloading backup from S3..."
aws s3 sync s3://my-backups/$BACKUP_DATE/ $BACKUP_DIR/

# 2. Restore Kubernetes resources
echo "Restoring Kubernetes resources..."
kubectl apply -f "$BACKUP_DIR/k8s-resources-$BACKUP_DATE.yaml"
kubectl apply -f "$BACKUP_DIR/configmaps-$BACKUP_DATE.yaml"

# 3. Restore database
echo "Restoring database..."
gunzip < "$BACKUP_DIR/postgres-$BACKUP_DATE.sql.gz" | \
  kubectl exec -i -n $NAMESPACE postgres-0 -- psql -U postgres

# 4. Restore volumes with Velero
echo "Restoring volumes..."
velero restore create "restore-$BACKUP_DATE" \
  --from-backup "backup-$BACKUP_DATE" \
  --wait

echo "Restore completed"
echo "Please verify application is working correctly"
```

### Disaster Recovery Planning

#### DR Runbook

```markdown
# Disaster Recovery Runbook

## Severity Levels

### SEV-1: Complete Outage
- RTO: 1 hour
- RPO: 5 minutes
- Response: Immediate

### SEV-2: Partial Outage
- RTO: 4 hours
- RPO: 15 minutes
- Response: Within 30 minutes

### SEV-3: Performance Degradation
- RTO: 24 hours
- RPO: 1 hour
- Response: Within 2 hours

## Common Scenarios

### Scenario 1: Database Failure

**Detection:**
- Database health check fails
- Connection errors in application logs
- Prometheus alert: `postgres_up == 0`

**Response:**
1. Check database pod status:
   ```bash
   kubectl get pods -n production -l app=postgres
   ```

2. Check database logs:
   ```bash
   kubectl logs -n production postgres-0
   ```

3. If pod is crashing, check events:
   ```bash
   kubectl describe pod -n production postgres-0
   ```

4. If data corruption, restore from backup:
   ```bash
   ./restore.sh <backup-date>
   ```

5. If replica failure, promote standby:
   ```bash
   kubectl exec -n production postgres-0 -- pg_ctl promote
   ```

**Verification:**
- Database health check passes
- Application can connect
- No errors in logs

### Scenario 2: Region Failure

**Detection:**
- Multiple services down
- Unable to reach region
- Cloud provider status page reports outage

**Response:**
1. Activate DR region:
   ```bash
   kubectl config use-context dr-region
   ```

2. Update DNS to point to DR region:
   ```bash
   aws route53 change-resource-record-sets \
     --hosted-zone-id Z123456 \
     --change-batch file://failover.json
   ```

3. Verify services in DR region:
   ```bash
   kubectl get pods -n production
   curl https://api-dr.example.com/health
   ```

4. Monitor traffic shift:
   ```bash
   watch -n 5 'kubectl top pods -n production'
   ```

**Verification:**
- All services healthy in DR region
- Traffic flowing to DR region
- Users can access application

### Scenario 3: Data Corruption

**Detection:**
- Invalid data in database
- User reports of incorrect results
- Data validation errors

**Response:**
1. Identify scope of corruption:
   ```sql
   SELECT COUNT(*) FROM predictions
   WHERE created_at > '2025-10-16 10:00:00'
   AND result IS NULL;
   ```

2. Stop writes to affected tables:
   ```sql
   REVOKE INSERT, UPDATE, DELETE ON predictions FROM app_user;
   ```

3. Restore from point-in-time backup:
   ```bash
   # Restore to 1 hour before corruption
   ./restore-pitr.sh "2025-10-16 09:00:00"
   ```

4. Verify data integrity:
   ```sql
   SELECT * FROM predictions
   WHERE created_at > '2025-10-16 09:00:00'
   LIMIT 10;
   ```

5. Re-enable writes:
   ```sql
   GRANT INSERT, UPDATE, DELETE ON predictions TO app_user;
   ```

**Verification:**
- Data is valid
- No corruption detected
- Application functioning normally
```

---

## Scalability Considerations

### Horizontal Scaling

```yaml
# HPA with multiple metrics
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: model-serving-hpa
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: model-serving
  minReplicas: 3  # Always at least 3 for HA
  maxReplicas: 50
  metrics:
  # CPU-based scaling
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  # Memory-based scaling
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  # Custom metric: requests per second
  - type: Pods
    pods:
      metric:
        name: http_requests_per_second
      target:
        type: AverageValue
        averageValue: "100"
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100  # Double pods
        periodSeconds: 15
      - type: Pods
        value: 5  # Or add 5 pods
        periodSeconds: 15
      selectPolicy: Max
    scaleDown:
      stabilizationWindowSeconds: 300  # Wait 5 min
      policies:
      - type: Percent
        value: 50  # Max 50% at once
        periodSeconds: 60
```

### Vertical Scaling

```yaml
# VPA for automatic resource adjustment
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: model-serving-vpa
  namespace: production
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: model-serving
  updatePolicy:
    updateMode: "Auto"  # Automatically update pods
  resourcePolicy:
    containerPolicies:
    - containerName: app
      minAllowed:
        cpu: 500m
        memory: 1Gi
      maxAllowed:
        cpu: 4
        memory: 8Gi
      controlledResources: ["cpu", "memory"]
```

### Database Scaling

```sql
-- Connection pooling configuration
-- PostgreSQL pgBouncer

[databases]
mydb = host=localhost port=5432 dbname=mydb

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
reserve_pool_size = 5
reserve_pool_timeout = 3
max_db_connections = 100
```

```yaml
# PgBouncer deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pgbouncer
  namespace: production
spec:
  replicas: 2
  selector:
    matchLabels:
      app: pgbouncer
  template:
    metadata:
      labels:
        app: pgbouncer
    spec:
      containers:
      - name: pgbouncer
        image: pgbouncer/pgbouncer:latest
        ports:
        - containerPort: 6432
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

---

## Monitoring and Alerting

### Application Metrics

```python
from prometheus_client import Counter, Histogram, Gauge, Info
import time
from functools import wraps

# Define metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

ACTIVE_REQUESTS = Gauge(
    'http_requests_active',
    'Number of active HTTP requests'
)

MODEL_INFO = Info(
    'model',
    'Information about the model'
)

PREDICTION_ERRORS = Counter(
    'prediction_errors_total',
    'Total prediction errors',
    ['model_id', 'error_type']
)

INFERENCE_TIME = Histogram(
    'model_inference_duration_seconds',
    'Model inference time',
    ['model_id'],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
)

# Set model info
MODEL_INFO.info({
    'version': '1.0.0',
    'framework': 'pytorch',
    'python_version': '3.11'
})

# Instrumentation decorator
def track_metrics(endpoint):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            ACTIVE_REQUESTS.inc()
            start = time.time()

            try:
                response = await func(*args, **kwargs)
                status = 200
                return response
            except Exception as e:
                status = 500
                raise
            finally:
                elapsed = time.time() - start
                ACTIVE_REQUESTS.dec()

                REQUEST_COUNT.labels(
                    method='POST',
                    endpoint=endpoint,
                    status=status
                ).inc()

                REQUEST_LATENCY.labels(
                    method='POST',
                    endpoint=endpoint
                ).observe(elapsed)

        return wrapper
    return decorator

# Usage
@app.post("/predict")
@track_metrics("/predict")
async def predict(data: dict):
    model_id = data.get('model_id', 'default')

    start = time.time()
    try:
        result = model.predict(data['input'])
        return {"prediction": result}
    except Exception as e:
        PREDICTION_ERRORS.labels(
            model_id=model_id,
            error_type=type(e).__name__
        ).inc()
        raise
    finally:
        elapsed = time.time() - start
        INFERENCE_TIME.labels(model_id=model_id).observe(elapsed)
```

### Infrastructure Metrics

**Prometheus Configuration:**

```yaml
# prometheus-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
  namespace: monitoring
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
      evaluation_interval: 15s

    alerting:
      alertmanagers:
      - static_configs:
        - targets:
          - alertmanager:9093

    rule_files:
      - /etc/prometheus/rules/*.yml

    scrape_configs:
    # Kubernetes pods
    - job_name: 'kubernetes-pods'
      kubernetes_sd_configs:
      - role: pod
      relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
        action: replace
        target_label: __metrics_path__
        regex: (.+)
      - source_labels: [__address__, __meta_kubernetes_pod_annotation_prometheus_io_port]
        action: replace
        regex: ([^:]+)(?::\d+)?;(\d+)
        replacement: $1:$2
        target_label: __address__

    # Node exporter
    - job_name: 'node-exporter'
      kubernetes_sd_configs:
      - role: node
      relabel_configs:
      - source_labels: [__address__]
        regex: '(.*):10250'
        replacement: '${1}:9100'
        target_label: __address__

    # kube-state-metrics
    - job_name: 'kube-state-metrics'
      static_configs:
      - targets: ['kube-state-metrics:8080']
```

### Alerting Strategy

**Alert Rules:**

```yaml
# prometheus-alerts.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-alerts
  namespace: monitoring
data:
  alerts.yml: |
    groups:
    - name: application
      interval: 30s
      rules:
      # High error rate
      - alert: HighErrorRate
        expr: |
          rate(http_requests_total{status=~"5.."}[5m])
          / rate(http_requests_total[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
          team: ml-platform
        annotations:
          summary: "High error rate on {{ $labels.endpoint }}"
          description: "Error rate is {{ $value | humanizePercentage }} on {{ $labels.endpoint }}"

      # High latency
      - alert: HighLatency
        expr: |
          histogram_quantile(0.95,
            rate(http_request_duration_seconds_bucket[5m])
          ) > 1.0
        for: 10m
        labels:
          severity: warning
          team: ml-platform
        annotations:
          summary: "High latency on {{ $labels.endpoint }}"
          description: "p95 latency is {{ $value }}s on {{ $labels.endpoint }}"

      # Pod down
      - alert: PodDown
        expr: up{job="kubernetes-pods"} == 0
        for: 5m
        labels:
          severity: critical
          team: ml-platform
        annotations:
          summary: "Pod {{ $labels.pod }} is down"
          description: "Pod {{ $labels.pod }} in namespace {{ $labels.namespace }} has been down for 5 minutes"

      # High memory usage
      - alert: HighMemoryUsage
        expr: |
          container_memory_usage_bytes{pod=~"model-serving.*"}
          / container_spec_memory_limit_bytes > 0.9
        for: 10m
        labels:
          severity: warning
          team: ml-platform
        annotations:
          summary: "High memory usage on {{ $labels.pod }}"
          description: "Memory usage is {{ $value | humanizePercentage }} on {{ $labels.pod }}"

      # CPU throttling
      - alert: CPUThrottling
        expr: |
          rate(container_cpu_cfs_throttled_seconds_total{pod=~"model-serving.*"}[5m])
          / rate(container_cpu_cfs_periods_total{pod=~"model-serving.*"}[5m]) > 0.5
        for: 10m
        labels:
          severity: warning
          team: ml-platform
        annotations:
          summary: "CPU throttling on {{ $labels.pod }}"
          description: "CPU is being throttled {{ $value | humanizePercentage }} of the time on {{ $labels.pod }}"

    - name: infrastructure
      interval: 30s
      rules:
      # Node not ready
      - alert: NodeNotReady
        expr: kube_node_status_condition{condition="Ready",status="true"} == 0
        for: 5m
        labels:
          severity: critical
          team: infrastructure
        annotations:
          summary: "Node {{ $labels.node }} is not ready"
          description: "Node {{ $labels.node }} has been not ready for 5 minutes"

      # Disk pressure
      - alert: DiskPressure
        expr: kube_node_status_condition{condition="DiskPressure",status="true"} == 1
        for: 5m
        labels:
          severity: warning
          team: infrastructure
        annotations:
          summary: "Disk pressure on {{ $labels.node }}"
          description: "Node {{ $labels.node }} is experiencing disk pressure"

      # PVC almost full
      - alert: PVCAlmostFull
        expr: |
          kubelet_volume_stats_used_bytes
          / kubelet_volume_stats_capacity_bytes > 0.9
        for: 10m
        labels:
          severity: warning
          team: infrastructure
        annotations:
          summary: "PVC {{ $labels.persistentvolumeclaim }} is almost full"
          description: "PVC {{ $labels.persistentvolumeclaim }} is {{ $value | humanizePercentage }} full"
```

**AlertManager Configuration:**

```yaml
# alertmanager-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: alertmanager-config
  namespace: monitoring
data:
  alertmanager.yml: |
    global:
      resolve_timeout: 5m
      slack_api_url: 'https://hooks.slack.com/services/XXX/YYY/ZZZ'

    route:
      group_by: ['alertname', 'cluster', 'service']
      group_wait: 10s
      group_interval: 10s
      repeat_interval: 12h
      receiver: 'slack-notifications'
      routes:
      # Critical alerts go to PagerDuty
      - match:
          severity: critical
        receiver: 'pagerduty'
        continue: true
      # Warning alerts go to Slack
      - match:
          severity: warning
        receiver: 'slack-notifications'

    receivers:
    - name: 'slack-notifications'
      slack_configs:
      - channel: '#alerts'
        title: '{{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
        send_resolved: true

    - name: 'pagerduty'
      pagerduty_configs:
      - service_key: 'YOUR_PAGERDUTY_KEY'
        description: '{{ .GroupLabels.alertname }}'

    inhibit_rules:
    - source_match:
        severity: 'critical'
      target_match:
        severity: 'warning'
      equal: ['alertname', 'cluster', 'service']
```

---

## Logging and Observability

### Structured Logging

```python
import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict

class StructuredLogger:
    def __init__(self, name: str, level: str = "INFO"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level))

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(handler)

    def _log(self, level: str, message: str, **kwargs):
        extra = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': level,
            **kwargs
        }
        getattr(self.logger, level.lower())(message, extra=extra)

    def info(self, message: str, **kwargs):
        self._log('INFO', message, **kwargs)

    def error(self, message: str, **kwargs):
        self._log('ERROR', message, **kwargs)

    def warning(self, message: str, **kwargs):
        self._log('WARNING', message, **kwargs)

    def debug(self, message: str, **kwargs):
        self._log('DEBUG', message, **kwargs)

class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': getattr(record, 'timestamp', datetime.utcnow().isoformat()),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        # Add exception info
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        # Add custom fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename',
                          'funcName', 'levelname', 'levelno', 'lineno',
                          'module', 'msecs', 'message', 'pathname',
                          'process', 'processName', 'relativeCreated',
                          'thread', 'threadName', 'exc_info', 'exc_text',
                          'stack_info', 'timestamp']:
                log_data[key] = value

        return json.dumps(log_data)

# Usage
logger = StructuredLogger('model-serving')

@app.post("/predict")
async def predict(data: dict, request_id: str = None):
    logger.info(
        "Prediction request received",
        request_id=request_id,
        model_id=data.get('model_id'),
        input_size=len(data.get('input', []))
    )

    try:
        result = model.predict(data['input'])
        logger.info(
            "Prediction successful",
            request_id=request_id,
            inference_time_ms=result['time']
        )
        return result
    except Exception as e:
        logger.error(
            "Prediction failed",
            request_id=request_id,
            error=str(e),
            exc_info=True
        )
        raise
```

### Log Aggregation

**Fluentd Configuration:**

```yaml
# fluentd-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluentd-config
  namespace: logging
data:
  fluent.conf: |
    <source>
      @type tail
      path /var/log/containers/*.log
      pos_file /var/log/fluentd-containers.log.pos
      tag kubernetes.*
      read_from_head true
      <parse>
        @type json
        time_format %Y-%m-%dT%H:%M:%S.%NZ
      </parse>
    </source>

    <filter kubernetes.**>
      @type kubernetes_metadata
      @id filter_kube_metadata
    </filter>

    <filter kubernetes.**>
      @type parser
      key_name log
      reserve_data true
      <parse>
        @type json
      </parse>
    </filter>

    <match kubernetes.**>
      @type elasticsearch
      host elasticsearch
      port 9200
      logstash_format true
      logstash_prefix kubernetes
      include_tag_key true
      type_name fluentd
      <buffer>
        @type file
        path /var/log/fluentd-buffers/kubernetes.system.buffer
        flush_mode interval
        retry_type exponential_backoff
        flush_thread_count 2
        flush_interval 5s
        retry_forever
        retry_max_interval 30
        chunk_limit_size 2M
        queue_limit_length 8
        overflow_action block
      </buffer>
    </match>
```

### Distributed Tracing

```python
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

# Configure tracer
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

# Configure Jaeger exporter
jaeger_exporter = JaegerExporter(
    agent_host_name="jaeger",
    agent_port=6831,
)

trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(jaeger_exporter)
)

# Instrument FastAPI
app = FastAPI()
FastAPIInstrumentor.instrument_app(app)
RequestsInstrumentor().instrument()

# Manual tracing
@app.post("/predict")
async def predict(data: dict):
    with tracer.start_as_current_span("predict") as span:
        span.set_attribute("model_id", data.get('model_id'))

        # Preprocessing
        with tracer.start_as_current_span("preprocess"):
            processed = preprocess(data['input'])

        # Model inference
        with tracer.start_as_current_span("inference") as inf_span:
            result = model.predict(processed)
            inf_span.set_attribute("inference_time_ms", result['time'])

        # Postprocessing
        with tracer.start_as_current_span("postprocess"):
            output = postprocess(result)

        return output
```

---

## Testing Requirements

### Unit Testing

```python
import pytest
import torch
from src.model import ModelServer
from src.preprocessing import preprocess

@pytest.fixture
def model_server():
    """Fixture for model server"""
    server = ModelServer(model_path="/tmp/test_model.pth")
    yield server
    server.cleanup()

@pytest.fixture
def sample_input():
    """Fixture for sample input"""
    return [[1.0, 2.0, 3.0, 4.0]]

class TestModelServer:
    def test_model_loads(self, model_server):
        """Test that model loads successfully"""
        assert model_server.model is not None
        assert isinstance(model_server.model, torch.nn.Module)

    def test_predict_shape(self, model_server, sample_input):
        """Test prediction output shape"""
        result = model_server.predict(sample_input)
        assert isinstance(result, list)
        assert len(result) == len(sample_input)

    def test_predict_range(self, model_server, sample_input):
        """Test prediction values are in valid range"""
        result = model_server.predict(sample_input)
        for pred in result:
            assert all(0 <= p <= 1 for p in pred)

    def test_predict_invalid_input(self, model_server):
        """Test error handling for invalid input"""
        with pytest.raises(ValueError):
            model_server.predict([[]])

    def test_predict_batch(self, model_server):
        """Test batch prediction"""
        batch = [[1, 2, 3, 4]] * 10
        result = model_server.predict(batch)
        assert len(result) == 10

class TestPreprocessing:
    def test_preprocess_normalization(self):
        """Test input normalization"""
        input_data = [[1, 2, 3, 4]]
        result = preprocess(input_data)
        assert torch.is_tensor(result)
        assert result.shape == (1, 4)

    def test_preprocess_handles_nan(self):
        """Test NaN handling"""
        input_data = [[1, float('nan'), 3, 4]]
        with pytest.raises(ValueError, match="contains NaN"):
            preprocess(input_data)

# Run with: pytest tests/ -v --cov=src --cov-report=html
```

### Integration Testing

```python
import pytest
import requests
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

@pytest.fixture(scope="module")
def api_url():
    """API base URL"""
    return "http://localhost:8080"

class TestAPIIntegration:
    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_predict_endpoint(self):
        """Test prediction endpoint"""
        payload = {
            "model_id": "resnet50",
            "input": [[1.0, 2.0, 3.0, 4.0]]
        }
        response = client.post("/predict", json=payload)
        assert response.status_code == 200
        assert "prediction" in response.json()

    def test_predict_authentication(self):
        """Test authentication required"""
        payload = {"input": [[1, 2, 3, 4]]}
        response = client.post("/predict", json=payload)
        assert response.status_code == 401

    def test_predict_rate_limit(self):
        """Test rate limiting"""
        payload = {"input": [[1, 2, 3, 4]]}
        headers = {"Authorization": "Bearer test-token"}

        # Send many requests
        responses = []
        for _ in range(100):
            resp = client.post("/predict", json=payload, headers=headers)
            responses.append(resp)

        # Check some were rate limited
        rate_limited = [r for r in responses if r.status_code == 429]
        assert len(rate_limited) > 0

class TestDatabaseIntegration:
    def test_prediction_saved_to_database(self, db_session):
        """Test prediction is saved to database"""
        # Make prediction
        payload = {"input": [[1, 2, 3, 4]]}
        response = client.post("/predict", json=payload)
        prediction_id = response.json()["id"]

        # Check database
        from src.models import Prediction
        pred = db_session.query(Prediction).filter_by(id=prediction_id).first()
        assert pred is not None
        assert pred.result is not None

    def test_cache_hit(self, redis_client):
        """Test cache hit for repeated requests"""
        payload = {"input": [[1, 2, 3, 4]]}

        # First request (cache miss)
        resp1 = client.post("/predict", json=payload)
        time1 = resp1.elapsed.total_seconds()

        # Second request (cache hit)
        resp2 = client.post("/predict", json=payload)
        time2 = resp2.elapsed.total_seconds()

        # Cache hit should be faster
        assert time2 < time1 * 0.5
        assert resp1.json()["prediction"] == resp2.json()["prediction"]
```

### Load Testing

```python
# locustfile.py
from locust import HttpUser, task, between
import random

class ModelServingUser(HttpUser):
    wait_time = between(1, 3)  # Wait 1-3 seconds between requests

    def on_start(self):
        """Login and get token"""
        response = self.client.post("/auth/login", json={
            "username": "test@example.com",
            "password": "password123"
        })
        self.token = response.json()["access_token"]

    @task(3)  # Weight: 3x more frequent than model_info
    def predict(self):
        """Make prediction request"""
        payload = {
            "model_id": random.choice(["resnet50", "vgg16", "efficientnet"]),
            "input": [[random.random() for _ in range(224*224*3)]]
        }
        self.client.post(
            "/predict",
            json=payload,
            headers={"Authorization": f"Bearer {self.token}"}
        )

    @task(1)
    def model_info(self):
        """Get model information"""
        model_id = random.choice(["resnet50", "vgg16", "efficientnet"])
        self.client.get(
            f"/models/{model_id}",
            headers={"Authorization": f"Bearer {self.token}"}
        )

    @task(1)
    def health_check(self):
        """Health check"""
        self.client.get("/health")

# Run with:
# locust -f locustfile.py --host=http://localhost:8080 --users=100 --spawn-rate=10
```

### Chaos Engineering

```yaml
# chaos-experiment.yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: pod-failure-test
  namespace: production
spec:
  action: pod-failure
  mode: one
  selector:
    namespaces:
      - production
    labelSelectors:
      app: model-serving
  duration: "30s"
  scheduler:
    cron: "@every 1h"  # Run every hour

---
# Network latency chaos
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: network-delay
  namespace: production
spec:
  action: delay
  mode: all
  selector:
    namespaces:
      - production
    labelSelectors:
      app: model-serving
  delay:
    latency: "100ms"
    jitter: "50ms"
  duration: "5m"

---
# CPU stress test
apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: cpu-stress
  namespace: production
spec:
  mode: one
  selector:
    namespaces:
      - production
    labelSelectors:
      app: model-serving
  stressors:
    cpu:
      workers: 2
      load: 80
  duration: "2m"
```

---

## CI/CD Pipeline

```yaml
# .github/workflows/ci-cd.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Cache dependencies
      uses: actions/cache@v3
      with:
        path: ~/.cache/pip
        key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt

    - name: Lint with flake8
      run: |
        flake8 src/ --count --select=E9,F63,F7,F82 --show-source --statistics
        flake8 src/ --count --exit-zero --max-complexity=10 --max-line-length=127

    - name: Type check with mypy
      run: mypy src/

    - name: Run tests
      run: |
        pytest tests/ -v \
          --cov=src \
          --cov-report=xml \
          --cov-report=html \
          --junitxml=junit.xml

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        fail_ci_if_error: true

  security-scan:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3

    - name: Run Trivy vulnerability scanner
      uses: aquasecurity/trivy-action@master
      with:
        scan-type: 'fs'
        scan-ref: '.'
        format: 'sarif'
        output: 'trivy-results.sarif'

    - name: Upload Trivy results to GitHub Security tab
      uses: github/codeql-action/upload-sarif@v2
      with:
        sarif_file: 'trivy-results.sarif'

    - name: Run Bandit security scan
      run: |
        pip install bandit
        bandit -r src/ -f json -o bandit-report.json

  build:
    needs: [test, security-scan]
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
    - uses: actions/checkout@v3

    - name: Log in to Container Registry
      uses: docker/login-action@v2
      with:
        registry: ${{ env.REGISTRY }}
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}

    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v4
      with:
        images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
        tags: |
          type=ref,event=branch
          type=ref,event=pr
          type=semver,pattern={{version}}
          type=semver,pattern={{major}}.{{minor}}
          type=sha

    - name: Build and push Docker image
      uses: docker/build-push-action@v4
      with:
        context: .
        push: true
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}
        cache-from: type=gha
        cache-to: type=gha,mode=max

  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/develop'
    environment: staging

    steps:
    - uses: actions/checkout@v3

    - name: Configure kubectl
      uses: azure/k8s-set-context@v3
      with:
        method: kubeconfig
        kubeconfig: ${{ secrets.KUBE_CONFIG_STAGING }}

    - name: Deploy to staging
      run: |
        kubectl set image deployment/model-serving \
          app=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:sha-${GITHUB_SHA::7} \
          --namespace=staging

        kubectl rollout status deployment/model-serving \
          --namespace=staging \
          --timeout=5m

    - name: Run smoke tests
      run: |
        chmod +x ./scripts/smoke-tests.sh
        ./scripts/smoke-tests.sh staging

  deploy-production:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    environment: production

    steps:
    - uses: actions/checkout@v3

    - name: Configure kubectl
      uses: azure/k8s-set-context@v3
      with:
        method: kubeconfig
        kubeconfig: ${{ secrets.KUBE_CONFIG_PRODUCTION }}

    - name: Deploy to production
      run: |
        kubectl set image deployment/model-serving \
          app=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:sha-${GITHUB_SHA::7} \
          --namespace=production

        kubectl rollout status deployment/model-serving \
          --namespace=production \
          --timeout=10m

    - name: Run smoke tests
      run: |
        chmod +x ./scripts/smoke-tests.sh
        ./scripts/smoke-tests.sh production

    - name: Notify deployment
      uses: 8398a7/action-slack@v3
      with:
        status: ${{ job.status }}
        text: 'Deployment to production completed'
        webhook_url: ${{ secrets.SLACK_WEBHOOK }}
      if: always()
```

---

## Deployment Strategies

### Blue-Green Deployment

```yaml
# Blue deployment (current production)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: model-serving-blue
  namespace: production
  labels:
    app: model-serving
    version: blue
spec:
  replicas: 3
  selector:
    matchLabels:
      app: model-serving
      version: blue
  template:
    metadata:
      labels:
        app: model-serving
        version: blue
    spec:
      containers:
      - name: app
        image: model-serving:v1.0.0
        ports:
        - containerPort: 8080

---
# Green deployment (new version)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: model-serving-green
  namespace: production
  labels:
    app: model-serving
    version: green
spec:
  replicas: 3
  selector:
    matchLabels:
      app: model-serving
      version: green
  template:
    metadata:
      labels:
        app: model-serving
        version: green
    spec:
      containers:
      - name: app
        image: model-serving:v1.1.0
        ports:
        - containerPort: 8080

---
# Service (initially points to blue)
apiVersion: v1
kind: Service
metadata:
  name: model-serving
  namespace: production
spec:
  selector:
    app: model-serving
    version: blue  # Switch to "green" to activate new version
  ports:
  - port: 80
    targetPort: 8080
```

**Deployment Script:**

```bash
#!/bin/bash
# blue-green-deploy.sh

set -e

NAMESPACE="production"
NEW_VERSION=$1

if [ -z "$NEW_VERSION" ]; then
  echo "Usage: $0 <new-version>"
  exit 1
fi

echo "Deploying green version: $NEW_VERSION"

# 1. Deploy green deployment
kubectl set image deployment/model-serving-green \
  app=model-serving:$NEW_VERSION \
  --namespace=$NAMESPACE

# 2. Wait for green to be ready
kubectl rollout status deployment/model-serving-green \
  --namespace=$NAMESPACE \
  --timeout=5m

# 3. Run smoke tests on green
echo "Running smoke tests on green..."
GREEN_POD=$(kubectl get pod -n $NAMESPACE -l version=green -o jsonpath='{.items[0].metadata.name}')
kubectl port-forward -n $NAMESPACE $GREEN_POD 9090:8080 &
PF_PID=$!
sleep 5

if curl -f http://localhost:9090/health; then
  echo "Smoke tests passed!"
else
  echo "Smoke tests failed!"
  kill $PF_PID
  exit 1
fi
kill $PF_PID

# 4. Switch traffic to green
echo "Switching traffic to green..."
kubectl patch service model-serving \
  -n $NAMESPACE \
  -p '{"spec":{"selector":{"version":"green"}}}'

echo "Deployment complete!"
echo "Monitor for issues. To rollback:"
echo "  kubectl patch service model-serving -n $NAMESPACE -p '{\"spec\":{\"selector\":{\"version\":\"blue\"}}}'"
```

### Canary Deployment

```yaml
# Stable deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: model-serving-stable
  namespace: production
spec:
  replicas: 9  # 90% of traffic
  selector:
    matchLabels:
      app: model-serving
      track: stable
  template:
    metadata:
      labels:
        app: model-serving
        track: stable
    spec:
      containers:
      - name: app
        image: model-serving:v1.0.0

---
# Canary deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: model-serving-canary
  namespace: production
spec:
  replicas: 1  # 10% of traffic
  selector:
    matchLabels:
      app: model-serving
      track: canary
  template:
    metadata:
      labels:
        app: model-serving
        track: canary
    spec:
      containers:
      - name: app
        image: model-serving:v1.1.0

---
# Service balances across both
apiVersion: v1
kind: Service
metadata:
  name: model-serving
  namespace: production
spec:
  selector:
    app: model-serving
  ports:
  - port: 80
    targetPort: 8080
```

**Gradual Rollout Script:**

```bash
#!/bin/bash
# canary-deploy.sh

set -e

NAMESPACE="production"
NEW_VERSION=$1
TOTAL_REPLICAS=10

if [ -z "$NEW_VERSION" ]; then
  echo "Usage: $0 <new-version>"
  exit 1
fi

# Update canary image
kubectl set image deployment/model-serving-canary \
  app=model-serving:$NEW_VERSION \
  --namespace=$NAMESPACE

# Wait for canary to be ready
kubectl rollout status deployment/model-serving-canary \
  --namespace=$NAMESPACE

echo "Canary deployed. Monitoring metrics..."

# Gradual rollout: 10% -> 25% -> 50% -> 100%
for PERCENT in 10 25 50 100; do
  CANARY_REPLICAS=$(($TOTAL_REPLICAS * $PERCENT / 100))
  STABLE_REPLICAS=$(($TOTAL_REPLICAS - $CANARY_REPLICAS))

  echo "Scaling to $PERCENT%: canary=$CANARY_REPLICAS, stable=$STABLE_REPLICAS"

  kubectl scale deployment/model-serving-canary \
    --replicas=$CANARY_REPLICAS \
    --namespace=$NAMESPACE

  kubectl scale deployment/model-serving-stable \
    --replicas=$STABLE_REPLICAS \
    --namespace=$NAMESPACE

  # Wait and check metrics
  sleep 300  # 5 minutes

  # Check error rate (pseudo-code)
  ERROR_RATE=$(check_error_rate)
  if [ $ERROR_RATE -gt 5 ]; then
    echo "High error rate detected! Rolling back..."
    kubectl scale deployment/model-serving-canary --replicas=0 --namespace=$NAMESPACE
    kubectl scale deployment/model-serving-stable --replicas=$TOTAL_REPLICAS --namespace=$NAMESPACE
    exit 1
  fi

  echo "$PERCENT% rollout successful. Continuing..."
done

echo "Canary deployment complete!"
```

---

## Incident Response

### Incident Response Runbook

```markdown
# Incident Response Procedures

## Incident Severity Levels

| Level | Description | Response Time | Examples |
|-------|-------------|---------------|----------|
| SEV-1 | Critical outage | Immediate | Total system down, data loss |
| SEV-2 | Major impact | 15 minutes | Partial outage, high error rate |
| SEV-3 | Minor impact | 2 hours | Performance degradation |
| SEV-4 | Minimal impact | 24 hours | Minor bugs, cosmetic issues |

## Incident Response Steps

### 1. Detection and Acknowledgment
- Alert fires or user report received
- On-call engineer acknowledges
- Create incident ticket
- Notify stakeholders

### 2. Assessment
- Determine severity
- Identify scope of impact
- Check recent changes
- Review metrics and logs

### 3. Mitigation
- Implement immediate fix or rollback
- Communicate status to stakeholders
- Document actions taken

### 4. Resolution
- Verify fix resolves issue
- Monitor for recurrence
- Update incident ticket
- Close alert

### 5. Post-Mortem
- Schedule blameless post-mortem
- Document timeline
- Identify root cause
- Define action items

## Common Incidents

### Incident: High Error Rate

**Detection:**
```
Alert: HighErrorRate
Error rate >5% for 5 minutes
```

**Response:**
1. Check recent deployments:
   ```bash
   kubectl rollout history deployment/model-serving -n production
   ```

2. Check application logs:
   ```bash
   kubectl logs -n production -l app=model-serving --tail=100
   ```

3. If recent deployment, rollback:
   ```bash
   kubectl rollout undo deployment/model-serving -n production
   ```

4. Monitor error rate:
   ```
   rate(http_requests_total{status=~"5.."}[5m]) /
   rate(http_requests_total[5m])
   ```

5. If persists, scale up replicas:
   ```bash
   kubectl scale deployment/model-serving --replicas=10 -n production
   ```

**Communication Template:**
```
Incident: High Error Rate on Model Serving API
Status: Investigating / Identified / Monitoring / Resolved
Impact: X% of requests failing
Actions: Rolled back deployment to v1.0.0
ETA: Monitoring for 30 minutes
```

### Incident: Database Down

**Detection:**
```
Alert: DatabaseDown
Database connection failures
```

**Response:**
1. Check database pod status:
   ```bash
   kubectl get pods -n production -l app=postgres
   kubectl describe pod postgres-0 -n production
   ```

2. Check database logs:
   ```bash
   kubectl logs postgres-0 -n production --tail=200
   ```

3. If pod is down, check if it can be restarted:
   ```bash
   kubectl delete pod postgres-0 -n production
   ```

4. If data corruption, restore from backup:
   ```bash
   ./scripts/restore-db.sh latest
   ```

5. If complete failure, failover to replica:
   ```bash
   kubectl exec postgres-1 -n production -- pg_ctl promote
   ```

**Escalation:**
- SEV-1: Page database team lead
- SEV-2: Notify database team
```

---

## Cost Management

### Cost Optimization Strategies

```yaml
# Resource quotas per namespace
apiVersion: v1
kind: ResourceQuota
metadata:
  name: production-quota
  namespace: production
spec:
  hard:
    requests.cpu: "100"
    requests.memory: "200Gi"
    requests.nvidia.com/gpu: "8"
    limits.cpu: "200"
    limits.memory: "400Gi"
    limits.nvidia.com/gpu: "8"
    persistentvolumeclaims: "20"
    services.loadbalancers: "5"

---
# Limit ranges for individual pods
apiVersion: v1
kind: LimitRange
metadata:
  name: production-limits
  namespace: production
spec:
  limits:
  - max:
      cpu: "8"
      memory: "32Gi"
    min:
      cpu: "100m"
      memory: "128Mi"
    default:
      cpu: "1"
      memory: "2Gi"
    defaultRequest:
      cpu: "500m"
      memory: "1Gi"
    type: Container
```

### Cost Monitoring

```python
# Cost estimation script
import boto3
from datetime import datetime, timedelta

def estimate_monthly_cost():
    """Estimate monthly AWS cost"""
    ce = boto3.client('ce')

    end = datetime.now().date()
    start = end - timedelta(days=30)

    response = ce.get_cost_and_usage(
        TimePeriod={
            'Start': start.strftime('%Y-%m-%d'),
            'End': end.strftime('%Y-%m-%d')
        },
        Granularity='MONTHLY',
        Metrics=['UnblendedCost'],
        GroupBy=[
            {'Type': 'DIMENSION', 'Key': 'SERVICE'},
            {'Type': 'TAG', 'Key': 'Environment'}
        ]
    )

    for result in response['ResultsByTime']:
        print(f"Period: {result['TimePeriod']['Start']} to {result['TimePeriod']['End']}")
        for group in result['Groups']:
            service = group['Keys'][0]
            env = group['Keys'][1]
            cost = float(group['Metrics']['UnblendedCost']['Amount'])
            print(f"  {service} ({env}): ${cost:.2f}")

# Cost alerts
cost_alert = {
    'threshold': 10000,  # $10,000/month
    'notification': 'slack://infrastructure'
}
```

---

## Documentation Requirements

### Required Documentation

```markdown
## Documentation Checklist

### Architecture Documentation
- [ ] System architecture diagram
- [ ] Data flow diagrams
- [ ] Network topology
- [ ] Security architecture
- [ ] Deployment architecture

### API Documentation
- [ ] OpenAPI/Swagger specification
- [ ] Authentication guide
- [ ] Rate limiting documentation
- [ ] Error codes and handling
- [ ] Example requests/responses

### Runbooks
- [ ] Deployment procedures
- [ ] Rollback procedures
- [ ] Backup and restore
- [ ] Incident response
- [ ] Troubleshooting guide

### Operations Documentation
- [ ] Monitoring and alerting
- [ ] Logging and tracing
- [ ] Scaling procedures
- [ ] Disaster recovery
- [ ] On-call rotation

### Development Documentation
- [ ] Setup instructions
- [ ] Development workflow
- [ ] Testing procedures
- [ ] Code style guide
- [ ] Contributing guidelines
```

---

## Project-Specific Checklists

### Project 01: Model Serving API

```markdown
## Pre-Production Checklist

### Security
- [ ] API key authentication implemented
- [ ] Rate limiting configured (100 req/min)
- [ ] TLS certificate configured
- [ ] Secrets in Kubernetes secrets
- [ ] Container runs as non-root user
- [ ] Network policies defined

### Reliability
- [ ] Health endpoint returns 200
- [ ] Readiness probe configured (initial delay: 30s)
- [ ] Liveness probe configured
- [ ] 3 replicas deployed across zones
- [ ] PodDisruptionBudget (min available: 2)
- [ ] Resource limits set (2 CPU, 4Gi memory)

### Monitoring
- [ ] Prometheus metrics exposed on /metrics
- [ ] Request latency tracked
- [ ] Error rate tracked
- [ ] Grafana dashboard created
- [ ] Alerts configured (error rate, latency, pod down)

### Testing
- [ ] Unit tests >80% coverage
- [ ] Integration tests passing
- [ ] Load test: 100 req/s sustained
- [ ] Stress test: Handles 500 req/s
- [ ] Model accuracy validated

### Documentation
- [ ] API documentation (OpenAPI)
- [ ] Deployment runbook
- [ ] Troubleshooting guide
- [ ] Example client code
```

### Project 02: Multi-Model Serving

```markdown
## Pre-Production Checklist

### Security
- [ ] Model access control implemented
- [ ] Input validation for model selection
- [ ] Model registry access restricted
- [ ] Audit logging for model usage

### Reliability
- [ ] Model lazy loading implemented
- [ ] Model cache with LRU eviction
- [ ] Graceful handling of model load failures
- [ ] Circuit breaker for model loading
- [ ] Fallback to default model

### Performance
- [ ] Model preloading for top 3 models
- [ ] Cache hit rate >60%
- [ ] Model switch time <100ms
- [ ] Memory usage monitored per model

### Monitoring
- [ ] Per-model metrics (requests, latency, errors)
- [ ] Model cache metrics (hit rate, evictions)
- [ ] Model registry metrics
- [ ] Model load time tracked
```

### Project 03: GPU-Accelerated Inference

```markdown
## Pre-Production Checklist

### GPU Resources
- [ ] GPU quota allocated (2 GPUs)
- [ ] GPU node pool configured
- [ ] GPU scheduling tested
- [ ] GPU metrics monitored

### Performance
- [ ] GPU utilization >80% under load
- [ ] Dynamic batching implemented
- [ ] Batch size optimized (32)
- [ ] Mixed precision (FP16) enabled
- [ ] Model compiled with TorchScript/TensorRT

### Monitoring
- [ ] GPU utilization metrics
- [ ] GPU memory metrics
- [ ] Batch size metrics
- [ ] Inference time per batch size
- [ ] Queue depth metrics

### Cost
- [ ] GPU usage tracked
- [ ] Cost per inference calculated
- [ ] Autoscaling configured
- [ ] Spot instance usage evaluated
```

---

## Launch Checklist

### Pre-Launch (1 week before)

```markdown
- [ ] All production readiness criteria met
- [ ] Load testing completed
- [ ] Security audit passed
- [ ] Disaster recovery tested
- [ ] Runbooks reviewed and updated
- [ ] On-call rotation scheduled
- [ ] Stakeholders notified of launch date
- [ ] Marketing materials prepared
- [ ] Customer support trained
- [ ] Monitoring dashboards reviewed
```

### Launch Day

```markdown
- [ ] Deploy to production (use deployment strategy)
- [ ] Verify all services healthy
- [ ] Run smoke tests
- [ ] Monitor error rates
- [ ] Monitor latency
- [ ] Monitor resource usage
- [ ] Check logs for errors
- [ ] Verify external integrations working
- [ ] Test user workflows
- [ ] Update status page
- [ ] Notify stakeholders of successful launch
```

### Post-Launch (First 24 hours)

```markdown
- [ ] Monitor error rates continuously
- [ ] Monitor latency continuously
- [ ] Check cost tracking
- [ ] Review alert firing rates
- [ ] Collect user feedback
- [ ] Address critical issues immediately
- [ ] Document any incidents
- [ ] Team debrief meeting
- [ ] Update documentation with learnings
- [ ] Plan optimization improvements
```

### Post-Launch (First week)

```markdown
- [ ] Review week's worth of metrics
- [ ] Analyze cost vs. budget
- [ ] Review and tune alerts
- [ ] Address performance issues
- [ ] Implement quick wins
- [ ] Schedule post-launch retrospective
- [ ] Document lessons learned
- [ ] Plan next iteration
```

---

## Resources and References

### Official Documentation
- **Kubernetes Production Best Practices**: https://kubernetes.io/docs/setup/best-practices/
- **CNCF Cloud Native Security**: https://www.cncf.io/projects/security/
- **Prometheus Best Practices**: https://prometheus.io/docs/practices/

### Tools
- **Security**: Trivy, Falco, OPA/Gatekeeper
- **Monitoring**: Prometheus, Grafana, Datadog
- **Logging**: Fluentd, Elasticsearch, Loki
- **Tracing**: Jaeger, Zipkin, OpenTelemetry
- **CI/CD**: GitHub Actions, GitLab CI, ArgoCD
- **Chaos Engineering**: Chaos Mesh, Litmus

### Books
- "Site Reliability Engineering" by Google
- "The DevOps Handbook" by Gene Kim et al.
- "Accelerate" by Nicole Forsgren et al.

---

**Production readiness is a journey, not a destination. Continuously improve your systems, processes, and practices.**

**Good luck with your production launch!**
