#!/bin/bash
set -e

echo "Setting up ML Framework Benchmark..."

# Create virtual environment
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install package
pip install -e .

# Create directories
mkdir -p results configs

echo "Setup complete!"
