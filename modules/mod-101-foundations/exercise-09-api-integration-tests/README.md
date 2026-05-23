# Layered Test Suite — Solution

Reference solution for [learning exercise-09-api-integration-tests](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/tree/main/lessons/mod-101-foundations/exercises/exercise-09-api-integration-tests/README.md).

Demonstrates the four test tiers for the model-serve API (from ex-08): unit, contract, integration, consumer-driven (Pact).

## Layout

```
exercise-09-api-integration-tests/
├── README.md, requirements.txt
├── pyproject.toml
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   └── test_schemas.py
│   ├── contract/
│   │   └── test_predict_contract.py
│   ├── integration/
│   │   ├── conftest.py
│   │   └── test_observability.py
│   └── consumer_contract/
│       └── test_consumer.py
└── .github/workflows/test.yml   # 4 parallel CI jobs
```

## Run

```bash
pytest -m unit                    # < 5 sec
pytest -m contract                # < 30 sec
pytest -m integration             # requires Docker; < 5 min
pytest -m consumer_contract       # runs against Pact
```
