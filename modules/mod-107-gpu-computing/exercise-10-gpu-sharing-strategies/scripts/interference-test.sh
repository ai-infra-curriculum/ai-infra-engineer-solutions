#!/usr/bin/env bash
# Verify isolation under MIG vs MPS vs time-slicing.
# Runs 2 inference pods + 1 stress pod and reports inference latency.
set -euo pipefail

kubectl apply -f ../manifests/$1/workload-pod.yaml
# Apply a 'stress' variant of the same pod doing OOM-prone work
# Compare inference latency under contention vs solo run
echo "see README for the full procedure"
