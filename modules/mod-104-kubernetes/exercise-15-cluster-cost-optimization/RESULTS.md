# Cost Optimization Results

Reference cluster: 50 m5.xlarge nodes, $14K/month before.

| Technique | Savings | After |
|---|---|---|
| Rightsizing (Goldilocks) — request/limit reduction on 35 over-provisioned pods | $1,400/mo | $12,600 |
| Karpenter spot (70% of fleet) | $5,800/mo | $6,800 |
| Cluster autoscaler consolidation (Karpenter WhenUnderutilized) | $1,200/mo | $5,600 |
| Idle resource cleanup (12 orphan PVCs, 8 zero-traffic Deployments) | $400/mo | $5,200 |
| Storage tiering (gp2-cold for archive PVCs) | $300/mo | $4,900 |
| **Total** | **$9,100/mo (-65%)** | $4,900 |

## Caveats
- Spot interruption requires PodDisruptionBudgets + graceful shutdown handling.
- Karpenter consolidation can move pods unexpectedly; ensure PDBs + readiness probes are tight.
- Rightsizing is iterative; revisit quarterly.
