# GPU Sharing Strategies (MIG / MPS / Time-Slicing) — Solution

Reference for [learning exercise-10-gpu-sharing-strategies](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/tree/main/lessons/mod-107-gpu-computing/exercises/exercise-10-gpu-sharing-strategies/README.md).

Three NVIDIA Device Plugin configurations + matching Pod specs + isolation test scripts.

## Layout

```
exercise-10-gpu-sharing-strategies/
├── README.md
├── manifests/
│   ├── mig/device-plugin.yaml          + workload-pod.yaml
│   ├── mps/device-plugin.yaml          + workload-pod.yaml
│   └── time-slicing/device-plugin.yaml + workload-pod.yaml
└── scripts/
    ├── enable-mig.sh
    └── interference-test.sh
```

## Notes

These configs require Ampere+ data-center GPUs (A100/H100) for MIG. MPS and
time-slicing work on any CUDA GPU but offer weaker isolation.
