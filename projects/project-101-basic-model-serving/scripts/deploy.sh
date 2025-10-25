#!/bin/bash

# Deployment script for Kubernetes
# This script deploys the model serving system to a Kubernetes cluster

set -e  # Exit on error

echo "=========================================="
echo "Model Serving System - Deployment Script"
echo "=========================================="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Configuration
IMAGE_NAME=${IMAGE_NAME:-"model-serving-api:latest"}
NAMESPACE=${NAMESPACE:-"model-serving"}

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    print_error "kubectl is not installed. Please install kubectl first."
    exit 1
fi

# Check if connected to a cluster
if ! kubectl cluster-info &> /dev/null; then
    print_error "Not connected to a Kubernetes cluster. Please configure kubectl."
    exit 1
fi

print_status "Connected to Kubernetes cluster"

# Check if Docker image exists or needs to be built
echo ""
echo "Checking Docker image..."
if ! docker image inspect $IMAGE_NAME &> /dev/null; then
    print_warning "Docker image not found. Building..."
    docker build -t $IMAGE_NAME .
    print_status "Docker image built"
else
    print_status "Docker image found"
    read -p "Rebuild image? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker build -t $IMAGE_NAME .
        print_status "Docker image rebuilt"
    fi
fi

# Create namespace
echo ""
echo "Creating namespace..."
if kubectl get namespace $NAMESPACE &> /dev/null; then
    print_warning "Namespace $NAMESPACE already exists"
else
    kubectl apply -f kubernetes/namespace.yaml
    print_status "Namespace created"
fi

# Apply ConfigMap
echo ""
echo "Applying ConfigMap..."
kubectl apply -f kubernetes/configmap.yaml
print_status "ConfigMap applied"

# Apply Deployment
echo ""
echo "Deploying application..."
kubectl apply -f kubernetes/deployment.yaml
print_status "Deployment applied"

# Wait for deployment to be ready
echo ""
echo "Waiting for deployment to be ready..."
kubectl rollout status deployment/model-serving -n $NAMESPACE --timeout=5m
print_status "Deployment is ready"

# Apply Service
echo ""
echo "Creating service..."
kubectl apply -f kubernetes/service.yaml
print_status "Service created"

# Apply HPA (optional)
echo ""
read -p "Enable Horizontal Pod Autoscaler? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    kubectl apply -f kubernetes/hpa.yaml
    print_status "HPA enabled"
fi

# Get service information
echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""

# Get service URL
SERVICE_TYPE=$(kubectl get svc model-serving -n $NAMESPACE -o jsonpath='{.spec.type}')

if [ "$SERVICE_TYPE" = "LoadBalancer" ]; then
    echo "Waiting for LoadBalancer IP..."
    kubectl wait --for=jsonpath='{.status.loadBalancer.ingress}' svc/model-serving -n $NAMESPACE --timeout=2m 2>/dev/null || true
    EXTERNAL_IP=$(kubectl get svc model-serving -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
    if [ -n "$EXTERNAL_IP" ]; then
        echo "Service URL: http://$EXTERNAL_IP"
        echo "API Docs: http://$EXTERNAL_IP/docs"
    else
        print_warning "LoadBalancer IP not yet assigned"
    fi
elif [ "$SERVICE_TYPE" = "NodePort" ]; then
    NODE_PORT=$(kubectl get svc model-serving-nodeport -n $NAMESPACE -o jsonpath='{.spec.ports[0].nodePort}')
    NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="ExternalIP")].address}')
    if [ -z "$NODE_IP" ]; then
        NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
    fi
    echo "Service URL: http://$NODE_IP:$NODE_PORT"
    echo "API Docs: http://$NODE_IP:$NODE_PORT/docs"
fi

echo ""
echo "Useful commands:"
echo "  View pods:        kubectl get pods -n $NAMESPACE"
echo "  View logs:        kubectl logs -f deployment/model-serving -n $NAMESPACE"
echo "  Port forward:     kubectl port-forward svc/model-serving 8000:80 -n $NAMESPACE"
echo "  Delete deployment: kubectl delete namespace $NAMESPACE"
echo ""
