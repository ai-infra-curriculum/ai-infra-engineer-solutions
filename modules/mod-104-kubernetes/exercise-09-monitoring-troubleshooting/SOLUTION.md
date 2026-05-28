# SOLUTION — Exercise 09: Kubernetes Monitoring and Troubleshooting Mastery

> Read this with a cluster you can break on purpose. The exercise is about
> *diagnosis under a known signal*: given a symptom, produce the commands
> that localize the fault and name the likely cause. The worked recipes
> live alongside this file in [`RUNBOOK.md`](./RUNBOOK.md).

## 1. Solution overview

Exercise 09 has two halves:

1. **Stand up monitoring.** Install `kube-prometheus-stack` so you have
   metrics, alerts, and dashboards to drive diagnosis.
2. **Diagnose five incident categories.** For each — networking, resource,
   scheduling, configuration, and state — recognize the symptom, run the
   right diagnostic commands, and name the most common root cause.

A passing submission demonstrates that the student reaches for *evidence*
(`describe`, `logs --previous`, `top`, `get endpoints`) before guessing,
and that they can map a symptom to the component that owns it.

## 2. Implementation

This is the worked answer — installing the monitoring stack and applying
the symptom → diagnose → cause recipe across all five incident categories
is the implementation a passing submission must reproduce.

### Install the monitoring stack

```bash
helm install kube-prom prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace
```

This bundles Prometheus, Alertmanager, Grafana, and the node/kube-state
exporters — enough to observe the five categories below.

### Five incident categories and the diagnostic recipe

The model recipes are in [`RUNBOOK.md`](./RUNBOOK.md). Each follows the
same shape — *symptom → diagnostic commands → common cause*:

| # | Category | Symptom | First commands | Common cause |
|---|---|---|---|---|
| 1 | Networking | `lookup svc: no such host` in pod logs | `nslookup` from a test pod; `kubectl get endpoints`; CoreDNS logs | NetworkPolicy blocking egress; bad Service selector |
| 2 | Resource | restarts with `reason: OOMKilled` | `kubectl describe pod` (Last State); `kubectl top pod` | memory limit too low; leak |
| 3 | Scheduling | Pod stuck `Pending`, `0/N nodes available` | `describe pod` Events; `describe nodes` (taints + capacity) | no node matches affinity/taint; requests exceed any node |
| 4 | Configuration | `CrashLoopBackOff`, restarts every few seconds | `kubectl logs --previous`; `describe pod` | missing env var; bad config; misconfigured probe |
| 5 | State | StatefulSet rollout stuck at N/M | `rollout status sts/...`; `describe sts`; `get pvc` | failing readinessProbe blocks next pod; PVC bound to old node |

The discriminating skill is choosing the right *first* command:

- For a crash that already happened, `kubectl logs --previous` is the only
  way to see the logs from *before* the restart.
- For "why won't this Pod schedule," the answer is almost always in
  `kubectl describe pod ... | grep -A20 Events`.
- For DNS, prove whether the Service even *has* endpoints before blaming
  CoreDNS.

## 3. Validation steps

```bash
# Monitoring is up.
kubectl get pods -n monitoring
kubectl -n monitoring port-forward svc/kube-prom-grafana 3000:80   # dashboards reachable

# Reproduce + diagnose one incident end to end (example: OOMKilled).
kubectl describe pod <pod> | grep -A5 'Last State'    # expect reason: OOMKilled
kubectl top pod <pod>                                 # memory at/above limit

# Scheduling drill.
kubectl describe pod <pending-pod> | grep -A20 Events # expect FailedScheduling
kubectl describe nodes | grep -iE 'taint|allocatable'

# Config drill.
kubectl logs --previous pod/<crashing-pod>            # error from before the crash
```

A complete submission shows, for each category it claims to cover, the
diagnostic output that pins the cause — not just the cause stated from
memory.

## 4. Rubric / review checklist

| Criterion | Weight | Pass condition |
|---|---|---|
| Monitoring stack installed | 15% | `kube-prometheus-stack` pods Running; a dashboard reachable |
| All five categories covered | 25% | Networking, resource, scheduling, configuration, state each addressed |
| Correct first command | 25% | Picks the diagnostic that localizes the fault (e.g. `--previous` for crashes) |
| Evidence over guessing | 20% | Shows actual `describe`/`logs`/`top` output backing each cause |
| Root-cause accuracy | 15% | Named cause is consistent with the evidence shown |

Borderline: naming the right cause without the diagnostic output that
proves it is a partial pass at best — the exercise is mastery of the
*diagnosis*, not trivia about failure modes.

## 5. Common mistakes

1. **Reading current logs after a crash.** `kubectl logs` shows the *new*
   container; use `kubectl logs --previous` to see why the old one died.
2. **Blaming DNS without checking endpoints.** A Service with no endpoints
   (selector typo, no ready pods) fails resolution the same way DNS does —
   check `kubectl get endpoints` first.
3. **Treating `Pending` as a node-health problem.** It is usually
   scheduling: taints, affinity, or resource requests larger than any
   node. The answer is in the Pod's Events, not the node's status.
4. **Raising limits to "fix" OOMKilled without measuring.** Confirm with
   `kubectl top` whether it is an undersized limit or a genuine leak.
5. **Forgetting that a failing readinessProbe stalls StatefulSet
   rollouts.** The next pod will not roll until the current one is Ready,
   so the rollout looks stuck when the real fault is the probe.
6. **No resource requests at all** — a recurring module-wide miss (see
   [`../SOLUTION.md`](../SOLUTION.md)) that makes scheduling and autoscaling
   behave unpredictably and is itself a frequent root cause here.

## 6. References

- Local exercise context: [`RUNBOOK.md`](./RUNBOOK.md) — install command and
  the five symptom → diagnose → cause recipes.
- Module rationale: [`../SOLUTION.md`](../SOLUTION.md) (see "Common mistakes
  graders see").
- Learning exercise brief: `lessons/mod-104-kubernetes/exercises/exercise-09-monitoring-troubleshooting`
  ([README](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-104-kubernetes/exercises/exercise-09-monitoring-troubleshooting/README.md)).
- Official Kubernetes documentation — Troubleshooting Applications:
  https://kubernetes.io/docs/tasks/debug/debug-application/
- Official Kubernetes documentation — Debug Running Pods:
  https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/
- `kube-prometheus-stack` Helm chart (prometheus-community):
  https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack
