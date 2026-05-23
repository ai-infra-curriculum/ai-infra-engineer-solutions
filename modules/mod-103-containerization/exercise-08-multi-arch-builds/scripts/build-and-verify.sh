#!/usr/bin/env bash
# Build multi-arch image, push, verify manifest list.
set -euo pipefail
IMAGE=${IMAGE:-ghcr.io/me/iris-api:multi}

docker buildx create --name multi --driver docker-container --bootstrap --use 2>/dev/null || true
docker buildx build --platform linux/amd64,linux/arm64 -t "$IMAGE" --push .

echo "--- Manifest inspection ---"
docker manifest inspect "$IMAGE" | jq '.manifests[] | {platform: .platform, digest: .digest}'
