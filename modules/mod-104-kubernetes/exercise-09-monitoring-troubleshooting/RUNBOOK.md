# K8s Troubleshooting Runbook

Reference for [learning exercise-09](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-104-kubernetes/exercises/exercise-09-monitoring-troubleshooting/README.md).

## Install kube-prometheus-stack

```bash
helm install kube-prom prometheus-community/kube-prometheus-stack -n monitoring --create-namespace
```

## 5 incident categories + diagnostic recipe

### 1. Networking (DNS resolution failing)
- **Symptom**: pod logs `dial tcp: lookup svc.namespace: no such host`
- **Diagnose**:
  ```bash
  kubectl run -it --rm dnstest --image=busybox --restart=Never -- nslookup my-svc.my-ns
  kubectl get endpoints -n my-ns my-svc          # any endpoints?
  kubectl logs -n kube-system -l k8s-app=kube-dns
  ```
- **Common cause**: NetworkPolicy blocking egress; bad svc selector

### 2. Resource (OOMKilled)
- **Symptom**: pod restarts, `lastState.terminated.reason: OOMKilled`
- **Diagnose**:
  ```bash
  kubectl describe pod ... | grep -A5 'Last State'
  kubectl top pod ...
  ```
- **Common cause**: limit too low; memory leak

### 3. Scheduling (Pending)
- **Symptom**: pod stays Pending; events say "0/3 nodes are available"
- **Diagnose**:
  ```bash
  kubectl describe pod ... | grep -A20 Events
  kubectl describe nodes        # taints + capacity
  ```
- **Common cause**: no node matches affinity/taint; requests exceed any node

### 4. Configuration (CrashLoopBackoff)
- **Symptom**: container restarts every few seconds
- **Diagnose**:
  ```bash
  kubectl logs --previous pod/...    # logs from BEFORE the crash
  kubectl describe pod ...
  ```
- **Common cause**: missing env var; bad config; misconfigured probe

### 5. State (StatefulSet won't roll)
- **Symptom**: only N/M pods updated; rollout stuck
- **Diagnose**:
  ```bash
  kubectl rollout status sts/postgres
  kubectl describe sts postgres
  kubectl get pvc -l app=postgres
  ```
- **Common cause**: failing readinessProbe blocks next pod; PVC bound to old node
