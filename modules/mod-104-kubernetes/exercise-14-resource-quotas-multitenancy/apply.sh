#!/usr/bin/env bash
# Idempotent setup: render team template per team in teams.yaml.
set -euo pipefail

apply_team() {
    local TEAM=$1 CPU_REQ=$2 CPU_LIM=$3 MEM_REQ=$4 MEM_LIM=$5 GPU=$6
    for f in team-template/*.yaml; do
        envsubst < "$f" | TEAM="$TEAM" CPU_REQ="$CPU_REQ" CPU_LIM="$CPU_LIM" \
            MEM_REQ="$MEM_REQ" MEM_LIM="$MEM_LIM" GPU="$GPU" \
            kubectl apply -f -
    done
}

# Manually expanded (or use yq + xargs in real life)
TEAM=ml-platform   CPU_REQ=20 CPU_LIM=40 MEM_REQ=80Gi MEM_LIM=120Gi GPU=4 apply_team
TEAM=data-science  CPU_REQ=10 CPU_LIM=20 MEM_REQ=40Gi MEM_LIM=60Gi  GPU=2 apply_team
TEAM=trust-safety  CPU_REQ=5  CPU_LIM=10 MEM_REQ=20Gi MEM_LIM=30Gi  GPU=1 apply_team
