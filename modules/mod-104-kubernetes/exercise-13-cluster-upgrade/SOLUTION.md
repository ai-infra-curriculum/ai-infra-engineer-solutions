# SOLUTION — Exercise 13: Cluster Upgrade Procedure

> Read this before you upgrade anything you care about. The exercise is a
> *procedure design* problem: produce an upgrade plan that is safe to
> execute, ordered correctly, and reversible. The worked plan (1.29 → 1.30
> on a kubeadm cluster) lives alongside this file in
> [`UPGRADE.md`](./UPGRADE.md).

## 1. Solution overview

Exercise 13 asks for a complete, ordered cluster-upgrade plan with three
non-negotiable properties:

1. **Preflight before you touch the control plane** — deprecation check
   and an etcd backup, so you can both predict and recover from breakage.
2. **Correct ordering** — control plane first (one node at a time), then
   workers (drain → upgrade kubelet → uncordon), verifying health between
   each step.
3. **A real rollback path** — not "hope it works."

A passing submission also respects the version-skew rules: you may skip at
most one minor version per hop, and kubelets must not lead the control
plane.

## 2. Implementation

This is the worked answer — the model upgrade plan (preflight, ordered
procedure, rollback path, and version-skew rule) is the implementation a
passing submission must reproduce.

The model plan is [`UPGRADE.md`](./UPGRADE.md). Its shape:

### Preflight (before changing the control plane)

1. **API deprecation check** — find workloads still calling APIs that the
   target version removes:
   ```bash
   kubectl get --raw='/metrics' | grep apiserver_requested_deprecated_apis
   # or: pluto detect-files -d .   against manifests + rendered Helm charts
   ```
2. **Etcd backup** — a snapshot is the foundation of the rollback path:
   ```bash
   kubectl exec -n kube-system etcd-<node> -- \
     etcdctl --endpoints=https://127.0.0.1:2379 \
     --cacert=... --cert=... --key=... \
     snapshot save /tmp/etcd-snapshot-pre-1.30.db
   ```
3. **Read the release notes** for the target version:
   https://kubernetes.io/releases/notes/

### Procedure (kubeadm-managed)

| Step | Action |
|---|---|
| 1 | Drain + upgrade the first control-plane node |
| 2 | Verify cluster healthy (`kubectl get nodes`, component status) |
| 3 | Upgrade remaining control-plane nodes, one at a time |
| 4 | Upgrade workers one at a time: `drain` → upgrade kubelet → `uncordon` |
| 5 | Verify no `Pending` pods and all DaemonSets healthy |
| 6 | Smoke-test a representative workload and the critical paths |

The worker step in full:

```bash
kubectl drain $NODE --ignore-daemonsets --delete-emptydir-data --timeout=10m
# upgrade kubelet + kubeadm on $NODE, then:
kubectl uncordon $NODE
kubectl rollout status -n kube-system daemonset/<name>
```

### Rollback path

- Restore the etcd snapshot to a fresh control plane, **or**
- if applied very recently and within skew, reverse the upgrade order.

The etcd snapshot is the durable rollback; reversing the order is only an
option in the narrow window before workloads have written new state.

### Version-skew rule

Kubernetes supports skipping one minor version per hop (e.g. 1.29 → 1.31
done as two upgrades). Never skip two or more minor versions in a single
hop — control-plane/kubelet skew limits are documented in the upgrade
guide.

## 3. Validation steps

These are *verification gates* between steps, not a one-shot script — run
them and stop if any fails.

```bash
# Preflight gate: no in-use deprecated APIs the target release removes.
kubectl get --raw='/metrics' | grep apiserver_requested_deprecated_apis

# Preflight gate: snapshot exists and is non-empty.
kubectl exec -n kube-system etcd-<node> -- ls -l /tmp/etcd-snapshot-pre-1.30.db

# After each control-plane node:
kubectl get nodes                       # node back Ready at the new version
kubectl get pods -n kube-system         # control-plane pods Running

# After each worker:
kubectl get pods -A --field-selector=status.phase=Pending   # expect none
kubectl get ds -A                       # desired == ready for every DaemonSet

# Final smoke test:
kubectl rollout status deployment/<representative-app>
```

The upgrade is only "done" when there are zero `Pending` pods, every
DaemonSet is fully ready, and the smoke-test workload serves traffic.

## 4. Rubric / review checklist

| Criterion | Weight | Pass condition |
|---|---|---|
| Preflight present | 20% | Deprecation check *and* etcd backup before any control-plane change |
| Correct ordering | 25% | Control plane before workers; one node at a time; health check between steps |
| Safe worker drain | 15% | Uses `drain --ignore-daemonsets`, then upgrade, then `uncordon` |
| Rollback path | 20% | A concrete, executable rollback (etcd restore), not a vague intent |
| Version-skew correctness | 10% | States the skip-one-minor rule and never skips two+ |
| Verification gates | 10% | Defines what "healthy" means between steps (no Pending, DaemonSets ready) |

Borderline: a plan that upgrades the control plane and workers but never
verifies health between steps, or has no rollback, is not safe to execute
and should not pass — those are the properties the exercise exists to
teach.

## 5. Common mistakes

1. **Skipping the etcd backup.** Without a snapshot there is no real
   rollback; "reverse the upgrade" only works in a tiny window.
2. **Skipping two or more minor versions in one hop.** Violates the
   supported skew; do it as separate one-minor hops.
3. **Upgrading workers before the control plane.** The control plane must
   lead; kubelets must not run ahead of the apiserver version.
4. **Draining without `--ignore-daemonsets`.** The drain stalls on
   DaemonSet pods that cannot be evicted; the flag is required.
5. **Not checking for deprecated APIs first.** Workloads on removed API
   versions break silently after the apiserver upgrades — catch them in
   preflight with the metric or `pluto`.
6. **Calling it done without verifying DaemonSets and Pending pods.** A
   green control plane can still hide stuck node-level components.

## 6. References

- Local exercise context: [`UPGRADE.md`](./UPGRADE.md) — the worked
  1.29 → 1.30 plan, drain commands, and rollback path.
- Module rationale: [`../SOLUTION.md`](../SOLUTION.md).
- Learning exercise brief: `lessons/mod-104-kubernetes/exercises/exercise-13-cluster-upgrade`
  ([README](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-104-kubernetes/exercises/exercise-13-cluster-upgrade/README.md)).
- Official Kubernetes documentation — Upgrading kubeadm clusters:
  https://kubernetes.io/docs/tasks/administer-cluster/kubeadm/kubeadm-upgrade/
- Official Kubernetes documentation — Version skew policy:
  https://kubernetes.io/releases/version-skew-policy/
- Official Kubernetes documentation — Safely drain a node:
  https://kubernetes.io/docs/tasks/administer-cluster/safely-drain-node/
- Official Kubernetes release notes: https://kubernetes.io/releases/notes/
