#!/usr/bin/env bash
# Incident C: shrink memory limit, causing OOMKilled within ~1min.
set -euo pipefail
NS=${NS:-default}

kubectl set resources -n "$NS" deployment/iris-api \
  --containers=iris-api --limits=memory=256Mi
echo "[$(date)] Injected: iris-api memory limit lowered to 256Mi. Pods will OOM."
