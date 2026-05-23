# Custom Operator (ModelDeployment CRD) — Solution

Reference for [learning exercise-11](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-104-kubernetes/exercises/exercise-11-custom-operator/README.md).

Generated with kubebuilder v3. Reconciles `ModelDeployment` → Deployment + Service + HPA + ServiceMonitor.

```
exercise-11-custom-operator/
├── README.md, Makefile
├── api/v1/modeldeployment_types.go
├── controllers/modeldeployment_controller.go
└── config/crd/bases/ml.example.com_modeldeployments.yaml
```

## Setup

```bash
kubebuilder init --domain ml.example.com --repo github.com/me/model-operator
kubebuilder create api --group ml --version v1 --kind ModelDeployment
make manifests && make install && make run
```
