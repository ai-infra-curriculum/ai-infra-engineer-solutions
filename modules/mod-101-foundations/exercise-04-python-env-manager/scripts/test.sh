#!/bin/bash
set -e

echo "Running tests for Python Environment Manager..."

# Run pytest with coverage
pytest tests/ \
    --cov=src/pyenvman \
    --cov-report=term-missing \
    --cov-report=html \
    -v

echo "Tests complete! Coverage report generated in htmlcov/"
