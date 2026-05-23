#!/usr/bin/env bash
# Benchmark inference latency on each platform.
set -euo pipefail
IMAGE=${IMAGE:-ghcr.io/me/iris-api:multi}

for plat in linux/amd64 linux/arm64; do
  echo "--- $plat ---"
  docker run --rm --platform "$plat" -d -p 8000:8000 --name iris "$IMAGE"
  sleep 5
  curl -sf -X POST -H 'content-type: application/json' \
    -d '{"features":[5.1,3.5,1.4,0.2]}' \
    http://localhost:8000/predict
  ab -n 200 -c 10 -p body.json -T application/json http://localhost:8000/predict || true
  docker rm -f iris
done
