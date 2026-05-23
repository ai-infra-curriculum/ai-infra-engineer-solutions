#!/usr/bin/env bash
set -euo pipefail
# Requires Minio running:
# docker run -d --name minio -p 9000:9000 -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin minio/minio server /data
pytest tests/ -v
