# SOLUTION — Exercise 02: Control Plane Tour

> Read this after you have a running cluster (kind, minikube, or a real
> kubeadm cluster) and can reach the `kube-system` namespace. This is an
> *observation* exercise: the deliverable is a correct mental model of how
> a request moves through the control plane, not a deployed workload.

## 1. Solution overview

Exercise 02 asks you to trace a single `kubectl apply -f deployment.yaml`
through the control plane and then inspect each component in isolation.
The worked notes for this exercise live alongside this file in
[`CONTROL_PLANE.md`](./CONTROL_PLANE.md); this document explains what a
complete answer must demonstrate and how a grader should score it.

The four things a passing submission proves:

1. The student can name the control-plane components and what each one is
   responsible for (apiserver, etcd, scheduler, controller-manager,
   kubelet).
2. The student can describe the *order* of the request flow, including
   that the apiserver is the only component that talks to etcd, and that
   controllers and the scheduler act on watch events rather than direct
   calls.
3. The student inspected real component logs/state, not just diagrams.
4. The student triggered at least one observable effect and explained it.

## 2. Implementation

This is the worked answer — the model request-flow trace, the
component-inspection commands, and the observable effects that together
constitute the implementation a passing submission must reproduce.

### Request flow for `kubectl apply -f deployment.yaml`

The flow captured in [`CONTROL_PLANE.md`](./CONTROL_PLANE.md) is the model
answer:

1. `kubectl` POSTs the manifest to `kube-apiserver` (`/apis/apps/v1/...`).
2. The apiserver runs authentication, authorization, and admission, then
   persists the object to **etcd**. The apiserver is the *only* component
   that reads/writes etcd directly.
3. The apiserver returns `201 Created` to `kubectl`.
4. The **deployment controller** (in kube-controller-manager) sees the new
   Deployment via a watch and creates a ReplicaSet; the **replicaset
   controller** creates Pods. The Pods start life unscheduled
   (`nodeName` empty).
5. The **scheduler** watches for unscheduled Pods, runs *filter → score →
   bind*, and writes the chosen `nodeName` back through the apiserver.
6. The **kubelet** on that node sees a Pod bound to it, pulls images,
   creates containers, and reports status back to the apiserver.

The single most important insight to articulate: every component
communicates *through the apiserver via watches*, not point-to-point. That
is what makes the control plane a set of independent reconcile loops.

### Components and how to inspect each

The model commands and observations are tabulated in
[`CONTROL_PLANE.md`](./CONTROL_PLANE.md). In summary:

| Component | What it does | How to observe it |
|---|---|---|
| kube-apiserver | Front door; validation, admission, persistence | `kubectl logs -n kube-system kube-apiserver-<node>` |
| etcd | Backing key-value store of all API objects | `etcdctl get /registry --prefix --keys-only` via `kubectl exec` |
| kube-scheduler | Binds Pods to nodes (filter → score → bind) | `kubectl logs -n kube-system kube-scheduler-<node>` |
| kube-controller-manager | Hosts reconcile loops (deployment, replicaset, …) | `kubectl logs -n kube-system kube-controller-manager-<node>` |
| kubelet | Node agent; creates containers, posts status | `journalctl -u kubelet` on the host |

### Observable effects to trigger

Any one of the three demonstrations in [`CONTROL_PLANE.md`](./CONTROL_PLANE.md)
is sufficient:

- **Scale up** (`kubectl scale deployment/... --replicas=5`) and watch the
  scheduler emit new bind events.
- **Kill the scheduler pod** and watch new Pods sit `Pending` until it
  self-restarts (it is a static pod managed by the kubelet), then the
  backlog clears.
- **Read the raw object out of etcd** to see that what you applied is
  exactly what is stored.

## 3. Validation steps

```bash
# 1. Confirm you can see the control-plane pods at all.
kubectl get pods -n kube-system -o wide

# 2. Tail the apiserver and apply something; confirm the request appears.
kubectl logs -n kube-system kube-apiserver-<node> --tail=20
kubectl apply -f deployment.yaml

# 3. Confirm the object landed in etcd (path-only, no secrets dumped).
kubectl exec -n kube-system etcd-<node> -- \
  etcdctl get /registry/deployments --prefix --keys-only

# 4. Confirm the scheduler bound the pods.
kubectl logs -n kube-system kube-scheduler-<node> | grep -i bind

# 5. Trigger and observe one effect (scale is the safest on a shared cluster).
kubectl scale deployment/<name> --replicas=5
kubectl get events --sort-by=.lastTimestamp | grep -i scheduled
```

A correct run shows the request in the apiserver log, the object key in
etcd, and bind events in the scheduler log — confirming the chain end to
end.

## 4. Rubric / review checklist

| Criterion | Weight | Pass condition |
|---|---|---|
| Component identification | 20% | All five components named with correct responsibilities |
| Request-flow ordering | 25% | Flow is correct *and* notes that only the apiserver touches etcd |
| Watch-based architecture | 20% | Explains controllers/scheduler act on watch events, not direct calls |
| Real inspection | 20% | Shows actual log/etcd output, not just a redrawn diagram |
| Observable effect | 15% | Triggered ≥1 effect and explained the cause |

Borderline cases: a submission that reproduces the diagram perfectly but
shows no real component output should not pass the "real inspection"
criterion — the point of the exercise is to look, not to recite.

## 5. Common mistakes

1. **Claiming a component talks to etcd directly.** Only the apiserver
   does. Schedulers/controllers/kubelets all go through the apiserver.
2. **Describing the flow as synchronous calls.** Controllers and the
   scheduler react to *watch events*; the apiserver does not "call" them.
3. **Confusing the scheduler with the kubelet.** The scheduler *chooses* a
   node (sets `nodeName`); the kubelet *runs* the pod on that node.
4. **Treating control-plane pods as ordinary Deployments.** In a kubeadm
   cluster they are static pods managed directly by the kubelet, which is
   why the scheduler restarts itself after you delete it.
5. **Dumping secret values out of etcd.** Inspect keys (`--keys-only`);
   avoid printing Secret contents on a shared cluster.

## 6. References

- Local exercise context: [`CONTROL_PLANE.md`](./CONTROL_PLANE.md) — the
  worked request-flow diagram, component table, and triggered effects.
- Module rationale: [`../SOLUTION.md`](../SOLUTION.md).
- Learning exercise brief: `lessons/mod-104-kubernetes/exercises/exercise-02-control-plane-tour`
  ([README](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-104-kubernetes/exercises/exercise-02-control-plane-tour/README.md)).
- Official Kubernetes documentation — Cluster Components:
  https://kubernetes.io/docs/concepts/overview/components/
- Official Kubernetes documentation — Kubernetes API and the apiserver:
  https://kubernetes.io/docs/concepts/overview/kubernetes-api/
