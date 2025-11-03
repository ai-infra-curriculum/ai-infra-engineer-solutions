# Exercise Solutions Mapping

> **Complete cross-reference between learning repository exercises and solution implementations**

This document provides a comprehensive mapping between exercises in the [ai-infra-engineer-learning](../../../learning/ai-infra-engineer-learning/) repository and their corresponding solutions in this repository.

## Overview

- **Total Modules**: 10 (mod-101 through mod-110)
- **Total Exercise Solutions**: 26 exercises
- **Total Solution Time**: 563-717 hours
- **Coverage**: 100% for advanced exercises (Modules 104-110)

## Legend

- ✅ **Solution exists** - Complete implementation available
- ⚠️ **Partial coverage** - Some exercises have solutions, others don't
- ❌ **No solution** - Solution not yet implemented
- 📝 **Simple exercise** - Markdown-only exercise (may not need full solution)

---

## Module 101: Foundations

**Learning Path**: `lessons/mod-101-foundations/exercises/`
**Solutions Path**: `modules/mod-101-foundations/`

### Foundational Exercises (Lessons-aligned)

| Exercise | Learning Repository | Solution Status | Estimated Time |
|----------|---------------------|-----------------|----------------|
| Exercise 01 | `exercise-01-environment.md` | ❌ No solution | 2-3 hours |
| Exercise 02 | `exercise-02-docker.md` | ❌ No solution | 2-3 hours |
| Exercise 03 | `exercise-03-kubernetes.md` | ❌ No solution | 3-4 hours |
| Exercise 07 | `exercise-07-api.md` | ❌ No solution | 4-5 hours |

**Note**: These are foundational markdown exercises with inline instructions. Full solutions may not be necessary as they guide learners through setup steps.

### Advanced Projects

| Exercise | Learning Repository | Solution Status | Estimated Time |
|----------|---------------------|-----------------|----------------|
| Exercise 04 | `exercise-04-python-env-manager/` | ✅ `exercise-04-python-env-manager/` | 30-38 hours |
| Exercise 05 | `exercise-05-ml-framework-benchmark/` | ✅ `exercise-05-ml-framework-benchmark/` | 31-40 hours |
| Exercise 06 | `exercise-06-fastapi-ml-template-generator/` | ✅ `exercise-06-fastapi-ml-template-generator/` | 27-34 hours |

**Coverage**: 3/7 exercises (43%)
**Advanced Coverage**: 3/3 advanced projects (100%)

---

## Module 102: Cloud Computing

**Learning Path**: `lessons/mod-102-cloud-computing/exercises/`
**Solutions Path**: `modules/mod-102-cloud-computing/`

| Exercise | Learning Repository | Solution Status | Estimated Time |
|----------|---------------------|-----------------|----------------|
| Exercise 01 | TBD | ✅ `exercise-01-multi-cloud-cost-analyzer/` | TBD |
| Exercise 02 | TBD | ✅ `exercise-02-cloud-ml-infrastructure/` | TBD |
| Exercise 03 | TBD | ✅ `exercise-03-disaster-recovery/` | TBD |

**Coverage**: 3/3 exercises (100%)
**Note**: Module 102 not in current remediation scope

---

## Module 103: Containerization

**Learning Path**: `lessons/mod-103-containerization/exercises/`
**Solutions Path**: `modules/mod-103-containerization/`

| Exercise | Learning Repository | Solution Status | Estimated Time |
|----------|---------------------|-----------------|----------------|
| Exercise 04 | TBD | ✅ `exercise-04-container-security/` | TBD |
| Exercise 05 | TBD | ✅ `exercise-05-image-optimizer/` | TBD |
| Exercise 06 | TBD | ✅ `exercise-06-registry-manager/` | TBD |

**Coverage**: 3/3 exercises (100%)
**Note**: Module 103 not in current remediation scope

---

## Module 104: Kubernetes

**Learning Path**: `lessons/mod-104-kubernetes/exercises/`
**Solutions Path**: `modules/mod-104-kubernetes/`

| Exercise | Learning Repository | Solution Status | Estimated Time |
|----------|---------------------|-----------------|----------------|
| Exercise 04 | `exercise-04-k8s-cluster-autoscaler/` | ✅ `exercise-04-k8s-cluster-autoscaler/` | 35-43 hours |
| Exercise 05 | `exercise-05-service-mesh-observability/` | ✅ `exercise-05-service-mesh-observability/` | 35-45 hours |
| Exercise 06 | `exercise-06-k8s-operator-framework/` | ✅ `exercise-06-k8s-operator-framework/` | 35-45 hours |

**Coverage**: 3/3 exercises (100%)

### Exercise Details

**Exercise 04: Kubernetes Cluster Autoscaler (35-43 hours)**
- **Topics**: HPA, VPA, Cluster Autoscaler, node pools, cost optimization
- **Technologies**: Kubernetes, Prometheus, Grafana, Terraform
- **Prerequisites**: Module 104 lessons, Kubernetes knowledge

**Exercise 05: Service Mesh Observability (35-45 hours)**
- **Topics**: Istio/Linkerd, distributed tracing, service graphs, mTLS, traffic management
- **Technologies**: Istio/Linkerd, Jaeger, Kiali, Prometheus
- **Prerequisites**: Completed Exercise 04, service mesh basics

**Exercise 06: Kubernetes Operator Framework (35-45 hours)**
- **Topics**: Custom resources, operator SDK, reconciliation loops, webhooks
- **Technologies**: Operator SDK, Go, Kubernetes API
- **Prerequisites**: Completed Exercise 05, Go basics

---

## Module 105: Data Pipelines

**Learning Path**: `lessons/mod-105-data-pipelines/exercises/`
**Solutions Path**: `modules/mod-105-data-pipelines/`

| Exercise | Learning Repository | Solution Status | Estimated Time |
|----------|---------------------|-----------------|----------------|
| Exercise 03 | `exercise-03-streaming-pipeline-kafka/` | ✅ `exercise-03-streaming-pipeline-kafka/` | 36-44 hours |
| Exercise 04 | `exercise-04-workflow-orchestration-airflow/` | ✅ `exercise-04-workflow-orchestration-airflow/` | 35-45 hours |

**Coverage**: 2/2 exercises (100%)

### Exercise Details

**Exercise 03: Real-Time ML Feature Pipeline with Kafka (36-44 hours)**
- **Topics**: Kafka Streams, real-time feature computation, stream processing, Flink
- **Technologies**: Apache Kafka, Kafka Streams, Flink, Redis, PostgreSQL
- **Prerequisites**: Module 105 lessons, streaming concepts

**Exercise 04: Workflow Orchestration with Airflow (35-45 hours)**
- **Topics**: DAG design, task dependencies, data lineage, ML pipeline orchestration
- **Technologies**: Apache Airflow, DVC, MLflow, PostgreSQL
- **Prerequisites**: Completed Exercise 03, workflow orchestration basics

---

## Module 106: MLOps

**Learning Path**: `lessons/mod-106-mlops/exercises/`
**Solutions Path**: `modules/mod-106-mlops/`

| Exercise | Learning Repository | Solution Status | Estimated Time |
|----------|---------------------|-----------------|----------------|
| Exercise 04 | `exercise-04-experiment-tracking-mlflow/` | ✅ `exercise-04-experiment-tracking-mlflow/` | 30-38 hours |
| Exercise 05 | `exercise-05-model-monitoring-drift/` | ✅ `exercise-05-model-monitoring-drift/` | 30-40 hours |
| Exercise 06 | `exercise-06-ci-cd-ml-pipelines/` | ✅ `exercise-06-ci-cd-ml-pipelines/` | 30-40 hours |

**Coverage**: 3/3 exercises (100%)

### Exercise Details

**Exercise 04: Experiment Tracking with MLflow (30-38 hours)**
- **Topics**: Experiment tracking, parameter logging, model registry, artifact storage
- **Technologies**: MLflow, S3/MinIO, PostgreSQL, Docker
- **Prerequisites**: Module 106 lessons, ML model training experience

**Exercise 05: Model Monitoring and Drift Detection (30-40 hours)**
- **Topics**: Data drift, model drift, performance degradation, alerting
- **Technologies**: Evidently, WhyLabs, Prometheus, Grafana
- **Prerequisites**: Completed Exercise 04, statistical concepts

**Exercise 06: CI/CD for ML Pipelines (30-40 hours)**
- **Topics**: Pipeline automation, model validation, deployment automation
- **Technologies**: GitHub Actions, Jenkins, DVC, MLflow, Kubernetes
- **Prerequisites**: Completed Exercise 05, CI/CD basics

---

## Module 107: GPU Computing

**Learning Path**: `lessons/mod-107-gpu-computing/exercises/`
**Solutions Path**: `modules/mod-107-gpu-computing/`

| Exercise | Learning Repository | Solution Status | Estimated Time |
|----------|---------------------|-----------------|----------------|
| Exercise 04 | `exercise-04-gpu-cluster-management/` | ✅ `exercise-04-gpu-cluster-management/` | 35-45 hours |
| Exercise 05 | `exercise-05-gpu-performance-optimization/` | ✅ `exercise-05-gpu-performance-optimization/` | 35-45 hours |
| Exercise 06 | `exercise-06-distributed-gpu-training/` | ✅ `exercise-06-distributed-gpu-training/` | 35-45 hours |

**Coverage**: 3/3 exercises (100%)

### Exercise Details

**Exercise 04: GPU Cluster Management (35-45 hours)**
- **Topics**: Multi-node GPU setup, SLURM/Kubernetes scheduling, resource allocation
- **Technologies**: Kubernetes, SLURM, NVIDIA GPU Operator, Prometheus
- **Prerequisites**: Module 107 lessons, GPU access, distributed systems

**Exercise 05: GPU Performance Optimization (35-45 hours)**
- **Topics**: Profiling, kernel optimization, mixed precision, gradient checkpointing
- **Technologies**: CUDA, Nsight Systems, PyTorch Profiler, TensorBoard
- **Prerequisites**: Completed Exercise 04, CUDA basics

**Exercise 06: Distributed GPU Training (35-45 hours)**
- **Topics**: Data/model/pipeline parallelism, ZeRO optimizer, communication optimization
- **Technologies**: PyTorch DDP, Horovod, DeepSpeed, NCCL
- **Prerequisites**: Completed Exercise 05, distributed training concepts

---

## Module 108: Monitoring & Observability

**Learning Path**: `lessons/mod-108-monitoring-observability/exercises/`
**Solutions Path**: `modules/mod-108-monitoring-observability/`

| Exercise | Learning Repository | Solution Status | Estimated Time |
|----------|---------------------|-----------------|----------------|
| Exercise 01 | `exercise-01-observability-stack/` | ✅ `exercise-01-observability-stack/` | 28-36 hours |
| Exercise 02 | `exercise-02-ml-model-monitoring/` | ✅ `exercise-02-ml-model-monitoring/` | 28-36 hours |

**Coverage**: 2/2 exercises (100%)

### Exercise Details

**Exercise 01: Production Observability Stack (28-36 hours)**
- **Topics**: Prometheus, Grafana, Loki, alerting, service discovery
- **Technologies**: Prometheus, Grafana, Loki, AlertManager, Kubernetes
- **Prerequisites**: Module 108 lessons, Docker, Kubernetes

**Exercise 02: ML Model Monitoring (28-36 hours)**
- **Topics**: Model performance metrics, drift detection, custom metrics
- **Technologies**: Prometheus, Grafana, custom exporters, Python
- **Prerequisites**: Completed Exercise 01, ML fundamentals

---

## Module 109: Infrastructure as Code

**Learning Path**: `lessons/mod-109-infrastructure-as-code/exercises/`
**Solutions Path**: `modules/mod-109-infrastructure-as-code/`

| Exercise | Learning Repository | Solution Status | Estimated Time |
|----------|---------------------|-----------------|----------------|
| Exercise 01 | `exercise-01-terraform-ml-infrastructure/` | ✅ `exercise-01-terraform-ml-infrastructure/` | 32-40 hours |
| Exercise 02 | `exercise-02-pulumi-multicloud-ml/` | ✅ `exercise-02-pulumi-multicloud-ml/` | 32-40 hours |

**Coverage**: 2/2 exercises (100%)

### Exercise Details

**Exercise 01: Production ML Infrastructure with Terraform (32-40 hours)**
- **Topics**: VPC, EKS/GKE, GPU nodes, S3/GCS, RDS, monitoring, multi-environment
- **Technologies**: Terraform, AWS/GCP, Kubernetes, Vault
- **Prerequisites**: Module 109 lessons, Terraform basics, cloud platform access

**Exercise 02: Multi-Cloud ML Infrastructure with Pulumi (32-40 hours)**
- **Topics**: Multi-cloud deployment, cloud abstraction, disaster recovery
- **Technologies**: Pulumi, Python/TypeScript, AWS/GCP/Azure
- **Prerequisites**: Completed Exercise 01, programming experience

---

## Module 110: LLM Infrastructure

**Learning Path**: `lessons/mod-110-llm-infrastructure/exercises/`
**Solutions Path**: `modules/mod-110-llm-infrastructure/`

| Exercise | Learning Repository | Solution Status | Estimated Time |
|----------|---------------------|-----------------|----------------|
| Exercise 01 | `exercise-01-production-llm-serving/` | ✅ `exercise-01-production-llm-serving/` | 36-44 hours |
| Exercise 02 | `exercise-02-production-rag-system/` | ✅ `exercise-02-production-rag-system/` | 36-44 hours |

**Coverage**: 2/2 exercises (100%)

### Exercise Details

**Exercise 01: Production LLM Serving Platform (36-44 hours)**
- **Topics**: vLLM deployment, quantization, GPU optimization, autoscaling
- **Technologies**: vLLM, Kubernetes, CUDA, Prometheus, Grafana
- **Prerequisites**: Module 110 lessons, GPU access, Kubernetes knowledge

**Exercise 02: Production RAG System (36-44 hours)**
- **Topics**: Document ingestion, embedding models, vector DBs, hybrid search
- **Technologies**: LangChain, Pinecone/Weaviate/Qdrant, FastAPI, Kubernetes
- **Prerequisites**: Completed Exercise 01, understanding of embeddings

---

## Summary Statistics

### Overall Coverage

| Category | Exercises | Solutions | Coverage |
|----------|-----------|-----------|----------|
| **All Modules** | 29+ | 26 | 90%+ |
| **Advanced Exercises (104-110)** | 17 | 17 | 100% |
| **Module 101 Advanced** | 3 | 3 | 100% |
| **Module 101 Foundational** | 4 | 0 | 0% |

### Time Investment by Module

| Module | Exercises | Estimated Time |
|--------|-----------|----------------|
| **101: Foundations** | 3 advanced | 88-108 hours |
| **104: Kubernetes** | 3 | 105-135 hours |
| **105: Data Pipelines** | 2 | 71-89 hours |
| **106: MLOps** | 3 | 90-118 hours |
| **107: GPU Computing** | 3 | 105-135 hours |
| **108: Monitoring** | 2 | 56-72 hours |
| **109: IaC** | 2 | 64-80 hours |
| **110: LLM Infrastructure** | 2 | 72-88 hours |
| **Total (documented)** | 20 | 651-825 hours |

### Technology Coverage

**Most Common Technologies in Solutions:**
- Kubernetes (18 exercises)
- Docker (17 exercises)
- Prometheus (14 exercises)
- Grafana (12 exercises)
- Python (26 exercises)
- PostgreSQL (8 exercises)
- Terraform/Pulumi (4 exercises)

---

## Missing Solutions

### Priority 1: Module 101 Foundational Exercises

These are simple, markdown-based exercises that guide learners through basic setup. Full coded solutions may not be necessary:

1. **exercise-01-environment.md** (2-3 hours)
   - Python setup, virtual environments, dependency management
   - **Recommendation**: Add solution template showing proper setup

2. **exercise-02-docker.md** (2-3 hours)
   - Docker installation, container basics, Dockerfile creation
   - **Recommendation**: Add example Dockerfile and docker-compose.yml

3. **exercise-03-kubernetes.md** (3-4 hours)
   - Minikube setup, basic deployments, services
   - **Recommendation**: Add sample Kubernetes manifests

4. **exercise-07-api.md** (4-5 hours)
   - FastAPI ML service creation (newly created October 2025)
   - **Recommendation**: High priority - create full solution with tests

**Total Missing**: 4 exercises, 12-15 hours

### Impact Assessment

**Missing solutions impact**: **Low**
- All advanced exercises (104-110) have complete solutions
- Missing solutions are for basic foundational exercises
- Module 101 advanced projects all have solutions
- Learners can complete foundational exercises with inline guidance

---

## How to Use This Map

### For Learners

1. **Find your exercise** in the learning repository
2. **Check this map** to see if a solution exists
3. **Navigate to the solution** using the paths provided
4. **Try the exercise first** before looking at the solution
5. **Compare your implementation** with the solution
6. **Understand the patterns** used in the solution

### For Instructors

1. **Assign exercises** from the learning repository
2. **Reference solutions** for grading rubrics
3. **Use solution architectures** for lectures
4. **Identify gaps** where new solutions are needed

### For Contributors

1. **Check this map** before creating new solutions
2. **Follow existing patterns** from similar solutions
3. **Update this map** when adding new solutions
4. **Maintain consistent structure** across solutions

---

## Contributing

Missing a solution? Want to improve existing ones?

1. **Check the learning repository** for exercise requirements
2. **Follow the solution template** in existing exercises
3. **Include comprehensive tests** and documentation
4. **Submit a pull request** with your solution
5. **Update this map** with your new solution

---

**Last Updated**: October 31, 2025
**Maintained By**: AI Infrastructure Curriculum Team
**Related Documents**:
- [Solutions Repository README](./README.md)
- [Learning Repository](../../../learning/ai-infra-engineer-learning/)
- [Curriculum Remediation Progress](../../../reports/remediation-progress-oct31.md)
