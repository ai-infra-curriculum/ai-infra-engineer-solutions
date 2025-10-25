# Step-by-Step Implementation Guide

This guide walks through implementing the complete MLOps pipeline from scratch.

## Table of Contents

1. [Environment Setup](#1-environment-setup)
2. [Data Pipeline Implementation](#2-data-pipeline-implementation)
3. [Training Pipeline Implementation](#3-training-pipeline-implementation)
4. [Model Registry Setup](#4-model-registry-setup)
5. [Deployment Pipeline](#5-deployment-pipeline)
6. [Monitoring Setup](#6-monitoring-setup)
7. [CI/CD Integration](#7-cicd-integration)
8. [Production Deployment](#8-production-deployment)

## 1. Environment Setup

### 1.1 Prerequisites Installation

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installations
docker --version
docker-compose --version
```

### 1.2 Project Initialization

```bash
# Clone or create project directory
mkdir -p project-102-mlops-pipeline
cd project-102-mlops-pipeline

# Create directory structure
mkdir -p {dags,src/{common,data,training,deployment,monitoring},tests/{unit,integration},docker,kubernetes,monitoring,scripts,docs}

# Copy environment file
cp .env.example .env

# Edit configuration
vi .env
```

### 1.3 Start Local Environment

```bash
# Run setup script
chmod +x scripts/setup.sh
./scripts/setup.sh

# Wait for services to be ready (2-3 minutes)
docker-compose ps

# Check service health
curl http://localhost:8080/health  # Airflow
curl http://localhost:5000/health  # MLflow
```

## 2. Data Pipeline Implementation

### 2.1 Data Ingestion

The data ingestion module (`src/data/ingestion.py`) handles:
- Fetching data from various sources (URLs, databases, files)
- Generating synthetic data for testing
- Uploading to S3-compatible storage (MinIO)

**Key Functions:**
```python
# Generate synthetic churn data
ingestor = DataIngestor()
df = ingestor.generate_synthetic_data(n_samples=10000)

# Save and upload
file_path = ingestor.save_data(df, 'churn_data.csv', upload_to_s3=True)
```

### 2.2 Data Validation

The validation module (`src/data/validation.py`) checks:
- Schema compliance
- Missing values
- Duplicate rows
- Data ranges
- Target distribution
- Data quality score

**Implementation:**
```python
validator = DataValidator()
report = validator.validate(df)

if not report.is_valid:
    print(f"Validation failed: {report.validation_errors}")
    # Handle validation failure
```

### 2.3 Data Preprocessing

The preprocessing module (`src/data/preprocessing.py`) performs:
- Missing value imputation
- Feature engineering
- Categorical encoding
- Numerical scaling
- Train/test splitting

**Implementation:**
```python
preprocessor = DataPreprocessor()

# Preprocess data
X, y = preprocessor.preprocess(df, is_training=True)

# Split data
X_train, X_test, y_train, y_test = preprocessor.split_data(X, y)

# Save processed data
paths = preprocessor.save_processed_data(X_train, X_test, y_train, y_test)

# Save preprocessor for inference
preprocessor.save_preprocessor('preprocessor.pkl')
```

### 2.4 Airflow DAG - Data Pipeline

The `data_pipeline` DAG orchestrates the entire data workflow:

```python
# dags/data_pipeline.py

@dag(
    dag_id='data_pipeline',
    schedule_interval='@daily',
    ...
)
def data_pipeline():
    ingest = ingest_data()
    validate = validate_data(ingest)
    preprocess = preprocess_data(ingest, validate)
    commit_dvc = commit_to_dvc(preprocess)
```

**Testing:**
```bash
# Trigger data pipeline
docker-compose exec airflow-webserver airflow dags trigger data_pipeline

# Monitor progress in Airflow UI
open http://localhost:8080
```

## 3. Training Pipeline Implementation

### 3.1 Model Training

The trainer module (`src/training/trainer.py`) supports:
- Multiple model types (LR, RF, GBM, XGBoost)
- Cross-validation
- Hyperparameter tuning
- MLflow experiment tracking

**Implementation:**
```python
trainer = ModelTrainer()

# Train single model
model, run_id = trainer.train_model(
    'xgboost',
    X_train, y_train,
    X_test, y_test
)

# Train all models
results = trainer.train_all_models(X_train, y_train, X_test, y_test)

# Hyperparameter tuning
best_model, run_id = trainer.hyperparameter_tuning(
    'random_forest',
    X_train, y_train,
    X_test, y_test,
    n_iter=20
)
```

### 3.2 Model Evaluation

The evaluator module (`src/training/evaluator.py`) provides:
- Comprehensive metrics calculation
- Performance visualization
- Threshold validation
- Model comparison

**Implementation:**
```python
evaluator = ModelEvaluator()

# Evaluate single model
metrics = evaluator.evaluate_model(model, X_test, y_test)

# Compare multiple models
comparison = evaluator.compare_models(models, X_test, y_test)

# Generate evaluation report
report = evaluator.generate_evaluation_report(model, X_test, y_test)
```

### 3.3 Airflow DAG - Training Pipeline

The `training_pipeline` DAG handles:
- Loading processed data
- Training multiple models
- Selecting best model
- Registering to MLflow
- Validation against thresholds

**Workflow:**
```
Load Data → Train Models → Select Best → Register → Validate → Trigger Deployment
```

**Testing:**
```bash
# Trigger training pipeline
docker-compose exec airflow-webserver airflow dags trigger training_pipeline

# Check MLflow for experiments
open http://localhost:5000
```

## 4. Model Registry Setup

### 4.1 MLflow Configuration

MLflow is configured with:
- PostgreSQL backend for metadata
- MinIO (S3) for artifacts
- Experiment tracking
- Model registry

**Configuration in docker-compose.yml:**
```yaml
mlflow:
  environment:
    MLFLOW_BACKEND_STORE_URI: postgresql://mlflow:mlflow@postgres:5432/mlflow
    MLFLOW_DEFAULT_ARTIFACT_ROOT: s3://mlflow-artifacts
    MLFLOW_S3_ENDPOINT_URL: http://minio:9000
```

### 4.2 Model Registration

The registry module (`src/training/registry.py`) manages:
- Model registration
- Stage transitions (None → Staging → Production)
- Model versioning
- Metadata and tags

**Implementation:**
```python
registry = ModelRegistry()

# Register model from run
version = registry.register_model(
    run_id='abc123',
    tags={'model_type': 'xgboost', 'dataset': 'churn_v1'}
)

# Transition to Staging
registry.transition_model_stage(
    model_name='churn-classifier',
    version=version,
    stage='Staging'
)

# Load model
model = registry.load_model(stage='Production')
```

### 4.3 Model Promotion Workflow

**Manual Promotion:**
```bash
./scripts/promote-model.sh churn-classifier 3
```

**Automated Promotion in Training Pipeline:**
```python
# After validation passes
if validation_passed:
    registry.promote_to_production(
        model_name='churn-classifier',
        version=best_version,
        min_metrics={'test_f1': 0.70, 'test_accuracy': 0.75}
    )
```

## 5. Deployment Pipeline

### 5.1 Kubernetes Client

The K8s client (`src/deployment/kubernetes_client.py`) handles:
- Deployment updates
- Image rolling updates
- Health checks
- Rollback capabilities

**Implementation:**
```python
k8s_client = KubernetesClient()

# Update deployment image
k8s_client.update_deployment_image(
    name='churn-model',
    image='model-server:v3'
)

# Wait for rollout
success = k8s_client.wait_for_deployment_rollout('churn-model', timeout=300)

# Rollback if needed
if not success:
    k8s_client.rollback_deployment('churn-model')
```

### 5.2 Model Deployer

The deployer (`src/deployment/deployer.py`) orchestrates:
- Model retrieval from registry
- Deployment to Kubernetes
- Smoke tests
- Monitoring setup

**Implementation:**
```python
deployer = ModelDeployer()

# Deploy model
success = deployer.deploy_model(
    model_name='churn-classifier',
    version='3',
    stage='Production'
)

# Promote and deploy
deployer.promote_and_deploy(
    model_name='churn-classifier',
    version='3'
)
```

### 5.3 Airflow DAG - Deployment Pipeline

The `deployment_pipeline` DAG performs:
- Fetching model from Staging
- Running integration tests
- Deploying to Production
- Verification and monitoring setup

**Workflow:**
```
Get Staging Model → Integration Tests → Deploy → Verify → Setup Monitoring → Notify
```

**Testing:**
```bash
# Trigger deployment
docker-compose exec airflow-webserver airflow dags trigger deployment_pipeline
```

## 6. Monitoring Setup

### 6.1 Prometheus Configuration

Prometheus scrapes metrics from:
- Airflow (pipeline metrics)
- MLflow (model metrics)
- Kubernetes (pod metrics)
- Custom exporters

**Configuration in `monitoring/prometheus/prometheus.yml`**

### 6.2 Metrics Collection

The metrics collector (`src/monitoring/metrics_collector.py`) tracks:
- Pipeline execution metrics
- Data processing metrics
- Model performance metrics
- Drift detection metrics

**Implementation:**
```python
metrics = MetricsCollector()

# Record pipeline run
metrics.record_pipeline_run(
    pipeline_name='training_pipeline',
    status='success',
    duration=120.5
)

# Record model training
metrics.record_model_training(
    model_type='xgboost',
    duration=45.2,
    metrics={'accuracy': 0.85, 'f1_score': 0.82},
    model_name='churn-classifier',
    model_version='3'
)
```

### 6.3 Drift Detection

The drift detector (`src/monitoring/drift_detector.py`) monitors:
- Feature drift (distribution changes)
- Prediction drift (output changes)
- Uses KS test and JS divergence

**Implementation:**
```python
drift_detector = DriftDetector(threshold=0.1)

# Set reference data
drift_detector.set_reference_data(X_train, y_train)

# Detect drift on new data
drift_results = drift_detector.monitor_drift(X_new, y_pred_new)

if drift_results['overall_drift_detected']:
    print("Drift detected! Retrain model.")
```

### 6.4 Grafana Dashboards

Access Grafana at http://localhost:3000 to view:
- Pipeline execution dashboard
- Model performance dashboard
- Resource utilization
- Alert status

## 7. CI/CD Integration

### 7.1 GitHub Actions Workflow

The CI/CD pipeline (`.github/workflows/mlops-ci-cd.yml`) includes:
- Linting and testing
- Model training
- Performance validation
- Deployment to staging
- Production approval gate

**Workflow Stages:**
```
Lint/Test → Integration Tests → DVC Pipeline → Model Training →
Validation → Deploy Staging → [Manual Approval] → Deploy Production
```

### 7.2 Secrets Configuration

Configure GitHub secrets:
```
MLFLOW_TRACKING_URI
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
```

### 7.3 Testing in CI

```bash
# Run locally
make test

# With coverage
make test-coverage

# In CI (automatic on push)
git push origin main
```

## 8. Production Deployment

### 8.1 Kubernetes Deployment

```bash
# Deploy full stack to Kubernetes
./scripts/deploy.sh

# Or manually
kubectl create namespace ml-serving
kubectl apply -f kubernetes/ -n ml-serving

# Check deployment
kubectl get pods -n ml-serving
kubectl get services -n ml-serving
```

### 8.2 Production Checklist

- [ ] Configure persistent volumes for data
- [ ] Set resource limits and requests
- [ ] Configure horizontal pod autoscaling
- [ ] Set up ingress for external access
- [ ] Configure TLS/SSL certificates
- [ ] Set up backup and disaster recovery
- [ ] Configure log aggregation
- [ ] Set up alerting (PagerDuty, Slack)
- [ ] Document runbooks
- [ ] Perform load testing

### 8.3 Monitoring in Production

```bash
# Check metrics
kubectl port-forward -n ml-serving svc/prometheus 9090:9090
open http://localhost:9090

# View dashboards
kubectl port-forward -n ml-serving svc/grafana 3000:3000
open http://localhost:3000

# Check logs
kubectl logs -f -n ml-serving deployment/airflow-scheduler
```

### 8.4 Model Updates

```bash
# 1. Train new model
docker-compose exec airflow-webserver airflow dags trigger training_pipeline

# 2. Validate in MLflow UI
open http://localhost:5000

# 3. Promote to Staging
./scripts/promote-model.sh churn-classifier 4

# 4. Test in Staging
# Run integration tests

# 5. Promote to Production
# Manual approval in MLflow or via script

# 6. Monitor performance
# Check Grafana dashboards
```

## Troubleshooting

### Common Issues

**Services not starting:**
```bash
docker-compose logs [service-name]
docker-compose restart [service-name]
```

**Airflow DAG not appearing:**
```bash
# Check DAG syntax
docker-compose exec airflow-webserver python dags/data_pipeline.py

# Refresh DAGs
docker-compose restart airflow-scheduler
```

**MLflow connection issues:**
```bash
# Check MLflow health
curl http://localhost:5000/health

# Verify database connection
docker-compose exec postgres psql -U mlflow -d mlflow -c "SELECT 1;"
```

**Kubernetes deployment fails:**
```bash
# Check events
kubectl get events -n ml-serving --sort-by='.lastTimestamp'

# Describe pod
kubectl describe pod <pod-name> -n ml-serving

# Check logs
kubectl logs <pod-name> -n ml-serving
```

## Next Steps

1. **Customize for your use case**
   - Replace synthetic data with real data
   - Adjust models and features
   - Configure thresholds

2. **Scale the pipeline**
   - Add distributed training (Ray, Horovod)
   - Implement feature store
   - Add A/B testing capability

3. **Enhance monitoring**
   - Custom metrics and dashboards
   - Advanced drift detection
   - Anomaly detection

4. **Production hardening**
   - Security hardening
   - Performance optimization
   - Cost optimization

## Resources

- [Airflow Documentation](https://airflow.apache.org/docs/)
- [MLflow Documentation](https://mlflow.org/docs/latest/index.html)
- [DVC Documentation](https://dvc.org/doc)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Prometheus Documentation](https://prometheus.io/docs/)

---

**Completed!** You now have a fully functional MLOps pipeline.
