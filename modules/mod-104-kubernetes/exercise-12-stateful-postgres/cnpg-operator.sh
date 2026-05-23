#!/usr/bin/env bash
set -euo pipefail
kubectl apply --server-side -f https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg/release-1.24/releases/cnpg-1.24.0.yaml
kubectl rollout status -n cnpg-system deployment/cnpg-controller-manager
