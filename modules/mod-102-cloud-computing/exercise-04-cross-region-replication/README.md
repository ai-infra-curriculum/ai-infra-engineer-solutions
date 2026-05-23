# Cross-Region Artifact Replicator — Solution

Reference solution for [learning exercise-04-cross-region-replication](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/tree/main/lessons/mod-102-cloud-computing/exercises/exercise-04-cross-region-replication/README.md).

## What this implements

A CLI that keeps an object store prefix synchronized between two regions/buckets with:
- Manifest-based incremental sync (SQLite) — no full re-listing each run
- Bandwidth-limited concurrent transfers
- SHA-256 integrity verification per object
- Atomic temp→rename writes
- `status`, `sync`, `watch`, `verify` commands

## Layout

```
exercise-04-cross-region-replication/
├── README.md
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── cli.py              # entrypoint
│   ├── manifest.py         # SQLite-backed sync state
│   ├── backends.py         # S3 backend (Minio for tests); extensible
│   ├── transfer.py         # rate-limited copy logic
│   └── limits.py           # token bucket
├── tests/
│   ├── conftest.py         # spins Minio via testcontainers
│   └── test_replicator.py
└── scripts/
    ├── setup.sh
    ├── run.sh
    └── test.sh
```

## Quick start

```bash
./scripts/setup.sh

# Smoke test
python -m src.cli status \
  --src s3://src-bucket/prefix \
  --dst s3://dst-bucket/prefix \
  --aws-endpoint http://localhost:9000

python -m src.cli sync \
  --src s3://src-bucket/prefix \
  --dst s3://dst-bucket/prefix \
  --rate-mbps 50 --concurrency 4
```

## Validation

`./scripts/test.sh` runs the test suite. Tests use testcontainers to spin up a real Minio instance and exercise the full replicate → verify → resume flow.

## Decisions worth noting

- **SQLite manifest** over Redis or a database: zero-deploy state for a CLI tool; trivially backupable; sufficient for < 10M objects.
- **token-bucket bandwidth limit** in `limits.py`: simpler than streaming-byte tracking and accurate to within ~5%.
- **temp-then-rename** for atomicity: S3 doesn't have rename; we use a `.tmp-replication/<uuid>/<key>` prefix and `CopyObject` + `DeleteObject` to simulate.
- **Per-object SHA verified end-to-end**: prevents silent corruption from network or storage layer.
