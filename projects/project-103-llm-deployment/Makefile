.PHONY: help install install-dev test lint format clean docker-build docker-up docker-down k8s-deploy k8s-delete run

help:
	@echo "Available commands:"
	@echo "  make install       - Install dependencies"
	@echo "  make install-dev   - Install dev dependencies"
	@echo "  make test          - Run tests"
	@echo "  make lint          - Run linting"
	@echo "  make format        - Format code"
	@echo "  make clean         - Clean generated files"
	@echo "  make docker-build  - Build Docker image"
	@echo "  make docker-up     - Start Docker Compose stack"
	@echo "  make docker-down   - Stop Docker Compose stack"
	@echo "  make k8s-deploy    - Deploy to Kubernetes"
	@echo "  make k8s-delete    - Delete from Kubernetes"
	@echo "  make run           - Run API locally"

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt
	pre-commit install

test:
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term

test-fast:
	pytest tests/ -v -m "not slow"

lint:
	flake8 src/ tests/
	mypy src/

format:
	black src/ tests/
	isort src/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .coverage htmlcov
	rm -rf build dist *.egg-info

docker-build:
	docker build -t llm-deployment-platform:latest .

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f llm-api

k8s-deploy:
	kubectl apply -f kubernetes/namespace.yaml
	kubectl apply -f kubernetes/configmap.yaml
	kubectl apply -f kubernetes/pvc.yaml
	kubectl apply -f kubernetes/deployment.yaml
	kubectl apply -f kubernetes/service.yaml
	kubectl apply -f kubernetes/hpa.yaml

k8s-delete:
	kubectl delete -f kubernetes/ --ignore-not-found=true

k8s-logs:
	kubectl logs -f deployment/llm-api -n llm-platform

run:
	python -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Development helpers
dev-setup:
	python -m venv venv
	./venv/bin/pip install -r requirements-dev.txt
	cp .env.example .env

benchmark:
	python scripts/benchmark.sh

download-model:
	bash scripts/download-model.sh tiny-llama

ingest-sample-data:
	python -m scripts.ingest_docs data/sample-docs/
