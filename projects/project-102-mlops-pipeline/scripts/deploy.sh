#!/bin/bash
set -e

echo "==============================================="
echo "Kubernetes Deployment Script"
echo "==============================================="

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo "${RED}kubectl not found. Please install kubectl first.${NC}"
    exit 1
fi

echo "${GREEN}✓ kubectl found${NC}"

# Create namespace if not exists
NAMESPACE="ml-serving"
if kubectl get namespace $NAMESPACE &> /dev/null; then
    echo "${GREEN}✓ Namespace $NAMESPACE already exists${NC}"
else
    echo "Creating namespace $NAMESPACE..."
    kubectl create namespace $NAMESPACE
    echo "${GREEN}✓ Namespace created${NC}"
fi

# Apply Kubernetes manifests
echo "Applying Kubernetes manifests..."

echo "Deploying PostgreSQL..."
kubectl apply -f kubernetes/postgres/ -n $NAMESPACE

echo "Deploying Redis..."
kubectl apply -f kubernetes/redis/ -n $NAMESPACE

echo "Deploying MinIO..."
kubectl apply -f kubernetes/minio/ -n $NAMESPACE

echo "Waiting for storage services to be ready..."
sleep 10

echo "Deploying MLflow..."
kubectl apply -f kubernetes/mlflow/ -n $NAMESPACE

echo "Deploying Airflow..."
kubectl apply -f kubernetes/airflow/ -n $NAMESPACE

echo "${GREEN}✓ All manifests applied${NC}"

# Wait for deployments to be ready
echo "Waiting for deployments to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment --all -n $NAMESPACE

echo "${GREEN}✓ All deployments are ready${NC}"

# Display service information
echo ""
echo "==============================================="
echo "Deployment Complete!"
echo "==============================================="
echo ""
echo "Services deployed in namespace: $NAMESPACE"
echo ""
echo "To access services:"
echo "  kubectl get services -n $NAMESPACE"
echo ""
echo "To view pods:"
echo "  kubectl get pods -n $NAMESPACE"
echo ""
echo "To view logs:"
echo "  kubectl logs -f <pod-name> -n $NAMESPACE"
echo ""
