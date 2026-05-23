#!/usr/bin/env bash
set -euo pipefail
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml -f secret.yaml
kubectl apply -f deployment.yaml -f service.yaml -f ingress.yaml -f hpa.yaml
kubectl rollout status -n iris deployment/iris-api --timeout=120s
