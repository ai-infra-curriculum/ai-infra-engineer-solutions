#!/usr/bin/env bash
set -euo pipefail

ok() { echo "[ok]  $*"; }
fail() { echo "[fail] $*" >&2; exit 1; }

# Python version
ver=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
case "$ver" in
  3.11|3.12) ok "Python $ver";;
  *) fail "Python 3.11 or 3.12 required (got $ver)";;
esac

# Virtual env
if [ -z "${VIRTUAL_ENV:-}" ]; then
  echo "[warn] not in a virtualenv; consider creating one"
fi

# Tools
command -v ruff >/dev/null && ok "ruff installed" || fail "ruff missing"
command -v mypy >/dev/null && ok "mypy installed" || fail "mypy missing"
command -v pytest >/dev/null && ok "pytest installed" || fail "pytest missing"
command -v pre-commit >/dev/null && ok "pre-commit installed" || fail "pre-commit missing"

# Git
command -v git >/dev/null && ok "git installed" || fail "git missing"

echo "Environment OK."
