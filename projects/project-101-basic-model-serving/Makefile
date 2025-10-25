# Makefile for Model Serving System

.PHONY: help install test lint format clean docker-build docker-run k8s-deploy k8s-delete

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

test: ## Run tests
	pytest tests/ -v --cov=src --cov-report=term-missing

test-fast: ## Run tests without coverage
	pytest tests/ -v

lint: ## Run linters
	flake8 src/ tests/ --max-line-length=100 --extend-ignore=E203,W503
	mypy src/ --ignore-missing-imports

format: ## Format code
	black src/ tests/
	isort src/ tests/

format-check: ## Check code formatting
	black --check src/ tests/
	isort --check-only src/ tests/

clean: ## Clean temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache .coverage htmlcov/ dist/ build/

run: ## Run application locally
	python -m uvicorn src.api:app --reload --host 0.0.0.0 --port 8000

docker-build: ## Build Docker image
	docker build -t model-serving-api:latest .

docker-run: ## Run Docker container
	docker run -p 8000:8000 \
		-e MODEL_DEVICE=cpu \
		-e LOG_LEVEL=INFO \
		--name model-serving \
		model-serving-api:latest

docker-stop: ## Stop Docker container
	docker stop model-serving
	docker rm model-serving

docker-compose-up: ## Start all services with docker-compose
	docker-compose up -d

docker-compose-down: ## Stop all services
	docker-compose down

docker-compose-logs: ## View docker-compose logs
	docker-compose logs -f

k8s-deploy: ## Deploy to Kubernetes
	./scripts/deploy.sh

k8s-delete: ## Delete Kubernetes deployment
	kubectl delete namespace model-serving

k8s-logs: ## View Kubernetes logs
	kubectl logs -f deployment/model-serving -n model-serving

k8s-status: ## Check Kubernetes deployment status
	kubectl get pods -n model-serving
	kubectl get svc -n model-serving

smoke-test: ## Run smoke tests
	./scripts/test-deployment.sh

load-test: ## Run load tests
	./scripts/load-test.sh

setup: ## Run setup script
	./scripts/setup.sh

all: format lint test ## Run format, lint, and test

ci: lint test ## Run CI checks (lint and test)
