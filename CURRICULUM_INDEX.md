# Curriculum Index - AI Infrastructure Engineer Solutions

**Complete catalog of all exercises in the mid-level track**

This index provides a comprehensive overview of all 26 exercises, their relationships, difficulty levels, time estimates, and skill alignments.

---

## 📊 Quick Statistics

| Metric | Value |
|--------|-------|
| Total Modules | 10 |
| Total Exercises | 26 |
| Difficulty Range | Intermediate → Advanced |
| Total Learning Time | 200-280 hours |
| Prerequisites | Junior Engineer track |
| Target Role Level | L4-L5 (Mid-Level) |

---

## 📚 Table of Contents

1. [Module Overview](#module-overview)
2. [Complete Exercise Catalog](#complete-exercise-catalog)
3. [Difficulty Progression](#difficulty-progression)
4. [Skill Matrix](#skill-matrix)
5. [Technology Coverage](#technology-coverage)
6. [Learning Paths](#learning-paths)
7. [Time Estimates](#time-estimates)
8. [Prerequisites Map](#prerequisites-map)
9. [Career Alignment](#career-alignment)

---

## Module Overview

### Summary Table

| Module | Code | Exercises | Total Hours | Primary Focus |
|--------|------|-----------|-------------|---------------|
| Foundations | mod-101 | 3 | 18-24 | Advanced tooling & frameworks |
| Cloud Computing | mod-102 | 3 | 24-30 | Multi-cloud & cost optimization |
| Containerization | mod-103 | 3 | 20-26 | Security & optimization |
| Kubernetes | mod-104 | 3 | 26-34 | Advanced orchestration |
| Data Pipelines | mod-105 | 2 | 22-28 | Streaming & workflow |
| MLOps | mod-106 | 3 | 24-32 | Production ML lifecycle |
| GPU Computing | mod-107 | 3 | 28-36 | GPU management & optimization |
| Monitoring | mod-108 | 2 | 20-26 | Observability & ML metrics |
| Infrastructure as Code | mod-109 | 2 | 20-26 | Terraform & Pulumi |
| LLM Infrastructure | mod-110 | 2 | 38-48 | LLM serving & RAG |

---

## Complete Exercise Catalog

### mod-101: Foundations

Advanced tools and frameworks for ML infrastructure development.

#### Exercise 04: Python Environment Manager

**Difficulty**: ⭐⭐⭐ Intermediate
**Time**: 6-8 hours
**Prerequisites**: Python, virtualenv, Docker

**Description**: Build an automated Python environment management tool that handles virtual environments, dependency management, and containerization for ML projects.

**Key Technologies**:
- Python: `subprocess`, `pathlib`, `typing`
- Environment: `pyenv`, `Poetry`, `Conda`
- Containers: Docker, docker-compose

**Learning Objectives**:
- Automate environment setup workflows
- Integrate multiple environment managers
- Build CLI tools with Click
- Handle complex dependency resolution
- Containerize Python environments

**Deliverables**:
- CLI tool for environment management
- Support for venv, Poetry, Conda
- Docker integration
- Configuration file support
- Comprehensive test suite

**Career Skills**: Developer tooling, automation, dependency management

---

#### Exercise 05: ML Framework Benchmark

**Difficulty**: ⭐⭐⭐ Intermediate
**Time**: 6-8 hours
**Prerequisites**: PyTorch, TensorFlow, basic ML

**Description**: Create a comprehensive benchmarking suite to compare ML frameworks (PyTorch, TensorFlow, JAX) across different model architectures and hardware configurations.

**Key Technologies**:
- Frameworks: PyTorch, TensorFlow, JAX
- Benchmarking: `timeit`, `memory_profiler`
- Visualization: Plotly, Matplotlib
- Models: CNN, Transformer, LSTM

**Learning Objectives**:
- Design fair benchmarking methodologies
- Measure training and inference performance
- Profile memory usage
- Analyze GPU utilization
- Generate comparative reports

**Deliverables**:
- Benchmark suite for multiple frameworks
- Performance metrics collection
- Memory profiling
- Interactive visualizations
- Automated report generation

**Career Skills**: Performance optimization, framework evaluation, technical analysis

---

#### Exercise 06: FastAPI ML Template Generator

**Difficulty**: ⭐⭐⭐ Intermediate
**Time**: 6-8 hours
**Prerequisites**: FastAPI, Jinja2, project structure

**Description**: Build a code generation tool that creates standardized FastAPI-based ML serving projects with best practices, monitoring, and deployment configurations.

**Key Technologies**:
- Framework: FastAPI
- Templating: Jinja2
- Project: Cookiecutter patterns
- Standards: OpenAPI, Pydantic

**Learning Objectives**:
- Implement code generation patterns
- Design reusable project templates
- Apply API best practices
- Standardize ML serving patterns
- Create scaffolding tools

**Deliverables**:
- Template generator CLI
- Multiple project templates
- Configuration customization
- Generated projects are deployable
- Documentation generator

**Career Skills**: Code generation, standardization, API design, tooling

---

### mod-102: Cloud Computing

Multi-cloud infrastructure management and optimization.

#### Exercise 01: Multi-Cloud Cost Analyzer

**Difficulty**: ⭐⭐⭐⭐ Intermediate-Advanced
**Time**: 8-10 hours
**Prerequisites**: AWS/GCP/Azure APIs, cost concepts

**Description**: Build a comprehensive cost analysis tool that aggregates, analyzes, and visualizes spending across AWS, GCP, and Azure, with optimization recommendations.

**Key Technologies**:
- Cloud APIs: Boto3, Google Cloud, Azure SDK
- Analysis: Pandas, NumPy
- Visualization: Plotly, Dash
- Reporting: Jinja2

**Learning Objectives**:
- Integrate multiple cloud provider APIs
- Aggregate cost data across clouds
- Identify cost optimization opportunities
- Build interactive dashboards
- Generate automated reports

**Deliverables**:
- Multi-cloud cost aggregation
- Cost anomaly detection
- Optimization recommendations
- Interactive dashboards
- Scheduled reporting

**Career Skills**: Cloud cost management, FinOps, multi-cloud expertise, data analysis

---

#### Exercise 02: Cloud ML Infrastructure

**Difficulty**: ⭐⭐⭐⭐ Intermediate-Advanced
**Time**: 8-10 hours
**Prerequisites**: Terraform, cloud platforms

**Description**: Deploy a complete ML infrastructure stack to multiple cloud providers using Terraform, including compute, storage, networking, and ML-specific services.

**Key Technologies**:
- IaC: Terraform
- Clouds: AWS (SageMaker), GCP (Vertex AI), Azure (Azure ML)
- Networking: VPCs, subnets, security groups
- Storage: S3, GCS, Blob Storage

**Learning Objectives**:
- Write cloud-agnostic Terraform modules
- Deploy to multiple cloud providers
- Configure ML-specific services
- Implement security best practices
- Manage infrastructure state

**Deliverables**:
- Terraform modules for each cloud
- ML infrastructure deployment
- Network configuration
- Security setup (IAM, service accounts)
- Documentation and runbooks

**Career Skills**: Multi-cloud deployment, Terraform expertise, ML infrastructure, security

---

#### Exercise 03: Disaster Recovery

**Difficulty**: ⭐⭐⭐⭐ Advanced
**Time**: 8-12 hours
**Prerequisites**: Cloud platforms, databases, backup strategies

**Description**: Implement a comprehensive disaster recovery solution for ML infrastructure, including backup automation, failover mechanisms, and recovery testing.

**Key Technologies**:
- Backup: Cloud-native backup services
- DR: Cross-region replication, failover
- Testing: Chaos engineering, DR drills
- Monitoring: Recovery time objectives (RTO/RPO)

**Learning Objectives**:
- Design DR strategies for ML systems
- Implement automated backups
- Configure cross-region replication
- Test recovery procedures
- Measure and optimize RTO/RPO

**Deliverables**:
- Automated backup system
- Failover automation
- DR testing framework
- Recovery playbooks
- RTO/RPO monitoring

**Career Skills**: Disaster recovery, business continuity, reliability engineering

---

### mod-103: Containerization

Advanced container security, optimization, and registry management.

#### Exercise 04: Container Security

**Difficulty**: ⭐⭐⭐⭐ Intermediate-Advanced
**Time**: 7-9 hours
**Prerequisites**: Docker, security concepts

**Description**: Build a comprehensive container security scanning and compliance tool that checks images for vulnerabilities, misconfigurations, and generates SBOMs.

**Key Technologies**:
- Scanning: Trivy, Grype
- Compliance: CIS Docker Benchmark
- SBOM: Syft
- Reporting: JSON, HTML reports

**Learning Objectives**:
- Implement vulnerability scanning
- Generate Software Bill of Materials
- Check CIS compliance
- Detect secrets in images
- Create security scorecards

**Deliverables**:
- Automated security scanner
- Multi-tool integration
- SBOM generation
- Compliance reporting
- CI/CD integration

**Career Skills**: Container security, compliance, supply chain security, DevSecOps

---

#### Exercise 05: Image Optimizer

**Difficulty**: ⭐⭐⭐ Intermediate
**Time**: 6-8 hours
**Prerequisites**: Docker, multi-stage builds

**Description**: Create a tool that analyzes and optimizes Docker images for size, layer count, and build time, with automated recommendations and refactoring.

**Key Technologies**:
- Docker: Multi-stage builds, BuildKit
- Analysis: Dive, docker-slim
- Optimization: Layer caching, .dockerignore
- Comparison: Size and performance metrics

**Learning Objectives**:
- Analyze Docker image layers
- Optimize image size
- Reduce build times
- Implement build caching
- Generate optimization reports

**Deliverables**:
- Image analysis tool
- Optimization recommendations
- Automated refactoring (optional)
- Before/after comparisons
- Best practices checker

**Career Skills**: Docker optimization, build engineering, efficiency

---

#### Exercise 06: Registry Manager

**Difficulty**: ⭐⭐⭐⭐ Intermediate-Advanced
**Time**: 7-9 hours
**Prerequisites**: Container registries, image signing

**Description**: Build a private container registry management system with image signing, scanning, retention policies, and replication across multiple registries.

**Key Technologies**:
- Registries: Harbor, ECR, GCR, ACR
- Signing: Cosign, Notary
- Policies: Retention, garbage collection
- Replication: Cross-registry sync

**Learning Objectives**:
- Deploy and manage Harbor registry
- Implement image signing and verification
- Configure retention policies
- Set up cross-registry replication
- Automate registry operations

**Deliverables**:
- Registry deployment (Harbor)
- Image signing pipeline
- Retention policy automation
- Replication configuration
- Registry monitoring

**Career Skills**: Registry management, image signing, supply chain security

---

### mod-104: Kubernetes

Advanced Kubernetes cluster management and patterns.

#### Exercise 04: K8s Cluster Autoscaler

**Difficulty**: ⭐⭐⭐⭐ Advanced
**Time**: 9-11 hours
**Prerequisites**: Kubernetes, HPA, metrics

**Description**: Implement intelligent autoscaling for Kubernetes clusters using HPA, VPA, and Cluster Autoscaler, with custom metrics and cost optimization.

**Key Technologies**:
- Autoscaling: HPA, VPA, Cluster Autoscaler
- Metrics: Prometheus, custom metrics
- Optimization: Cost-aware scheduling
- Monitoring: Grafana dashboards

**Learning Objectives**:
- Configure Horizontal Pod Autoscaler
- Implement Vertical Pod Autoscaler
- Deploy Cluster Autoscaler
- Use custom metrics for scaling
- Optimize for cost and performance

**Deliverables**:
- Complete autoscaling setup
- Custom metrics integration
- Cost optimization policies
- Monitoring dashboards
- Testing and validation

**Career Skills**: Kubernetes autoscaling, resource optimization, cost management

---

#### Exercise 05: Service Mesh Observability

**Difficulty**: ⭐⭐⭐⭐ Advanced
**Time**: 8-11 hours
**Prerequisites**: Kubernetes, service mesh concepts

**Description**: Deploy and configure a service mesh (Istio or Linkerd) for microservices observability, including distributed tracing, traffic management, and security.

**Key Technologies**:
- Service Mesh: Istio or Linkerd
- Tracing: Jaeger, Zipkin
- Monitoring: Prometheus, Grafana
- Traffic: Canary, blue-green

**Learning Objectives**:
- Deploy service mesh to Kubernetes
- Configure distributed tracing
- Implement traffic management
- Set up mutual TLS
- Monitor service mesh metrics

**Deliverables**:
- Service mesh deployment
- Distributed tracing setup
- Traffic management policies
- mTLS configuration
- Observability dashboards

**Career Skills**: Service mesh, distributed tracing, microservices, advanced networking

---

#### Exercise 06: K8s Operator Framework

**Difficulty**: ⭐⭐⭐⭐⭐ Advanced
**Time**: 9-12 hours
**Prerequisites**: Kubernetes, Python, CRDs

**Description**: Build custom Kubernetes operators using Kopf framework to automate ML model deployment, scaling, and lifecycle management.

**Key Technologies**:
- Framework: Kopf (Python)
- K8s: Custom Resource Definitions
- Controllers: Reconciliation loops
- API: Kubernetes Python client

**Learning Objectives**:
- Design custom resource definitions
- Implement operator reconciliation logic
- Handle resource lifecycle events
- Manage dependent resources
- Test operators thoroughly

**Deliverables**:
- Custom operator for ML models
- CRD definitions
- Reconciliation logic
- Event handling
- Operator testing

**Career Skills**: Kubernetes operators, CRDs, automation, platform engineering

---

### mod-105: Data Pipelines

Real-time streaming and workflow orchestration.

#### Exercise 03: Streaming Pipeline Kafka

**Difficulty**: ⭐⭐⭐⭐ Advanced
**Time**: 11-14 hours
**Prerequisites**: Kafka, streaming concepts, Spark

**Description**: Build a real-time streaming data pipeline using Kafka for ingestion, Spark for processing, and various sinks for ML model training and inference.

**Key Technologies**:
- Streaming: Apache Kafka
- Processing: PySpark, Flink (optional)
- Storage: S3, databases
- Monitoring: Kafka metrics

**Learning Objectives**:
- Design streaming architectures
- Implement Kafka producers/consumers
- Process streams with Spark
- Handle backpressure and failures
- Monitor pipeline health

**Deliverables**:
- End-to-end streaming pipeline
- Data quality checks
- Exactly-once semantics
- Failure recovery
- Monitoring and alerting

**Career Skills**: Stream processing, Kafka, real-time systems, data engineering

---

#### Exercise 04: Workflow Orchestration Airflow

**Difficulty**: ⭐⭐⭐⭐ Intermediate-Advanced
**Time**: 11-14 hours
**Prerequisites**: Airflow, DAGs, Python

**Description**: Create complex ML workflow orchestration using Apache Airflow, including data pipelines, training jobs, model deployment, and monitoring.

**Key Technologies**:
- Orchestration: Apache Airflow
- Tasks: PythonOperator, KubernetesPodOperator
- Scheduling: Cron, sensors
- Monitoring: Airflow UI, alerts

**Learning Objectives**:
- Design DAG structures for ML workflows
- Implement task dependencies
- Use dynamic DAG generation
- Configure sensors and triggers
- Monitor workflow execution

**Deliverables**:
- Complete ML workflow DAGs
- Data validation tasks
- Training and deployment tasks
- Monitoring and alerting
- SLA tracking

**Career Skills**: Workflow orchestration, Airflow, MLOps, data pipeline engineering

---

### mod-106: MLOps

Production ML lifecycle management.

#### Exercise 04: Experiment Tracking MLflow

**Difficulty**: ⭐⭐⭐⭐ Intermediate-Advanced
**Time**: 8-10 hours
**Prerequisites**: MLflow, ML frameworks, PostgreSQL

**Description**: Set up a production MLflow deployment for experiment tracking, model registry, and artifact storage, integrated with training pipelines.

**Key Technologies**:
- MLflow: Tracking, Registry, Projects
- Storage: S3, PostgreSQL
- Integration: PyTorch, TensorFlow
- Deployment: Docker, Kubernetes

**Learning Objectives**:
- Deploy MLflow server infrastructure
- Track experiments programmatically
- Manage model lifecycle in registry
- Integrate with training code
- Automate model promotion

**Deliverables**:
- MLflow server deployment
- Experiment tracking integration
- Model registry setup
- Artifact storage (S3)
- Model promotion workflows

**Career Skills**: Experiment tracking, MLOps, model management, ML infrastructure

---

#### Exercise 05: Model Monitoring Drift

**Difficulty**: ⭐⭐⭐⭐ Advanced
**Time**: 8-11 hours
**Prerequisites**: ML monitoring, statistics, Evidently

**Description**: Implement comprehensive model monitoring using Evidently to detect data drift, model drift, and performance degradation in production.

**Key Technologies**:
- Monitoring: Evidently
- Metrics: Custom ML metrics
- Alerting: Prometheus, alertmanager
- Dashboards: Grafana

**Learning Objectives**:
- Implement drift detection algorithms
- Monitor model performance metrics
- Set up automated alerting
- Create monitoring dashboards
- Trigger retraining on drift

**Deliverables**:
- Drift detection system
- Performance monitoring
- Automated alerts
- Grafana dashboards
- Retraining triggers

**Career Skills**: ML monitoring, drift detection, production ML, data science

---

#### Exercise 06: CI/CD ML Pipelines

**Difficulty**: ⭐⭐⭐⭐ Advanced
**Time**: 8-11 hours
**Prerequisites**: GitHub Actions, DVC, testing

**Description**: Build automated CI/CD pipelines for ML projects including data versioning, model testing, deployment, and rollback capabilities.

**Key Technologies**:
- CI/CD: GitHub Actions, GitLab CI
- Versioning: DVC, Git LFS
- Testing: pytest, Great Expectations
- Deployment: Kubernetes, Docker

**Learning Objectives**:
- Design ML-specific CI/CD workflows
- Version datasets with DVC
- Implement model testing
- Automate deployment pipelines
- Handle rollbacks and monitoring

**Deliverables**:
- Complete CI/CD workflows
- Data versioning setup
- Automated testing suite
- Deployment automation
- Rollback mechanisms

**Career Skills**: CI/CD, MLOps, automation, DevOps for ML

---

### mod-107: GPU Computing

GPU cluster management and optimization.

#### Exercise 04: GPU Cluster Management

**Difficulty**: ⭐⭐⭐⭐⭐ Advanced
**Time**: 9-12 hours
**Prerequisites**: Kubernetes, NVIDIA GPUs, multi-tenancy

**Description**: Deploy and manage a multi-tenant GPU cluster using NVIDIA GPU Operator, with resource quotas, monitoring, and cost tracking.

**Key Technologies**:
- GPUs: NVIDIA GPU Operator
- Kubernetes: Device plugins, taints/tolerations
- Monitoring: dcgm-exporter, Prometheus
- Scheduling: Node selectors, affinity

**Learning Objectives**:
- Deploy NVIDIA GPU Operator
- Configure GPU device plugins
- Implement multi-tenancy with quotas
- Monitor GPU utilization
- Track GPU costs per team

**Deliverables**:
- GPU cluster deployment
- Multi-tenancy configuration
- Resource quotas and limits
- GPU monitoring dashboards
- Cost allocation system

**Career Skills**: GPU infrastructure, Kubernetes, multi-tenancy, cost management

---

#### Exercise 05: GPU Performance Optimization

**Difficulty**: ⭐⭐⭐⭐⭐ Advanced
**Time**: 9-12 hours
**Prerequisites**: CUDA, PyTorch, profiling

**Description**: Optimize GPU utilization for ML workloads through profiling, memory optimization, and kernel tuning, with comprehensive benchmarking.

**Key Technologies**:
- Profiling: NVIDIA Nsight, PyTorch Profiler
- Optimization: Mixed precision, gradient accumulation
- Monitoring: GPU metrics, memory usage
- Frameworks: PyTorch, TensorFlow

**Learning Objectives**:
- Profile GPU workloads
- Optimize memory usage
- Implement mixed-precision training
- Tune batch sizes and workers
- Benchmark optimizations

**Deliverables**:
- Profiling framework
- Optimization recommendations
- Memory optimization techniques
- Performance benchmarks
- Best practices documentation

**Career Skills**: GPU optimization, performance tuning, CUDA, ML acceleration

---

#### Exercise 06: Distributed GPU Training

**Difficulty**: ⭐⭐⭐⭐⭐ Advanced
**Time**: 10-12 hours
**Prerequisites**: Distributed systems, PyTorch DDP, Ray

**Description**: Implement distributed training across multiple GPUs and nodes using Ray, Horovod, and PyTorch DistributedDataParallel.

**Key Technologies**:
- Distributed: Ray, Horovod
- PyTorch: DistributedDataParallel (DDP)
- Communication: NCCL, Gloo
- Orchestration: Kubernetes

**Learning Objectives**:
- Implement data parallelism
- Configure distributed training
- Optimize communication overhead
- Handle fault tolerance
- Scale training across nodes

**Deliverables**:
- Distributed training setup
- Multi-node configuration
- Fault tolerance mechanisms
- Performance optimization
- Scaling benchmarks

**Career Skills**: Distributed training, Ray, PyTorch DDP, large-scale ML

---

### mod-108: Monitoring & Observability

Production observability for ML systems.

#### Exercise 01: Observability Stack

**Difficulty**: ⭐⭐⭐⭐ Advanced
**Time**: 10-13 hours
**Prerequisites**: Prometheus, Grafana, Kubernetes

**Description**: Deploy a comprehensive observability stack with Prometheus, Grafana, Jaeger, and ELK for metrics, tracing, and logging of ML systems.

**Key Technologies**:
- Metrics: Prometheus, Grafana
- Tracing: Jaeger, OpenTelemetry
- Logging: Elasticsearch, Fluentd, Kibana
- Alerting: Alertmanager

**Learning Objectives**:
- Deploy full observability stack
- Configure metric collection
- Set up distributed tracing
- Implement centralized logging
- Create comprehensive dashboards

**Deliverables**:
- Complete observability stack
- Custom metrics collection
- Distributed tracing setup
- Centralized logging
- Alert rules and dashboards

**Career Skills**: Observability, SRE, monitoring, distributed systems

---

#### Exercise 02: ML Model Monitoring

**Difficulty**: ⭐⭐⭐⭐ Advanced
**Time**: 10-13 hours
**Prerequisites**: Prometheus, ML serving, statistics

**Description**: Implement ML-specific monitoring including prediction latency, model accuracy, feature distributions, and business metrics.

**Key Technologies**:
- Monitoring: Prometheus, Grafana
- ML Metrics: Custom exporters
- Analysis: Statistical tests
- Alerting: Smart thresholds

**Learning Objectives**:
- Define ML-specific metrics
- Implement custom exporters
- Create ML dashboards
- Set up intelligent alerting
- Monitor model health

**Deliverables**:
- ML metrics collection
- Custom Prometheus exporters
- Grafana dashboards for ML
- Alerting rules
- Model health scorecards

**Career Skills**: ML monitoring, metrics design, observability, SRE for ML

---

### mod-109: Infrastructure as Code

Advanced IaC with Terraform and Pulumi.

#### Exercise 01: Terraform ML Infrastructure

**Difficulty**: ⭐⭐⭐⭐ Intermediate-Advanced
**Time**: 10-13 hours
**Prerequisites**: Terraform, cloud platforms, modules

**Description**: Build reusable Terraform modules for deploying ML infrastructure across AWS, GCP, and Azure, with state management and testing.

**Key Technologies**:
- IaC: Terraform 1.5+
- Clouds: AWS, GCP, Azure
- Testing: Terratest, tflint
- State: Remote backends, locking

**Learning Objectives**:
- Design reusable Terraform modules
- Implement multi-cloud deployments
- Manage state securely
- Test infrastructure code
- Version and publish modules

**Deliverables**:
- ML infrastructure modules
- Multi-cloud deployments
- State management setup
- Module testing
- Documentation and examples

**Career Skills**: Terraform, IaC, multi-cloud, DevOps

---

#### Exercise 02: Pulumi Multi-Cloud ML

**Difficulty**: ⭐⭐⭐⭐ Advanced
**Time**: 10-13 hours
**Prerequisites**: Pulumi, Python, cloud platforms

**Description**: Implement cloud-agnostic ML infrastructure using Pulumi with Python, including component resources and automation API.

**Key Technologies**:
- IaC: Pulumi with Python
- Clouds: AWS, GCP, Azure
- Automation: Pulumi Automation API
- Testing: Python unit tests

**Learning Objectives**:
- Write IaC in Python with Pulumi
- Create component resources
- Use Pulumi Automation API
- Test infrastructure code
- Implement GitOps workflows

**Deliverables**:
- Pulumi programs for ML infra
- Component resources
- Automation API usage
- Infrastructure testing
- GitOps integration

**Career Skills**: Pulumi, programmatic IaC, Python, multi-cloud

---

### mod-110: LLM Infrastructure

Production LLM serving and RAG systems.

#### Exercise 01: Production LLM Serving

**Difficulty**: ⭐⭐⭐⭐⭐ Advanced
**Time**: 19-24 hours
**Prerequisites**: LLMs, vLLM, GPU optimization

**Description**: Deploy optimized LLM serving infrastructure using vLLM or TensorRT-LLM with GPU optimization, batching, and production monitoring.

**Key Technologies**:
- Serving: vLLM, TensorRT-LLM
- API: FastAPI, streaming
- GPUs: NVIDIA A100/H100 optimization
- Monitoring: Custom LLM metrics

**Learning Objectives**:
- Deploy optimized LLM serving
- Implement dynamic batching
- Configure GPU settings
- Optimize inference latency
- Monitor LLM performance and costs

**Deliverables**:
- Production LLM serving API
- vLLM/TensorRT deployment
- GPU optimization
- Streaming responses
- Comprehensive monitoring

**Career Skills**: LLM serving, GPU optimization, GenAI infrastructure

---

#### Exercise 02: Production RAG System

**Difficulty**: ⭐⭐⭐⭐⭐ Advanced
**Time**: 19-24 hours
**Prerequisites**: LangChain, vector DBs, document processing

**Description**: Build a production RAG (Retrieval-Augmented Generation) system with document ingestion, vector storage, and optimized retrieval.

**Key Technologies**:
- RAG: LangChain
- Vector DB: ChromaDB, Pinecone
- Processing: Unstructured, PyPDF
- LLM: OpenAI API or self-hosted

**Learning Objectives**:
- Design RAG architectures
- Implement document ingestion
- Optimize vector search
- Tune retrieval parameters
- Monitor RAG quality

**Deliverables**:
- Complete RAG system
- Document processing pipeline
- Vector database setup
- Retrieval optimization
- Quality monitoring

**Career Skills**: RAG systems, vector databases, LLM applications, GenAI

---

## Difficulty Progression

### Difficulty Levels Explained

- ⭐⭐⭐ **Intermediate**: Requires solid foundation, introduces new concepts
- ⭐⭐⭐⭐ **Intermediate-Advanced**: Complex integrations, production considerations
- ⭐⭐⭐⭐⭐ **Advanced**: Cutting-edge technologies, complex architectures

### Recommended Learning Order

```
Level 1 (Intermediate):
├── mod-101: All exercises (3)
├── mod-103: Exercise 05 (1)
└── Total: 4 exercises

Level 2 (Intermediate-Advanced):
├── mod-102: Exercises 01-02 (2)
├── mod-103: Exercises 04, 06 (2)
├── mod-105: Exercise 04 (1)
├── mod-106: Exercises 04, 06 (2)
└── Total: 7 exercises

Level 3 (Advanced):
├── mod-102: Exercise 03 (1)
├── mod-104: All exercises (3)
├── mod-105: Exercise 03 (1)
├── mod-106: Exercise 05 (1)
├── mod-107: All exercises (3)
├── mod-108: All exercises (2)
├── mod-109: All exercises (2)
├── mod-110: All exercises (2)
└── Total: 15 exercises
```

---

## Skill Matrix

### Technical Skills by Exercise

| Exercise | Cloud | K8s | Docker | ML | GPU | IaC | Monitoring | Data Eng |
|----------|-------|-----|--------|----|----|-----|------------|----------|
| 101-04 | ○ | ○ | ● | ○ | ○ | ○ | ○ | ○ |
| 101-05 | ○ | ○ | ○ | ● | ● | ○ | ○ | ○ |
| 101-06 | ○ | ○ | ○ | ● | ○ | ○ | ○ | ○ |
| 102-01 | ● | ○ | ○ | ○ | ○ | ○ | ○ | ○ |
| 102-02 | ● | ○ | ○ | ● | ○ | ● | ○ | ○ |
| 102-03 | ● | ○ | ○ | ○ | ○ | ○ | ● | ● |
| 103-04 | ○ | ○ | ● | ○ | ○ | ○ | ○ | ○ |
| 103-05 | ○ | ○ | ● | ○ | ○ | ○ | ○ | ○ |
| 103-06 | ● | ● | ● | ○ | ○ | ○ | ○ | ○ |
| 104-04 | ● | ● | ○ | ○ | ○ | ○ | ● | ○ |
| 104-05 | ○ | ● | ○ | ○ | ○ | ○ | ● | ○ |
| 104-06 | ○ | ● | ○ | ● | ○ | ○ | ○ | ○ |
| 105-03 | ○ | ● | ● | ○ | ○ | ○ | ● | ● |
| 105-04 | ○ | ● | ○ | ● | ○ | ○ | ● | ● |
| 106-04 | ● | ● | ● | ● | ○ | ○ | ○ | ○ |
| 106-05 | ○ | ○ | ○ | ● | ○ | ○ | ● | ○ |
| 106-06 | ○ | ● | ● | ● | ○ | ○ | ○ | ○ |
| 107-04 | ● | ● | ○ | ○ | ● | ○ | ● | ○ |
| 107-05 | ○ | ○ | ○ | ● | ● | ○ | ● | ○ |
| 107-06 | ○ | ● | ○ | ● | ● | ○ | ○ | ○ |
| 108-01 | ○ | ● | ● | ○ | ○ | ○ | ● | ○ |
| 108-02 | ○ | ● | ○ | ● | ○ | ○ | ● | ○ |
| 109-01 | ● | ● | ○ | ● | ● | ● | ○ | ○ |
| 109-02 | ● | ● | ○ | ● | ○ | ● | ○ | ○ |
| 110-01 | ● | ● | ● | ● | ● | ○ | ● | ○ |
| 110-02 | ● | ● | ○ | ● | ● | ○ | ● | ● |

**Legend**: ● Primary skill | ○ Secondary skill

---

## Technology Coverage

### By Category

**Cloud Platforms**:
- AWS: 8 exercises
- GCP: 8 exercises
- Azure: 8 exercises
- Multi-cloud: 6 exercises

**Container & Orchestration**:
- Docker: 12 exercises
- Kubernetes: 16 exercises
- Helm: 8 exercises
- Service Mesh: 1 exercise

**ML Frameworks**:
- PyTorch: 12 exercises
- TensorFlow: 4 exercises
- JAX: 1 exercise
- HuggingFace: 4 exercises

**MLOps Tools**:
- MLflow: 2 exercises
- Airflow: 1 exercise
- DVC: 1 exercise
- Evidently: 1 exercise

**Data & Streaming**:
- Kafka: 1 exercise
- Spark: 1 exercise
- PostgreSQL: 4 exercises
- Redis: 2 exercises

**GPU & Acceleration**:
- CUDA: 3 exercises
- NVIDIA Tools: 3 exercises
- Distributed Training: 1 exercise

**Monitoring**:
- Prometheus: 8 exercises
- Grafana: 8 exercises
- Jaeger: 1 exercise
- ELK Stack: 1 exercise

**Infrastructure as Code**:
- Terraform: 2 exercises
- Pulumi: 1 exercise

**LLM Infrastructure**:
- vLLM: 1 exercise
- LangChain: 1 exercise
- Vector DBs: 1 exercise

---

## Learning Paths

### Path 1: Complete Mastery (All 26 exercises)
**Order**: Sequential (mod-101 → mod-110)
**Duration**: 200-280 hours
**Best for**: Comprehensive skill building

### Path 2: Fast Track MLOps (12 exercises)
**Order**: 101{4,5,6} → 106{4,5,6} → 108{2} → 102{2} → 107{4,5} → 109{1}
**Duration**: 110-150 hours
**Best for**: MLOps specialists

### Path 3: Platform Engineering (13 exercises)
**Order**: 104{4,5,6} → 103{4,5,6} → 109{1,2} → 108{1,2} → 102{1,2} → 107{4}
**Duration**: 130-180 hours
**Best for**: Platform engineers

### Path 4: LLM Specialist (12 exercises)
**Order**: 110{1,2} → 107{4,5,6} → 108{2} → 104{4,5} → 102{2} → 109{1}
**Duration**: 140-190 hours
**Best for**: GenAI infrastructure

---

## Time Estimates

### By Time Commitment

**Full-Time Study (40 hrs/week)**:
- Complete Path: 10-14 weeks
- Fast Track: 6-8 weeks
- Platform: 7-9 weeks
- LLM: 7-10 weeks

**Part-Time Study (20 hrs/week)**:
- Complete Path: 20-28 weeks
- Fast Track: 11-15 weeks
- Platform: 13-18 weeks
- LLM: 14-19 weeks

**Casual Study (10 hrs/week)**:
- Complete Path: 40-56 weeks
- Fast Track: 22-30 weeks
- Platform: 26-36 weeks
- LLM: 28-38 weeks

---

## Prerequisites Map

### Module Dependencies

```
mod-101 (Foundations)
    └──> mod-102 (Cloud)
            └──> mod-103 (Containers)
                    └──> mod-104 (Kubernetes)
                            ├──> mod-105 (Data Pipelines)
                            ├──> mod-106 (MLOps)
                            ├──> mod-107 (GPU)
                            │       └──> mod-110 (LLM)
                            ├──> mod-108 (Monitoring)
                            └──> mod-109 (IaC)
```

### Skills Prerequisites

**Before Starting**:
- ✅ Junior Engineer track completed
- ✅ Python OOP and async
- ✅ Docker fundamentals
- ✅ Basic Kubernetes
- ✅ Git proficiency
- ✅ Linux command line
- ✅ Basic ML concepts

**Developed During**:
- Advanced Kubernetes patterns
- Multi-cloud expertise
- GPU infrastructure
- Production MLOps
- LLM deployment
- Advanced monitoring
- Infrastructure as Code mastery

---

## Career Alignment

### By Target Role

**ML Infrastructure Engineer (L4-L5)**:
- Priority: Complete Path or Fast Track MLOps
- Key modules: 106, 107, 108, 109, 110
- Certifications: AWS ML, GCP ML Engineer

**Platform Engineer**:
- Priority: Platform Engineering Path
- Key modules: 103, 104, 108, 109
- Certifications: CKA, CKAD, Terraform

**MLOps Engineer**:
- Priority: Fast Track MLOps Path
- Key modules: 105, 106, 108
- Certifications: AWS ML, MLOps practices

**SRE - ML Systems**:
- Priority: Complete Path with focus on 108
- Key modules: 104, 107, 108, 109
- Certifications: CKA, Prometheus

**LLM Infrastructure Specialist**:
- Priority: LLM Specialist Path
- Key modules: 107, 110
- Certifications: NVIDIA DLI, cloud certifications

---

## Appendix: Quick Reference

### Exercise Code Reference

| Code | Exercise Name |
|------|--------------|
| 101-04 | Python Environment Manager |
| 101-05 | ML Framework Benchmark |
| 101-06 | FastAPI ML Template Generator |
| 102-01 | Multi-Cloud Cost Analyzer |
| 102-02 | Cloud ML Infrastructure |
| 102-03 | Disaster Recovery |
| 103-04 | Container Security |
| 103-05 | Image Optimizer |
| 103-06 | Registry Manager |
| 104-04 | K8s Cluster Autoscaler |
| 104-05 | Service Mesh Observability |
| 104-06 | K8s Operator Framework |
| 105-03 | Streaming Pipeline Kafka |
| 105-04 | Workflow Orchestration Airflow |
| 106-04 | Experiment Tracking MLflow |
| 106-05 | Model Monitoring Drift |
| 106-06 | CI/CD ML Pipelines |
| 107-04 | GPU Cluster Management |
| 107-05 | GPU Performance Optimization |
| 107-06 | Distributed GPU Training |
| 108-01 | Observability Stack |
| 108-02 | ML Model Monitoring |
| 109-01 | Terraform ML Infrastructure |
| 109-02 | Pulumi Multi-Cloud ML |
| 110-01 | Production LLM Serving |
| 110-02 | Production RAG System |

---

**Use this index to navigate the curriculum and plan your learning journey!** 📚

*Last Updated: October 25, 2025*
*Version: 1.0*
