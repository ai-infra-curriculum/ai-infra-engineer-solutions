#!/bin/bash
# Run script for exercise-02-pulumi-multicloud-ml

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
echo "Running exercise-02-pulumi-multicloud-ml..."
python -m src.main "$@"
