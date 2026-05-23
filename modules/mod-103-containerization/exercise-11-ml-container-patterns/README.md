# ML-Specific Container Patterns — Solution

Reference for [learning exercise-11](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-103-containerization/exercises/exercise-11-ml-container-patterns/README.md).

Four patterns + measured impact:

| Pattern | Metric | Before | After |
|---|---|---|---|
| Startup warmup | First-request p99 | 1.8s | 60ms |
| Init-container model preload | Container restart time | 22s | 4s |
| Sidecar dynamic batching | Throughput at 50 concurrent | 180 r/s | 720 r/s |
| Hot model swap | Swap downtime | 18s | <100ms |

## Layout

```
exercise-11-ml-container-patterns/
├── README.md
├── pattern-1-warmup/
├── pattern-2-init-preload/
├── pattern-3-batcher-sidecar/
└── pattern-4-hot-swap/
```
