# gpu-info CLI — Solution

Reference for [learning exercise-01-gpu-introspection](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/tree/main/lessons/mod-107-gpu-computing/exercises/exercise-01-gpu-introspection/README.md).

GPU introspection + benchmark CLI. Exit codes: 0 healthy, 1 degraded, 2 no GPU.

## Layout

```
exercise-01-gpu-introspection/
├── README.md, requirements.txt
├── src/
│   ├── __init__.py
│   ├── cli.py        # gpu-info entrypoint
│   ├── inventory.py  # pynvml-based device inventory + NVLink + MIG
│   └── bench.py      # matmul + bandwidth benchmarks
└── tests/
    └── test_smoke.py
```

## Run

```bash
./scripts/setup.sh
python -m src.cli                # text output
python -m src.cli --json         # machine-readable
echo $?                          # exit code
```
