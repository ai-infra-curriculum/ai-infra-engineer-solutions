# End-to-End IaC for ML Workloads — Solution

Reference for [learning exercise-13](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-109-infrastructure-as-code/exercises/exercise-13-iac-for-ml-workloads/README.md).

End-to-end project: `terraform apply` + `argocd app sync` → fully functional ML serving cluster.

## Layout

```
exercise-13-iac-for-ml-workloads/
├── README.md
├── terraform/
│   ├── main.tf          # VPC + EKS (CPU + GPU node pools) + S3 + IAM + IRSA + ECR
│   └── variables.tf
├── argocd-bootstrap/
│   ├── root-app.yaml    # app-of-apps
│   ├── platform/        # ingress + cert-manager + ESO + NVIDIA + prometheus
│   └── apps/            # iris-api + vllm + grafana dashboards
└── BOOTSTRAP.md          # 1-page apply-from-scratch checklist
```
