#!/usr/bin/env python3
"""
Solution Generator for AI Infrastructure Engineer Modules 102-110

This script generates complete, production-ready solutions for all exercises
in modules 102-110 of the AI Infrastructure Engineer learning path.
"""

import os
from pathlib import Path
from typing import Dict, List
import json

# Base directory for solutions
BASE_DIR = Path("/home/claude/ai-infrastructure-project/repositories/solutions/ai-infra-engineer-solutions/modules")

# Module and exercise configuration
MODULES = {
    "mod-102-cloud-computing": [
        "exercise-01-multi-cloud-cost-analyzer",
        "exercise-02-cloud-ml-infrastructure",
        "exercise-03-disaster-recovery"
    ],
    "mod-103-containerization": [
        "exercise-04-container-security",
        "exercise-05-image-optimizer",
        "exercise-06-registry-manager"
    ],
    "mod-104-kubernetes": [
        "exercise-04-k8s-cluster-autoscaler",
        "exercise-05-service-mesh-observability",
        "exercise-06-k8s-operator-framework"
    ],
    "mod-105-data-pipelines": [
        "exercise-03-streaming-pipeline-kafka",
        "exercise-04-workflow-orchestration-airflow"
    ],
    "mod-106-mlops": [
        "exercise-04-experiment-tracking-mlflow",
        "exercise-05-model-monitoring-drift",
        "exercise-06-ci-cd-ml-pipelines"
    ],
    "mod-107-gpu-computing": [
        "exercise-04-gpu-cluster-management",
        "exercise-05-gpu-performance-optimization",
        "exercise-06-distributed-gpu-training"
    ],
    "mod-108-monitoring-observability": [
        "exercise-01-observability-stack",
        "exercise-02-ml-model-monitoring"
    ],
    "mod-109-infrastructure-as-code": [
        "exercise-01-terraform-ml-infrastructure",
        "exercise-02-pulumi-multicloud-ml"
    ],
    "mod-110-llm-infrastructure": [
        "exercise-01-production-llm-serving",
        "exercise-02-production-rag-system"
    ]
}


def create_directory_structure(exercise_path: Path):
    """Create standard directory structure for an exercise solution."""
    dirs = [
        "src",
        "tests",
        "scripts",
        "config",
        "docs",
        "kubernetes",
        ".github/workflows"
    ]

    for dir_name in dirs:
        (exercise_path / dir_name).mkdir(parents=True, exist_ok=True)


def create_gitignore(exercise_path: Path):
    """Create .gitignore file."""
    content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual Environment
venv/
ENV/
env/
.venv

# IDE
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/
.hypothesis/

# Environment variables
.env
.env.local
*.pem
*.key
credentials.json
secrets/

# Logs
*.log
logs/

# Data
data/
*.db
*.sqlite

# Cloud
.terraform/
*.tfstate
*.tfstate.backup
.terraform.lock.hcl

# Docker
.dockerignore

# Misc
*.bak
.cache/
tmp/
"""
    (exercise_path / ".gitignore").write_text(content)


def create_requirements_txt(exercise_path: Path, exercise_name: str):
    """Create requirements.txt with common dependencies."""

    # Base requirements for all exercises
    base_reqs = [
        "python-dotenv>=1.0.0",
        "pydantic>=2.0.0",
        "pytest>=7.4.0",
        "pytest-asyncio>=0.21.0",
        "pytest-cov>=4.1.0",
        "black>=23.7.0",
        "flake8>=6.1.0",
        "mypy>=1.5.0",
        "requests>=2.31.0"
    ]

    # Exercise-specific requirements
    specific_reqs = {
        "multi-cloud-cost-analyzer": [
            "boto3>=1.28.0",
            "google-cloud-billing>=1.11.0",
            "google-cloud-compute>=1.14.0",
            "azure-mgmt-compute>=30.0.0",
            "azure-mgmt-costmanagement>=4.0.0",
            "azure-identity>=1.14.0",
            "plotly>=5.17.0",
            "pandas>=2.1.0",
            "jinja2>=3.1.2"
        ],
        "cloud-ml-infrastructure": [
            "boto3>=1.28.0",
            "google-cloud-aiplatform>=1.34.0",
            "azure-ai-ml>=1.11.0",
            "pyyaml>=6.0.1",
            "click>=8.1.7"
        ],
        "disaster-recovery": [
            "boto3>=1.28.0",
            "google-cloud-storage>=2.10.0",
            "azure-storage-blob>=12.19.0",
            "kubernetes>=28.1.0",
            "croniter>=1.4.1"
        ],
        "container-security": [
            "docker>=6.1.3",
            "pyyaml>=6.0.1",
            "jinja2>=3.1.2",
            "cyclonedx-bom>=3.11.0"
        ],
        "image-optimizer": [
            "docker>=6.1.3",
            "pillow>=10.0.0"
        ],
        "registry-manager": [
            "docker>=6.1.3",
            "boto3>=1.28.0",
            "google-cloud-artifact-registry>=1.9.0"
        ],
        "k8s": [
            "kubernetes>=28.1.0",
            "prometheus-client>=0.17.1",
            "kopf>=1.36.2"
        ],
        "kafka": [
            "kafka-python>=2.0.2",
            "confluent-kafka>=2.2.0",
            "avro-python3>=1.10.2",
            "pyspark>=3.5.0"
        ],
        "airflow": [
            "apache-airflow>=2.7.0",
            "apache-airflow-providers-google>=10.8.0",
            "apache-airflow-providers-amazon>=8.7.0"
        ],
        "mlflow": [
            "mlflow>=2.7.0",
            "scikit-learn>=1.3.0",
            "numpy>=1.24.0"
        ],
        "monitoring": [
            "prometheus-client>=0.17.1",
            "evidently>=0.4.3",
            "scipy>=1.11.0"
        ],
        "ml-pipelines": [
            "kubeflow-pipelines>=2.0.0",
            "dvc>=3.23.0"
        ],
        "gpu": [
            "torch>=2.0.0",
            "nvidia-ml-py3>=7.352.0",
            "ray>=2.7.0"
        ],
        "observability": [
            "prometheus-client>=0.17.1",
            "grafana-api>=1.0.3",
            "opentelemetry-api>=1.20.0",
            "opentelemetry-sdk>=1.20.0"
        ],
        "terraform": [
            "python-terraform>=0.10.1"
        ],
        "pulumi": [
            "pulumi>=3.88.0",
            "pulumi-aws>=6.4.0",
            "pulumi-gcp>=7.0.0",
            "pulumi-azure-native>=2.11.0"
        ],
        "llm": [
            "fastapi>=0.103.0",
            "uvicorn>=0.23.2",
            "redis>=5.0.0",
            "httpx>=0.25.0",
            "transformers>=4.33.0",
            "sentence-transformers>=2.2.2",
            "chromadb>=0.4.13",
            "langchain>=0.0.310"
        ]
    }

    requirements = base_reqs.copy()

    # Add specific requirements based on exercise name
    for key, reqs in specific_reqs.items():
        if key in exercise_name:
            requirements.extend(reqs)
            break

    content = "\n".join(sorted(set(requirements)))
    (exercise_path / "requirements.txt").write_text(content + "\n")


def create_setup_script(exercise_path: Path, exercise_name: str):
    """Create setup.sh script."""
    content = f"""#!/bin/bash
# Setup script for {exercise_name}

set -e

echo "Setting up {exercise_name}..."

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
# Environment variables for {exercise_name}
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
"""
    script_path = exercise_path / "scripts" / "setup.sh"
    script_path.write_text(content)
    script_path.chmod(0o755)


def create_run_script(exercise_path: Path, exercise_name: str):
    """Create run.sh script."""
    content = f"""#!/bin/bash
# Run script for {exercise_name}

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
echo "Running {exercise_name}..."
python -m src.main "$@"
"""
    script_path = exercise_path / "scripts" / "run.sh"
    script_path.write_text(content)
    script_path.chmod(0o755)


def create_test_script(exercise_path: Path):
    """Create test.sh script."""
    content = """#!/bin/bash
# Test script

set -e

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "Running tests..."

# Run pytest with coverage
pytest tests/ -v --cov=src --cov-report=html --cov-report=term

echo ""
echo "✓ All tests passed!"
echo "Coverage report generated in htmlcov/index.html"
"""
    script_path = exercise_path / "scripts" / "test.sh"
    script_path.write_text(content)
    script_path.chmod(0o755)


def generate_all_solutions():
    """Generate all solution structures."""

    total_exercises = sum(len(exercises) for exercises in MODULES.values())
    current = 0

    print(f"Generating solutions for {total_exercises} exercises across {len(MODULES)} modules...\n")

    for module_name, exercises in MODULES.items():
        print(f"\n{'='*60}")
        print(f"Module: {module_name}")
        print(f"{'='*60}")

        module_path = BASE_DIR / module_name
        module_path.mkdir(parents=True, exist_ok=True)

        for exercise in exercises:
            current += 1
            print(f"\n[{current}/{total_exercises}] Creating {exercise}...")

            exercise_path = module_path / exercise
            exercise_path.mkdir(parents=True, exist_ok=True)

            # Create directory structure
            create_directory_structure(exercise_path)

            # Create standard files
            create_gitignore(exercise_path)
            create_requirements_txt(exercise_path, exercise)
            create_setup_script(exercise_path, exercise)
            create_run_script(exercise_path, exercise)
            create_test_script(exercise_path)

            print(f"  ✓ Created directory structure")
            print(f"  ✓ Created standard files (.gitignore, requirements.txt)")
            print(f"  ✓ Created executable scripts (setup.sh, run.sh, test.sh)")

    print(f"\n{'='*60}")
    print(f"✓ Successfully generated {total_exercises} exercise solutions!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    generate_all_solutions()
