# Cluster Upgrade Plan: 1.29 → 1.30

Reference for [learning exercise-13](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-104-kubernetes/exercises/exercise-13-cluster-upgrade/README.md).

## Preflight (do BEFORE touching control plane)

1. **API deprecation check**:
   ```bash
   kubectl get --raw='/metrics' | grep apiserver_requested_deprecated_apis
   # OR run `pluto detect-files -d .` against manifests + helm renders
   ```
2. **Etcd backup**:
   ```bash
   kubectl exec -n kube-system etcd-<node> -- \
     etcdctl --endpoints=https://127.0.0.1:2379 \
     --cacert=... --cert=... --key=... \
     snapshot save /tmp/etcd-snapshot-pre-1.30.db
   ```
3. **Skim release notes**: https://kubernetes.io/releases/notes/

## Procedure (kubeadm-managed cluster)

| Step | Action |
|---|---|
| 1 | Drain + upgrade control plane node 1 |
| 2 | Verify cluster healthy (`kubectl get nodes`, `kubectl get cs`) |
| 3 | Upgrade additional control plane nodes (one at a time) |
| 4 | Upgrade worker nodes one at a time: `kubectl drain` → upgrade kubelet → uncordon |
| 5 | Verify no Pending pods + all DaemonSets healthy |
| 6 | Run smoke tests: representative workload + critical paths |

## Worker drain command

```bash
kubectl drain $NODE --ignore-daemonsets --delete-emptydir-data --timeout=10m
# Upgrade kubelet on $NODE
kubectl uncordon $NODE
kubectl rollout status -n kube-system daemonset/...
```

## Rollback path

- Restore etcd snapshot to a fresh cluster
- Or `kubeadm upgrade plan` shows the previous version; reverse the order if applied < 30min

## Skip-version checks
Kubernetes supports skip-1-version (1.29 → 1.31 in two steps). Never skip 2+ versions; control plane and kubelet skew limits are documented in the upgrade guide.
