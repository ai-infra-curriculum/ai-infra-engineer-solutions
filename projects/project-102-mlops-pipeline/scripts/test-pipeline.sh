#!/bin/bash
set -e

echo "==============================================="
echo "End-to-End Pipeline Test"
echo "==============================================="

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if services are running
echo "Checking if services are running..."
if ! docker-compose ps | grep -q "Up"; then
    echo "${RED}Services not running. Please run 'make docker-up' first.${NC}"
    exit 1
fi

echo "${GREEN}✓ Services are running${NC}"

# Run unit tests
echo ""
echo "Running unit tests..."
docker-compose exec -T airflow-webserver pytest tests/unit -v

echo "${GREEN}✓ Unit tests passed${NC}"

# Trigger data pipeline
echo ""
echo "Triggering data pipeline..."
docker-compose exec -T airflow-webserver airflow dags trigger data_pipeline

# Wait for data pipeline to complete
echo "Waiting for data pipeline to complete..."
sleep 60

# Check data pipeline status
STATUS=$(docker-compose exec -T airflow-webserver airflow dags state data_pipeline 2>&1 | tail -1)
if echo "$STATUS" | grep -q "success"; then
    echo "${GREEN}✓ Data pipeline completed successfully${NC}"
else
    echo "${YELLOW}⚠ Data pipeline status: $STATUS${NC}"
fi

# Trigger training pipeline
echo ""
echo "Triggering training pipeline..."
docker-compose exec -T airflow-webserver airflow dags trigger training_pipeline

# Wait for training pipeline
echo "Waiting for training pipeline to complete..."
sleep 120

# Check training pipeline status
STATUS=$(docker-compose exec -T airflow-webserver airflow dags state training_pipeline 2>&1 | tail -1)
if echo "$STATUS" | grep -q "success"; then
    echo "${GREEN}✓ Training pipeline completed successfully${NC}"
else
    echo "${YELLOW}⚠ Training pipeline status: $STATUS${NC}"
fi

# Run integration tests
echo ""
echo "Running integration tests..."
docker-compose exec -T airflow-webserver pytest tests/integration -v

echo "${GREEN}✓ Integration tests passed${NC}"

echo ""
echo "==============================================="
echo "Pipeline Test Complete!"
echo "==============================================="
echo ""
echo "Check the following UIs for results:"
echo "  - Airflow: http://localhost:8080"
echo "  - MLflow:  http://localhost:5000"
echo ""
