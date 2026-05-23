#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

kind create cluster --config kind-config.yaml || true
docker tag hello-flask:0.1 hello-flask:0.1
kind load docker-image hello-flask:0.1 --name lab-03
kubectl apply -f deployment.yaml -f service.yaml
kubectl rollout status deployment/hello-flask --timeout=2m
curl -sf http://localhost:8080/health && echo " — OK"
