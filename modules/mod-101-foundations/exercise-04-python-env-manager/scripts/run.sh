#!/bin/bash
set -e

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run pyenvman CLI
python -m pyenvman.cli "$@"
