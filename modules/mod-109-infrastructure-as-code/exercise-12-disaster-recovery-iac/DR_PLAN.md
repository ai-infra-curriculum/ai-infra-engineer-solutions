# Disaster Recovery Plan — ML Platform

**Targets:** RTO < 4 hours • RPO < 1 hour

## Disaster scenarios covered

1. **Region failure** — entire AWS region unavailable.
2. **Account compromise** — IAM credentials leaked; need to fence + rebuild in new account.
3. **State file corruption** — Terraform state lost or unreadable.
4. **Kubernetes cluster destruction** — accidental `terraform destroy` or admin error.

## Pre-conditions (always ready)

- Terraform state versioned in S3 (cross-region replicated to `us-west-2`)
- Vault snapshots taken every 30min, stored in `us-west-2` S3
- Model artifacts in S3 with cross-region replication
- Database PITR (point-in-time-recovery) enabled, 35-day window
- Bootstrap script (`recover.sh`) tested quarterly via Game Day

## Recovery procedure (region failure)

| Step | Action | Time budget |
|---|---|---|
| 0 | Declare DR; primary on-call notifies leadership | 5min |
| 1 | Bring up new cluster in DR region: `cd dr/ && terraform apply` | 60min |
| 2 | Restore Vault snapshot: `vault operator raft snapshot restore vault.snap` | 15min |
| 3 | ArgoCD bootstrap: `argocd app sync root` (deploys all apps from Git) | 30min |
| 4 | RDS restore from PITR snapshot in DR region | 30min |
| 5 | DNS cutover via Route53 weighted records (95% DR, 5% old) | 5min |
| 6 | Run `post-recovery-checks.py`; ramp DR to 100% | 30min |
| 7 | Postmortem: log all steps + decisions | (later) |

**Total: ~3 hours** under tested conditions.

## Quarterly Game Day

- Pick a Tuesday morning; entire ML platform team participates
- Pick a scenario (rotate through the 4 above)
- Run the recovery; measure actual time-to-restore
- Compare against RTO/RPO; document deviations
- Update DR_PLAN.md + scripts based on lessons learned
