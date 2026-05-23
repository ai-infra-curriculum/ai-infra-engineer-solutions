#!/usr/bin/env bash
# Incident A: deploy a slow image variant. SlowResponses warning should fire ~10min.
set -euo pipefail
NS=${NS:-default}

kubectl set image -n "$NS" deployment/iris-api iris-api=iris-api:0.3-slow
kubectl rollout status -n "$NS" deployment/iris-api --timeout=60s
echo "[$(date)] Injected: latency regression. Watch grafana SLO budget panel + amtool query."
