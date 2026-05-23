# GPU Memory Profiling — Solution

Reference for [learning exercise-07-gpu-memory-profiling](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/tree/main/lessons/mod-107-gpu-computing/exercises/exercise-07-gpu-memory-profiling/README.md).

Scripts demonstrating baseline OOM, gradient checkpointing, Adam8bit, and a measurement harness.

## Files

```
exercise-07-gpu-memory-profiling/
├── README.md, requirements.txt
├── train_baseline.py     # OOM-prone
├── train_optimized.py    # gradient checkpoint + Adam8bit
└── snapshot.py           # memory snapshot helper
```

## Run

```bash
./scripts/setup.sh
python train_baseline.py        # likely OOM at batch=16
python train_optimized.py       # same batch, but headroom
python snapshot.py              # produce memory trace
```
