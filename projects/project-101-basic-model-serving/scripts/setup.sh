#!/bin/bash

# Setup script for local development environment
# This script sets up the complete development environment

set -e  # Exit on error

echo "=========================================="
echo "Model Serving System - Setup Script"
echo "=========================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Check if Python is installed
echo "Checking prerequisites..."
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed. Please install Python 3.11 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
print_status "Python version: $PYTHON_VERSION"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_warning "Docker is not installed. You'll need it for containerization."
else
    print_status "Docker is installed"
fi

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    print_warning "kubectl is not installed. You'll need it for Kubernetes deployment."
else
    print_status "kubectl is installed"
fi

# Create virtual environment
echo ""
echo "Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    print_status "Virtual environment created"
else
    print_warning "Virtual environment already exists"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate
print_status "Virtual environment activated"

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1
print_status "pip upgraded"

# Install dependencies
echo ""
echo "Installing Python dependencies..."
pip install -r requirements.txt > /dev/null 2>&1
print_status "Production dependencies installed"

echo ""
echo "Installing development dependencies..."
pip install -r requirements-dev.txt > /dev/null 2>&1
print_status "Development dependencies installed"

# Create .env file if it doesn't exist
echo ""
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_status ".env file created"
    else
        print_warning ".env.example not found, creating basic .env file"
        cat > .env << EOF
# Application settings
APP_NAME=model-serving-api
APP_VERSION=1.0.0
DEBUG=false
LOG_LEVEL=INFO

# Model settings
MODEL_NAME=resnet50
MODEL_DEVICE=cpu

# API settings
API_HOST=0.0.0.0
API_PORT=8000
EOF
        print_status ".env file created"
    fi
else
    print_warning ".env file already exists"
fi

# Create necessary directories
echo ""
echo "Creating necessary directories..."
mkdir -p logs
mkdir -p data
print_status "Directories created"

# Run tests to verify installation
echo ""
echo "Running tests to verify installation..."
if pytest tests/ -q --tb=short > /dev/null 2>&1; then
    print_status "All tests passed!"
else
    print_warning "Some tests failed. This might be expected if model needs to download."
fi

# Print summary
echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Activate virtual environment: source venv/bin/activate"
echo "  2. Review and update .env file if needed"
echo "  3. Run the application: python -m uvicorn src.api:app --reload"
echo "  4. Access API docs at: http://localhost:8000/docs"
echo ""
echo "For Docker deployment:"
echo "  docker-compose up --build"
echo ""
echo "For Kubernetes deployment:"
echo "  ./scripts/deploy.sh"
echo ""
