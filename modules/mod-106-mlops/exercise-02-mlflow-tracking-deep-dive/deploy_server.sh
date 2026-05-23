#!/usr/bin/env bash
# Serve a registered model as a REST endpoint via mlflow models serve.
set -euo pipefail

mlflow models serve -m models:/iris-rf/Production --host 0.0.0.0 --port 5001 \
  --env-manager local
