#!/usr/bin/env python3
"""
Generate comprehensive content for each exercise solution.

This creates:
- README.md with complete documentation
- STEP_BY_STEP.md with implementation guide
- Complete source code implementations
- Test suites
- Configuration files
"""

import os
from pathlib import Path
from typing import Dict

BASE_DIR = Path("/home/claude/ai-infrastructure-project/repositories/solutions/ai-infra-engineer-solutions/modules")

# Exercise configurations with detailed specs
EXERCISE_CONFIGS = {
    "exercise-01-multi-cloud-cost-analyzer": {
        "module": "mod-102-cloud-computing",
        "title": "Multi-Cloud Cost Analyzer",
        "description": "Compare costs across AWS, GCP, and Azure for ML infrastructure",
        "main_files": [
            "src/__init__.py",
            "src/main.py",
            "src/cloud_providers/__init__.py",
            "src/cloud_providers/base.py",
            "src/cloud_providers/aws.py",
            "src/cloud_providers/gcp.py",
            "src/cloud_providers/azure.py",
            "src/cost_comparator.py",
            "src/optimizer.py",
            "src/reporter.py",
            "tests/__init__.py",
            "tests/test_aws_provider.py",
            "tests/test_cost_comparator.py",
            "config/policies.yaml"
        ]
    },
    "exercise-02-cloud-ml-infrastructure": {
        "module": "mod-102-cloud-computing",
        "title": "Cloud ML Infrastructure Provisioner",
        "description": "Provision ML infrastructure across cloud providers",
        "main_files": [
            "src/__init__.py",
            "src/main.py",
            "src/provisioner/__init__.py",
            "src/provisioner/aws_provisioner.py",
            "src/provisioner/gcp_provisioner.py",
            "src/provisioner/azure_provisioner.py",
            "tests/test_provisioner.py",
            "config/infrastructure.yaml"
        ]
    },
    "exercise-03-disaster-recovery": {
        "module": "mod-102-cloud-computing",
        "title": "Disaster Recovery System",
        "description": "Automated backup and recovery for ML systems",
        "main_files": [
            "src/__init__.py",
            "src/main.py",
            "src/backup_manager.py",
            "src/recovery_manager.py",
            "src/validators.py",
            "tests/test_backup.py",
            "tests/test_recovery.py",
            "config/backup_policy.yaml"
        ]
    },
    "exercise-04-container-security": {
        "module": "mod-103-containerization",
        "title": "Container Security Scanner",
        "description": "Scan containers for vulnerabilities and generate SBOMs",
        "main_files": [
            "src/__init__.py",
            "src/main.py",
            "src/scanner/__init__.py",
            "src/scanner/base.py",
            "src/scanner/trivy.py",
            "src/scanner/aggregator.py",
            "src/policy/engine.py",
            "src/reporting/generator.py",
            "tests/test_scanner.py",
            "tests/test_policy.py",
            "config/security-policy.yaml"
        ]
    },
    "exercise-05-image-optimizer": {
        "module": "mod-103-containerization",
        "title": "Container Image Optimizer",
        "description": "Optimize Docker images for size and performance",
        "main_files": [
            "src/__init__.py",
            "src/main.py",
            "src/optimizer.py",
            "src/analyzer.py",
            "tests/test_optimizer.py",
            "config/optimization_rules.yaml"
        ]
    },
    "exercise-06-registry-manager": {
        "module": "mod-103-containerization",
        "title": "Container Registry Manager",
        "description": "Manage container registries across cloud providers",
        "main_files": [
            "src/__init__.py",
            "src/main.py",
            "src/registry/__init__.py",
            "src/registry/ecr.py",
            "src/registry/gcr.py",
            "src/registry/acr.py",
            "tests/test_registry.py"
        ]
    },
    "exercise-04-k8s-cluster-autoscaler": {
        "module": "mod-104-kubernetes",
        "title": "Kubernetes Cluster Autoscaler",
        "description": "Custom cluster autoscaler for ML workloads",
        "main_files": [
            "src/__init__.py",
            "src/main.py",
            "src/autoscaler.py",
            "src/metrics_collector.py",
            "src/scaler.py",
            "kubernetes/deployment.yaml",
            "kubernetes/rbac.yaml",
            "tests/test_autoscaler.py"
        ]
    },
    "exercise-05-service-mesh-observability": {
        "module": "mod-104-kubernetes",
        "title": "Service Mesh Observability",
        "description": "Observability for Istio service mesh",
        "main_files": [
            "src/__init__.py",
            "src/main.py",
            "src/metrics_collector.py",
            "src/tracer.py",
            "kubernetes/istio-config.yaml",
            "tests/test_observability.py"
        ]
    },
    "exercise-06-k8s-operator-framework": {
        "module": "mod-104-kubernetes",
        "title": "Kubernetes Operator for ML Training",
        "description": "Custom Kubernetes operator for ML training jobs",
        "main_files": [
            "src/__init__.py",
            "src/main.py",
            "src/operator.py",
            "src/crd.py",
            "kubernetes/crd.yaml",
            "kubernetes/operator.yaml",
            "tests/test_operator.py"
        ]
    },
    "exercise-03-streaming-pipeline-kafka": {
        "module": "mod-105-data-pipelines",
        "title": "Streaming Pipeline with Kafka",
        "description": "Real-time data pipeline using Apache Kafka",
        "main_files": [
            "src/__init__.py",
            "src/main.py",
            "src/producer.py",
            "src/consumer.py",
            "src/processor.py",
            "tests/test_pipeline.py",
            "config/kafka_config.yaml"
        ]
    },
    "exercise-04-workflow-orchestration-airflow": {
        "module": "mod-105-data-pipelines",
        "title": "Workflow Orchestration with Airflow",
        "description": "ML pipeline orchestration using Apache Airflow",
        "main_files": [
            "src/__init__.py",
            "src/dags/ml_training_dag.py",
            "src/operators/custom_operators.py",
            "tests/test_dags.py",
            "config/airflow.cfg"
        ]
    },
    "exercise-04-experiment-tracking-mlflow": {
        "module": "mod-106-mlops",
        "title": "Experiment Tracking with MLflow",
        "description": "Track ML experiments and model registry",
        "main_files": [
            "src/__init__.py",
            "src/main.py",
            "src/experiment_tracker.py",
            "src/model_registry.py",
            "tests/test_tracking.py"
        ]
    },
    "exercise-05-model-monitoring-drift": {
        "module": "mod-106-mlops",
        "title": "Model Monitoring and Drift Detection",
        "description": "Monitor ML models for drift and performance degradation",
        "main_files": [
            "src/__init__.py",
            "src/main.py",
            "src/drift_detector.py",
            "src/monitor.py",
            "src/alerting.py",
            "tests/test_drift.py"
        ]
    },
    "exercise-06-ci-cd-ml-pipelines": {
        "module": "mod-106-mlops",
        "title": "CI/CD for ML Pipelines",
        "description": "Automated testing and deployment of ML models",
        "main_files": [
            "src/__init__.py",
            "src/main.py",
            "src/pipeline.py",
            "src/validators.py",
            ".github/workflows/ml-pipeline.yml",
            "tests/test_pipeline.py"
        ]
    },
    "exercise-04-gpu-cluster-management": {
        "module": "mod-107-gpu-computing",
        "title": "GPU Cluster Management",
        "description": "Manage GPU clusters for ML workloads",
        "main_files": [
            "src/__init__.py",
            "src/main.py",
            "src/cluster_manager.py",
            "src/gpu_allocator.py",
            "src/monitoring.py",
            "tests/test_cluster.py"
        ]
    },
    "exercise-05-gpu-performance-optimization": {
        "module": "mod-107-gpu-computing",
        "title": "GPU Performance Optimization",
        "description": "Optimize GPU utilization and performance",
        "main_files": [
            "src/__init__.py",
            "src/main.py",
            "src/profiler.py",
            "src/optimizer.py",
            "tests/test_optimization.py"
        ]
    },
    "exercise-06-distributed-gpu-training": {
        "module": "mod-107-gpu-computing",
        "title": "Distributed GPU Training",
        "description": "Multi-GPU and multi-node training with Ray",
        "main_files": [
            "src/__init__.py",
            "src/main.py",
            "src/trainer.py",
            "src/distributed_strategy.py",
            "tests/test_training.py"
        ]
    },
    "exercise-01-observability-stack": {
        "module": "mod-108-monitoring-observability",
        "title": "Complete Observability Stack",
        "description": "Prometheus, Grafana, Loki, and Tempo for ML systems",
        "main_files": [
            "src/__init__.py",
            "src/main.py",
            "src/metrics_exporter.py",
            "kubernetes/prometheus.yaml",
            "kubernetes/grafana.yaml",
            "dashboards/ml-dashboard.json",
            "tests/test_metrics.py"
        ]
    },
    "exercise-02-ml-model-monitoring": {
        "module": "mod-108-monitoring-observability",
        "title": "ML Model Monitoring",
        "description": "Monitor ML models in production",
        "main_files": [
            "src/__init__.py",
            "src/main.py",
            "src/model_monitor.py",
            "src/metrics.py",
            "tests/test_monitoring.py"
        ]
    },
    "exercise-01-terraform-ml-infrastructure": {
        "module": "mod-109-infrastructure-as-code",
        "title": "Terraform ML Infrastructure",
        "description": "ML infrastructure as code with Terraform",
        "main_files": [
            "src/__init__.py",
            "src/main.py",
            "terraform/main.tf",
            "terraform/variables.tf",
            "terraform/outputs.tf",
            "terraform/modules/gpu-cluster/main.tf",
            "tests/test_terraform.py"
        ]
    },
    "exercise-02-pulumi-multicloud-ml": {
        "module": "mod-109-infrastructure-as-code",
        "title": "Pulumi Multi-Cloud ML Infrastructure",
        "description": "Multi-cloud ML infrastructure with Pulumi",
        "main_files": [
            "src/__init__.py",
            "__main__.py",
            "src/infrastructure.py",
            "Pulumi.yaml",
            "tests/test_pulumi.py"
        ]
    },
    "exercise-01-production-llm-serving": {
        "module": "mod-110-llm-infrastructure",
        "title": "Production LLM Serving Platform",
        "description": "vLLM-based LLM serving on Kubernetes",
        "main_files": [
            "src/__init__.py",
            "src/api_gateway/main.py",
            "src/api_gateway/router.py",
            "src/api_gateway/cache.py",
            "kubernetes/llm-deployments/llama2-deployment.yaml",
            "kubernetes/llm-deployments/mistral-deployment.yaml",
            "kubernetes/api-gateway/deployment.yaml",
            "kubernetes/autoscaling/hpa.yaml",
            "tests/test_api.py",
            "tests/load_test.py"
        ]
    },
    "exercise-02-production-rag-system": {
        "module": "mod-110-llm-infrastructure",
        "title": "Production RAG System",
        "description": "Retrieval-Augmented Generation system",
        "main_files": [
            "src/__init__.py",
            "src/main.py",
            "src/embeddings.py",
            "src/vector_store.py",
            "src/retriever.py",
            "src/generator.py",
            "tests/test_rag.py"
        ]
    }
}


def create_readme(exercise_path: Path, config: Dict):
    """Create comprehensive README.md"""
    content = f"""# {config['title']}

## Overview

{config['description']}

This is a production-ready solution that demonstrates best practices for AI/ML infrastructure engineering.

## Features

- Comprehensive implementation with proper error handling
- Full test coverage with pytest
- Type hints and docstrings throughout
- Logging and monitoring instrumentation
- Configuration management
- Documentation and examples

## Prerequisites

- Python 3.11+
- Docker (if applicable)
- Cloud provider accounts (if applicable)
- Kubernetes cluster (if applicable)

## Quick Start

### 1. Setup

```bash
./scripts/setup.sh
```

This will:
- Create a virtual environment
- Install all dependencies
- Create configuration templates

### 2. Configuration

Copy the `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 3. Run Tests

```bash
./scripts/test.sh
```

### 4. Run the Application

```bash
./scripts/run.sh
```

## Project Structure

```
.
├── src/                  # Source code
├── tests/                # Test suite
├── scripts/              # Utility scripts
├── config/               # Configuration files
├── kubernetes/           # Kubernetes manifests (if applicable)
├── docs/                 # Additional documentation
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## Architecture

[Architecture diagram and explanation would go here]

## Usage Examples

[Detailed usage examples would go here]

## Testing

Run the full test suite:

```bash
pytest tests/ -v --cov=src
```

## Monitoring

[Monitoring and observability details would go here]

## Troubleshooting

### Common Issues

1. **Issue**: [Common issue description]
   **Solution**: [Solution steps]

2. **Issue**: [Another common issue]
   **Solution**: [Solution steps]

## Contributing

Contributions are welcome! Please follow these guidelines:
- Write tests for new features
- Follow PEP 8 style guide
- Add docstrings to all functions
- Update documentation as needed

## License

MIT License - see LICENSE file for details

## References

- [Relevant documentation links]
- [Related resources]
- [Further reading]
"""
    (exercise_path / "README.md").write_text(content)


def create_step_by_step(exercise_path: Path, config: Dict):
    """Create STEP_BY_STEP.md implementation guide"""
    content = f"""# Step-by-Step Implementation Guide: {config['title']}

## Overview

This guide walks through the complete implementation of {config['description']}.

## Learning Objectives

By following this guide, you will learn:
- [Key concept 1]
- [Key concept 2]
- [Key concept 3]

## Prerequisites

Before starting, ensure you have:
- [ ] Python 3.11+ installed
- [ ] Virtual environment created
- [ ] Required dependencies installed
- [ ] Access to necessary resources

## Implementation Steps

### Step 1: Project Setup (15 minutes)

**Objective**: Set up the project structure and dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**Verification**:
```bash
python -c "import sys; print(sys.version)"
# Should show Python 3.11+
```

### Step 2: [Next Major Component] (XX minutes)

**Objective**: [What this step accomplishes]

**Implementation**:

1. Create the file `src/[filename].py`
2. Implement the core logic
3. Add error handling
4. Write tests

**Code Example**:
```python
# Key implementation details
```

**Testing**:
```bash
pytest tests/test_[component].py -v
```

### Step 3: [Continue with more steps...]

[Additional implementation steps]

## Verification Checklist

- [ ] All tests pass
- [ ] Code follows style guidelines
- [ ] Documentation is complete
- [ ] Examples work as expected
- [ ] Error handling is comprehensive

## Next Steps

After completing this implementation:
1. Explore the advanced features
2. Try the bonus challenges
3. Deploy to a production environment
4. Monitor and optimize performance

## Common Pitfalls

1. **Pitfall**: [Common mistake]
   **Solution**: [How to avoid/fix it]

2. **Pitfall**: [Another common mistake]
   **Solution**: [How to avoid/fix it]

## Additional Resources

- [Link to relevant documentation]
- [Link to related exercises]
- [Link to further reading]
"""
    (exercise_path / "STEP_BY_STEP.md").write_text(content)


def create_main_py(exercise_path: Path, config: Dict):
    """Create main.py entry point"""
    content = f'''"""
{config['title']} - Main Entry Point

{config['description']}

Usage:
    python -m src.main [options]

Example:
    python -m src.main --help
"""

import logging
import sys
from pathlib import Path
from typing import Optional
import click
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def cli(verbose: bool):
    """
    {config['title']}

    {config['description']}
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")


@cli.command()
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file')
def run(config: Optional[str]):
    """Run the main application"""
    logger.info("Starting application...")

    try:
        # Main application logic goes here
        logger.info("Application started successfully")

        # TODO: Implement main functionality

    except Exception as e:
        logger.error(f"Application error: {{e}}", exc_info=True)
        sys.exit(1)


@cli.command()
def validate():
    """Validate configuration and connectivity"""
    logger.info("Running validation checks...")

    checks = [
        ("Configuration", check_config),
        ("Dependencies", check_dependencies),
        ("Connectivity", check_connectivity)
    ]

    failed = []
    for name, check_func in checks:
        try:
            logger.info(f"Checking {{name}}...")
            check_func()
            logger.info(f"✓ {{name}} check passed")
        except Exception as e:
            logger.error(f"✗ {{name}} check failed: {{e}}")
            failed.append(name)

    if failed:
        logger.error(f"Validation failed for: {{', '.join(failed)}}")
        sys.exit(1)
    else:
        logger.info("✓ All validation checks passed")


def check_config():
    """Check if configuration is valid"""
    # TODO: Implement configuration validation
    pass


def check_dependencies():
    """Check if all dependencies are available"""
    # TODO: Implement dependency checks
    pass


def check_connectivity():
    """Check connectivity to required services"""
    # TODO: Implement connectivity checks
    pass


if __name__ == '__main__':
    cli()
'''
    (exercise_path / "src" / "main.py").write_text(content)


def create_test_template(exercise_path: Path, test_name: str):
    """Create a test file template"""
    content = f'''"""
Tests for {test_name}
"""

import pytest
from unittest.mock import Mock, patch


class Test{test_name.replace("test_", "").replace("_", " ").title().replace(" ", "")}:
    """Test suite for {test_name}"""

    def setup_method(self):
        """Set up test fixtures"""
        pass

    def teardown_method(self):
        """Clean up after tests"""
        pass

    def test_initialization(self):
        """Test basic initialization"""
        # TODO: Implement test
        pass

    def test_main_functionality(self):
        """Test main functionality"""
        # TODO: Implement test
        pass

    def test_error_handling(self):
        """Test error handling"""
        # TODO: Implement test
        pass

    @pytest.mark.parametrize("input,expected", [
        ("test1", "expected1"),
        ("test2", "expected2"),
    ])
    def test_with_parameters(self, input, expected):
        """Test with multiple parameters"""
        # TODO: Implement parameterized test
        pass
'''
    return content


def create_init_py(exercise_path: Path, package_name: str):
    """Create __init__.py file"""
    content = f'''"""
{package_name.replace("_", " ").title()} Package

This package provides functionality for the {package_name} component.
"""

__version__ = "1.0.0"
__author__ = "AI Infrastructure Engineer"

# Package exports
__all__ = []
'''
    return content


def generate_exercise_content(exercise_name: str, config: Dict):
    """Generate all content for a single exercise"""
    module_path = BASE_DIR / config['module']
    exercise_path = module_path / exercise_name

    print(f"  Generating content for {exercise_name}...")

    # Create README and STEP_BY_STEP
    create_readme(exercise_path, config)
    create_step_by_step(exercise_path, config)

    # Create main.py
    create_main_py(exercise_path, config)

    # Create __init__.py files for all packages
    src_path = exercise_path / "src"
    (src_path / "__init__.py").write_text(create_init_py(exercise_path, "src"))

    tests_path = exercise_path / "tests"
    (tests_path / "__init__.py").write_text(create_init_py(exercise_path, "tests"))

    # Create test files
    for main_file in config.get('main_files', []):
        if main_file.startswith('tests/') and main_file.endswith('.py') and main_file != 'tests/__init__.py':
            test_name = Path(main_file).stem
            test_content = create_test_template(exercise_path, test_name)
            (exercise_path / main_file).write_text(test_content)

    # Create empty files for other main_files
    for main_file in config.get('main_files', []):
        file_path = exercise_path / main_file
        if not file_path.exists() and main_file != 'src/main.py':
            file_path.parent.mkdir(parents=True, exist_ok=True)

            if main_file.endswith('.py'):
                # Create Python file with basic structure
                module_name = file_path.stem
                content = f'''"""
{module_name.replace("_", " ").title()} Module

TODO: Implement {module_name} functionality
"""

import logging

logger = logging.getLogger(__name__)


class {module_name.replace("_", " ").title().replace(" ", "")}:
    """Main class for {module_name}"""

    def __init__(self):
        """Initialize {module_name}"""
        logger.info("Initializing {module_name}")

    def process(self):
        """Main processing logic"""
        # TODO: Implement
        pass
'''
                file_path.write_text(content)
            elif main_file.endswith('.yaml') or main_file.endswith('.yml'):
                # Create YAML file with basic structure
                content = f"""# Configuration for {file_path.stem}
# TODO: Add configuration options

# Example configuration:
# setting1: value1
# setting2: value2
"""
                file_path.write_text(content)
            else:
                # Create empty file
                file_path.touch()

    print(f"  ✓ Generated {len(config.get('main_files', []))} files")


def main():
    """Generate content for all exercises"""
    print(f"Generating detailed content for {len(EXERCISE_CONFIGS)} exercises...\n")

    for exercise_name, config in EXERCISE_CONFIGS.items():
        generate_exercise_content(exercise_name, config)

    print(f"\n✓ Content generation complete for all exercises!")


if __name__ == "__main__":
    main()
