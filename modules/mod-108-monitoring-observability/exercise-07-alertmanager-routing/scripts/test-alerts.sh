#!/usr/bin/env bash
# Fire one of each severity through amtool to verify routing.
set -euo pipefail

AM=${AM:-http://localhost:9093}
amtool --alertmanager.url=$AM alert add alertname=HighErrorRate severity=critical service=iris-api
amtool --alertmanager.url=$AM alert add alertname=SlowResponses severity=warning service=iris-api
amtool --alertmanager.url=$AM alert add alertname=HighCpuThrottling severity=info service=iris-api
amtool --alertmanager.url=$AM alert query
