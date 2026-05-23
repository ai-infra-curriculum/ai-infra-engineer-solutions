# ML Orchestration Patterns — Solution

Reference for [learning exercise-11](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-106-mlops/exercises/exercise-11-ml-orchestration-patterns/README.md).

## Layout

```
exercise-11-ml-orchestration-patterns/
├── README.md, COMPARISON.md
├── pattern-1-dag-per-model/iris_dag.py
├── pattern-2-parametric-dag/parametric_dag.py
├── pattern-3-event-driven/s3_trigger.py
└── pattern-4-continuous-training/ct_dag.py
```

## Picking the right pattern

| Scenario | Pattern | Why |
|---|---|---|
| 3 models, each with different processing | DAG-per-model | explicit, easy to debug |
| 200 models, identical pipeline different data | Parametric DAG | one file, scales to 1000s |
| Retrain when new data lands in S3 | Event-driven | natural fit for late-arriving data |
| Retrain hourly to catch drift | Continuous training | matches the cadence requirement |
