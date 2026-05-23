# DVC Pipeline — Solution

Reference for [learning exercise-06](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-105-data-pipelines/exercises/exercise-06-data-versioning-dvc/README.md).

## Layout

```
exercise-06-data-versioning-dvc/
├── README.md
├── dvc.yaml          # 4-stage pipeline
├── params.yaml       # per-stage parameters
├── src/ingest.py, preprocess.py, train.py, evaluate.py
└── ci-examples/dvc-repro.yml
```

## Run

```bash
dvc init
dvc remote add -d storage s3://my-bucket/dvc-cache
dvc repro                                    # build everything
dvc exp run -S train.n_estimators=500        # sweep one parameter
dvc exp diff                                  # compare to baseline
dvc push                                      # push artifacts to remote
git add -A && git commit -m "exp: n_estimators=500"
```
