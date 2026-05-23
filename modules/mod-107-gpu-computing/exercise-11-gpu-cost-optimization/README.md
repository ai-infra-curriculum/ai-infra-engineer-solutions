# GPU Cost Optimization Model — Solution

Reference for [learning exercise-11-gpu-cost-optimization](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/tree/main/lessons/mod-107-gpu-computing/exercises/exercise-11-gpu-cost-optimization/README.md).

Spreadsheet-style cost model in Python. Loads workload definitions + price table, computes monthly cost per scenario, produces recommendation.

## Files

```
exercise-11-gpu-cost-optimization/
├── README.md, requirements.txt
├── prices.yaml              # GPU price table
├── workloads.yaml           # workload inventory
├── cost_model.py            # the computation
└── recommend.py             # produces final recommendation
```

## Run

```bash
./scripts/setup.sh
python cost_model.py --workloads workloads.yaml --prices prices.yaml
python recommend.py          # outputs RECOMMENDATIONS.md
```
