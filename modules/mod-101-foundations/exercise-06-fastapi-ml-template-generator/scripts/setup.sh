#!/bin/bash
set -e

echo "Setting up FastAPI ML Template Generator..."

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install -e .

mkdir -p templates

echo "Setup complete!"
