# Multi-stage Dockerfile for LLM deployment platform
# Supports both GPU and CPU deployments

# Stage 1: Base image with CUDA support
FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04 as base

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3-dev \
    build-essential \
    git \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN python3 -m pip install --upgrade pip setuptools wheel

# Stage 2: Dependencies
FROM base as dependencies

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Stage 3: Application
FROM dependencies as application

WORKDIR /app

# Copy application code
COPY src/ ./src/
COPY prompts/ ./prompts/
COPY data/ ./data/

# Create directories for runtime data
RUN mkdir -p /app/chroma_db /app/models /app/logs

# Set Python path
ENV PYTHONPATH=/app

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["python3", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Stage 4: Development image (with dev dependencies)
FROM application as development

USER root

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

# Install Jupyter for development
RUN pip install --no-cache-dir jupyter jupyterlab

USER appuser

# Expose Jupyter port
EXPOSE 8888

# Development command includes reload
CMD ["python3", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
