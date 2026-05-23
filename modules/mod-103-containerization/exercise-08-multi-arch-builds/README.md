# Multi-Arch Builds — Solution

Reference for [learning exercise-08](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-103-containerization/exercises/exercise-08-multi-arch-builds/README.md).

```bash
./scripts/build-and-verify.sh    # builds + pushes manifest list
./scripts/bench-platforms.sh     # measures per-platform latency
```

Result: single tag (`iris-api:multi`) backed by 2 platform images; arm64 ~30% cheaper at the same throughput on Graviton.
