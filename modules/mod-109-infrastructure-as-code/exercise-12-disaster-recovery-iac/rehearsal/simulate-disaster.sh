#!/usr/bin/env bash
# Simulate region failure: detach DNS, stop accepting traffic in primary.
set -euo pipefail

PRIMARY_REGION=${PRIMARY_REGION:-us-east-1}
ZONE_ID=${ZONE_ID:-Z0123456789}

echo "[$(date)] Marking primary region $PRIMARY_REGION as unhealthy via Route53 health check"
aws route53 update-health-check --health-check-id $HC_ID --disabled
echo "Primary now drained. Begin recovery script in DR region."
