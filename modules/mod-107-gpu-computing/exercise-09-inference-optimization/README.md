# Inference Optimization Chain — Solution

Reference for [learning exercise-09-inference-optimization](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/tree/main/lessons/mod-107-gpu-computing/exercises/exercise-09-inference-optimization/README.md).

Cumulative speedup chain: baseline → torch.compile → bf16 → quantization → TensorRT → continuous batching.

## Files

- `bench_inference.py` — runs each variant, reports latency + throughput
- `continuous_batcher.py` — async aggregator demo

## Run

```bash
./scripts/setup.sh
python bench_inference.py
python continuous_batcher.py     # see CLI for load options
```
