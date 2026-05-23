#!/usr/bin/env bash
# Stand up DR region from scratch. Pair with DR_PLAN.md.
set -euo pipefail

DR_REGION=${DR_REGION:-us-west-2}

t0=$(date +%s)

echo "[step 1] terraform apply DR cluster"
cd dr/ && AWS_REGION=$DR_REGION terraform apply -auto-approve && cd ..

echo "[step 2] restore vault snapshot"
LATEST_SNAP=$(aws s3 ls s3://vault-dr-snapshots/ --recursive | sort | tail -1 | awk '{print $4}')
aws s3 cp s3://vault-dr-snapshots/$LATEST_SNAP ./vault.snap
vault operator raft snapshot restore vault.snap

echo "[step 3] argo bootstrap"
argocd app sync root

echo "[step 4] RDS PITR restore"
TARGET_TS=$(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%S)
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier iris-prod \
  --target-db-instance-identifier iris-dr-$(date +%s) \
  --restore-time $TARGET_TS \
  --region $DR_REGION

echo "[step 5] DNS cutover"
aws route53 change-resource-record-sets --hosted-zone-id $ZONE_ID --change-batch file://dns-cutover.json

echo "[step 6] post-recovery verification"
python verification/post-recovery-checks.py

t1=$(date +%s)
echo "Recovery complete in $((t1 - t0))s"
