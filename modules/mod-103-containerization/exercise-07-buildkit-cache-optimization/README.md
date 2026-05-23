# BuildKit Cache Optimization — Solution

Reference for [learning exercise-07](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-103-containerization/exercises/exercise-07-buildkit-cache-optimization/README.md).

## Measured (on iris-api with ~600MB of model weights)

| Build | Time |
|---|---|
| Cold (no cache) | 10m 22s |
| Warm (local layer cache) | 2m 14s |
| CI (registry-backed cache) | 1m 58s |
| Reduction vs cold | **81%** |

## Run locally

```bash
echo "$HF_TOKEN" > hf_token
DOCKER_BUILDKIT=1 docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --cache-from type=registry,ref=ghcr.io/me/iris-api:buildcache \
  --cache-to   type=registry,ref=ghcr.io/me/iris-api:buildcache,mode=max \
  --secret id=hf_token,src=hf_token \
  -t iris-api:dev .
```
