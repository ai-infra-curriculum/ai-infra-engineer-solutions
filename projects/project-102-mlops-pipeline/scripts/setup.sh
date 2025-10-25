#!/bin/bash
set -e

echo "==============================================="
echo "MLOps Pipeline Setup Script"
echo "==============================================="

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "${YELLOW}Docker not found. Please install Docker first.${NC}"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "${YELLOW}Docker Compose not found. Please install Docker Compose first.${NC}"
    exit 1
fi

echo "${GREEN}✓ Docker and Docker Compose found${NC}"

# Create necessary directories
echo "Creating directories..."
mkdir -p data/raw data/processed models logs mlruns

echo "${GREEN}✓ Directories created${NC}"

# Copy environment file if not exists
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo "${GREEN}✓ .env file created${NC}"
    echo "${YELLOW}⚠ Please review and update .env file with your configuration${NC}"
else
    echo "${GREEN}✓ .env file already exists${NC}"
fi

# Build Docker images
echo "Building Docker images..."
docker-compose build

echo "${GREEN}✓ Docker images built${NC}"

# Initialize Airflow database
echo "Initializing Airflow database..."
docker-compose up airflow-init

echo "${GREEN}✓ Airflow database initialized${NC}"

# Start services
echo "Starting services..."
docker-compose up -d

echo "${GREEN}✓ Services started${NC}"

# Wait for services to be healthy
echo "Waiting for services to be ready..."
sleep 30

# Check service health
echo "Checking service health..."

services=("postgres" "redis" "minio" "mlflow" "airflow-webserver")
for service in "${services[@]}"; do
    if docker-compose ps | grep -q "$service.*Up"; then
        echo "${GREEN}✓ $service is running${NC}"
    else
        echo "${YELLOW}⚠ $service may not be fully ready${NC}"
    fi
done

echo ""
echo "==============================================="
echo "Setup Complete!"
echo "==============================================="
echo ""
echo "Access the services at:"
echo "  - Airflow UI:    http://localhost:8080 (admin/admin)"
echo "  - MLflow UI:     http://localhost:5000"
echo "  - MinIO Console: http://localhost:9001 (minioadmin/minioadmin)"
echo "  - Grafana:       http://localhost:3000 (admin/admin)"
echo "  - Prometheus:    http://localhost:9090"
echo ""
echo "To view logs: docker-compose logs -f"
echo "To stop:      docker-compose down"
echo ""
