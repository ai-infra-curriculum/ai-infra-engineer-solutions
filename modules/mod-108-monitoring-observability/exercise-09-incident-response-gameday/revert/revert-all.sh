#!/usr/bin/env bash
set -euo pipefail
NS=${NS:-default}

kubectl set image -n "$NS" deployment/iris-api iris-api=iris-api:0.2 || true
kubectl delete -n "$NS" networkpolicy block-feature-store-egress --ignore-not-found
kubectl set resources -n "$NS" deployment/iris-api \
  --containers=iris-api --limits=memory=1Gi || true
kubectl rollout restart -n "$NS" deployment/iris-api
echo "[$(date)] Reverted all injections."
