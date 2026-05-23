#!/usr/bin/env bash
# Connect cluster-A and cluster-B with Cilium ClusterMesh.
set -euo pipefail

cilium clustermesh enable --context cluster-a --service-type NodePort
cilium clustermesh enable --context cluster-b --service-type NodePort
cilium clustermesh connect --context cluster-a --destination-context cluster-b
cilium clustermesh status --context cluster-a
