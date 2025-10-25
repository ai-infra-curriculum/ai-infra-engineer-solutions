#!/bin/bash
# Run script for exercise-05-image-optimizer

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
echo "Running exercise-05-image-optimizer..."
python -m src.main "$@"
