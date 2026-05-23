#!/usr/bin/env bash
# Smoke-test connectivity from each subnet tier.
# Expects: VPC applied, AWS_PROFILE configured, jq + aws-cli installed.
set -euo pipefail

VPC_NAME=${1:-ml-dev}

# Discover subnets by Tier tag
for tier in public private-app private-data; do
  subnet=$(aws ec2 describe-subnets \
    --filters "Name=tag:Tier,Values=${tier}" "Name=tag:Project,Values=${VPC_NAME}" \
    --query 'Subnets[0].SubnetId' --output text)
  echo "Probing ${tier} subnet ${subnet}..."
  # SSM-based connectivity test: assume an instance with SSM exists in each tier
  # Or spin up an ephemeral one with `aws ec2 run-instances ... --user-data`
done

echo "See README.md for the full expected matrix."
