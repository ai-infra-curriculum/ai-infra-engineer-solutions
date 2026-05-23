#!/usr/bin/env bash
# Switch traffic from blue to green by editing the Service selector.
set -euo pipefail

kubectl patch service iris-api -p '{"spec":{"selector":{"app":"iris-api","color":"green"}}}'
echo "traffic switched to green. Monitor for 10 min, then delete blue."
