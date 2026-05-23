# Mixed-Precision Benchmark Suite — Solution

Reference for [learning exercise-08-mixed-precision](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/tree/main/lessons/mod-107-gpu-computing/exercises/exercise-08-mixed-precision/README.md).

Benchmark fp32 vs fp16 (AMP) vs bf16 vs TF32 for ResNet-50 + small transformer.

## Run

```bash
./scripts/setup.sh
python bench.py --model resnet50 --batch-sizes 32,128,512
python bench.py --model transformer --batch-sizes 8,32,64
```
