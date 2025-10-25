# Step-by-Step Implementation Guide

This guide walks you through implementing the Model Serving System from scratch, explaining each component and design decision.

## Overview

We'll build a production-ready ML serving system in 6 phases:
1. Core Application (FastAPI + Model)
2. Containerization (Docker)
3. Orchestration (Kubernetes)
4. Monitoring (Prometheus + Grafana)
5. CI/CD Pipeline
6. Documentation

**Time estimate:** 20-30 hours

## Phase 1: Core Application (6-8 hours)

### Step 1.1: Project Setup

```bash
# Create project structure
mkdir -p project-101-basic-model-serving/{src,tests,kubernetes,monitoring,docs,scripts}
cd project-101-basic-model-serving

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Create requirements.txt
cat > requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6
pydantic==2.5.0
pydantic-settings==2.1.0
torch==2.1.1
torchvision==0.16.1
pillow==10.1.0
numpy==1.26.2
prometheus-fastapi-instrumentator==6.1.0
prometheus-client==0.19.0
requests==2.31.0
python-dotenv==1.0.0
EOF

# Install dependencies
pip install -r requirements.txt
```

**Why these choices:**
- **FastAPI**: High performance, automatic docs, type hints
- **PyTorch**: Most popular ML framework, great pretrained models
- **Pydantic**: Type-safe configuration and validation

### Step 1.2: Configuration Management (`src/config.py`)

Start with configuration to make everything configurable:

```python
from pydantic import BaseModel, Field, validator

class Settings(BaseModel):
    """Application settings loaded from environment variables."""

    # Core settings
    app_name: str = Field(default="model-serving-api", env="APP_NAME")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # Model settings
    model_name: str = Field(default="resnet50", env="MODEL_NAME")
    model_device: str = Field(default="cpu", env="MODEL_DEVICE")
    top_k_predictions: int = Field(default=5, env="TOP_K_PREDICTIONS")

    @validator("model_device")
    def validate_device(cls, v):
        if v.lower() not in ["cpu", "cuda"]:
            raise ValueError("Model device must be 'cpu' or 'cuda'")
        return v.lower()

    class Config:
        env_file = ".env"

settings = Settings()
```

**Key concepts:**
- Environment-based configuration (12-factor app)
- Type validation with Pydantic
- Sensible defaults

### Step 1.3: Utility Functions (`src/utils.py`)

Implement image processing utilities:

```python
from PIL import Image
import torch
from torchvision import transforms

def get_image_transform():
    """Standard ImageNet preprocessing."""
    return transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        )
    ])

def load_image_from_bytes(image_bytes: bytes) -> Image.Image:
    """Load and validate image from bytes."""
    import io

    try:
        image = Image.open(io.BytesIO(image_bytes))

        # Validate
        if image.size[0] > 4096 or image.size[1] > 4096:
            raise ValueError("Image too large")

        # Convert to RGB
        if image.mode != "RGB":
            image = image.convert("RGB")

        return image
    except Exception as e:
        raise ValueError(f"Failed to load image: {e}")
```

**Key concepts:**
- ImageNet preprocessing (standard for ResNet)
- Input validation (prevent memory issues)
- Error handling

### Step 1.4: Model Loading (`src/model.py`)

Implement model wrapper with singleton pattern:

```python
import torch
import torch.nn as nn
from torchvision.models import resnet50, ResNet50_Weights

class ResNetClassifier:
    """ResNet50 classifier with pretrained weights."""

    def __init__(self, device: str = "cpu"):
        self.device = device
        self.model = None
        self.labels = []
        self.is_loaded = False

    def load(self):
        """Load model and labels."""
        if self.is_loaded:
            return

        # Load pretrained model
        weights = ResNet50_Weights.IMAGENET1K_V2
        self.model = resnet50(weights=weights)
        self.model.eval()
        self.model = self.model.to(self.device)

        # Load labels
        self.labels = self._load_imagenet_labels()

        self.is_loaded = True

    def predict(self, image_tensor: torch.Tensor, top_k: int = 5):
        """Perform inference."""
        if not self.is_loaded:
            raise RuntimeError("Model not loaded")

        # Move to device
        image_tensor = image_tensor.to(self.device)

        # Inference
        with torch.no_grad():
            logits = self.model(image_tensor)
            probs = torch.nn.functional.softmax(logits, dim=1)

        # Get top k
        top_probs, top_indices = torch.topk(probs, top_k)

        # Format results
        predictions = []
        for prob, idx in zip(top_probs[0], top_indices[0]):
            predictions.append({
                "class_id": int(idx),
                "label": self.labels[idx],
                "confidence": float(prob)
            })

        return {"predictions": predictions}
```

**Key concepts:**
- Singleton pattern (load model once)
- Device management (CPU/GPU)
- Separation of concerns (model separate from API)

### Step 1.5: FastAPI Application (`src/api.py`)

Create the REST API:

```python
from fastapi import FastAPI, File, UploadFile, HTTPException
from contextlib import asynccontextmanager
import time

from src.model import ResNetClassifier
from src.utils import load_image_from_bytes, preprocess_image
from src.config import settings

# Singleton model instance
model = ResNetClassifier(device=settings.model_device)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown logic."""
    # Startup
    model.load()
    yield
    # Shutdown
    model.unload()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/health")
async def health_check():
    """Health check for Kubernetes."""
    return {
        "status": "healthy" if model.is_loaded else "unhealthy",
        "model_loaded": model.is_loaded,
        "timestamp": time.time()
    }

@app.post("/predict")
async def predict_from_file(
    file: UploadFile = File(...),
    top_k: int = 5
):
    """Predict from uploaded file."""
    try:
        # Read file
        contents = await file.read()

        # Load and preprocess image
        image = load_image_from_bytes(contents)
        tensor = preprocess_image(image)

        # Predict
        result = model.predict(tensor, top_k=top_k)

        return result

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

**Key concepts:**
- Lifespan events (startup/shutdown hooks)
- Async endpoints (better concurrency)
- Error handling with HTTP status codes
- Automatic API documentation

### Step 1.6: Testing

Create comprehensive tests (`tests/test_api.py`):

```python
from fastapi.testclient import TestClient
from src.api import app

client = TestClient(app)

def test_health_check():
    """Test health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_predict_valid_image():
    """Test prediction with valid image."""
    # Create test image
    from PIL import Image
    import io

    img = Image.new('RGB', (224, 224), color=(73, 109, 137))
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    buf.seek(0)

    # Make request
    response = client.post(
        "/predict",
        files={"file": ("test.jpg", buf, "image/jpeg")},
        params={"top_k": 3}
    )

    assert response.status_code == 200
    result = response.json()
    assert "predictions" in result
    assert len(result["predictions"]) == 3
```

**Run tests:**
```bash
pytest tests/ -v
```

## Phase 2: Containerization (3-4 hours)

### Step 2.1: Create Dockerfile

Multi-stage build for optimal size:

```dockerfile
# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /build
COPY requirements.txt .

# Install dependencies to local directory
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Copy dependencies from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application
COPY src/ ./src/

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Set PATH
ENV PATH=/home/appuser/.local/bin:$PATH

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Key optimizations:**
- Multi-stage build (smaller final image)
- Layer caching (faster rebuilds)
- Non-root user (security)
- Slim base image

### Step 2.2: Create .dockerignore

```
__pycache__/
*.pyc
venv/
.git/
tests/
docs/
*.md
.env
```

### Step 2.3: Build and Test

```bash
# Build
docker build -t model-serving-api:latest .

# Run
docker run -p 8000:8000 model-serving-api:latest

# Test
curl http://localhost:8000/health
```

## Phase 3: Kubernetes Deployment (4-6 hours)

### Step 3.1: Create Namespace

```yaml
# kubernetes/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: model-serving
```

### Step 3.2: Create ConfigMap

```yaml
# kubernetes/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: model-serving-config
  namespace: model-serving
data:
  LOG_LEVEL: "INFO"
  MODEL_DEVICE: "cpu"
  TOP_K_PREDICTIONS: "5"
```

### Step 3.3: Create Deployment

```yaml
# kubernetes/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: model-serving
  namespace: model-serving
spec:
  replicas: 3
  selector:
    matchLabels:
      app: model-serving
  template:
    metadata:
      labels:
        app: model-serving
    spec:
      containers:
      - name: model-serving
        image: model-serving-api:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: model-serving-config
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
```

**Key concepts:**
- Replicas for HA (3 minimum)
- Resource limits (prevent resource starvation)
- Health probes (automatic restart if unhealthy)
- ConfigMap for configuration

### Step 3.4: Create Service

```yaml
# kubernetes/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: model-serving
  namespace: model-serving
spec:
  type: LoadBalancer
  selector:
    app: model-serving
  ports:
  - port: 80
    targetPort: 8000
```

### Step 3.5: Deploy

```bash
# Apply all manifests
kubectl apply -f kubernetes/

# Check status
kubectl get pods -n model-serving
kubectl get svc -n model-serving

# Test
SERVICE_URL=$(kubectl get svc model-serving -n model-serving -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
curl http://$SERVICE_URL/health
```

## Phase 4: Monitoring (4-6 hours)

### Step 4.1: Add Prometheus Metrics to API

```python
# In src/api.py, add:
from prometheus_fastapi_instrumentator import Instrumentator

# After app creation:
Instrumentator().instrument(app).expose(app)
```

This adds:
- Request count
- Request duration
- In-progress requests
- `/metrics` endpoint

### Step 4.2: Create Prometheus Configuration

```yaml
# monitoring/prometheus/prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'model-serving-api'
    kubernetes_sd_configs:
      - role: pod
        namespaces:
          names:
            - model-serving
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
```

### Step 4.3: Add Grafana Dashboard

Create dashboard showing:
- Request rate
- Latency (p95, p99)
- Error rate
- Resource usage

### Step 4.4: Deploy Monitoring Stack

```bash
# Using docker-compose for local testing
docker-compose up -d prometheus grafana

# Access Grafana
open http://localhost:3000
```

## Phase 5: CI/CD Pipeline (3-4 hours)

### Step 5.1: Create GitHub Actions Workflow

```yaml
# .github/workflows/ci-cd.yml
name: CI/CD Pipeline

on:
  push:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: pytest tests/ -v --cov=src

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/build-push-action@v5
        with:
          push: true
          tags: ${{ github.repository }}:latest
```

**Pipeline stages:**
1. Linting (flake8, black)
2. Testing (pytest)
3. Security scanning (trivy)
4. Build Docker image
5. Push to registry
6. Deploy (optional)

## Phase 6: Documentation (2-3 hours)

### Step 6.1: Create README.md

Include:
- Project overview
- Quick start guide
- Architecture diagram
- Links to detailed docs

### Step 6.2: Create API Documentation

Already auto-generated by FastAPI at `/docs`

### Step 6.3: Create Additional Docs

- ARCHITECTURE.md: System design
- DEPLOYMENT.md: Deployment instructions
- TROUBLESHOOTING.md: Common issues

## Best Practices Implemented

1. **12-Factor App Principles**
   - Config in environment
   - Stateless processes
   - Port binding
   - Disposability

2. **Production Readiness**
   - Health checks
   - Graceful shutdown
   - Resource limits
   - Error handling

3. **Security**
   - Non-root user
   - Input validation
   - No secrets in code
   - Security scanning

4. **Observability**
   - Structured logging
   - Metrics collection
   - Health endpoints
   - Distributed tracing (optional)

5. **Testing**
   - Unit tests
   - Integration tests
   - API tests
   - Coverage >80%

## Common Pitfalls to Avoid

1. **Not loading model at startup**: Causes slow first request
2. **Missing health checks**: K8s can't detect failures
3. **Hardcoded configuration**: Not portable across environments
4. **No resource limits**: Can starve other pods
5. **Large Docker images**: Slow deployments
6. **Not testing container locally**: Find issues early

## Next Steps

After completing this project:

1. **Optimize**: Profile and optimize hot paths
2. **Scale**: Test with high load
3. **Extend**: Add features (caching, batching, etc.)
4. **Productionize**: Add auth, rate limiting, etc.
5. **Document**: Write blog post about what you learned

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Kubernetes Best Practices](https://kubernetes.io/docs/concepts/)
- [PyTorch Serving Guide](https://pytorch.org/serve/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/)

## Questions?

Contact: ai-infra-curriculum@joshua-ferguson.com
