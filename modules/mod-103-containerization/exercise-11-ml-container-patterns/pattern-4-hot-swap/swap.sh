#!/usr/bin/env bash
# Atomically swap model on disk. Pair with `mv -T` for race-free rename.
set -euo pipefail
NEW_VERSION=$1
MODEL_DIR=${MODEL_DIR:-/models}

curl -fsSL "https://models.internal/iris/${NEW_VERSION}.joblib" \
  -o "$MODEL_DIR/incoming-$$.joblib"
mv -T "$MODEL_DIR/incoming-$$.joblib" "$MODEL_DIR/current.joblib"
echo "swapped to $NEW_VERSION at $(date)"
