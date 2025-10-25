#!/bin/bash
# Setup script for exercise-03-disaster-recovery

set -e

echo "Setting up exercise-03-disaster-recovery..."

# Create virtual environment
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✓ Created virtual environment"
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

echo "✓ Installed Python dependencies"

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    cat > .env << 'EOF'
# Environment variables for exercise-03-disaster-recovery
# Copy this file and fill in your values

# Add your environment variables here
EOF
    echo "✓ Created .env template"
fi

echo ""
echo "Setup complete! Next steps:"
echo "1. Activate virtual environment: source venv/bin/activate"
echo "2. Configure .env file with your credentials"
echo "3. Run tests: ./scripts/test.sh"
echo "4. Run application: ./scripts/run.sh"
