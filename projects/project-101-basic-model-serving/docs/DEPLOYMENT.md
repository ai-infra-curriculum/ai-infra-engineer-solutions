# Deployment Guide

This guide covers deploying the Model Serving System in various environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development](#local-development)
3. [Docker Deployment](#docker-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Cloud Deployments](#cloud-deployments)
6. [Production Checklist](#production-checklist)
7. [Rollback Procedures](#rollback-procedures)

## Prerequisites

### Required Tools

- **Python 3.9+**: Application runtime
- **Docker 20.10+**: Containerization
- **kubectl 1.25+**: Kubernetes CLI
- **git**: Version control

### Optional Tools

- **minikube**: Local Kubernetes cluster
- **helm**: Kubernetes package manager
- **k9s**: Kubernetes CLI UI

### Access Requirements

- Docker registry access (for pushing images)
- Kubernetes cluster access (for deployment)
- Appropriate RBAC permissions

## Local Development

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd project-101-basic-model-serving
```

### Step 2: Run Setup Script

```bash
./scripts/setup.sh
```

This script will:
- Create virtual environment
- Install dependencies
- Create .env file
- Run tests

### Step 3: Start Application

```bash
# Activate virtual environment
source venv/bin/activate

# Run application
python -m uvicorn src.api:app --reload --host 0.0.0.0 --port 8000
```

### Step 4: Verify Installation

```bash
# In another terminal
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "model_loaded": true,
  "timestamp": 1234567890.123,
  "version": "1.0.0"
}
```

### Step 5: Access API Documentation

Open in browser: http://localhost:8000/docs

## Docker Deployment

### Build Docker Image

```bash
docker build -t model-serving-api:latest .
```

**Build time**: ~5-10 minutes (first time)
**Image size**: ~1.8GB

### Run Container Locally

```bash
docker run -p 8000:8000 \
  -e MODEL_DEVICE=cpu \
  -e LOG_LEVEL=INFO \
  --name model-serving \
  model-serving-api:latest
```

### Test Container

```bash
./scripts/test-deployment.sh
```

### Docker Compose (with Monitoring)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

Services:
- **API**: http://localhost:8000
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)

## Kubernetes Deployment

### Option 1: Automated Deployment

```bash
./scripts/deploy.sh
```

This script handles:
- Building Docker image
- Creating namespace
- Applying all manifests
- Waiting for rollout
- Displaying service URL

### Option 2: Manual Deployment

#### Step 1: Build and Push Image

```bash
# Build image
docker build -t <registry>/model-serving-api:v1.0.0 .

# Push to registry
docker push <registry>/model-serving-api:v1.0.0
```

#### Step 2: Update Image Reference

Edit `kubernetes/deployment.yaml`:
```yaml
spec:
  template:
    spec:
      containers:
      - name: model-serving
        image: <registry>/model-serving-api:v1.0.0
```

#### Step 3: Apply Manifests

```bash
# Create namespace
kubectl apply -f kubernetes/namespace.yaml

# Apply ConfigMap
kubectl apply -f kubernetes/configmap.yaml

# Deploy application
kubectl apply -f kubernetes/deployment.yaml

# Create service
kubectl apply -f kubernetes/service.yaml

# Optional: Enable HPA
kubectl apply -f kubernetes/hpa.yaml
```

#### Step 4: Verify Deployment

```bash
# Check pods
kubectl get pods -n model-serving

# Check deployment status
kubectl rollout status deployment/model-serving -n model-serving

# Check service
kubectl get svc -n model-serving
```

#### Step 5: Access Application

**For LoadBalancer:**
```bash
# Get external IP
kubectl get svc model-serving -n model-serving

# Access API
curl http://<EXTERNAL-IP>/health
```

**For NodePort:**
```bash
# Get node IP and port
kubectl get nodes -o wide
kubectl get svc model-serving-nodeport -n model-serving

# Access API
curl http://<NODE-IP>:<NODE-PORT>/health
```

**Port Forwarding (for testing):**
```bash
kubectl port-forward svc/model-serving 8000:80 -n model-serving

# Access locally
curl http://localhost:8000/health
```

### Minikube Deployment

```bash
# Start minikube
minikube start --memory=8192 --cpus=4

# Enable addons
minikube addons enable metrics-server
minikube addons enable ingress

# Build image in minikube
eval $(minikube docker-env)
docker build -t model-serving-api:latest .

# Deploy
kubectl apply -f kubernetes/

# Get service URL
minikube service model-serving -n model-serving --url
```

## Cloud Deployments

### AWS EKS

#### Prerequisites
- AWS CLI configured
- eksctl installed
- IAM permissions

#### Steps

```bash
# Create EKS cluster
eksctl create cluster \
  --name model-serving-cluster \
  --region us-east-1 \
  --nodes 3 \
  --node-type t3.large

# Configure kubectl
aws eks update-kubeconfig --name model-serving-cluster --region us-east-1

# Push image to ECR
aws ecr create-repository --repository-name model-serving-api
docker tag model-serving-api:latest <account>.dkr.ecr.us-east-1.amazonaws.com/model-serving-api:latest
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/model-serving-api:latest

# Deploy application
./scripts/deploy.sh

# Access via LoadBalancer
kubectl get svc model-serving -n model-serving
```

### Google GKE

```bash
# Create GKE cluster
gcloud container clusters create model-serving-cluster \
  --num-nodes=3 \
  --machine-type=n1-standard-2 \
  --zone=us-central1-a

# Get credentials
gcloud container clusters get-credentials model-serving-cluster --zone=us-central1-a

# Push to GCR
docker tag model-serving-api:latest gcr.io/<project-id>/model-serving-api:latest
docker push gcr.io/<project-id>/model-serving-api:latest

# Deploy
./scripts/deploy.sh
```

### Azure AKS

```bash
# Create resource group
az group create --name model-serving-rg --location eastus

# Create AKS cluster
az aks create \
  --resource-group model-serving-rg \
  --name model-serving-cluster \
  --node-count 3 \
  --node-vm-size Standard_D2s_v3

# Get credentials
az aks get-credentials --resource-group model-serving-rg --name model-serving-cluster

# Push to ACR
az acr create --resource-group model-serving-rg --name <registry-name> --sku Basic
az acr login --name <registry-name>
docker tag model-serving-api:latest <registry-name>.azurecr.io/model-serving-api:latest
docker push <registry-name>.azurecr.io/model-serving-api:latest

# Deploy
./scripts/deploy.sh
```

## Configuration

### Environment Variables

Edit `kubernetes/configmap.yaml`:

```yaml
data:
  # Application settings
  LOG_LEVEL: "INFO"  # DEBUG, INFO, WARNING, ERROR
  MODEL_DEVICE: "cpu"  # cpu or cuda
  TOP_K_PREDICTIONS: "5"

  # Performance
  MAX_UPLOAD_SIZE: "10485760"  # 10MB
  INFERENCE_TIMEOUT: "30.0"

  # Features
  ENABLE_METRICS: "true"
```

### Resource Limits

Edit `kubernetes/deployment.yaml`:

```yaml
resources:
  requests:
    memory: "2Gi"    # Minimum required
    cpu: "1000m"     # 1 CPU core
  limits:
    memory: "4Gi"    # Maximum allowed
    cpu: "2000m"     # 2 CPU cores
```

### Scaling Configuration

Edit `kubernetes/hpa.yaml`:

```yaml
spec:
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

## Monitoring Setup

### Prometheus

```bash
# Install Prometheus (using Helm)
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace

# Access Prometheus
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
```

### Grafana

```bash
# Access Grafana
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80

# Default credentials: admin / prom-operator

# Import dashboard
# Navigate to Dashboards > Import
# Upload monitoring/grafana/dashboards/model-serving-dashboard.json
```

## Production Checklist

### Before Deployment

- [ ] All tests passing
- [ ] Code reviewed and approved
- [ ] Security scan completed
- [ ] Resource limits configured
- [ ] Monitoring configured
- [ ] Alerting configured
- [ ] Documentation updated
- [ ] Backup strategy defined

### Configuration Review

- [ ] Environment variables set correctly
- [ ] Secrets managed securely
- [ ] Resource limits appropriate
- [ ] Replica count sufficient
- [ ] Health checks configured
- [ ] Service type appropriate

### Security Review

- [ ] Container runs as non-root
- [ ] No secrets in code/images
- [ ] Network policies configured
- [ ] RBAC configured
- [ ] Image scanning enabled
- [ ] API authentication enabled (if required)

### Performance Review

- [ ] Load testing completed
- [ ] Resource usage validated
- [ ] Latency targets met
- [ ] Auto-scaling tested
- [ ] Cache configured (if needed)

### Monitoring Review

- [ ] Metrics being collected
- [ ] Dashboards created
- [ ] Alerts configured
- [ ] Log aggregation configured
- [ ] Tracing configured (if needed)

## Rollback Procedures

### Rollback Kubernetes Deployment

```bash
# View rollout history
kubectl rollout history deployment/model-serving -n model-serving

# Rollback to previous version
kubectl rollout undo deployment/model-serving -n model-serving

# Rollback to specific revision
kubectl rollout undo deployment/model-serving -n model-serving --to-revision=2

# Verify rollback
kubectl rollout status deployment/model-serving -n model-serving
```

### Rollback Docker Image

```bash
# Tag previous version as latest
docker tag model-serving-api:v1.0.0 model-serving-api:latest

# Push to registry
docker push <registry>/model-serving-api:latest

# Restart pods
kubectl rollout restart deployment/model-serving -n model-serving
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl get pods -n model-serving

# View pod logs
kubectl logs <pod-name> -n model-serving

# Describe pod
kubectl describe pod <pod-name> -n model-serving

# Common issues:
# - Image pull errors: Check registry access
# - OOM errors: Increase memory limits
# - Startup timeout: Increase startup probe delay
```

### Service Not Accessible

```bash
# Check service
kubectl get svc -n model-serving

# Check endpoints
kubectl get endpoints -n model-serving

# Test from within cluster
kubectl run test-pod --image=curlimages/curl -it --rm -- sh
curl http://model-serving.model-serving.svc.cluster.local/health
```

### High Latency

```bash
# Check resource usage
kubectl top pods -n model-serving

# Check HPA status
kubectl get hpa -n model-serving

# View metrics
kubectl port-forward svc/model-serving 8000:80 -n model-serving
curl http://localhost:8000/metrics
```

## Maintenance

### Update Application

```bash
# Build new image
docker build -t <registry>/model-serving-api:v1.1.0 .
docker push <registry>/model-serving-api:v1.1.0

# Update deployment
kubectl set image deployment/model-serving \
  model-serving=<registry>/model-serving-api:v1.1.0 \
  -n model-serving

# Monitor rollout
kubectl rollout status deployment/model-serving -n model-serving
```

### Scale Application

```bash
# Manual scaling
kubectl scale deployment/model-serving --replicas=5 -n model-serving

# Auto-scaling (HPA)
kubectl apply -f kubernetes/hpa.yaml
```

### View Logs

```bash
# Recent logs
kubectl logs deployment/model-serving -n model-serving --tail=100

# Follow logs
kubectl logs -f deployment/model-serving -n model-serving

# Logs from specific pod
kubectl logs <pod-name> -n model-serving
```

## Support

For deployment issues:
- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Review pod logs
- Check monitoring dashboards
- Contact: ai-infra-curriculum@joshua-ferguson.com
