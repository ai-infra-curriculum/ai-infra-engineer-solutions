#!/usr/bin/env bash
# Incident B: block feature-store egress with a NetworkPolicy.
set -euo pipefail
NS=${NS:-default}

kubectl apply -n "$NS" -f - <<'EOF'
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: block-feature-store-egress
spec:
  podSelector: { matchLabels: { app: feature-store } }
  policyTypes: [Egress]
  egress: []   # deny all
EOF
echo "[$(date)] Injected: feature-store egress blocked. Expect 504s from iris-api."
