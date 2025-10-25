# Project 03: LLM Deployment Platform

A production-ready LLM deployment platform with RAG support, GPU optimization, comprehensive monitoring, and cost tracking.

## Features

- **LLM Serving**: High-performance serving with vLLM (with transformers fallback)
- **RAG System**: Complete Retrieval-Augmented Generation pipeline with vector database
- **Document Ingestion**: Multi-format document loading (PDF, TXT, MD, HTML, JSON, CSV)
- **GPU Optimization**: FP16 quantization, continuous batching, KV cache optimization
- **Monitoring**: Prometheus metrics, Grafana dashboards, GPU monitoring
- **Cost Tracking**: Real-time cost calculation and optimization recommendations
- **Production-Ready**: Docker, Kubernetes, CI/CD, comprehensive testing

## Quick Start

### Local Development

```bash
# 1. Clone and setup
cd project-103-llm-deployment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your settings

# 3. Run the API
python -m uvicorn src.api.main:app --reload

# 4. Access the API
# Swagger docs: http://localhost:8000/docs
# Metrics: http://localhost:8000/metrics
```

### Docker Deployment

```bash
# Start all services (API, ChromaDB, Prometheus, Grafana)
docker-compose up -d

# View logs
docker-compose logs -f llm-api

# Stop services
docker-compose down
```

### Kubernetes Deployment

```bash
# Apply manifests
kubectl apply -f kubernetes/namespace.yaml
kubectl apply -f kubernetes/configmap.yaml
kubectl apply -f kubernetes/secret.yaml  # Create secrets first!
kubectl apply -f kubernetes/pvc.yaml
kubectl apply -f kubernetes/deployment.yaml
kubectl apply -f kubernetes/service.yaml
kubectl apply -f kubernetes/hpa.yaml

# Check status
kubectl get pods -n llm-platform
kubectl logs -f deployment/llm-api -n llm-platform
```

## Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│  FastAPI API    │
│   (Routing)     │
└────┬────────┬───┘
     │        │
     ▼        ▼
┌────────┐  ┌──────────────┐
│  RAG   │  │ Direct LLM   │
│ System │  │  Generation  │
└────┬───┘  └──────┬───────┘
     │             │
     ▼             │
┌──────────┐       │
│ ChromaDB │       │
│ (Vector  │       │
│Database) │       │
└──────────┘       │
     │             │
     └─────┬───────┘
           ▼
    ┌──────────────┐
    │  vLLM Engine │
    │ (Llama 2 7B) │
    │   with GPU   │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │ Monitoring   │
    │ (Prometheus, │
    │  Grafana)    │
    └──────────────┘
```

## API Endpoints

### Core Endpoints

- `POST /generate` - Direct LLM text generation
- `POST /generate/stream` - Streaming generation (SSE)
- `POST /rag-generate` - RAG-augmented generation
- `POST /ingest` - Ingest documents into vector database

### Management Endpoints

- `GET /health` - Health check
- `GET /ready` - Readiness check
- `GET /models` - Model information
- `GET /metrics` - Prometheus metrics
- `GET /cost` - Cost breakdown and recommendations

## Configuration

### Environment Variables

Key environment variables (see `.env.example`):

```bash
# Model Configuration
MODEL_CONFIG=tiny-llama              # Model to use
EMBEDDING_MODEL=all-MiniLM-L6-v2     # Embedding model
VECTOR_DB_BACKEND=chromadb           # Vector database

# RAG Settings
RAG_TOP_K=5                          # Number of chunks to retrieve
RAG_CHUNK_SIZE=512                   # Chunk size in characters
RAG_CHUNK_OVERLAP=50                 # Overlap between chunks

# Cost Tracking
GPU_COST_PER_HOUR=1.0                # GPU cost for tracking

# Rate Limiting
RATE_LIMIT_RPM=60                    # Requests per minute

# Paths
CHROMA_PERSIST_DIR=./chroma_db       # ChromaDB storage
```

### Model Configurations

Available model configs (see `src/llm/model_config.py`):

- `tiny-llama`: TinyLlama 1.1B (testing, low GPU requirements)
- `llama2-7b-chat`: Llama 2 7B Chat (production, ~14GB GPU RAM)
- `llama2-7b-chat-quantized`: Llama 2 7B AWQ quantized (~7GB GPU RAM)
- `mistral-7b-instruct`: Mistral 7B Instruct (~14GB GPU RAM)
- `mock`: Mock model for testing without GPU

## GPU Requirements

### Minimum (Development)
- **GPU**: NVIDIA T4 (16GB VRAM)
- **CPU**: 4 cores
- **RAM**: 16GB
- **Storage**: 50GB

### Recommended (Production)
- **GPU**: NVIDIA A10 or A100 (24GB+ VRAM)
- **CPU**: 8 cores
- **RAM**: 32GB
- **Storage**: 100GB

## Performance Targets

- **Time to first token**: <500ms
- **Throughput**: >50 tokens/sec
- **GPU utilization**: >70% under load
- **API latency (p95)**: <2s for 200 token generation

## Cost Optimization

### Tips

1. **Model Quantization**: Use AWQ/GPTQ quantization to reduce memory by 50%
2. **Spot Instances**: Use cloud spot/preemptible instances for 60-80% savings
3. **Auto-scaling**: Scale to zero during off-hours
4. **Request Batching**: Increase throughput with continuous batching
5. **Caching**: Cache frequent queries and responses

### Estimated Costs

**Monthly Cloud Costs** (24/7 operation):
- GPU instance (A10): $300-500
- Vector database (managed): $50-100
- Storage and networking: $20-50
- **Total**: $370-650/month

**Cost Optimizations**:
- Spot instances: ~$150-250/month (60% savings)
- Auto-scaling (8hrs/day): ~$100-170/month (70% savings)

## Monitoring

### Metrics

Access Grafana dashboards at `http://localhost:3000` (Docker) or via LoadBalancer (K8s).

**Key metrics tracked**:
- Request rates and latencies
- Token throughput (tokens/sec)
- GPU utilization and memory
- Cost per request and monthly projections
- RAG retrieval performance
- Error rates and types

### Alerts

Configured alerts (see `monitoring/prometheus/alerts.yml`):
- High error rate (>5%)
- High latency (>10s P95)
- Low GPU utilization (<30%)
- GPU memory high (>90%)
- High estimated monthly cost (>$1000)
- API down

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_complete_system.py

# Run with verbose output
pytest -v

# Run only fast tests (skip slow integration tests)
pytest -m "not slow"
```

## Development

### Setup Development Environment

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run linting
black src/
isort src/
flake8 src/

# Type checking
mypy src/
```

### Project Structure

```
project-103-llm-deployment/
├── src/
│   ├── api/              # FastAPI application
│   ├── llm/              # LLM serving logic
│   ├── rag/              # RAG implementation
│   ├── ingestion/        # Document ingestion
│   └── monitoring/       # Metrics and cost tracking
├── tests/                # Test suite
├── kubernetes/           # K8s manifests
├── monitoring/           # Prometheus & Grafana configs
├── docs/                 # Documentation
├── scripts/              # Deployment scripts
├── data/                 # Sample data
└── prompts/              # Prompt templates
```

## Documentation

Detailed documentation available in `/docs`:

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - System architecture and design
- [DEPLOYMENT.md](docs/DEPLOYMENT.md) - Deployment guides
- [OPTIMIZATION.md](docs/OPTIMIZATION.md) - Performance optimization
- [COST.md](docs/COST.md) - Cost analysis and optimization
- [GPU.md](docs/GPU.md) - GPU configuration
- [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) - Common issues
- [STEP_BY_STEP.md](STEP_BY_STEP.md) - Detailed implementation guide

## Troubleshooting

### Common Issues

**1. GPU not detected**
```bash
# Check NVIDIA drivers
nvidia-smi

# Check Docker GPU support
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

**2. Out of memory errors**
- Use a smaller model (`tiny-llama`)
- Enable quantization
- Reduce batch size
- Decrease `max_model_len`

**3. Slow inference**
- Ensure GPU is being used
- Check GPU utilization with `nvidia-smi`
- Enable continuous batching (vLLM default)
- Increase batch size if GPU memory allows

**4. Vector DB connection issues**
```bash
# Check ChromaDB status
curl http://localhost:8001/api/v1/heartbeat

# Restart ChromaDB
docker-compose restart chromadb
```

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for more issues and solutions.

## Security

- Never commit secrets or API keys
- Use Kubernetes secrets for sensitive data
- Enable authentication for production deployments
- Run containers as non-root user
- Validate and sanitize all user inputs
- Rate limiting enabled by default
- Regular security updates

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run linting and tests
6. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

For issues and questions:
- GitHub Issues: [Create an issue]
- Documentation: See `/docs`
- Email: ai-infra-curriculum@joshua-ferguson.com

## Acknowledgments

- vLLM for high-performance LLM serving
- Hugging Face for model hosting
- ChromaDB for vector storage
- FastAPI for the web framework

---

**Part of the AI Infrastructure Engineer curriculum**
**Visit**: https://github.com/ai-infra-curriculum
