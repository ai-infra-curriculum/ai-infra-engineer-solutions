# Managed ML Services Comparison — Solution

Reference solution for [learning exercise-06-managed-ml-services-comparison](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/tree/main/lessons/mod-102-cloud-computing/exercises/exercise-06-managed-ml-services-comparison/README.md).

Deploys the same iris-api to SageMaker, Vertex AI, and Azure ML Online Endpoints. Provides a benchmark harness to measure cold-start, warm-latency, and throughput, plus an analysis report.

## Layout

```
exercise-06/
├── README.md
├── requirements.txt
├── deploy/
│   ├── sagemaker.py
│   ├── vertex.py
│   └── azure_ml.py
├── src/
│   ├── inference.py    # the model + handler used by all three
│   └── bench.py        # benchmark harness
└── reports/
    └── COMPARISON.md   # final matrix (placeholder)
```

## Quick start

```bash
./scripts/setup.sh

# Deploy to one
python deploy/sagemaker.py --model-uri s3://.../model.tar.gz

# Benchmark
python src/bench.py --endpoint <endpoint-name> --provider sagemaker
```
