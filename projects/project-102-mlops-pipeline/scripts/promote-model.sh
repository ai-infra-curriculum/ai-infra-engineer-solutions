#!/bin/bash
set -e

echo "==============================================="
echo "Model Promotion Script"
echo "==============================================="

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check arguments
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <model_name> <version>"
    echo "Example: $0 churn-classifier 1"
    exit 1
fi

MODEL_NAME=$1
VERSION=$2

echo "Promoting model: $MODEL_NAME version $VERSION to Production"

# Promote model using Python script
docker-compose exec -T airflow-webserver python3 << EOF
import sys
sys.path.insert(0, '/opt/airflow')

from src.training.registry import ModelRegistry

registry = ModelRegistry()

try:
    # Transition to Production
    result = registry.transition_model_stage(
        model_name='$MODEL_NAME',
        version='$VERSION',
        stage='Production',
        archive_existing=True
    )
    print(f"✓ Model promoted to Production")
    print(f"Version: {result['version']}")
    print(f"Stage: {result['stage']}")
except Exception as e:
    print(f"✗ Failed to promote model: {e}")
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    echo "${GREEN}✓ Model promotion successful${NC}"
    echo ""
    echo "Triggering deployment pipeline..."
    docker-compose exec -T airflow-webserver airflow dags trigger deployment_pipeline
    echo "${GREEN}✓ Deployment pipeline triggered${NC}"
else
    echo "${RED}✗ Model promotion failed${NC}"
    exit 1
fi
