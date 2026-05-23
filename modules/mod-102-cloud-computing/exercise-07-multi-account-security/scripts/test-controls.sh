#!/usr/bin/env bash
# Verify SCPs actually block what they're supposed to.
# Run AS the test user in a workload account.
set -euo pipefail

PASS=0; FAIL=0
check() {
  local desc=$1; local expected=$2; shift 2
  if "$@" 2>/dev/null; then actual=allowed; else actual=denied; fi
  if [ "$expected" = "$actual" ]; then PASS=$((PASS+1)); echo "[PASS] $desc"
  else FAIL=$((FAIL+1)); echo "[FAIL] $desc (expected $expected, got $actual)"; fi
}

# 1. Region restriction should block ap-southeast-2 actions
check "region restriction blocks ap-southeast-2" denied \
  aws ec2 describe-instances --region ap-southeast-2

# 2. us-west-2 should work
check "us-west-2 is allowed" allowed \
  aws sts get-caller-identity --region us-west-2

# 3. Creating IAM user in prod should be denied (run as MLEngineer in prod account)
check "IAM user creation denied in prod" denied \
  aws iam create-user --user-name test-deny

# 4. Stopping CloudTrail should be denied org-wide
check "CloudTrail stop denied" denied \
  aws cloudtrail stop-logging --name some-trail

echo "Summary: $PASS passed, $FAIL failed"
[ $FAIL -eq 0 ]
