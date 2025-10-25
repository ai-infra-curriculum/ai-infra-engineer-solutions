# Project 01: Basic Model Serving System - Complete Solution

A production-ready machine learning model serving system that deploys a pretrained ResNet50 image classification model as a REST API. This solution demonstrates essential AI infrastructure engineering skills including API development, containerization, orchestration, monitoring, and CI/CD.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688.svg)](https://fastapi.tiangolo.com/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.1-EE4C2C.svg)](https://pytorch.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-Ready-326CE5.svg)](https://kubernetes.io/)

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Deployment](#deployment)
- [API Documentation](#api-documentation)
- [Monitoring](#monitoring)
- [Development](#development)
- [Testing](#testing)
- [Production Considerations](#production-considerations)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Overview

This project implements a complete ML serving system with:
- **FastAPI** REST API for image classification
- **PyTorch ResNet50** pretrained on ImageNet (1000 classes)
- **Docker** containerization with multi-stage builds
- **Kubernetes** deployment with auto-scaling
- **Prometheus + Grafana** monitoring stack
- **GitHub Actions** CI/CD pipeline

**Use Cases:**
- Image classification service
- ML model serving reference architecture
- Learning production ML infrastructure
- Interview project demonstration

## Features

### Core Functionality
- Image classification with ResNet50 (top-k predictions)
- File upload and URL-based prediction
- Automatic API documentation (OpenAPI/Swagger)
- Health and readiness probes
- Request validation and error handling

### Production Features
- Horizontal pod autoscaling (HPA)
- Zero-downtime rolling updates
- Prometheus metrics export
- Grafana dashboards
- Resource limits and requests
- Non-root container execution
- Security scanning in CI/CD

### Performance
- **Latency**: p95 < 100ms (CPU inference)
- **Throughput**: 10+ concurrent requests per pod
- **Availability**: 99.9% uptime target
- **Scalability**: Auto-scale 3-10 pods

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Load Balancer                           │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ↓                   ↓                   ↓
┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│   API Pod 1    │  │   API Pod 2    │  │   API Pod 3    │
│  ┌──────────┐  │  │  ┌──────────┐  │  │  ┌──────────┐  │
│  │ FastAPI  │  │  │  │ FastAPI  │  │  │  │ FastAPI  │  │
│  │ ResNet50 │  │  │  │ ResNet50 │  │  │  │ ResNet50 │  │
│  └──────────┘  │  │  └──────────┘  │  │  └──────────┘  │
└────────┬───────┘  └────────┬───────┘  └────────┬───────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             ↓
                    ┌────────────────┐
                    │   Prometheus   │
                    │     Grafana    │
                    └────────────────┘
```

**Key Components:**
- **API Layer**: FastAPI with async endpoints
- **Model Layer**: PyTorch ResNet50 (singleton pattern)
- **Infrastructure**: Kubernetes with HPA
- **Monitoring**: Prometheus metrics + Grafana dashboards

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed design documentation.

## Quick Start

### Prerequisites

- Python 3.11+
- Docker 20.10+
- kubectl 1.25+ (for Kubernetes deployment)
- 4GB RAM minimum (8GB recommended)

### Local Development

```bash
# 1. Clone repository
git clone <repository-url>
cd project-101-basic-model-serving

# 2. Run setup script
./scripts/setup.sh

# 3. Activate virtual environment
source venv/bin/activate

# 4. Start application
python -m uvicorn src.api:app --reload --host 0.0.0.0 --port 8000

# 5. Access API
open http://localhost:8000/docs
```

### Docker Deployment

```bash
# Build and run with docker-compose (includes monitoring)
docker-compose up -d

# Services:
# - API: http://localhost:8000
# - Prometheus: http://localhost:9090
# - Grafana: http://localhost:3000 (admin/admin)
```

### Kubernetes Deployment

```bash
# Quick deploy
./scripts/deploy.sh

# Or manual deployment
kubectl apply -f kubernetes/

# Access service
kubectl port-forward svc/model-serving 8000:80 -n model-serving
```

## Deployment

### Local Development

```bash
# Install dependencies
make install

# Run application
make run

# Run tests
make test
```

### Docker

```bash
# Build image
make docker-build

# Run container
make docker-run

# Or use docker-compose for full stack
make docker-compose-up
```

### Kubernetes

Supports multiple environments:

**Minikube (local):**
```bash
minikube start --memory=8192 --cpus=4
eval $(minikube docker-env)
make docker-build
make k8s-deploy
```

**Cloud (AWS EKS, GCP GKE, Azure AKS):**
```bash
# 1. Build and push image to registry
docker build -t <registry>/model-serving-api:v1.0.0 .
docker push <registry>/model-serving-api:v1.0.0

# 2. Update image in deployment.yaml
# 3. Deploy
kubectl apply -f kubernetes/
```

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for detailed instructions.

## API Documentation

### Endpoints

#### Prediction

**POST /predict** - Upload file
```bash
curl -X POST "http://localhost:8000/predict" \
  -F "file=@dog.jpg" \
  -F "top_k=5"
```

**POST /predict/url** - Classify from URL
```bash
curl -X POST "http://localhost:8000/predict/url" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/dog.jpg", "top_k": 5}'
```

**Response:**
```json
{
  "predictions": [
    {
      "class_id": 258,
      "label": "Samoyed",
      "confidence": 0.8932
    },
    {
      "class_id": 259,
      "label": "Pomeranian",
      "confidence": 0.0541
    }
  ],
  "inference_time_ms": 45.23,
  "preprocessing_time_ms": 12.45
}
```

#### Monitoring

**GET /health** - Health check
**GET /ready** - Readiness check
**GET /metrics** - Prometheus metrics
**GET /model/info** - Model information

### Interactive Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

See [API.md](docs/API.md) for complete API documentation.

## Monitoring

### Metrics

The system exports comprehensive metrics:

**Application Metrics:**
- Request rate (requests/second)
- Response latency (p50, p95, p99)
- Error rate (%)
- Prediction count

**Infrastructure Metrics:**
- CPU usage (%)
- Memory usage (bytes)
- Pod count
- Network I/O

### Dashboards

Access Grafana at http://localhost:3000 (when using docker-compose)

**Default credentials:** admin/admin

**Included dashboards:**
- API Overview: Request rates, latencies, error rates
- Resource Usage: CPU, memory, network
- Business Metrics: Total predictions, popular classes

### Alerts

Configured alerts:
- Service down (>1 minute)
- High latency (p95 > 500ms for 5 min)
- High error rate (>5% for 5 min)
- High CPU usage (>80% for 10 min)
- High memory usage (>85% for 10 min)

## Development

### Project Structure

```
project-101-basic-model-serving/
├── src/
│   ├── __init__.py
│   ├── api.py           # FastAPI application
│   ├── model.py         # Model loading and inference
│   ├── utils.py         # Image processing utilities
│   └── config.py        # Configuration management
├── tests/
│   ├── test_api.py      # API tests
│   ├── test_model.py    # Model tests
│   ├── test_utils.py    # Utility tests
│   └── conftest.py      # Pytest fixtures
├── kubernetes/
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   └── hpa.yaml
├── monitoring/
│   ├── prometheus/
│   └── grafana/
├── docs/
│   ├── API.md
│   ├── ARCHITECTURE.md
│   ├── DEPLOYMENT.md
│   └── TROUBLESHOOTING.md
├── scripts/
│   ├── setup.sh
│   ├── deploy.sh
│   ├── test-deployment.sh
│   └── load-test.sh
├── .github/workflows/
│   └── ci-cd.yml
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

### Running Tests

```bash
# All tests
make test

# Fast tests (no coverage)
make test-fast

# Specific test file
pytest tests/test_api.py -v

# With coverage report
pytest --cov=src --cov-report=html
```

### Code Quality

```bash
# Format code
make format

# Check formatting
make format-check

# Run linters
make lint

# All quality checks
make ci
```

### Environment Variables

Create `.env` file from template:
```bash
cp .env.example .env
```

Key settings:
- `MODEL_DEVICE`: cpu or cuda
- `LOG_LEVEL`: DEBUG, INFO, WARNING, ERROR
- `TOP_K_PREDICTIONS`: Number of predictions to return
- `MAX_UPLOAD_SIZE`: Maximum file size in bytes

## Testing

### Unit Tests

```bash
# Run all tests
pytest tests/

# With coverage
pytest tests/ --cov=src --cov-report=term-missing

# Specific test
pytest tests/test_api.py::test_health_check -v
```

### Integration Tests

```bash
# Start application
make run

# In another terminal, run smoke tests
./scripts/test-deployment.sh
```

### Load Testing

```bash
# Run load test
./scripts/load-test.sh

# Or with custom parameters
NUM_REQUESTS=200 CONCURRENCY=20 ./scripts/load-test.sh
```

## Production Considerations

### Security

- [x] Non-root container user
- [x] No secrets in code/images
- [x] Input validation
- [x] Security scanning in CI/CD
- [ ] API authentication (implement as needed)
- [ ] Rate limiting (implement as needed)
- [ ] Network policies (configure per environment)

### Performance

- [x] Model loaded at startup (no cold starts)
- [x] Async endpoints
- [x] Resource limits configured
- [x] Horizontal autoscaling
- [ ] Request batching (optional optimization)
- [ ] Result caching (optional optimization)

### Reliability

- [x] Health checks
- [x] Readiness probes
- [x] Multiple replicas
- [x] Rolling updates
- [x] Resource limits
- [x] Monitoring and alerting

### Scalability

- [x] Stateless design
- [x] Horizontal pod autoscaler
- [x] Load balancing
- [x] Configurable resources
- [ ] Multi-region deployment (for global scale)

## Troubleshooting

### Common Issues

**Issue: Model not loading**
```bash
# Check logs
kubectl logs <pod-name> -n model-serving | grep "Model"

# Solution: Increase memory limits in deployment.yaml
```

**Issue: Pods crash with OOM**
```bash
# Solution: Increase memory limits
kubectl edit deployment model-serving -n model-serving
# Increase resources.limits.memory to 6Gi
```

**Issue: High latency**
```bash
# Check resource usage
kubectl top pods -n model-serving

# Solution: Scale up
kubectl scale deployment/model-serving --replicas=5 -n model-serving
```

See [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for comprehensive troubleshooting guide.

## CI/CD Pipeline

The GitHub Actions pipeline includes:

1. **Linting**: Code style checks (black, flake8, mypy)
2. **Testing**: Unit and integration tests with coverage
3. **Security**: Vulnerability scanning (Trivy)
4. **Build**: Docker image build and push
5. **Deploy**: Automated deployment (optional)

**Pipeline runs on:**
- Every push to main/develop
- Every pull request to main

**Required secrets:**
- `GITHUB_TOKEN` (automatic)
- Registry credentials (for push)
- Kubernetes credentials (for deploy)

## Performance Benchmarks

**Hardware:** 2 CPU cores, 4GB RAM per pod

**Metrics:**
- **Latency**: p50: 45ms, p95: 85ms, p99: 120ms
- **Throughput**: ~15 requests/second per pod
- **Concurrency**: Handles 20+ concurrent requests
- **Startup time**: ~45 seconds (model download + loading)
- **Memory usage**: ~2.5GB per pod (with model loaded)

## Roadmap

### Phase 1 (Complete)
- [x] FastAPI implementation
- [x] Docker containerization
- [x] Kubernetes deployment
- [x] Monitoring setup
- [x] CI/CD pipeline

### Phase 2 (Future)
- [ ] GPU support
- [ ] Request batching
- [ ] Result caching (Redis)
- [ ] API authentication
- [ ] Rate limiting

### Phase 3 (Future)
- [ ] Multi-model support
- [ ] A/B testing
- [ ] Model versioning
- [ ] Distributed tracing
- [ ] Multi-region deployment

## Learning Resources

**Documentation:**
- [Step-by-Step Guide](STEP_BY_STEP.md) - Detailed implementation walkthrough
- [Architecture](docs/ARCHITECTURE.md) - System design and decisions
- [API Documentation](docs/API.md) - Complete API reference
- [Deployment Guide](docs/DEPLOYMENT.md) - Deployment instructions
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions

**External Resources:**
- [FastAPI Tutorial](https://fastapi.tiangolo.com/tutorial/)
- [PyTorch Documentation](https://pytorch.org/docs/stable/index.html)
- [Kubernetes Concepts](https://kubernetes.io/docs/concepts/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/naming/)

## Contributing

This is a learning project, but contributions are welcome!

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add/update tests
5. Submit a pull request

## License

This project is part of the AI Infrastructure Curriculum.

## Contact

- **Project**: AI Infrastructure Career Path Curriculum
- **Email**: ai-infra-curriculum@joshua-ferguson.com
- **Organization**: ai-infra-curriculum

## Acknowledgments

- PyTorch team for pretrained models
- FastAPI for excellent documentation
- Kubernetes community for best practices
- Contributors and learners using this project

---

**Ready to deploy?** Start with the [Quick Start](#quick-start) section or dive into the [Step-by-Step Guide](STEP_BY_STEP.md)!
