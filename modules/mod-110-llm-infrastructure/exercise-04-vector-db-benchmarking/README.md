# Vector DB Benchmarking — Solution

Reference for [learning exercise-04](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-110-llm-infrastructure/exercises/exercise-04-vector-db-benchmarking/README.md).

## Layout

```
exercise-04-vector-db-benchmarking/
├── README.md, DECISION_MATRIX.md
├── compose/
│   ├── qdrant.yaml
│   ├── weaviate.yaml
│   └── pgvector.yaml
├── load.py          # bulk insert 5M vectors
├── query.py         # latency + recall benchmark
└── recall.py        # ground truth from brute-force
```
