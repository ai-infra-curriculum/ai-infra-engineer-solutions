#!/bin/bash
# Setup script for LLM Deployment Platform

set -e

echo "========================================="
echo "LLM Deployment Platform Setup"
echo "========================================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

if ! python3 -c 'import sys; assert sys.version_info >= (3, 10)' 2>/dev/null; then
    echo "Error: Python 3.10 or higher is required"
    exit 1
fi

# Check for GPU
echo ""
echo "Checking for GPU..."
if command -v nvidia-smi &> /dev/null; then
    echo "NVIDIA GPU detected:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    GPU_AVAILABLE=true
else
    echo "No NVIDIA GPU detected. CPU-only mode will be used."
    GPU_AVAILABLE=false
fi

# Create virtual environment
echo ""
echo "Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment created"
else
    echo "Virtual environment already exists"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt

# Create directories
echo ""
echo "Creating directories..."
mkdir -p chroma_db models logs data/sample-docs

# Copy environment file
echo ""
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo ".env file created. Please edit it with your configuration."
else
    echo ".env file already exists"
fi

# Download model (optional)
echo ""
read -p "Download TinyLlama model for testing? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Downloading TinyLlama model..."
    python3 -c "from transformers import AutoTokenizer, AutoModelForCausalLM; AutoTokenizer.from_pretrained('TinyLlama/TinyLlama-1.1B-Chat-v1.0'); AutoModelForCausalLM.from_pretrained('TinyLlama/TinyLlama-1.1B-Chat-v1.0')"
    echo "Model downloaded"
fi

# Test installation
echo ""
echo "Testing installation..."
python3 -c "import torch; import transformers; import sentence_transformers; import fastapi; print('✓ All packages imported successfully')"

echo ""
echo "========================================="
echo "Setup complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Activate the virtual environment: source venv/bin/activate"
echo "2. Edit .env file with your configuration"
echo "3. Run the API: make run"
echo "   Or: python -m uvicorn src.api.main:app --reload"
echo ""
echo "For Docker deployment:"
echo "  make docker-up"
echo ""
echo "For Kubernetes deployment:"
echo "  make k8s-deploy"
echo ""
