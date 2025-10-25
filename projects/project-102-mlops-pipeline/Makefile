.PHONY: help setup install test lint format clean docker-build docker-up docker-down deploy

help:
	@echo "Available commands:"
	@echo "  make setup          - Set up development environment"
	@echo "  make install        - Install dependencies"
	@echo "  make test           - Run tests"
	@echo "  make lint           - Run linters"
	@echo "  make format         - Format code"
	@echo "  make clean          - Clean temporary files"
	@echo "  make docker-build   - Build Docker images"
	@echo "  make docker-up      - Start Docker containers"
	@echo "  make docker-down    - Stop Docker containers"
	@echo "  make deploy         - Deploy to Kubernetes"

setup:
	@echo "Setting up development environment..."
	python -m venv venv
	. venv/bin/activate && pip install --upgrade pip
	. venv/bin/activate && pip install -r requirements.txt -r requirements-dev.txt
	@echo "Setup complete!"

install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt -r requirements-dev.txt

test:
	@echo "Running tests..."
	pytest

test-unit:
	@echo "Running unit tests..."
	pytest tests/unit -v

test-integration:
	@echo "Running integration tests..."
	pytest tests/integration -v

test-coverage:
	@echo "Running tests with coverage..."
	pytest --cov=src --cov-report=html --cov-report=term

lint:
	@echo "Running linters..."
	flake8 src tests
	pylint src
	mypy src

format:
	@echo "Formatting code..."
	black src tests
	isort src tests

clean:
	@echo "Cleaning temporary files..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf dist
	rm -rf build

docker-build:
	@echo "Building Docker images..."
	docker-compose build

docker-up:
	@echo "Starting Docker containers..."
	docker-compose up -d

docker-down:
	@echo "Stopping Docker containers..."
	docker-compose down

docker-logs:
	@echo "Showing Docker logs..."
	docker-compose logs -f

docker-restart:
	@echo "Restarting Docker containers..."
	docker-compose restart

init-airflow:
	@echo "Initializing Airflow..."
	docker-compose up airflow-init

deploy-k8s:
	@echo "Deploying to Kubernetes..."
	kubectl apply -f kubernetes/

undeploy-k8s:
	@echo "Removing from Kubernetes..."
	kubectl delete -f kubernetes/

run-data-pipeline:
	@echo "Triggering data pipeline..."
	docker-compose exec airflow-webserver airflow dags trigger data_pipeline

run-training-pipeline:
	@echo "Triggering training pipeline..."
	docker-compose exec airflow-webserver airflow dags trigger training_pipeline

run-deployment-pipeline:
	@echo "Triggering deployment pipeline..."
	docker-compose exec airflow-webserver airflow dags trigger deployment_pipeline

check-status:
	@echo "Checking service status..."
	@echo "Docker containers:"
	docker-compose ps
	@echo "\nKubernetes pods:"
	kubectl get pods -n ml-serving
