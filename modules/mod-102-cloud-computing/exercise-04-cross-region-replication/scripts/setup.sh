#!/usr/bin/env bash
set -euo pipefail
python -m venv venv && source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "ok — activate with: source venv/bin/activate"
