# Architecture Documentation

## System Overview

The Model Serving System is a production-ready machine learning inference API that serves a pretrained ResNet50 image classification model. The system is designed for high availability, scalability, and observability.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Layer                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ Web App  │  │  Mobile  │  │   CLI    │  │  Other   │       │
│  │          │  │   App    │  │          │  │ Services │       │
│  └─────┬────┘  └─────┬────┘  └─────┬────┘  └─────┬────┘       │
└────────┼─────────────┼─────────────┼─────────────┼─────────────┘
         │             │             │             │
         └─────────────┴─────────────┴─────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Load Balancer / Ingress                      │
│              (Kubernetes Service / Cloud LB)                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ↓                   ↓                   ↓
┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│  API Pod 1     │  │  API Pod 2     │  │  API Pod 3     │
│ ┌────────────┐ │  │ ┌────────────┐ │  │ ┌────────────┐ │
│ │  FastAPI   │ │  │ │  FastAPI   │ │  │ │  FastAPI   │ │
│ │  Server    │ │  │ │  Server    │ │  │ │  Server    │ │
│ └─────┬──────┘ │  │ └─────┬──────┘ │  │ └─────┬──────┘ │
│       │        │  │       │        │  │       │        │
│ ┌─────┴──────┐ │  │ ┌─────┴──────┐ │  │ ┌─────┴──────┐ │
│ │ ResNet50   │ │  │ │ ResNet50   │ │  │ │ ResNet50   │ │
│ │   Model    │ │  │ │   Model    │ │  │ │   Model    │ │
│ └────────────┘ │  │ └────────────┘ │  │ └────────────┘ │
│                │  │                │  │                │
│ ┌────────────┐ │  │ ┌────────────┐ │  │ ┌────────────┐ │
│ │  Metrics   │ │  │ │  Metrics   │ │  │ │  Metrics   │ │
│ │ Exporter   │ │  │ │ Exporter   │ │  │ │ Exporter   │ │
│ └────────────┘ │  │ └────────────┘ │  │ └────────────┘ │
└────────┬───────┘  └────────┬───────┘  └────────┬───────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │ (metrics scraping)
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Monitoring Stack                             │
│  ┌──────────────────┐          ┌──────────────────┐            │
│  │   Prometheus     │  ──────> │    Grafana       │            │
│  │  (Metrics DB)    │          │  (Dashboards)    │            │
│  │                  │          │                  │            │
│  │ - Request rates  │          │ - API metrics    │            │
│  │ - Latencies      │          │ - Resource usage │            │
│  │ - Error rates    │          │ - Alerts         │            │
│  └──────────────────┘          └──────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────────────────────────────────┐
│                         Alerting                                │
│              (AlertManager / PagerDuty / Slack)                 │
└─────────────────────────────────────────────────────────────────┘
```

## Component Architecture

### 1. API Layer (FastAPI)

**Responsibilities:**
- HTTP request handling
- Request validation
- Response formatting
- Error handling
- API documentation

**Key Components:**
- `src/api.py`: Main FastAPI application
- Request/response models (Pydantic)
- Exception handlers
- Middleware (CORS, logging, metrics)

**Technology:**
- FastAPI: Modern, high-performance web framework
- Uvicorn: ASGI server for production
- Pydantic: Data validation

### 2. Model Layer

**Responsibilities:**
- Model loading and initialization
- Inference execution
- Model lifecycle management
- Memory management

**Key Components:**
- `src/model.py`: Model wrapper class
- ResNet50 model (PyTorch)
- Singleton pattern for model instance

**Technology:**
- PyTorch: Deep learning framework
- TorchVision: Pretrained models and transforms

### 3. Utility Layer

**Responsibilities:**
- Image preprocessing
- Image validation
- Image download (from URLs)
- Label management

**Key Components:**
- `src/utils.py`: Utility functions
- Image transformations (resize, normalize)
- Error handling

**Technology:**
- PIL/Pillow: Image processing
- NumPy: Array operations

### 4. Configuration Management

**Responsibilities:**
- Environment variable loading
- Configuration validation
- Settings management

**Key Components:**
- `src/config.py`: Settings class
- Environment variable parsing
- Default values

**Technology:**
- Pydantic Settings: Type-safe configuration

## Data Flow

### Prediction Request Flow

```
1. Client sends image (file or URL)
   ↓
2. API receives request
   ↓
3. Request validation (FastAPI/Pydantic)
   ↓
4. Image download (if URL) or read (if file)
   ↓
5. Image validation (size, format)
   ↓
6. Image preprocessing (resize, normalize)
   ↓
7. Model inference (forward pass)
   ↓
8. Post-processing (softmax, top-k)
   ↓
9. Response formatting
   ↓
10. Client receives predictions
```

### Metrics Flow

```
1. API receives request
   ↓
2. Prometheus instrumentator records metrics
   ↓
3. Metrics exposed at /metrics endpoint
   ↓
4. Prometheus scrapes metrics (every 15s)
   ↓
5. Grafana queries Prometheus
   ↓
6. Dashboards display visualizations
```

## Deployment Architecture

### Kubernetes Deployment

**Components:**

1. **Namespace**: Isolated environment (`model-serving`)

2. **Deployment**:
   - 3 replicas (default)
   - Rolling update strategy
   - Resource limits: 4Gi memory, 2 CPU
   - Probes: liveness, readiness, startup

3. **Service**:
   - LoadBalancer type (cloud) or NodePort (on-prem)
   - Port 80 → 8000 mapping
   - Session affinity: None (stateless)

4. **ConfigMap**:
   - Application configuration
   - Model settings
   - Feature flags

5. **HorizontalPodAutoscaler**:
   - Min replicas: 3
   - Max replicas: 10
   - CPU target: 70%
   - Memory target: 80%

### Container Architecture

**Multi-stage Docker build:**

```
Stage 1 (Builder):
- Install build dependencies
- Compile Python packages
- Create wheel files

Stage 2 (Runtime):
- Minimal base image (python:3.11-slim)
- Copy compiled packages
- Non-root user
- Minimal layers
```

**Container optimizations:**
- Layer caching
- Multi-stage builds
- Minimal base image
- Non-root user
- Health checks

## Design Decisions

### 1. Why FastAPI?

**Pros:**
- High performance (comparable to Node.js)
- Automatic API documentation (OpenAPI)
- Type hints and validation (Pydantic)
- Async support
- Great developer experience

**Cons:**
- Relatively new (but mature)
- Smaller ecosystem than Flask

**Alternatives considered:**
- Flask: Simpler but lacks async and auto-docs
- TorchServe: Too heavyweight for simple use case

### 2. Why In-Memory Model Loading?

**Pros:**
- Fast inference (no cold starts)
- Simple architecture
- Predictable latency

**Cons:**
- Higher memory usage per pod
- Longer startup time

**Alternatives considered:**
- External model server: More complex, additional latency
- On-demand loading: Cold start delays

### 3. Why CPU Deployment?

**Pros:**
- Lower cost
- Simpler infrastructure
- Sufficient for real-time inference

**Cons:**
- Slower than GPU
- Limited throughput

**For GPU deployment:**
- Change MODEL_DEVICE to "cuda"
- Add NVIDIA device plugin to Kubernetes
- Update resource requests (nvidia.com/gpu: 1)

### 4. Why Prometheus + Grafana?

**Pros:**
- Industry standard
- Pull-based metrics (more reliable)
- Powerful query language (PromQL)
- Rich visualization options

**Alternatives considered:**
- CloudWatch: Vendor lock-in
- Datadog: Expensive
- ELK Stack: Overkill for metrics

## Scalability

### Horizontal Scaling

**How it works:**
- HPA monitors CPU/memory usage
- Automatically adds/removes pods
- Load balancer distributes traffic

**Limits:**
- Min: 3 pods (high availability)
- Max: 10 pods (cost control)

**Scaling triggers:**
- CPU > 70%
- Memory > 80%
- Custom metrics (e.g., queue length)

### Vertical Scaling

**Current limits:**
- 2 CPU cores per pod
- 4Gi memory per pod

**To increase:**
- Update resource limits in deployment.yaml
- Ensure nodes have sufficient capacity

## High Availability

**Strategies:**

1. **Multiple replicas**: 3+ pods always running
2. **Pod anti-affinity**: Spread pods across nodes
3. **Liveness probes**: Restart unhealthy pods
4. **Readiness probes**: Don't send traffic to unready pods
5. **Rolling updates**: Zero-downtime deployments

**SLA targets:**
- Availability: 99.9% (43 minutes downtime/month)
- Error rate: < 0.1%
- p95 latency: < 100ms

## Security

**Implemented:**
- Non-root container user
- Read-only root filesystem (optional)
- Resource limits (prevent DoS)
- No secrets in code
- HTTPS termination at load balancer

**Recommended additions:**
- API authentication (JWT/API keys)
- Rate limiting
- Input sanitization
- Network policies
- Secret management (Kubernetes Secrets/Vault)

## Monitoring & Observability

### Key Metrics

**Application metrics:**
- Request rate (requests/second)
- Response latency (p50, p95, p99)
- Error rate (%)
- Prediction count

**Infrastructure metrics:**
- CPU usage (%)
- Memory usage (bytes)
- Network I/O
- Disk I/O

**Business metrics:**
- Total predictions
- Popular classes
- User geography

### Alerting Rules

1. **Service down**: > 1 minute
2. **High latency**: p95 > 500ms for 5 minutes
3. **High error rate**: > 5% for 5 minutes
4. **High CPU**: > 80% for 10 minutes
5. **High memory**: > 85% for 10 minutes

## Performance Optimization

### Current Optimizations

1. **Model loaded at startup**: No cold starts
2. **Batch size 1**: Low latency
3. **CPU inference**: Cost-effective
4. **Async endpoints**: Better concurrency
5. **Connection pooling**: Efficient resource use

### Future Optimizations

1. **Request batching**: Group multiple requests
2. **Model quantization**: Reduce model size
3. **GPU inference**: Faster computation
4. **Caching**: Cache frequent predictions
5. **CDN**: Serve static assets

## Disaster Recovery

**Backup strategy:**
- Container images: Stored in registry
- Configuration: Version controlled in Git
- Metrics: 7-day retention in Prometheus

**Recovery procedures:**
1. **Pod failure**: Automatic restart (Kubernetes)
2. **Node failure**: Pods rescheduled to healthy nodes
3. **Cluster failure**: Deploy to backup cluster
4. **Data center failure**: Multi-region deployment

## Future Enhancements

### Short-term (1-3 months)
- [ ] Add request caching (Redis)
- [ ] Implement API authentication
- [ ] Add request batching
- [ ] GPU support
- [ ] Multi-model support

### Medium-term (3-6 months)
- [ ] A/B testing framework
- [ ] Model versioning
- [ ] Blue-green deployments
- [ ] Distributed tracing (Jaeger)
- [ ] Enhanced monitoring dashboards

### Long-term (6-12 months)
- [ ] Multi-region deployment
- [ ] Auto-scaling based on queue depth
- [ ] Model retraining pipeline
- [ ] Feature store integration
- [ ] Advanced analytics

## References

- FastAPI Documentation: https://fastapi.tiangolo.com/
- PyTorch Documentation: https://pytorch.org/docs/
- Kubernetes Best Practices: https://kubernetes.io/docs/concepts/
- Prometheus Best Practices: https://prometheus.io/docs/practices/
