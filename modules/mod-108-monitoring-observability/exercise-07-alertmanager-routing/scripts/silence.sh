#!/usr/bin/env bash
# Silence a known-noisy alert for 2h.
set -euo pipefail

AM=${AM:-http://localhost:9093}
amtool --alertmanager.url=$AM silence add alertname=HighCpuThrottling \
  --duration=2h --comment "Investigating during scheduled maintenance" \
  --author "platform-oncall"
amtool --alertmanager.url=$AM silence query
