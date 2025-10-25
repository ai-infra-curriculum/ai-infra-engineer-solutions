#!/bin/bash
set -e

echo "Setting up Python Environment Manager..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install package in editable mode
echo "Installing package in editable mode..."
pip install -e .

echo "Setup complete! Activate the environment with: source venv/bin/activate"
