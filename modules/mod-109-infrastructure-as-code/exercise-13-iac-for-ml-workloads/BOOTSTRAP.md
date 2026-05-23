# Bootstrap from scratch — apply this in order

```bash
# 1. Bootstrap state bucket + lock table (mod-109 ex-04)
cd ../../exercise-04-state-management-at-scale/bootstrap
terraform apply -var=state_bucket_name=my-tf-state

# 2. Apply infrastructure: VPC + EKS + S3 + IAM
cd ../../exercise-13-iac-for-ml-workloads/terraform
terraform init
terraform apply -var=environment=prod

# 3. Configure kubectl
aws eks update-kubeconfig --name ml-platform-prod

# 4. Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/v2.12.0/manifests/install.yaml
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=argocd-server -n argocd

# 5. Bootstrap ArgoCD: it manages everything from here
kubectl apply -f ../argocd-bootstrap/root-app.yaml

# 6. Wait for all platform apps to sync
argocd app sync root --timeout 1200

# 7. Verify
kubectl get pods --all-namespaces
curl https://iris-api.example.com/health
```

Total wall-clock from empty AWS account to working ML cluster: ~45 minutes.
