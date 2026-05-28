# Control Plane Tour — Notes

Reference for [learning exercise-02](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-104-kubernetes/exercises/exercise-02-control-plane-tour/README.md).

## Request flow: `kubectl apply -f deployment.yaml`

```
kubectl              kube-apiserver           etcd            kube-scheduler         kubelet
  │                       │                     │                    │                  │
  │ POST /apis/apps/v1 ──>│                     │                    │                  │
  │                       │ validate + admit    │                    │                  │
  │                       │ ──────────────────> │ persist            │                  │
  │                       │ <─────────────────  │ ack                │                  │
  │ <─── 201 Created      │                     │                    │                  │
  │                       │ <─── watch event ── │                    │                  │
  │                       │                     │                    │                  │
  │                       │ deployment-controller creates ReplicaSet │                  │
  │                       │ replicaset-controller creates Pods       │                  │
  │                       │ <─ pod (unscheduled) ──                  │                  │
  │                       │ ───────────────────────────────────────> │ assign to node   │
  │                       │ <─── pod updated with nodeName ──        │                  │
  │                       │ ──────────────────────────────────────────────────────────> │
  │                                                                                     │
  │                                                              kubelet creates pod    │
```

## Components I peeked at

| Component | Command | What I observed |
|---|---|---|
| kube-apiserver | `kubectl logs -n kube-system kube-apiserver-<node>` | every `kubectl` request logged with verb + resource + duration |
| etcd | `kubectl exec -n kube-system etcd-<node> -- etcdctl get / --prefix --keys-only \| head` | flat keyspace `/registry/...`; data is the API objects |
| scheduler | `kubectl logs -n kube-system kube-scheduler-<node>` | per-pod scoring: filter (which nodes can run it) → score → bind |
| controller-manager | `kubectl logs -n kube-system kube-controller-manager-<node>` | each controller is a reconcile loop: list → diff → act |
| kubelet | `journalctl -u kubelet` (on host) | pulls images, creates containers, posts status |

## Triggered observable effects

1. `kubectl scale deployment/iris-api --replicas=5` — scheduler logs showed 3 new pod bind events within ~50ms.
2. Stopped scheduler pod with `kubectl delete pod -n kube-system kube-scheduler-<node>` — for ~5s, new pods stayed Pending; scheduler auto-restarted; backlog cleared.
3. `kubectl exec etcd -- etcdctl get /registry/deployments/iris/iris-api` — saw the raw deployment object protobuf.
