# Exercise 06: FastAPI ML Service Template Generator

A powerful code generator that creates production-ready FastAPI services for ML model serving, complete with tests, Docker configuration, and CI/CD pipelines.

## Features

- **Multiple Templates**: Image classification, text classification, object detection, time series, and generic ML APIs
- **Production-Ready Code**: FastAPI with Pydantic validation, error handling, and logging
- **Auto-Generated Documentation**: OpenAPI/Swagger docs with examples
- **Comprehensive Testing**: Unit tests, integration tests, and fixtures
- **Docker Support**: Multi-stage Dockerfiles and docker-compose configurations
- **CI/CD Pipelines**: GitHub Actions workflows for testing and deployment
- **Monitoring**: Optional Prometheus metrics and Grafana dashboards

## Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .
```

### Basic Usage

```bash
# Generate image classification API
mlapi-gen generate my-image-api --template image_classification

# Generate with all features
mlapi-gen generate my-api \
    --template generic \
    --with-auth \
    --with-monitoring \
    --with-rate-limiting

# List available templates
mlapi-gen list-templates

# Interactive mode
mlapi-gen generate my-project --interactive
```

## Project Structure

```
exercise-06-fastapi-ml-template-generator/
├── src/
│   ├── mlapi_gen/
│   │   ├── __init__.py
│   │   ├── template_engine.py      # Core generation engine
│   │   ├── cli.py                  # CLI interface
│   │   └── validators.py           # Config validation
├── templates/
│   ├── app/
│   │   ├── main.py.j2              # FastAPI app
│   │   ├── endpoints.py.j2         # API endpoints
│   │   └── schemas.py.j2           # Pydantic models
│   ├── tests/
│   │   ├── test_api.py.j2
│   │   └── conftest.py.j2
│   ├── Dockerfile.j2
│   ├── docker-compose.yml.j2
│   └── README.md.j2
├── tests/
├── scripts/
└── README.md
```

## Available Templates

### 1. Image Classification

```bash
mlapi-gen generate image-classifier --template image_classification
```

Features:
- Upload image endpoint
- ResNet/VGG model support
- Image preprocessing
- Top-K predictions
- Confidence scores

### 2. Text Classification

```bash
mlapi-gen generate text-classifier --template text_classification
```

Features:
- Text input endpoint
- BERT/transformer support
- Tokenization
- Multi-label classification

### 3. Object Detection

```bash
mlapi-gen generate object-detector --template object_detection
```

Features:
- Image upload
- Bounding box detection
- YOLO/Faster R-CNN support
- NMS post-processing

### 4. Time Series Prediction

```bash
mlapi-gen generate time-series-api --template time_series
```

Features:
- Historical data input
- LSTM/GRU models
- Multi-step forecasting
- Confidence intervals

### 5. Generic ML API

```bash
mlapi-gen generate generic-ml-api --template generic
```

Features:
- Customizable input/output schemas
- Flexible model integration
- Batch prediction support

## Generated Project Structure

```
my-api/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application
│   ├── api/
│   │   ├── __init__.py
│   │   └── endpoints.py        # API routes
│   ├── models/
│   │   ├── __init__.py
│   │   ├── schemas.py          # Pydantic models
│   │   └── ml_model.py         # ML model wrapper
│   └── core/
│       ├── __init__.py
│       ├── config.py           # Settings
│       └── logging.py          # Logging config
├── tests/
│   ├── __init__.py
│   ├── test_api.py
│   ├── test_model.py
│   └── conftest.py
├── models/                     # Model storage
│   └── .gitkeep
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── README.md
└── .github/
    └── workflows/
        └── test.yml
```

## Example Generated API

```python
# app/main.py
from fastapi import FastAPI
from app.api import endpoints

app = FastAPI(title="Image Classification API")
app.include_router(endpoints.router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

```python
# app/api/endpoints.py
@router.post("/predict", response_model=PredictionResponse)
async def predict(file: UploadFile = File(...)):
    # Load and preprocess image
    image = await file.read()
    result = model.predict(image)
    return PredictionResponse(**result)
```

## Configuration Options

```python
# Example ProjectConfig
config = ProjectConfig(
    name="my-api",
    description="Image classification API",
    template_type="image_classification",
    model_path="models/resnet50.pt",
    with_auth=True,
    with_rate_limiting=True,
    with_monitoring=True,
    python_version="3.11"
)
```

## Testing Generated Projects

```bash
cd my-generated-api

# Run tests
pytest tests/ -v

# Start API
uvicorn app.main:app --reload

# Open API docs
open http://localhost:8000/docs
```

## Docker Deployment

```bash
# Build image
docker build -t my-api .

# Run container
docker run -p 8000:8000 my-api

# Use docker-compose
docker-compose up
```

## Documentation

- [STEP_BY_STEP.md](STEP_BY_STEP.md) - Implementation guide
- [Template Customization](docs/templates.md) - How to add templates

## Requirements

- Python 3.11+
- FastAPI 0.100+
- Pydantic 2.0+
- Jinja2 3.1+

## License

MIT License
