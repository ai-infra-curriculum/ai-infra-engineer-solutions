#!/bin/bash
# Test script

set -e

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "Running tests..."

# Run pytest with coverage
pytest tests/ -v --cov=src --cov-report=html --cov-report=term

echo ""
echo "✓ All tests passed!"
echo "Coverage report generated in htmlcov/index.html"
