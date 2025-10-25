#!/bin/bash
# Run script for exercise-06-distributed-gpu-training

set -e

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Load environment variables
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Run the application
echo "Running exercise-06-distributed-gpu-training..."
python -m src.main "$@"
